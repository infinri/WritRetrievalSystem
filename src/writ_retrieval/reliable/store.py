"""Versioned single-writer Relate store with immutable evidence and retraction.

This extends, rather than rewrites, the Phase 2 LocalStore. Legacy paths remain
available for baseline comparisons. Supported reliable writers honor one owner
lock and one transaction/revision boundary; direct same-account DB access is trusted.
"""
from __future__ import annotations
from contextlib import contextmanager
import copy
import fcntl
import getpass
import json
import os
from pathlib import Path
import sys
import threading
import uuid
from writ_retrieval.graph.identity import Key, GRAPH_ID_FIELDS
from writ_retrieval.graph.snapshot import GraphSnapshot
from writ_retrieval.memory.store import LocalStore, claim_hash
from writ_retrieval.frequency import evaluate_graduation
from .contracts import Claim, Evidence, Binding, canonical, digest, text_digest, instant, now_utc, revision, binding_for, subject_digest, binding_matches, window_active

STATE=Key("_system","StoreState","revision")


def unpack(value, default=None):
    if isinstance(value,str):
        try: return json.loads(value)
        except ValueError: return default
    return value if value is not None else default


class ReliableStore(LocalStore):
    def __init__(self,path,*,create=False,clock=now_utc,initialize=True):
        self.clock=clock; self._dirty=False;self._storage_fault=False;self._capture_new_decisions=None
        path=Path(path).resolve()
        if create: path.parent.mkdir(parents=True,exist_ok=True)
        if not create and not path.exists(): raise FileNotFoundError(path)
        self._owner=(path.parent/("."+path.name+".reliable-owner.lock")).open("a+")
        try: fcntl.flock(self._owner.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self._owner.close();raise RuntimeError("reliable store already has an owner")
        try: super().__init__(path,create=create)
        except BaseException:
            self._owner.close();raise
        self.path=path
        if not self.get(STATE):
            if not initialize:
                self.close();raise ValueError("initialize reliable storage through local-owner CLI before agent reads")
            with self.transaction():
                self._set(STATE,{"state_id":"revision","project":"_system","revision":0,"store_id":str(uuid.uuid4()),"contract_version":"writ-store/1"})

    def close(self):
        try: super().close()
        finally:
            if not self._owner.closed: self._owner.close()

    def current_revision(self):
        node=self.get(STATE)
        if not node or node.get("contract_version")!="writ-store/1": raise RuntimeError("store revision unavailable")
        return revision(node["revision"])

    def _set(self,key,props):
        old=self.get(key)
        if old is not None and all(old.get(k)==v for k,v in props.items()): return
        super()._set(key,props);self._dirty=True

    def _edge(self,source,kind,target):
        before=self.rows(f"MATCH (a:{source.label} {{project:$sp,{GRAPH_ID_FIELDS[source.label]}:$sid}})-[r:{kind}]->(b:{target.label} {{project:$tp,{GRAPH_ID_FIELDS[target.label]}:$tid}}) RETURN count(r) AS n",sp=source.project,sid=source.id,tp=target.project,tid=target.id)[0]["n"]
        if not before: super()._edge(source,kind,target);self._dirty=True

    @contextmanager
    def transaction(self):
        with self._lock:
            if self._storage_fault: raise RuntimeError("storage commit outcome uncertain; close and reopen store")
            if self._in_transaction: raise RuntimeError("nested reliable transaction")
            self._in_transaction=True;self._dirty=False;self._db.autocommit=False
            try:
                yield
                if self._capture_new_decisions is not None:
                    for key in self._capture_new_decisions:
                        node=self.get(key)
                        bindings=[self.bind(unpack(snapshot["ref"])) for snapshot in unpack(node.get("rule_snapshots"),[])]
                        self._set(key,{"rule_version_bindings":canonical(bindings),"capture_contract":"writ-record-capture/1"})
                if self._dirty:
                    state=self.get(STATE)
                    new_revision=revision(state["revision"])+1
                    super()._set(STATE,{"revision":new_revision,"updated_at":self.clock()})
                try: self._db.commit()
                except BaseException:
                    self._storage_fault=True;raise
            except BaseException:
                self._db.rollback();raise
            finally:
                self._db.autocommit=True;self._in_transaction=False
                from writ_retrieval.session.recall import invalidate_corpus
                invalidate_corpus(self)

    def capture(self,records):
        if not isinstance(records,list) or not 1<=len(records)<=5000: raise ValueError("capture requires 1..5000 records")
        for item in records:
            data=item["data"];instant(data["ts"])
            if instant(data["ts"])>instant(self.clock()): raise ValueError("future captured timestamp")
            if data.get("updated_at"): instant(data["updated_at"])
            if item.get("expected_revision") is not None: revision(item["expected_revision"])
        with self._lock:
            self._capture_new_decisions=[Key.of("Decision",r["data"]) for r in records if r.get("label")=="Decision" and self.get(Key.of("Decision",r["data"])) is None]
            try: return super().capture(records)
            finally: self._capture_new_decisions=None

    def lifecycle(self,ref,*,expected_revision,action,replacement=None):
        revision(expected_revision);key=Key.parse(ref)
        if key.label!="Claim": return super().lifecycle(ref,expected_revision=expected_revision,action=action,replacement=replacement)
        if action!="delete" or replacement is not None: raise ValueError("Claim supersession requires add_claim with an exact old binding")
        with self.transaction():
            node=self.get(key)
            if not node or node.get("revision")!=expected_revision or node.get("status")!="live": raise ValueError("stale/inactive claim")
            self._archive(key,node,"delete-claim")
            self._set(key,{"status":"deleted","revision":expected_revision+1})
        return self.get(key)

    def export(self):
        """One synchronous read transaction: no await or second channel read escapes it."""
        with self._lock:
            if self._storage_fault: raise RuntimeError("storage commit outcome uncertain; close and reopen store")
            if self._in_transaction: raise RuntimeError("cannot capture inside a write transaction")
            self._db.autocommit=False
            try:
                state=copy.deepcopy(self.get(STATE));rev=revision(state["revision"])
                physical={};nodes={};omitted=0
                for row in self.rows("MATCH (n) RETURN elementId(n) AS physical, labels(n) AS labels, properties(n) AS props"):
                    if len(row["labels"])!=1: omitted+=1;continue
                    try: key=Key.of(row["labels"][0],row["props"])
                    except ValueError: omitted+=1;continue
                    if key in nodes: raise RuntimeError("duplicate qualified physical identity")
                    physical[row["physical"]]=key
                    if key!=STATE: nodes[key]=copy.deepcopy(row["props"])
                edges=[]
                for row in self.rows("MATCH (a)-[r]->(b) RETURN elementId(a) AS a,type(r) AS kind,elementId(b) AS b,properties(r) AS props"):
                    if row["a"] in physical and row["b"] in physical:
                        edges.append((physical[row["a"]],row["kind"],physical[row["b"]],copy.deepcopy(row["props"])))
                self._db.commit()
                return {"store_id":state["store_id"],"revision":rev,"nodes":nodes,"edges":sorted(edges,key=lambda x:(x[0],x[1],x[2])),"omitted_nodes":omitted}
            except BaseException:
                self._db.rollback();raise
            finally: self._db.autocommit=True

    def bind(self,ref):
        key=Key.parse(ref);node=self.get(key)
        if not node: raise ValueError("missing binding subject")
        return binding_for(key,node)

    def add_claim(self,payload,*,supersedes=None):
        claim=Claim(**payload);claim.check_at(self.clock())
        key=Key(claim.project,"Claim",claim.claim_id)
        with self.transaction():
            node=self.get(key);data=claim.model_dump();request_digest=digest({"claim":data,"supersedes":supersedes})
            if node:
                if node.get("request_digest")!=request_digest: raise ValueError("claim identity reused for different immutable meaning")
                return node
            if supersedes:
                old_binding=Binding(**supersedes);oldkey=Key.parse(old_binding.ref);old=self.get(oldkey)
                if oldkey.label!="Claim" or oldkey.project!=key.project or not old or old.get("status")!="live" or not binding_matches(supersedes,{oldkey:old}): raise ValueError("stale supersession binding")
                self._archive(oldkey,old,"claim-supersession")
                self._set(oldkey,{"status":"superseded","revision":old["revision"]+1,"superseded_by":canonical(key.as_dict())})
            props={**data,"source":canonical(data["source"]),"revision":1,"status":"live","verification_status":"unverified",
                   "approval_status":"unknown","outcome_status":"unknown","request_digest":request_digest,"provenance":"record"}
            self._set(key,props)
            if supersedes: self._edge(key,"SUPERSEDES",oldkey)
        return self.get(key)

    def _bound_edge(self,a,kind,b,*,sources):
        self._edge(a,kind,b)
        attrs={"contract_version":"writ-relation/1","source_binding":canonical(self.bind(a.as_dict())),"target_binding":canonical(self.bind(b.as_dict())),
               "recorded_at":self.clock(),"source_refs":sources,"verification_status":"unverified"}
        self.rows(f"MATCH (a:{a.label} {{project:$ap,{GRAPH_ID_FIELDS[a.label]}:$ai}})-[r:{kind}]->(b:{b.label} {{project:$bp,{GRAPH_ID_FIELDS[b.label]}:$bi}}) SET r += $props",ap=a.project,ai=a.id,bp=b.project,bi=b.id,props=attrs)
        self._dirty=True

    def add_evidence(self,payload):
        evidence=Evidence(**payload);evidence.check_at(self.clock())
        key=Key(evidence.project,"Evidence",evidence.evidence_id);subject=Key.parse(evidence.subject.ref)
        with self.transaction():
            current=self.get(subject,active=True)
            if subject.project not in {key.project,"_shared"} and subject.label!="Rule": raise ValueError("foreign evidence binding")
            if not current or not binding_matches(evidence.subject.model_dump(),{subject:current}): raise ValueError("evidence subject revision/digest mismatch")
            data=evidence.model_dump();fingerprint=digest(data);old=self.get(key)
            if old:
                if old.get("request_digest")!=fingerprint: raise ValueError("evidence ID reused with different bytes/binding")
                return old
            props={**data,"subject":canonical(data["subject"]),"source":canonical(data["source"]),"revision":1,"status":"live",
                   "integrity_status":"digest_checked","verification_status":"unverified","verification_scope":"none",
                   "request_digest":fingerprint,"provenance":"record"}
            self._set(key,props);self._bound_edge(key,"SUPPORTS",subject,sources=[evidence.source.uri])
        return self.get(key)

    def declare_conflict(self,*,left,right,source_refs,note):
        a,b=Binding(**left),Binding(**right);ak,bk=Key.parse(a.ref),Key.parse(b.ref)
        if ak.project!=bk.project or ak==bk or ak.label not in {"Claim","Rule"} or bk.label not in {"Claim","Rule"}: raise ValueError("conflict must name two distinct scoped claims")
        if not source_refs or not note: raise ValueError("conflict requires provenance and explanation")
        with self.transaction():
            nodes={k:self.get(k) for k in (ak,bk)}
            if not binding_matches(left,nodes) or not binding_matches(right,nodes): raise ValueError("stale conflict binding")
            ident=digest([left,right,source_refs,note])[7:];key=Key(ak.project,"Conflict",ident)
            if self.get(key): return key.as_dict()
            self._set(key,{"project":ak.project,"conflict_id":ident,"left":canonical(left),"right":canonical(right),"source_refs":source_refs,
                           "note":note,"status":"unresolved","kind":"declared_potential_conflict","verification_status":"unverified","revision":1,"recorded_at":self.clock()})
            self._bound_edge(ak,"CONTRADICTS",bk,sources=source_refs)
        return key.as_dict()

    def retract_evidence(self,*,ref,expected_revision,request_id,reason):
        key=Key.parse(ref);revision(expected_revision)
        if key.label!="Evidence" or not isinstance(reason,str) or not reason.strip() or not isinstance(request_id,str) or not 1<=len(request_id)<=256: raise ValueError("invalid retraction")
        receipt=Key(key.project,"ReliableReceipt","retract:"+request_id)
        request=digest([ref,expected_revision,reason])
        with self.transaction():
            old=self.get(receipt)
            if old:
                if old["request_digest"]!=request: raise ValueError("retraction replay changed meaning")
                return {"replayed":True,"evidence":self.get(key)}
            node=self.get(key)
            if not node or node.get("revision")!=expected_revision or node.get("status")!="live": raise ValueError("stale/retracted evidence")
            self._set(key,{"status":"retracted","revision":node["revision"]+1,"retracted_at":self.clock(),"retraction_reason":reason})
            self._set(receipt,{"project":key.project,"receipt_id":receipt.id,"request_digest":request,"recorded_at":self.clock(),"provenance":"record"})
            self._recompute()
        return {"replayed":False,"evidence":self.get(key)}

    def confirm_evidence(self,refs):
        if not sys.stdin.isatty() or not sys.stdout.isatty(): raise PermissionError("evidence confirmation requires the local-owner terminal")
        bindings=[self.bind(ref) for ref in refs];token=digest(bindings)
        print(canonical({"evidence":[{"binding":b,"record":self.get(Key.parse(b["ref"])),"subject_record":self.get(Key.parse(unpack(self.get(Key.parse(b["ref"]))["subject"])["ref"]))} for b in bindings],"purpose":"owner judgment of evidence; NOT rule approval"}),flush=True)
        if input(f"Type 'confirm {token}' to record the local-owner judgment: ")!="confirm "+token: raise PermissionError("confirmation mismatch")
        with self.transaction():
            for binding in bindings:
                key=Key.parse(binding["ref"]);node=self.get(key)
                if key.label!="Evidence" or not node or node.get("status")!="live" or not binding_matches(binding,{key:node}): raise ValueError("stale evidence confirmation")
                self._set(key,{"judgment_kind":"owner_judgment","verification_status":"owner_confirmed","verification_scope":"owner_judgment_of_bound_subject",
                               "verified_at":self.clock(),"verified_by":getpass.getuser()})
                event=Key(key.project,"EvidenceEvent",digest([binding,self.clock(),"confirm"])[7:])
                self._set(event,{"project":key.project,"event_id":event.id,"subject":canonical(binding),"kind":"owner_confirmation","recorded_at":self.clock(),"os_login":getpass.getuser()})
            self._recompute()
        return {"confirmed":refs,"rule_approval_granted":False}

    def feedback_bound(self,*,project,batch_id,signals):
        if not isinstance(project,str) or not project.strip() or not isinstance(batch_id,str) or not 1<=len(batch_id)<=256 or not isinstance(signals,list) or not 1<=len(signals)<=1000: raise ValueError("invalid feedback batch identity/size")
        request=digest(signals);receipt=Key(project,"ReliableReceipt","feedback:"+batch_id)
        with self.transaction():
            existing=self.get(receipt)
            if existing:
                if existing["request_digest"]!=request: raise ValueError("feedback replay changed immutable binding")
                return {"replayed":True,"states":self._recompute()}
            for signal in signals:
                if set(signal)!={"rule","evidence_ref","signal"}: raise ValueError("invalid bound feedback")
                binding=Binding(**signal["rule"]);rk=Key.parse(binding.ref);ek=Key.parse(signal["evidence_ref"])
                rule=self.get(rk,active=True);evidence=self.get(ek)
                if rk.label!="Rule" or not rule or not binding_matches(signal["rule"],{rk:rule}): raise ValueError("obsolete rule binding")
                if ek.label!="Evidence" or ek.project!=project or not evidence or evidence.get("status")!="live": raise ValueError("missing/retracted evidence")
                if signal["signal"] not in {"positive","negative"}: raise ValueError("invalid observation sign")
                subject=unpack(evidence["subject"]);ok=Key.parse(subject["ref"]);outcome=self.get(ok,active=True)
                if ok.label!="Outcome" or ok.project!=project or not outcome or not binding_matches(subject,{ok:outcome}): raise ValueError("feedback needs a current bound outcome")
                dk=Key.parse(unpack(outcome["decision_ref"]));decision=self.get(dk,active=True)
                if not decision or not any(s.get("ref")==rk.as_dict() and s.get("claim_hash")==claim_hash(rule) for s in unpack(decision.get("rule_snapshots"),[])): raise ValueError("decision did not cite rule claim")
                if signal["rule"] not in unpack(decision.get("rule_version_bindings"),[]): raise ValueError("versioned decision did not cite this exact rule revision/digest")
                if outcome.get("result") not in {"pass","fail","mixed"}: raise ValueError("unknown outcome")
                if (outcome["result"],signal["signal"]) in {("pass","negative"),("fail","positive")}: raise ValueError("contradictory outcome sign")
                ident=digest([rk.token,binding.content_digest,ok.token])[7:];key=Key(project,"BoundObservation",ident);old=self.get(key)
                if old and old["signal"]!=signal["signal"]: raise ValueError("contradictory replay")
                if old and unpack(old["rule"])!=signal["rule"]: raise ValueError("observation binding is immutable across rule revisions")
                if old and unpack(old["evidence_ref"])!=ek.as_dict(): raise ValueError("Outcome already has an immutable evidence binding; duplicate evidence cannot add another observation")
                self._set(key,{"project":project,"observation_id":ident,"rule":canonical(signal["rule"]),"evidence_ref":canonical(ek.as_dict()),
                               "signal":signal["signal"],"recorded_at":old["recorded_at"] if old else self.clock(),"kind":"correlated_feedback","provenance":"record",
                               "contract_version":"writ-feedback-observation/1","evidence_binding":old["evidence_binding"] if old else canonical(self.bind(ek.as_dict()))})
            self._set(receipt,{"project":project,"receipt_id":receipt.id,"request_digest":request,"recorded_at":self.clock()})
            states=self._recompute()
        return {"replayed":False,"states":states}

    def _recompute(self):
        # Persistent materialization is refreshed on mutations; reads recompute at snapshot time as well.
        nodes={}
        for row in self.rows("MATCH (n) RETURN labels(n) AS labels,properties(n) AS props"):
            if len(row["labels"])!=1: continue
            try: nodes[Key.of(row["labels"][0],row["props"])]=row["props"]
            except ValueError: pass
        counts=active_counts(nodes,self.clock());states=[]
        for rk,(pos,neg) in counts.items():
            rule=nodes[rk];props={"times_seen_positive":pos,"times_seen_negative":neg,"feedback_policy":"active-bound-evidence/1",
                   "review_eligible":evaluate_graduation(pos,neg).graduated,"review_flagged":evaluate_graduation(pos,neg).flagged}
            if "legacy_positive" not in rule: props.update(legacy_positive=int(rule.get("times_seen_positive") or 0),legacy_negative=int(rule.get("times_seen_negative") or 0))
            if rule.get("provenance")=="proposed" and evaluate_graduation(pos,neg).graduated: props["provenance"]="graduation_pending"
            self._set(rk,props);states.append({"ref":rk.as_dict(),"positive":pos,"negative":neg})
        return states


def active_counts(nodes,at):
    touched={Key.parse(unpack(n["rule"])["ref"]) for k,n in nodes.items() if k.label=="BoundObservation"}
    result={key:[0,0] for key in touched if key in nodes}
    for key,node in nodes.items():
        if key.label!="BoundObservation": continue
        binding=unpack(node["rule"]);rk=Key.parse(binding["ref"]);ek=Key.parse(unpack(node["evidence_ref"]));ev=nodes.get(ek)
        if rk not in result or not binding_matches(binding,nodes) or not ev or ev.get("status")!="live" or not window_active(ev,at): continue
        if not binding_matches(unpack(node.get("evidence_binding")),nodes): continue
        if ev.get("verification_status")!="owner_confirmed" or ev.get("judgment_kind")!="owner_judgment": continue
        # Git object identity is observed, but is not verification of an Outcome's application result.
        subject=unpack(ev["subject"])
        if not binding_matches(subject,nodes): continue
        outcome=nodes[Key.parse(subject["ref"])]
        if outcome.get("status","live")!="live": continue
        decision_key=Key.parse(unpack(outcome.get("decision_ref")));decision=nodes.get(decision_key)
        if not decision or decision.get("status","live")!="live": continue
        if binding not in unpack(decision.get("rule_version_bindings"),[]): continue
        if not any(s.get("ref")==rk.as_dict() and s.get("claim_hash")==claim_hash(nodes[rk]) for s in unpack(decision.get("rule_snapshots"),[])): continue
        if nodes[rk].get("status","live")!="live" or nodes[rk].get("superseded"): continue
        result[rk][0 if node["signal"]=="positive" else 1]+=1
    return result

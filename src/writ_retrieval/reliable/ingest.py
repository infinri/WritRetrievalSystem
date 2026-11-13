"""Atomic, replay-safe ingestion of a frozen public Git history; no inferred approvals."""
from collections import defaultdict
import json
import re
from .contracts import Claim, Evidence, canonical, digest, text_digest, instant
from .git_history import export_history, PUBLIC_REPOSITORY
from .store import Key, unpack


def claim_key(project,doc): return Key(project,"Claim",digest(doc['uri'])[7:])


def ingest_history(store,history,*,project="writ-history",verify_repo=None):
    if history.get("contract_version")!="writ-git-history/1" or history.get("repository")!=PUBLIC_REPOSITORY: raise ValueError("not the supported public history contract")
    instant(history["recorded_at"])
    if instant(history["recorded_at"])>instant(store.clock()): raise ValueError("future recorded history")
    observed=False
    if verify_repo is not None:
        actual=export_history(verify_repo,history["end"],limit=history["limits"]["first_parent_commits"],recorded_at=history["recorded_at"])
        if digest(actual)!=digest(history): raise ValueError("frozen history differs from immutable Git objects")
        observed=True
    receipt=Key(project,"ReliableReceipt","git:"+history["end"])
    request_digest=digest(history);docs=history["documents"];commits={c['revision']:c for c in history['commits']}
    with store.transaction():
        old=store.get(receipt)
        if old:
            if old['request_digest']!=request_digest: raise ValueError("Git revision reused for different history material")
            return {"replayed":True,"receipt":receipt.as_dict(),"revision":store.current_revision()}
        for commit in history["commits"]:
            instant(commit["committed_at"])
            if any(commit.get(k)!=v for k,v in (("rationale",None),("approval","unknown"),("outcome","unknown"))): raise ValueError("commit metadata cannot assert rationale/approval/outcome")
            key=Key(project,"Commit",commit['revision'])
            props={"project":project,"commit_hash":key.id,"contract_version":"writ-git-commit/1","subject":commit['subject'],"body":commit['body'],
                   "ts":commit['committed_at'],"recorded_at":history['recorded_at'],"rationale":None,"rationale_status":"unknown","approval_status":"unknown","outcome_status":"unknown",
                   "source_refs":[f"{PUBLIC_REPOSITORY}/commit/{key.id}"],"revision":1,"status":"live","provenance":"record","source_origin":"read-only-git"}
            existing=store.get(key)
            if existing and existing.get('subject')!=props['subject']: raise ValueError("commit identity mismatch")
            if not existing: store._set(key,props)
        groups=defaultdict(list)
        for doc in docs:
            if doc.get('verification_status')!='unverified' or doc.get('source_kind')!='repository_assertion': raise ValueError("imported text cannot verify itself")
            if doc['revision'] not in commits: raise ValueError("document outside the frozen history")
            if text_digest(doc['text'])!='sha256:'+doc['digest']: raise ValueError("source content digest mismatch")
            source={"contract_version":"writ-source/1","uri":doc['uri'],"revision":doc['revision'],"path":doc['path'],"committed_at":doc['committed_at'],"start_line":doc["start_line"],"end_line":doc["end_line"]}
            key=claim_key(project,doc)
            value=Claim(project=project,claim_id=key.id,topic=doc['path']+'#'+(re.match(r'D-\d{3}:',doc['heading']).group(0)[:-1] if re.match(r'D-\d{3}:',doc['heading']) else doc['anchor']),title=doc['heading'],text=doc['text'],content_digest=text_digest(doc['text']),
                        source=source,kind="repository_assertion",recorded_at=history['recorded_at'],rationale=None)
            value.check_at(store.clock());data=value.model_dump();old=store.get(key)
            if not old:
                store._set(key,{**data,"source":canonical(data['source']),"revision":1,"status":"live","verification_status":"unverified","approval_status":"unknown","outcome_status":"unknown",
                                "provenance":"record","request_digest":digest(data)})
                evidence=Evidence(project=project,evidence_id='doc-'+key.id,subject=store.bind(key.as_dict()),source=source,material=doc['text'],content_digest=text_digest(doc['text']),kind='repository_assertion',recorded_at=history['recorded_at'])
                ed=evidence.model_dump();ek=Key(project,'Evidence',evidence.evidence_id)
                store._set(ek,{**ed,'subject':canonical(ed['subject']),'source':canonical(ed['source']),'revision':1,'status':'live','integrity_status':'digest_checked',
                               'verification_status':'unverified','verification_scope':'none','provenance':'record','request_digest':digest(ed)})
                store._bound_edge(ek,'SUPPORTS',key,sources=[doc['uri']])
            groups[value.topic].append(key)
        # Source-version replacement is mechanical document history, not policy approval or truth adjudication.
        for versions in groups.values():
            for older,newer in zip(versions,versions[1:]):
                node=store.get(older)
                if node.get('status')=='live':
                    store._archive(older,node,'document-version-replacement')
                    store._set(older,{'status':'superseded','revision':node['revision']+1,'superseded_by':canonical(newer.as_dict()),'supersession_kind':'document_version_replacement'})
        # Bind relations after all lifecycle revisions have reached their final state.
        for versions in groups.values():
            for older,newer in zip(versions,versions[1:]):
                store._bound_edge(newer,'SUPERSEDES',older,sources=[unpack(store.get(newer)['source'])['uri']])
        for doc in docs:
            ck=Key(project,'Commit',doc['revision']);dk=claim_key(project,doc)
            store._bound_edge(dk,'OBSERVED_IN',ck,sources=[doc['uri']])
            change=Key(project,'FileChange',digest([doc['revision'],doc['path']])[7:])
            if not store.get(change):
                store._set(change,{'project':project,'change_id':change.id,'contract_version':'writ-git-change/1','path':doc['path'],'change_type':'unknown',
                                   'reason':None,'reason_status':'unknown','commit_hash':ck.id,'ts':commits[ck.id]['committed_at'],'recorded_at':history['recorded_at'],
                                   'source_refs':[doc['uri']],'revision':1,'status':'live','provenance':'record'})
            store._bound_edge(ck,'INCLUDES',change,sources=[doc['uri']])
            store._bound_edge(change,'DERIVED_FROM',dk,sources=[doc['uri']])
        # Observing an immutable commit object verifies its identity, not assertions made in its message.
        for commit in history['commits']:
            ck=Key(project,'Commit',commit['revision']);ek=Key(project,'Evidence','git-'+ck.id)
            material=canonical(commit);binding=store.bind(ck.as_dict())
            store._set(ek,{'project':project,'evidence_id':ek.id,'contract_version':'writ-evidence/1','subject':canonical(binding),
                           'source':canonical({'contract_version':'writ-source/1','uri':f'{PUBLIC_REPOSITORY}/commit/{ck.id}','revision':ck.id}),
                           'material':material,'content_digest':text_digest(material),'kind':'tool_observation' if observed else 'repository_assertion',
                           'verification_status':'tool_observed' if observed else 'unverified','verification_scope':'git_object_identity_only' if observed else 'none',
                           'integrity_status':'digest_checked','recorded_at':history['recorded_at'],'revision':1,'status':'live','provenance':'record'})
            store._bound_edge(ek,'SUPPORTS',ck,sources=[f'{PUBLIC_REPOSITORY}/commit/{ck.id}'])
        store._set(receipt,{'project':project,'receipt_id':receipt.id,'contract_version':'writ-git-import-receipt/1','request_digest':request_digest,
                            'source_revision':history['end'],'git_objects_checked':observed,'recorded_at':store.clock(),'provenance':'record'})
    return {'replayed':False,'receipt':receipt.as_dict(),'commits':len(commits),'document_versions':len(docs),'git_objects_checked':observed}

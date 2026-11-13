"""Immutable, content-addressed local context generations.

All channels use one exported read transaction. Exact vector scanning is bounded
at 5000 units; it avoids ANN ambiguity for the deliberately small history sample.
The legacy V1 ranking/ANN path remains independently available.
"""
from __future__ import annotations
from collections import deque
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import threading
import numpy as np
from writ_retrieval.graph.identity import Key
from writ_retrieval.graph.snapshot import RECORD_EDGES
from writ_retrieval.retrieval.keyword import KeywordIndex
from writ_retrieval.retrieval.node_scope import is_visible
from writ_retrieval.retrieval.ranking import compute_confidence_weight
from .contracts import canonical, digest, subject_digest, binding_matches, window_active, instant
from .store import unpack, active_counts
from .budget import Budget, BudgetError, pack

POLICY = {'contract_version':'writ-context-policy/1', 'candidate_k':6, 'graph_hops':2,
          'max_graph_nodes':64, 'cosine_gate':.30, 'rrf_k':60, 'text_head_chars':1600,
          'embedding_batch_limit':16,'lexical_ties':'descending score then qualified identity',
          'ranking':'flat RRF; connected adds typed neighbors after identical seeds; confidence reported separately'}
LABELS = {'Rule','Skill','Playbook','Technique','AntiPattern','ForbiddenResponse',
          'Decision','Memory','Commit','FileChange','Outcome','Claim','Evidence'}
EXTRA_EDGES = {('Claim','OBSERVED_IN','Commit'),('FileChange','DERIVED_FROM','Claim'),
               ('Claim','SUPERSEDES','Claim'),('Claim','CONTRADICTS','Claim')}
EXTRA_EDGES |= {('Evidence','SUPPORTS',label) for label in ('Claim','Outcome','Commit','Decision','Memory','Rule')}


def texts(node):
    return '\n'.join(str(node[k]) for k in ('title','trigger','statement','text','material','rationale','description','subject','body','summary','path','reason') if node.get(k))


def lifecycle(node, at):
    state=node.get('status','live')
    if state=='deleted': return 'deleted'
    if state=='retracted' or node.get('evidence_status')=='retracted': return 'retracted'
    if state=='superseded' or node.get('superseded'): return 'historical'
    if not window_active(node,at): return 'outside_validity'
    return 'current'


def snapshot_document(export):
    return {'nodes':[[k.as_dict(),v] for k,v in sorted(export['nodes'].items())],
            'edges':[[a.as_dict(),kind,b.as_dict(),p] for a,kind,b,p in export['edges']]}


def normalize(matrix):
    matrix=np.asarray(matrix,dtype=np.float32)
    if matrix.ndim==1: matrix=matrix.reshape(1,-1)
    if matrix.ndim!=2 or not np.isfinite(matrix).all(): raise ValueError('invalid encoder output')
    return matrix/np.maximum(np.linalg.norm(matrix,axis=1,keepdims=True),1e-12)


def write_atomic(path, data):
    """Replace only complete, fsynced bytes; caller serializes the single writer."""
    fd,name=tempfile.mkstemp(prefix='.publish-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out: out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)


class ReliableSession:
    def __init__(self,store,encoder,*,encoder_id,cache_dir):
        if not encoder_id: raise ValueError('explicit encoder artifact identity required')
        self.store=store;self.encoder=encoder;self.encoder_id=encoder_id
        self.cache_dir=Path(cache_dir);self.cache_dir.mkdir(parents=True,exist_ok=True)
        self.current=None;self.previous=None;self._lock=threading.RLock()

    def _encode(self,items):
        fn=self.encoder.encode_batch if hasattr(self.encoder,'encode_batch') else self.encoder.encode
        return np.concatenate([normalize(fn(items[start:start+POLICY['embedding_batch_limit']])) for start in range(0,len(items),POLICY['embedding_batch_limit'])],axis=0)

    def _build(self,export,at):
        nodes=export['nodes'];source=snapshot_document(export);source_digest=digest(source)
        # Expiry and retraction affect a generation even if no new write occurred.
        validity=[[k.token,lifecycle(n,at)] for k,n in sorted(nodes.items())]
        counts=active_counts(nodes,at)
        generation=digest([source_digest,export['revision'],self.encoder_id,POLICY,validity])
        units={k:n for k,n in sorted(nodes.items()) if k.label in LABELS and lifecycle(n,at) not in {'deleted','outside_validity'}}
        if len(units)>5000: raise ValueError('bounded reliable working set exceeds 5000 units')
        rows=[{'ref':k.as_dict(),'text':texts(n)[:POLICY['text_head_chars']]} for k,n in units.items()]
        identity=digest([rows,self.encoder_id])
        root=self.cache_dir/export['store_id'];root.mkdir(exist_ok=True)
        final=root/generation[7:]
        if not final.exists():
            temporary=Path(tempfile.mkdtemp(prefix='.building-',dir=root))
            try:
                matrix=self._encode([r['text'] for r in rows]) if rows else np.empty((0,384),dtype=np.float32)
                if len(matrix)!=len(rows): raise ValueError('encoder returned wrong row count')
                np.save(temporary/'vectors.npy',matrix,allow_pickle=False)
                (temporary/'snapshot.json').write_text(canonical(source),encoding='utf-8')
                (temporary/'rows.json').write_text(canonical(rows),encoding='utf-8')
                manifest={'generation':generation,'revision':export['revision'],'source_digest':source_digest,
                          'encoder_id':self.encoder_id,'index_identity':identity,'policy':POLICY,
                          'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in temporary.iterdir()}}
                (temporary/'manifest.json').write_text(canonical(manifest),encoding='utf-8')
                for p in temporary.iterdir():
                    with p.open('rb') as f: os.fsync(f.fileno())
                os.rename(temporary,final)
            finally:
                if temporary.exists(): shutil.rmtree(temporary)
        manifest=json.loads((final/'manifest.json').read_text())
        if manifest['generation']!=generation or manifest['index_identity']!=identity or manifest['source_digest']!=source_digest: raise ValueError('generation manifest mismatch')
        for name,sha in manifest['files'].items():
            if name not in {'vectors.npy','snapshot.json','rows.json'} or hashlib.sha256((final/name).read_bytes()).hexdigest()!=sha: raise ValueError('generation artifact digest mismatch')
        matrix=np.load(final/'vectors.npy',allow_pickle=False)
        if len(matrix)!=len(rows) or not np.isfinite(matrix).all(): raise ValueError('generation vector shape/data mismatch')
        return {'id':generation,'export':export,'nodes':nodes,'units':units,'keys':list(units),'matrix':matrix,
                'counts':counts,'source_digest':source_digest,'root':root,'path':final,'as_of':at}

    def _publish(self,stage):
        pointer=stage['root']/'CURRENT.json'
        prior=json.loads(pointer.read_text()) if pointer.exists() else {}
        if prior.get('current')!=stage['id']:
            write_atomic(pointer,canonical({'contract_version':'writ-generation-pointer/1','current':stage['id'],
                'previous':prior.get('current'),'source_revision':stage['export']['revision']}).encode())
        if self.current and self.current['id']!=stage['id']: self.previous=self.current
        self.current=stage

    def _card(self,key,stage):
        node=stage['nodes'][key];body=texts(node);state=lifecycle(node,stage['as_of'])
        source=unpack(node.get('source'),{})
        references=list(dict.fromkeys([*(node.get('source_refs') or []),*([source['uri']] if source.get('uri') else [])]))
        card={'id':key.token,'ref':key.as_dict(),'record_revision':node.get('revision',0),
              'claim_digest':subject_digest(node),'content_digest':node.get('content_digest'),
              'channel':'guidance' if key.label=='Rule' else 'decision_recall' if key.label=='Decision' else 'memory',
              'lifecycle':state,'text':body[:640],'text_omitted_characters':max(0,len(body)-640),
              'source_refs':references,'source':source or None,'recorded_at':node.get('recorded_at') or node.get('ts'),
              'valid_from':node.get('valid_from'),'valid_to':node.get('valid_to'),
              'integrity_status':node.get('integrity_status','snapshot_digest_bound'),
              'observation_kind':node.get('kind','legacy_record_assertion'),
              'verification_status':node.get('verification_status','unverified'),
              'verification_scope':node.get('verification_scope','none'),
              'human_approval':node.get('approval_status','unknown'),'outcome':node.get('outcome_status',node.get('result','unknown'))}
        if key.label=='Claim':
            card['current_source_version']=state=='current'
            support={'active_assertions':0,'owner_confirmed':0,'retracted':0,'obsolete_or_outside_validity':0}
            for ek,ev in stage['nodes'].items():
                if ek.label!='Evidence': continue
                bound=unpack(ev.get('subject'))
                if not bound or bound['ref']!=key.as_dict(): continue
                if lifecycle(ev,stage['as_of'])=='retracted': support['retracted']+=1
                elif lifecycle(ev,stage['as_of'])=='current' and binding_matches(bound,stage['nodes']):
                    support['active_assertions']+=1
                    if ev.get('verification_status')=='owner_confirmed': support['owner_confirmed']+=1
                else: support['obsolete_or_outside_validity']+=1
            card['support_summary']=support
        if state=='historical': card['current_guidance']=False
        if node.get('superseded_by'): card['superseded_by']=unpack(node['superseded_by'])
        if node.get('retraction_reason'): card['retraction_reason']=node['retraction_reason']
        if key.label=='Evidence':
            binding=unpack(node.get('subject'))
            card['subject_binding']=binding;card['binding_current']=binding_matches(binding,stage['nodes']) if binding else False
            card['active_support']=bool(state=='current' and card['binding_current'])
        if key.label=='Decision': card['cited_claim_versions']=unpack(node.get('rule_snapshots'),[])
        if key.label=='Rule':
            pos,neg=stage['counts'].get(key,(node.get('times_seen_positive',0),node.get('times_seen_negative',0)))
            card['ranking_metadata']={'positive':pos,'negative':neg,'confidence_weight':compute_confidence_weight(node.get('confidence','production-validated'),pos,neg),
                                      'authority':node.get('authority','unknown'),'provenance':node.get('provenance','unknown')}
        return card

    def _visible(self,stage,project):
        return {k:n for k,n in stage['units'].items() if is_visible(k.label,k.project,project)}

    def _neighbors(self,seeds,stage,visible):
        adjacency={};rejected=0
        for a,kind,b,props in stage['export']['edges']:
            if a not in visible or b not in visible: continue
            if (a.label,kind,b.label) not in RECORD_EDGES|EXTRA_EDGES: continue
            if props.get('contract_version')=='writ-relation/1':
                if not binding_matches(unpack(props.get('source_binding')),stage['nodes']) or not binding_matches(unpack(props.get('target_binding')),stage['nodes']): rejected+=1;continue
            elif (a.label,kind,b.label) not in RECORD_EDGES: rejected+=1;continue
            # Do not turn retracted evidence or obsolete claims into proximity bridges.
            if lifecycle(visible[a],stage['as_of'])=='retracted' or lifecycle(visible[b],stage['as_of'])=='retracted': continue
            adjacency.setdefault(a,[]).append((b,kind));adjacency.setdefault(b,[]).append((a,kind))
        seen=set();queue=deque((k,0) for k in seeds);result=[];paths={}
        while queue and len(seen)<POLICY['max_graph_nodes']:
            key,depth=queue.popleft()
            if key in seen or key not in visible: continue
            seen.add(key)
            if key not in seeds: result.append(key)
            if depth<POLICY['graph_hops']:
                for target,kind in sorted(adjacency.get(key,[])):
                    if target.label=='Rule' and target not in seeds: continue
                    if target not in seen and target not in paths:
                        paths[target]=[*paths.get(key,[]),{'from':key.as_dict(),'edge':kind,'to':target.as_dict(),'binding':'snapshot-scoped; source assertion, not approval'}]
                    queue.append((target,depth+1))
        return result,{'visited':len(seen),'remaining':len(queue),'rejected_obsolete_relations':rejected,'paths':paths}

    def _render(self,stage,text,*,project,arm,budget,required):
        if arm not in {'lexical','vector','hybrid','connected'}: raise ValueError('unknown retrieval arm')
        visible=self._visible(stage,project)
        eligible={k:n for k,n in visible.items() if not (k.label=='Rule' and (n.get('mandatory') or n.get('always_on') or n.get('superseded')))}
        keyword=KeywordIndex()
        keyword.build([{'rule_id':k.token,'trigger':'','statement':texts(n)[:POLICY['text_head_chars']],'tags':''} for k,n in eligible.items()])
        by_token={k.token:k for k in eligible}
        hits=keyword.search(text[:2000],limit=len(eligible)) if eligible else []
        hits.sort(key=lambda hit:(-hit['score'],hit['rule_id']))
        lex=[by_token[h['rule_id']] for h in hits]
        vec=[]
        if arm!='lexical' and eligible:
            query=self._encode([text[:2000]])[0]
            if stage['matrix'].shape[1]!=len(query): raise ValueError('query/model dimension mismatch')
            similarities={k:float(np.dot(stage['matrix'][i],query)) for i,k in enumerate(stage['keys']) if k in eligible}
            vec=sorted((k for k in eligible if similarities[k]>=POLICY['cosine_gate']),key=lambda k:(-similarities[k],k))
        if arm=='lexical': ranked=lex
        elif arm=='vector': ranked=vec
        else:
            scores={}
            for order in (lex,vec):
                for rank,key in enumerate(order,1): scores[key]=scores.get(key,0)+1/(POLICY['rrf_k']+rank)
            ranked=sorted(scores,key=lambda k:(-scores[k],k))
        ranked=ranked[:POLICY['candidate_k']]
        expanded=[];graph={};paths={}
        if arm=='connected' and ranked:
            expanded,graph=self._neighbors(ranked[:1],stage,eligible)
            paths=graph.pop('paths')
            ranked=list(dict.fromkeys([ranked[0],*expanded,*ranked[1:]]))
        mandatory=[k for k,n in visible.items() if k.label=='Rule' and lifecycle(n,stage['as_of'])=='current' and (n.get('mandatory') or n.get('always_on'))]
        required=set(required)|{k.token for k in mandatory}
        keys=list(dict.fromkeys([*mandatory,*[k for k in visible if k.token in required],*ranked]))
        # Declared unresolved conflict is not adjudicated truth. Both bound texts travel together.
        conflicts=[]
        for key,node in sorted(stage['nodes'].items()):
            if key.label!='Conflict' or node.get('status')!='unresolved' or not is_visible(key.label,key.project,project): continue
            left,right=unpack(node['left']),unpack(node['right']);a,b=Key.parse(left['ref']),Key.parse(right['ref'])
            if a not in visible or b not in visible or not binding_matches(left,stage['nodes']) or not binding_matches(right,stage['nodes']): continue
            conflicts.append((a,b,{'id':key.token,'status':'unresolved_potential_conflict','note':node['note'],'source_refs':node['source_refs'],'verification_status':'unverified'}))
        bundles=[];used=set()
        for key in keys:
            if key in used: continue
            closure={key};annotations=[]
            changed=True
            while changed:
                changed=False
                for a,b,annotation in conflicts:
                    if (a in closure or b in closure) and (a not in closure or b not in closure): closure|={a,b};changed=True
                    if a in closure and b in closure and annotation not in annotations: annotations.append(annotation)
            bundle=[]
            for member in sorted(closure):
                card=self._card(member,stage)
                if member in paths: card['connected_via']=paths[member]
                if annotations: card['unresolved_conflicts']=annotations
                bundle.append(card)
            bundles.append(bundle);used|=closure
        header={'contract_version':'writ-context/1','snapshot':{'generation':stage['id'],'revision':stage['export']['revision'],
            'source_digest':stage['source_digest'],'as_of':stage['as_of'],'status':'current'},
            'trust':'untrusted source context; integrity, verification and human approval are distinct; no execution permission',
            'encoder_id':self.encoder_id,'abstained':not ranked,'ranked_abstained':not ranked,'budget_accounting':'entire UTF-8 JSON; token estimate ceil(chars/4), no exact tokenizer',
            'selection_policy':'writ-context-policy/1','mandatory_delivery':'separate from ranked candidates'}
        result=pack(header,bundles,budget,required=required)
        delivered=json.loads(result['payload'])
        delivered['abstained']=not delivered['items']
        result['payload']=canonical(delivered)
        result['diagnostics'].update(bytes=len(result['payload'].encode()),characters=len(result['payload']),estimated_tokens=math.ceil(len(result['payload'])/4))
        result['diagnostics'].update(arm=arm,visible_units=len(visible),candidate_ids=[k.token for k in ranked],expanded_ids=[k.token for k in expanded],graph=graph,
                                     snapshot_path=str(stage['path']),encoder_text_head_chars=POLICY['text_head_chars'])
        return result

    def context(self,text,*,project,arm='connected',budget=Budget(),required=()):
        """Failure leaves CURRENT and the in-memory previous generation unchanged."""
        with self._lock:
            try:
                # No await escapes this local single-writer boundary. Export is one DB read transaction.
                with self.store._lock:
                    export=self.store.export();at=self.store.clock();instant(at)
                    stage=self._build(export,at)
                    result=self._render(stage,text,project=project,arm=arm,budget=budget,required=required)
                    if self.store.current_revision()!=export['revision']: raise RuntimeError('source revision changed during generation build')
                    publication_time=self.store.clock()
                    if any(lifecycle(n,at)!=lifecycle(n,publication_time) for n in export['nodes'].values()): raise RuntimeError('validity changed during context build; retry')
                    self._publish(stage)
                return result
            except Exception as exc:
                return {'payload':None,'error':{'kind':type(exc).__name__,'message':str(exc),'last_complete_generation':self.current['id'] if self.current else None},
                        'diagnostics':{'status':'unavailable','publication_note':'No fresh payload; inspect CURRENT for the last atomically completed pointer.'}}

"""Opt-in complete-passage context and canonical-to-native index refresh.

Explicit request satisfaction is a mechanical contract check, never a claim that
retrieved prose is true, sufficient for an arbitrary question, or an execution permit.
"""
from __future__ import annotations
import copy
import json
import math
from typing import Literal
from pydantic import model_validator
import numpy as np
from writ_retrieval.graph.identity import Key
from writ_retrieval.retrieval.keyword import KeywordIndex
from writ_retrieval.retrieval.node_scope import is_visible
from .contracts import Closed, Source, Binding, canonical, digest, text_digest, binding_matches
from .session import ReliableSession, POLICY, lifecycle, texts, write_atomic
from .projection import RelateProjection, keywords
from .store import unpack
from .budget import Budget, BudgetError, pack

GROUNDED_POLICY={**POLICY,'contract_version':'writ-grounded-policy/1',
    'ranking':'flat RRF first; optional bounded typed enrichment after ranked sources',
    'rendering':'complete record text; indivisible conflicts; no text truncation',
    'lifecycle':'current only unless explicit history request; retracted evidence never active',
    'answerability':'explicit request satisfaction only; otherwise unassessed'}


class ContextRequest(Closed):
    contract_version:Literal['writ-context-request/1']='writ-context-request/1'
    source:Source|None=None
    binding:Binding|None=None
    verification:Literal['owner_confirmed']|None=None
    include_history:bool=False

    @model_validator(mode='after')
    def supported(self):
        if self.source and self.binding:raise ValueError('choose a source or a record binding, not both')
        if self.source and any(getattr(self.source,k) is not None for k in ('path','committed_at','start_line','end_line')):raise ValueError('source selector supports uri and revision only')
        return self

    @property
    def constrained(self):return self.source is not None or self.binding is not None or self.verification is not None


class GroundedSession(ReliableSession):
    def __init__(self,*args,backend='flat',**kwargs):
        if backend not in {'flat','relate'}:raise ValueError('unknown grounded backend')
        super().__init__(*args,policy=GROUNDED_POLICY,**kwargs)
        self.backend=backend;self.request=ContextRequest();self._indexes={};self._keywords={}

    def close(self):
        for index in self._indexes.values():index.close()
        self._indexes.clear()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def _publish(self,stage):
        # A separate pointer preserves the Phase 3 baseline. Source and permitted
        # search projection publish as one receipt only after rendering/validation.
        pointer=stage['root']/'GROUNDED-CURRENT.json'
        prior=json.loads(pointer.read_text()) if pointer.exists() else {}
        current={'generation':stage['id'],'source_revision':stage['export']['revision'],
                 'source_digest':stage['source_digest'],'projection':stage['projection']}
        if prior.get('current')!=current:
            write_atomic(pointer,canonical({'contract_version':'writ-grounded-pointer/1',
                        'current':current,'previous':prior.get('current') if prior.get('current',{}).get('generation')!=stage['id'] else prior.get('previous')}).encode())
        if self.current and self.current['id']!=stage['id']:self.previous=self.current
        self.current=stage

    def _visible(self,stage,project):
        if not isinstance(project,str) or not project:raise ValueError('explicit nonempty local project required')
        return {k:n for k,n in super()._visible(stage,project).items()
                if (lifecycle(n,stage['as_of'])=='current' and
                    (k.label!='Evidence' or binding_matches(unpack(n.get('subject')),stage['nodes']))) or
                (self.request.include_history and lifecycle(n,stage['as_of']) in {'current','historical','retracted'})}

    def _card(self,key,stage):
        card=super()._card(key,stage);body=texts(stage['nodes'][key])
        if key.label=='Evidence' and not card['binding_current']:card['recall_status']='obsolete_subject_binding'
        card.update(text=body,text_omitted_characters=0,rendered_text_digest=text_digest(body),
                    rendering='complete joined record text; no answer inferred from citation alone')
        return card

    def _matches(self,key,node,stage):
        req=self.request
        if req.source:
            source=unpack(node.get('source'),{})
            if source.get('uri')!=req.source.uri or source.get('revision')!=req.source.revision:return False
        if req.binding:
            if Key.parse(req.binding.ref)!=key or not binding_matches(req.binding.model_dump(),stage['nodes']):return False
        if req.verification:
            if lifecycle(node,stage['as_of'])!='current' or node.get('verification_status')!=req.verification:return False
            if key.label=='Evidence' and not binding_matches(unpack(node.get('subject')),stage['nodes']):return False
        return True

    def _lists(self,stage,eligible,text,project,arm):
        keys=list(eligible);by_token={k.token:k for k in keys}
        vectors={k:stage['matrix'][i] for i,k in enumerate(stage['keys']) if k in eligible}
        rows=[{'uid':k.token,'text':texts(eligible[k])[:self.policy['text_head_chars']],
               'embedding':list(map(float,vectors[k])),
               'payload':canonical(self._card(k,stage)),
               'partition':project} for k in keys]
        identity=digest([stage['id'],project,rows])
        query=self._encode([text[:2000]])[0] if arm!='lexical' and keys else None
        if self.backend=='relate':
            if identity not in self._indexes:
                if len(self._indexes)>=2:self._indexes.pop(next(iter(self._indexes))).close()
                self._indexes[identity]=RelateProjection(stage['root'],generation=stage['id'],project=project,rows=rows)
            index=self._indexes[identity]
            lex,vec=index.lists(text,query,k=max(1,len(keys)),gate=self.policy['cosine_gate'],mode=arm)
            stage['projection']={'backend':'relate','identity':index.identity,
                'path':str(index.path.relative_to(stage['root'])),'manifest_digest':digest(index.manifest),
                'permitted_rows':len(keys),'project':project}
        else:
            if identity not in self._keywords:
                if len(self._keywords)>=2:self._keywords.pop(next(iter(self._keywords)))
                keyword=KeywordIndex();keyword.build([{'rule_id':r['uid'],'trigger':'','statement':r['text'],'tags':''} for r in rows])
                self._keywords[identity]=keyword
            hits=self._keywords[identity].search(keywords(text),limit=max(1,len(keys))) if keys and arm!='vector' else []
            lex=[{'uid':h['rule_id'],'score':h['score']} for h in hits]
            vec=[{'uid':k.token,'score':float(np.dot(vectors[k],query))} for k in keys] if query is not None else []
            vec=[r for r in vec if r['score']>=self.policy['cosine_gate']]
            stage['projection']={'backend':'flat','identity':identity,'permitted_rows':len(keys),'project':project}
        lex.sort(key=lambda r:(-r['score'],r['uid']));vec.sort(key=lambda r:(-r['score'],r['uid']))
        return [by_token[r['uid']] for r in lex],[by_token[r['uid']] for r in vec]

    def _bundles(self,keys,stage,visible,paths):
        conflicts=[]
        for key,node in sorted(stage['nodes'].items()):
            if key.label!='Conflict' or node.get('status')!='unresolved' or not is_visible(key.label,key.project,self.project):continue
            left,right=unpack(node['left']),unpack(node['right'])
            if not binding_matches(left,stage['nodes']) or not binding_matches(right,stage['nodes']):continue
            a,b=Key.parse(left['ref']),Key.parse(right['ref'])
            conflicts.append((a,b,{'id':key.token,'status':'unresolved_potential_conflict',
                'note':node['note'],'source_refs':node['source_refs'],'verification_status':'unverified'}))
        bundles=[];used=set()
        for key in keys:
            if key in used:continue
            closure={key};annotations=[];changed=True
            while changed:
                changed=False
                for a,b,note in conflicts:
                    if a in closure or b in closure:
                        if a not in visible or b not in visible:raise ValueError('required conflict endpoint unavailable in permitted lifecycle')
                        if not {a,b}<=closure:closure|={a,b};changed=True
                        if note not in annotations:annotations.append(note)
            cards=[]
            for member in sorted(closure):
                card=self._card(member,stage)
                if member in paths:card['connected_via']=paths[member]
                if annotations:card['unresolved_conflicts']=annotations
                cards.append(card)
            bundles.append(cards);used|=closure
        return bundles

    def _render(self,stage,text,*,project,arm,budget,required):
        if arm not in {'lexical','vector','hybrid','connected'}:raise ValueError('unknown retrieval arm')
        visible=self._visible(stage,project)
        eligible={k:n for k,n in visible.items() if not (k.label=='Rule' and (n.get('mandatory') or n.get('always_on') or n.get('superseded')))}
        # Partition the entire permitted set before limits, including request constraints.
        eligible={k:n for k,n in eligible.items() if self._matches(k,n,stage)}
        lex,vec=self._lists(stage,eligible,text,project,arm)
        if arm=='lexical':ranked=lex
        elif arm=='vector':ranked=vec
        else:
            scores={}
            for hits in (lex,vec):
                for rank,key in enumerate(hits,1):scores[key]=scores.get(key,0)+1/(self.policy['rrf_k']+rank)
            ranked=sorted(scores,key=lambda k:(-scores[k],k))
        if self.request.source or self.request.binding:
            ranked=list(dict.fromkeys([*ranked,*eligible]))  # Explicit lookup can work without query-word overlap.
        ranked=ranked[:self.policy['candidate_k']]
        expanded=[];paths={};graph={}
        if arm=='connected' and ranked:
            # Retracted/historical records can be explicitly recalled but cannot be bridges.
            current={k:n for k,n in visible.items() if lifecycle(n,stage['as_of'])=='current'}
            expanded,graph=self._neighbors([k for k in ranked[:1] if k in current],stage,current);paths=graph.pop('paths')
        mandatory=[k for k,n in visible.items() if k.label=='Rule' and lifecycle(n,stage['as_of'])=='current' and (n.get('mandatory') or n.get('always_on'))]
        required=set(required)|{k.token for k in mandatory}
        # An explicit request needs at least one matching full record. A budget
        # failure is explicit; it must not turn satisfied into silently incomplete.
        if self.request.constrained and ranked:required.add(ranked[0].token)
        keys=list(dict.fromkeys([*mandatory,*[k for k in visible if k.token in required],*ranked,*expanded]))
        bundles=self._bundles(keys,stage,visible,paths)
        status='requirements_satisfied' if self.request.constrained and ranked else 'insufficient' if self.request.constrained else 'unassessed'
        header={'contract_version':'writ-grounded-context/1','snapshot':{'generation':stage['id'],
                'revision':stage['export']['revision'],'source_digest':stage['source_digest'],'as_of':stage['as_of'],'status':'current'},
            'projection':{k:v for k,v in stage['projection'].items() if k not in {'path','manifest_digest'}},
            'trust':'Untrusted context; source verification, integrity and human approval are separate; no execution permission',
            'encoder_id':self.encoder_id,'selection_policy':self.policy['contract_version'],
            'abstained':False,'ranked_abstained':not ranked,'mandatory_delivery':'separate from ranked candidates',
            'request':self.request.model_dump(exclude_none=True),'evidence_assessment':{'status':status,
                'reason':'matching full record required' if status=='requirements_satisfied' else 'no permitted record meets the request' if status=='insufficient' else 'no explicit evidence requirements; semantic sufficiency not established'},
            'budget_accounting':'complete canonical UTF-8 JSON; Unicode codepoints; ceil(chars/4) heuristic; exact tokens unknown'}
        result=pack(header,bundles,budget,required=required)
        payload=json.loads(result['payload']);payload['abstained']=not payload['items']
        if status=='requirements_satisfied' and not any(i['id'] in {k.token for k in ranked} for i in payload['items']):raise BudgetError('REQUIRED_EVIDENCE_NOT_DELIVERED')
        result['payload']=canonical(payload)
        if not budget.fits(result['payload']):raise BudgetError('FINAL_PAYLOAD_EXCEEDS_BUDGET')
        result['diagnostics'].update(bytes=len(result['payload'].encode()),characters=len(result['payload']),estimated_tokens=math.ceil(len(result['payload'])/4),
            backend=self.backend,arm=arm,visible_units=len(visible),eligible_units=len(eligible),candidate_ids=[k.token for k in ranked],expanded_ids=[k.token for k in expanded],graph=graph,
            snapshot_path=str(stage['path']),projection=stage['projection'],encoder_text_head_chars=self.policy['text_head_chars'])
        return result

    def context(self,text,*,project,arm='hybrid',budget=Budget(),required=(),request=None):
        with self._lock:
            # Validate before touching a generation. Base context returns failures as
            # unavailable, preserves the complete prior pointer, and verifies source freshness.
            try:
                self.request=ContextRequest(**(request or {}));self.project=project
            except (ValueError,TypeError) as exc:
                return {'payload':None,'error':{'kind':type(exc).__name__,'message':str(exc)},'diagnostics':{'status':'unavailable'}}
            return super().context(text,project=project,arm=arm,budget=budget,required=required)

"""Bound-evidence local-owner review, adapted from Phase 2's terminal trust boundary."""
import getpass
import json
import sys
from writ_retrieval.frequency import evaluate_graduation
from writ_retrieval.memory.store import normalized
from .contracts import canonical, digest
from .store import Key, unpack, active_counts


def review_state(store,ref):
    key=Key.parse(ref)
    if key.label!='Rule': raise ValueError('review requires a Rule proposal')
    node=store.get(key,active=True)
    if not node or node.get('authority')!='ai-provisional': raise ValueError('missing provisional rule')
    nodes={}
    for row in store.rows('MATCH (n) RETURN labels(n) AS labels,properties(n) AS props'):
        if len(row['labels'])!=1: continue
        try: nodes[Key.of(row['labels'][0],row['props'])]=row['props']
        except ValueError: pass
    counts=active_counts(nodes,store.clock()).get(key,(0,0));grade=evaluate_graduation(*counts)
    observations=[]
    for k,n in sorted(nodes.items()):
        if k.label=='BoundObservation' and Key.parse(unpack(n['rule'])['ref'])==key:
            evidence=nodes.get(Key.parse(unpack(n['evidence_ref'])))
            subject=unpack(evidence.get('subject')) if evidence else None
            observations.append({'observation':n,'evidence':evidence,'outcome':nodes.get(Key.parse(subject['ref'])) if subject else None})
    # Similarity/conflict inspection is transparent and scoped to the already-shared doctrine registry.
    others=[{'ref':k.as_dict(),'statement':n.get('statement')} for k,n in sorted(nodes.items()) if k.label=='Rule' and k!=key]
    return {'ref':ref,'rule_binding':store.bind(ref),'rule':node,'active_counts':{'positive':counts[0],'negative':counts[1]},
            'review_eligible':grade.graduated,'review_flagged':grade.flagged,'observations':observations,
            'other_rule_statements':others,'boundary':'correlated owner-confirmed reports, not causal proof; approval requires local-owner terminal judgment'}


def prepare_review(store,ref):
    with store.transaction():
        store._recompute();state=review_state(store,ref)
        if not state['review_eligible']: raise ValueError('insufficient active evidence for review')
        ident=digest(state);key=Key(Key.parse(ref).project,'ReviewSnapshot',ident[7:])
        artifact={'contract_version':'writ-bound-review/1','review_id':key.id,'state':state,'state_digest':ident}
        store._set(key,{'project':key.project,'review_id':key.id,'artifact':canonical(artifact),'state_digest':ident,'provenance':'record','recorded_at':store.clock()})
    return artifact


def apply_review(store,artifact,*,action):
    if not sys.stdin.isatty() or not sys.stdout.isatty(): raise PermissionError('rule approval requires local-owner terminal; unavailable to the agent interface')
    if action not in {'approve','reject'}: raise ValueError('invalid owner review action')
    ref=Key.parse(artifact['state']['ref']);key=Key(ref.project,'ReviewSnapshot',artifact['review_id']);stored=store.get(key)
    if not stored or stored['artifact']!=canonical(artifact): raise ValueError('unrecognized/edited review snapshot')
    print(json.dumps(unpack(stored['artifact']),indent=2),flush=True)
    phrase=action+' '+artifact['review_id']
    if input('Type '+phrase+': ')!=phrase: raise PermissionError('owner confirmation mismatch')
    with store.transaction():
        store._recompute();state=review_state(store,ref.as_dict())
        if digest(state)!=stored['state_digest'] or not state['review_eligible']: raise ValueError('review stale; active evidence or claim changed')
        rule=store.get(ref)
        if action=='approve':
            if not rule.get('violation') or not rule.get('pass_example'): raise ValueError('review requires failure and passing examples')
            others=store.rows('MATCH (r:Rule) RETURN properties(r) AS props')
            if any(Key.of('Rule',r['props'])!=ref and normalized(r['props'].get('statement'))==normalized(rule['statement']) for r in others): raise ValueError('duplicate statement; consolidate first')
            props={'authority':'ai-promoted','provenance':'graduated','approval_status':'local-owner-approved','graduated_via':'human-approve-asis'}
        else: props={'status':'rejected','superseded':True}
        store._archive(ref,rule,'bound-review-'+action);store._set(ref,props)
        event=Key(ref.project,'TrustEvent',digest([artifact['review_id'],action])[7:])
        store._set(event,{'project':ref.project,'event_id':event.id,'kind':action,'review_id':artifact['review_id'],'os_login':getpass.getuser(),'recorded_at':store.clock()})
    return {'action':action,'ref':ref.as_dict(),'trust_event':event.as_dict()}

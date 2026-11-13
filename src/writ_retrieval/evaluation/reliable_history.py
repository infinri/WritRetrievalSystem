"""Frozen time-separated source recovery, not a live agent or causal outcome trial."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import time
from writ_retrieval.reliable.cli import encoder, load_json, MODEL_HASHES
from writ_retrieval.reliable.contracts import canonical, digest
from writ_retrieval.reliable.store import ReliableStore, Key, unpack
from writ_retrieval.reliable.ingest import ingest_history, claim_key
from writ_retrieval.reliable.session import ReliableSession, POLICY
from writ_retrieval.reliable.budget import Budget

ARMS=('lexical','vector','hybrid','connected')


def input_hashes(root):
    frozen=load_json(root/'FROZEN-MANIFEST.json')
    actual={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in frozen['sha256']}
    if actual!=frozen['sha256']: raise ValueError('frozen evaluation material changed')
    return actual


def annotate_potential_tension(store,history,plan,project='writ-history'):
    """Explicit unreviewed benchmark annotation, never automatic semantic truth."""
    uris=[plan['queries'][0]['target_sources'][0],next(q for q in plan['queries'] if q['id']=='H11')['target_sources'][0]]
    keys=[claim_key(project,next(d for d in history['documents'] if d['uri']==uri)) for uri in uris]
    return store.declare_conflict(left=store.bind(keys[0].as_dict()),right=store.bind(keys[1].as_dict()),source_refs=uris,
        note=plan['contradiction_control']['description'])


def metrics(query,context):
    payload=json.loads(context['payload']);items=payload['items'];targets=set(query['target_sources'])
    refs=[set(i['source_refs']) for i in items];hits=targets&set().union(set(),*refs)
    first=next((i+1 for i,r in enumerate(refs) if targets&r),None)
    # Not a full relevance judgment: exact source-version coverage only.
    return {'target_count':len(targets),'covered_count':len(hits),'covered_sources':sorted(hits),
            'any_source_hit':bool(hits) if targets else None,'all_sources_hit':hits==targets if targets else None,
            'reciprocal_source_rank':1/first if first else 0 if targets else None,
            'abstained':payload['abstained'],'selected_units':len(items),
            'approval_assertions':sum(i['human_approval']!='unknown' for i in items),
            'outcome_assertions':sum(i['outcome']!='unknown' for i in items),
            'citation_integrity_correct':all(i['claim_digest'].startswith('sha256:') and i['source_refs'] for i in items),
            'context_bytes':len(context['payload'].encode()),'context_characters':len(context['payload'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fixtures',type=Path,default=Path('examples/phase3'));parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.work_dir.exists() or args.output.exists(): raise ValueError('new work/output directories required')
    if not 1<=args.repeats<=10: raise ValueError('repeats must be 1..10')
    inputs=input_hashes(args.fixtures);plan=load_json(args.fixtures/'evaluation.json');history=load_json(args.fixtures/'train-history.json')
    assert history['end']==plan['train_end'] and not set(plan['holdout_task_revisions'])&{c['revision'] for c in history['commits']}
    for name,value in plan['policy'].items():
        if name!='lexical_gate' and POLICY[name]!=value: raise ValueError('runtime/frozen policy mismatch: '+name)
    args.work_dir.mkdir(parents=True);args.output.mkdir(parents=True)
    started=time.perf_counter();model,model_id=encoder(args.model_dir)
    model_load_ms=(time.perf_counter()-started)*1000
    rows=[]
    with ReliableStore(args.work_dir/'graph',create=True) as store:
        ingestion=ingest_history(store,history,verify_repo=args.repo)
        conflict=annotate_potential_tension(store,history,plan)
        session=ReliableSession(store,model,encoder_id=model_id,cache_dir=args.work_dir/'cache')
        start=time.perf_counter();warm=session.context('index preparation',project='foreign',arm='lexical',budget=Budget(**plan['budget']))
        if warm.get('error'): raise RuntimeError(warm['error'])
        index_build_ms=(time.perf_counter()-start)*1000
        expected_source_refs={d['uri'] for d in history['documents']}|{f"{history['repository']}/commit/{c['revision']}" for c in history['commits']}
        for query in plan['queries']:
            for arm in ARMS:
                runs=[];context=None;selection=None
                for _ in range(args.repeats):
                    start=time.perf_counter();context=session.context(query['query'],project=query['project'],arm=arm,budget=Budget(**plan['budget']))
                    runs.append((time.perf_counter()-start)*1000)
                    if context.get('error'): raise RuntimeError(context['error'])
                    signature=[context['diagnostics']['candidate_ids'],context['diagnostics']['selected_ids']]
                    if selection is not None and signature!=selection: raise RuntimeError('non-deterministic selection in repeated query')
                    selection=signature
                delivered=json.loads(context['payload'])
                for item in delivered['items']:
                    if not set(item['source_refs'])<=expected_source_refs: raise AssertionError('unbound or holdout source leak')
                    key=Key.parse(item['ref']);actual=store.export()['nodes'][key]
                    from writ_retrieval.reliable.contracts import subject_digest
                    if item['claim_digest']!=subject_digest(actual): raise AssertionError('citation digest mismatch')
                rows.append({'query_id':query['id'],'query':query['query'],'project':query['project'],'arm':arm,
                    'label':query,'metrics':metrics(query,context),'latency_ms':runs,'latency_median_ms':statistics.median(runs),
                    'rss_process_high_water_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**context})
        snapshot=session.current['source_digest'];revision=store.current_revision()
    summary={'contract_version':'writ-history-evaluation-result/1','label_status':'model_authored_unreviewed; no human review or live-agent outcome evidence',
        'frozen_commit':'87ed6d2','input_sha256':inputs,'source_code_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
        'settings':{'policy':POLICY,'budget':plan['budget'],'repeats':args.repeats,'arm_order':ARMS},
        'split':plan['split'],'history_commits':len(history['commits']),'history_document_versions':len(history['documents']),
        'ingestion':ingestion,'potential_tension_annotation':conflict,'snapshot_digest':snapshot,'store_revision':revision,
        'model_sha256':MODEL_HASHES,'model_load_ms':model_load_ms,'initial_generation_build_ms':index_build_ms,
        'memory':{'peak_process_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'note':'Linux ru_maxrss high-water, shared process including ONNX/indexes; not per-query allocation or an isolated arm comparison'},
        'runtime':{'python':platform.python_version(),'platform':platform.platform()},'arms':{},'paired_connected_vs_hybrid':{},
        'limits':['Source-section proxy labels, not independently reviewed relevance gold.',
        'Flat arms and connected get identical documents, records, scope, model, common conflict closure and output budget.',
        'Connected changes selection order with typed bounded adjacency; it is a measured separate policy, not original V1 ranking.',
        'Source digest correctness is separate from semantic relevance, verification, approval and unknown outcomes.',
        'A returned relevant-looking source on a missing-evidence prompt is a false abstention under this provisional label, not proof of a false generated answer.',
        'No generative agent was run; no task success, causal effect, original-export equivalence or statistically significant advantage established.']}
    for arm in ARMS:
        selected=[r for r in rows if r['arm']==arm];positive=[r for r in selected if r['metrics']['target_count']];negative=[r for r in selected if r['label']['expected_abstention']]
        summary['arms'][arm]={'full_queries':len(selected),'source_target_queries':len(positive),'source_targets':sum(r['metrics']['target_count'] for r in positive),
            'any_source_hits':sum(r['metrics']['any_source_hit'] for r in positive),'all_source_hits':sum(r['metrics']['all_sources_hit'] for r in positive),
            'covered_source_targets':sum(r['metrics']['covered_count'] for r in positive),'mean_reciprocal_source_rank':statistics.mean(r['metrics']['reciprocal_source_rank'] for r in positive),
            'expected_abstention_queries':len(negative),'correct_abstentions':sum(r['metrics']['abstained'] for r in negative),
            'abstentions':[r['query_id'] for r in selected if r['metrics']['abstained']],
            'median_latency_ms':statistics.median(r['latency_median_ms'] for r in selected),
            'mean_context_bytes':statistics.mean(r['metrics']['context_bytes'] for r in selected),
            'all_citation_integrity_correct':all(r['metrics']['citation_integrity_correct'] for r in selected),
            'unknown_control_has_no_approval_or_outcome_assertions':all(not r['metrics']['approval_assertions'] and not r['metrics']['outcome_assertions'] for r in selected if r['query_id']=='H7')}
    for q in plan['queries']:
        pair={r['arm']:r['metrics'] for r in rows if r['query_id']==q['id']}
        if q['target_sources']:
            delta=pair['connected']['covered_count']-pair['hybrid']['covered_count']
            summary['paired_connected_vs_hybrid'][q['id']]={'source_coverage_delta':delta,'classification':'improved' if delta>0 else 'regressed' if delta<0 else 'unchanged'}
        else: summary['paired_connected_vs_hybrid'][q['id']]={'abstention_changed':pair['connected']['abstained']!=pair['hybrid']['abstained'],'classification':'control'}
    (args.output/'queries.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows))
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary['arms'],indent=2))


if __name__=='__main__': main()

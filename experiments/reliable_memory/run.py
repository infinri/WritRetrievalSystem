"""Frozen descriptive evaluation. Run under scripts/offline_run.py.

No tuning, downloading or model calls beyond pinned local embedding inference.
Every record is captured through supported canonical-memory interfaces.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,os,platform,random,resource,statistics,subprocess,time
from pathlib import Path
import numpy as np
from writ_retrieval.reliable.contracts import canonical,digest,text_digest
from writ_retrieval.reliable.store import ReliableStore
from writ_retrieval.reliable.passages import ingest_passages
from writ_retrieval.reliable.session import ReliableSession
from writ_retrieval.reliable.grounded import GroundedSession
from writ_retrieval.reliable.budget import Budget
ROOT=Path(__file__).parent


def load():
    frozen=json.loads((ROOT/'protocol/frozen.json').read_text())
    for path,sha in frozen['sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('frozen input drift: '+path)
    return json.loads((ROOT/'fixtures/tasks.json').read_text())['tasks'],json.loads((ROOT/'protocol/settings.json').read_text())


def fixture(pin):
    value=json.loads((ROOT/f'fixtures/history-{pin[:7]}.json').read_text())
    docs=[{k:v for k,v in d.items() if k!='file_group'} for d in value['documents']]
    return {'contract_version':'writ-passage-import/1','repository':value['repository'],'revision':pin,
            'recorded_at':value['recorded_at'],'documents':docs,'paths':list(dict.fromkeys(d['path'] for d in docs)),
            'unknowns':'Repository assertions unverified; commit identity is not approval, successful verification or known outcome.'}


def score(task,result,legacy=False):
    if not result.get('payload'):return {'failure':True,'error':result.get('error'),'gold_passages':len(task['gold']),'delivered_passages':0,'complete_proxy':False}
    p=json.loads(result['payload']);items=p['items'];gold=task['gold']
    hits=[next((i+1 for i,c in enumerate(items) if (c.get('source') or {}).get('uri')==g['uri'] and (c.get('source') or {}).get('revision')==g['revision'] and c.get('content_digest')==g['content_digest'] and g['answer_text'] in c['text']),None) for g in gold]
    hitcount=sum(x is not None for x in hits)
    citation_ok=all((c.get('source') or {}).get('revision')==task['corpus_revision'] and c['ref']['project']==task['project'] and c.get('record_revision',0)>=1 for c in items)
    rendered_ok=all(c.get('rendered_text_digest')==text_digest(c['text']) and c.get('text_omitted_characters')==0 for c in items) if not legacy else None
    satisfied=p.get('evidence_assessment',{}).get('status')
    unknown_correct=(satisfied=='insufficient') if task['track']=='structured' else p['abstained']
    return {'failure':False,'gold_passages':len(gold),'delivered_passages':hitcount,'complete_proxy':bool(gold) and hitcount==len(gold),
        'mrr':1/min(x for x in hits if x) if hitcount else 0 if gold else None,
        'ndcg':1/math.log2(hits[0]+1) if len(gold)==1 and hits[0] else 0 if len(gold)==1 else None,
        'precision':sum(any((c.get('source') or {}).get('uri')==g['uri'] and g['answer_text'] in c['text'] for g in gold) for c in items)/len(items) if items and gold else 0 if gold else None,
        'abstained':p['abstained'],'evidence_status':satisfied,'correct_unknown':unknown_correct if task['expected_unknown'] else None,
        'request_contract_supported':not legacy or task['track']=='natural','citation_correct':citation_ok,'rendered_digest_correct':rendered_ok,
        'bytes':len(result['payload'].encode()),'characters':len(result['payload']),'delivered_ids':[c['id'] for c in items]}


def summarize(rows):
    output={}
    for name in sorted({r['arm'] for r in rows}):
        # Quality once per task, not inflated by timing repetitions.
        first={r['task_id']:r for r in rows if r['arm']==name and r['repeat']==0}
        tracks={}
        for track in ('natural','structured','all'):
            selected=[r for r in first.values() if track=='all' or r['track']==track]
            positives=[r for r in selected if r['score']['gold_passages']];unknown=[r for r in selected if r['expected_unknown']]
            samples=[r['elapsed_ms'] for r in rows if r['arm']==name and (track=='all' or r['track']==track)]
            supported=[r for r in unknown if r['score'].get('request_contract_supported',False)]
            wins=sum(r['score']['complete_proxy'] for r in positives);n=len(positives)
            # Wilson interval descriptive per-family proportion; paired regressions below.
            z=1.96;den=1+z*z/n if n else 1;center=(wins/n+z*z/(2*n))/den if n else None
            half=z*math.sqrt((wins/n*(1-wins/n)+z*z/(4*n))/n)/den if n else None
            tracks[track]={'tasks':len(selected),'positive_tasks':n,'supported_positive_tasks':sum(r['score'].get('request_contract_supported',False) for r in positives),'complete_proxy':wins,'target_passage_delivery':wins/n if n else None,
                'wilson_95':([center-half,center+half] if n else None),'unknown_tasks':len(unknown),'supported_unknown_tasks':len(supported),
                'correct_unknown':sum(bool(r['score'].get('correct_unknown')) for r in supported),
                'failures':sum(r['score']['failure'] for r in selected),'citation_failures':sum(r['score'].get('citation_correct') is False for r in selected),
                'mrr':statistics.mean(r['score']['mrr'] or 0 for r in positives) if n else None,
                'latency_samples':len(samples),'p50_ms':float(np.percentile(samples,50)) if samples else None,'p95_ms':float(np.percentile(samples,95)) if samples else None}
        output[name]=tracks
    baseline={r['task_id']:r for r in rows if r['arm']=='grounded-flat' and r['repeat']==0}
    paired={}
    for name in output:
        candidates=[r for r in rows if r['arm']==name and r['repeat']==0 and r['score']['gold_passages']]
        paired[name]={'improved':[r['task_id'] for r in candidates if r['score']['complete_proxy'] and not baseline[r['task_id']]['score']['complete_proxy']],
                      'regressed':[r['task_id'] for r in candidates if not r['score']['complete_proxy'] and baseline[r['task_id']]['score']['complete_proxy']],
                      'unchanged':[r['task_id'] for r in candidates if r['score']['complete_proxy']==baseline[r['task_id']]['score']['complete_proxy']]}
    return {'arms':output,'paired_vs_grounded_flat':paired,'labels':'MODEL_AUTHORED_UNREVIEWED','quality_note':'Complete labelled paragraph actually delivered, not independently reviewed answer sufficiency. Timing repetitions are not independent quality tasks.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--split',choices=('development','heldout'),required=True);args=p.parse_args()
    tasks,settings=load();tasks=[t for t in tasks if t['split']==args.split]
    args.work_dir.mkdir(parents=True,exist_ok=True);args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'queries.jsonl.gz').exists():raise ValueError('refuse to overwrite raw results')
    import onnxruntime as ort
    original=ort.InferenceSession
    def fixed_session(*a,**kw):
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        kw['sess_options']=options;return original(*a,**kw)
    ort.InferenceSession=fixed_session
    from writ_retrieval.reliable.cli import encoder
    start=time.perf_counter();model,identity=encoder(args.model_dir);startup=(time.perf_counter()-start)*1000
    ort.InferenceSession=original
    cpu_start=time.process_time();records=[];imports={};sessions={};stores={};cold=[]
    try:
        for pin in settings['source_revisions']:
            value=fixture(pin);store=ReliableStore(args.work_dir/('store-'+pin[:7]),create=True,clock=lambda v=value:v['recorded_at']);stores[pin]=store
            start=time.perf_counter();receipt=ingest_passages(store,value,project='writ-public');imports[pin]={'elapsed_ms':(time.perf_counter()-start)*1000,'receipt':receipt,'documents':len(value['documents'])}
            for name in settings['comparisons']:
                if name.startswith('legacy'):
                    s=ReliableSession(store,model,encoder_id=identity,cache_dir=args.work_dir/'cache-legacy')
                else:s=GroundedSession(store,model,encoder_id=identity,cache_dir=args.work_dir/('cache-'+name),backend='relate' if name.endswith('relate') else 'flat')
                sessions[pin,name]=s
        budget=Budget(settings['budget_bytes'],settings['budget_chars']);rng=random.Random(settings['seed']);arms=settings['comparisons'];schedule=list(tasks);rng.shuffle(schedule)
        def call(task,name):
            s=sessions[task['corpus_revision'],name];kw={'project':task['project'],'arm':'connected' if name=='legacy-connected' else 'hybrid','budget':budget}
            if not name.startswith('legacy'):kw['request']=task['request']
            return s.context(task['query'],**kw)
        # All first builds are recorded separately. Warm measurements include shared
        # model inference, fresh canonical export/digest validation, DB/index I/O and rendering.
        for pin in settings['source_revisions']:
            task=next(t for t in tasks if t['corpus_revision']==pin and t['project']=='writ-public' and t['track']=='natural')
            order=list(arms);rng.shuffle(order)
            for name in order:
                start=time.perf_counter();result=call(task,name);cold.append({'arm':name,'revision':pin,'elapsed_ms':(time.perf_counter()-start)*1000,'error':result.get('error')})
        for repeat in range(settings['repetitions']):
            rng.shuffle(schedule)
            for task_index,task in enumerate(schedule):
                # Latin rotations, randomized initial order; no fastest-run selection.
                order=arms[(task_index+repeat)%len(arms):]+arms[:(task_index+repeat)%len(arms)]
                for name in order:
                    start=time.perf_counter();result=call(task,name);elapsed=(time.perf_counter()-start)*1000
                    records.append({'task_id':task['id'],'track':task['track'],'category':task['category'],'family':task['family'],
                        'expected_unknown':task['expected_unknown'],'corpus_revision':task['corpus_revision'],'query':task['query'],'request':task['request'],
                        'arm':name,'repeat':repeat,'elapsed_ms':elapsed,'score':score(task,result,name.startswith('legacy')),'result':result})
            print(f'{args.split}: repetition {repeat+1} complete',flush=True)
        with gzip.GzipFile(filename=str(args.out/'queries.jsonl.gz'),mode='wb',mtime=0) as f:
            for r in records:f.write((canonical(r)+'\n').encode())
        report=summarize(records)
        report.update(implementation_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sorted(Path('src/writ_retrieval/reliable').glob('*.py')),Path(__file__)]},split=args.split,protocol=digest(settings),model_identity=identity,model_startup_ms=startup,imports=imports,cold_first_context=cold,
            hardware={'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'cpu_model':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),None)},
            resources={'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cpu_seconds':time.process_time()-cpu_start,
                       'disk_bytes':sum(p.stat().st_size for p in args.work_dir.rglob('*') if p.is_file()),
                       'note':'Shared persistent Python process, embedded Relate and ONNX included. Peak RSS is whole run, not per-arm attribution. Local filesystem warm; no privileged cache flush.'},
            versions={k:__import__('importlib.metadata',fromlist=['version']).version(k) for k in ('relate-db','numpy','tantivy','onnxruntime','tokenizers','pydantic')},
            agent_trials={'status':'NOT RUN','missing':'Authorized generative endpoint/host invocation and exact generative model identity. Embedding inference and scripted tests are not agent trials.'})
        (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'out':str(args.out),'quality':{k:v['all'] for k,v in report['arms'].items()}},indent=2))
    finally:
        for s in sessions.values():
            if isinstance(s,GroundedSession):s.close()
        for store in stores.values():store.close()

if __name__=='__main__':main()

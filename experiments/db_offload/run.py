"""Development-only configuration comparison; held-out requires frozen selection."""
import argparse,contextlib,hashlib,json,random,resource,statistics,subprocess,time
from pathlib import Path
import numpy as np
from .data import load,permitted,render,score,digest
from .adapters import Flat,Native
from .model import Model
from .engine import neo4j_server

SOURCE_HASHES={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('data.py','adapters.py','embed.py','model.py','run.py')}

ARMS={'A-lexical':('A','lexical',False),'A-vector':('A','vector',False),'A-hybrid':('A','hybrid',False),'A-connected':('A','hybrid',True),'B-flat':('B','hybrid',False),'B-connected':('B','hybrid',True),'C-flat':('C','hybrid',False),'C-connected':('C','hybrid',True),'D-flat':('D','hybrid',False),'D-connected':('D','hybrid',True)}

def evaluation(args):
 corpus,tasks,settings=load()
 if args.partition=='heldout':
  if not args.selection:raise ValueError('held-out access requires a committed config selection')
  selection=json.loads(args.selection.read_text())
  if selection.get('frozen') is not True:raise ValueError('selection not frozen')
  subprocess.check_call(['git','ls-files','--error-unmatch',str(args.selection)],stdout=subprocess.DEVNULL)
 else:selection=None
 tasks=[t for t in tasks if t['partition']==args.partition]
 args.output.mkdir(parents=True,exist_ok=False);args.work.mkdir(parents=True,exist_ok=False)
 model=Model(args.model_dir);start=time.perf_counter();matrix,_=model.encode([u['text'] for u in corpus['units']]);corpus_embed_ms=(time.perf_counter()-start)*1000
 positions={u['id']:i for i,u in enumerate(corpus['units'])};rows=[];imports={}
 arm_names=args.arms.split(',')
 need_neo=any(ARMS[a][0]=='D' for a in arm_names)
 with contextlib.ExitStack() as stack:
  if need_neo:
   neo,server,startup=stack.enter_context(neo4j_server(args.neo4j_home,args.work/'neo4j'));imports['neo4j_startup_ms']=startup
  stack.callback(model.close)
  adapters={}
  for owner in set(ARMS[a][0] for a in arm_names):
   adapter=Flat() if owner=='A' else Native(args.work/owner,heavy=owner in {'C','D'},kind='neo4j' if owner=='D' else 'relate',db=neo if owner=='D' else None)
   adapters[owner]=adapter
   if owner!='D':stack.callback(adapter.close)
  configs=settings['tuning']['configs'] if selection is None else [None]
  rng=random.Random(settings['seed'])
  for config_index,configuration in enumerate(configs):
   order=[(task,arm) for task in tasks for arm in arm_names];rng.shuffle(order)
   for task,arm in order:
    if len(rows)%32==0:print('completed',len(rows),'of',len(configs)*len(order),flush=True)
    owner,mode,connected=ARMS[arm];adapter=adapters[owner];config=configuration if selection is None else selection['matched_policy'] if args.track=='matched' else selection['arms'][arm]
    units=permitted(corpus,task);vectors=matrix[[positions[u['id']] for u in units]]
    start=time.perf_counter();scope=adapter.prepare(units,vectors,corpus['edges']);prepare_ms=(time.perf_counter()-start)*1000
    repetitions=[];context=None;ranked=None
    try:
     qvector,_=model.encode([task['query']]);query_start=time.perf_counter();adapter.search(scope,task['query'],qvector[0],k=config['candidate_k'],gate=config['gate'],mode=mode,connected=connected);query_ms=(time.perf_counter()-query_start)*1000
     previous=None
     for _ in range(settings['quality_repetitions']):
      start=time.perf_counter();current=permitted(corpus,task);scope=adapter.prepare(current,matrix[[positions[u['id']] for u in current]],corpus['edges']);qvector,inference=model.encode([task['query']]);ranked=adapter.search(scope,task['query'],qvector[0],k=config['candidate_k'],gate=config['gate'],mode=mode,connected=connected)
      context=render(task,ranked,units,scope,settings);repetitions.append((time.perf_counter()-start)*1000)
      signature=([r['uid'] for r in ranked],context['payload'])
      if previous is not None and signature!=previous:raise ValueError('NONDETERMINISTIC_SELECTION')
      previous=signature
     rows.append({'task_id':task['id'],'category':task['category'],'family':task['id'].rsplit('-',1)[0],'arm':arm,'config':config,'config_index':config_index,'partition':args.partition,'query':task['query'],'gold':task['gold'],'expected_unknown':task['expected_unknown'],'metrics':score(task,context),'query_only_ms':query_ms,'e2e_ms':repetitions,'prepare_ms':prepare_ms,'allowed_units':len(units),'ranked':ranked,**context})
    except Exception as e:rows.append({'task_id':task['id'],'family':task['id'].rsplit('-',1)[0],'arm':arm,'config':config,'config_index':config_index,'partition':args.partition,'error':{'kind':type(e).__name__,'message':str(e)}})
  for owner,adapter in adapters.items():
   imports[owner]={'import_ms':adapter.import_ms,'materialized_partitions':len(adapter.views),'materialized_rows':sum(len(v[0] if owner=='A' else v['units']) for v in adapter.views.values())}
   if owner!='A':(args.output/(owner+'-queries.json')).write_text(json.dumps(adapter.query_log,indent=2)+'\n')
 model.close()
 summary={'version':'writ-bakeoff-quality/1','partition':args.partition,'track':args.track,'tasks':len(tasks),'label_status':'PROVISIONAL, NOT HUMAN REVIEWED','code_sha256':SOURCE_HASHES,'inference_threads':{'intra_op':2,'inter_op':1},'code_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'model':model.info,'corpus_embedding_ms':corpus_embed_ms,'corpus_sha256':hashlib.sha256(Path('experiments/db_offload/fixtures/corpus.json').read_bytes()).hexdigest(),'imports':imports,'arms':{},'measurement_note':'E2E includes permitted-set resolution, generation validation, inference, retrieval, fusion/expansion and rendering; initial import is separately measured', 'peak_client_process_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'memory_note':'quality process contains multiple arms; isolated total resources measured in performance profiles'}
 for arm in arm_names:
  for ci in range(len(configs)):
   group=[r for r in rows if r['arm']==arm and r['config_index']==ci];valid=[r for r in group if 'metrics' in r];positive=[r for r in valid if r['metrics']['gold_clauses']];negative=[r for r in valid if r['expected_unknown']]
   summary['arms'][arm+':'+str(ci)]={'n':len(group),'errors':len(group)-len(valid),'positive_tasks':len(positive),'complete_answers':sum(r['metrics']['complete_answer'] for r in positive),'delivered_clauses':sum(r['metrics']['delivered_clauses'] for r in positive),'gold_clauses':sum(r['metrics']['gold_clauses'] for r in positive),'mrr':statistics.mean(r['metrics']['mrr'] for r in positive) if positive else 0,'unknown_tasks':len(negative),'correct_abstentions':sum(r['metrics']['correct_abstention'] for r in negative),'e2e_p95_ms':float(np.percentile([x for r in valid for x in r['e2e_ms']],95)) if valid else None,'all_citations_scopes_correct':all(r['metrics']['citation_correct'] and r['metrics']['scope_correct'] for r in valid)}
 (args.output/'queries.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows));(args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary['arms'],indent=2))

def main():
 p=argparse.ArgumentParser();p.add_argument('--partition',choices=['development','heldout'],required=True);p.add_argument('--selection',type=Path);p.add_argument('--track',choices=['matched','best'],default='best');p.add_argument('--arms',default='A-lexical,A-vector,A-hybrid,A-connected,B-flat,B-connected,C-flat,C-connected');p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--neo4j-home',type=Path);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);evaluation(p.parse_args())
if __name__=='__main__':main()

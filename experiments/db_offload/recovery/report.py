"""Reports and review packets from NEW raw hosted results, never lost data reconstruction."""
import argparse,collections,csv,gzip,hashlib,json,random,statistics
from pathlib import Path
import numpy as np
from experiments.db_offload.data import load
def rows(folder):
 path=folder/'queries.jsonl'
 if path.exists():return [json.loads(x) for x in path.read_text().splitlines()]
 with gzip.open(str(path)+'.gz','rt') as f:return [json.loads(x) for x in f]
def read(path):
 if path.exists():return json.loads(path.read_text())
 with gzip.open(str(path)+'.gz','rt') as f:return json.load(f)
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();_,tasks,s=load();held=[t for t in tasks if t['partition']=='heldout'];result={'execution':'NEW hosted replication, not recovered local files','labels':'MODEL AUTHORED, NOT HUMAN REVIEWED','positive_tasks':20,'unknown_tasks':12,'positive_families':10,'unknown_families':6,'clauses':24,'tracks':{},'adoption':'BLOCKED: unreviewed labels and unsupported live-memory/shared/conflict/replay/storage integration gates'};lines=['# Hosted replication findings','','This is a new execution of already frozen policies after workspace loss. It is not a new unseen evaluation, tuning, or reconstruction of lost raw measurements. All labels remain provisional.','', 'Complete target delivery means all 120-character frozen source proxies with exact version/digest are actually present. It is not independent proof of full answer sufficiency. There are 20 positive tasks / ten families, 12 warranted-unknown controls / six families, 24 target instances and only five distinct source versions.','']
 review=a.root/'review';review.mkdir(exist_ok=True);packets={};blind=[];keys=[]
 for track in ('matched','best'):
  path=a.root/('heldout-'+track)
  if not path.exists():continue
  data=rows(path);lookup={(r['arm'],r['task_id']):r for r in data};arms=sorted({r['arm'] for r in data});out={};paired={}
  lines+=['## '+track,'','| Arm | Targets complete /20 | Clauses /24 | MRR | Empty abstentions /12 | E2E p95 ms | Errors |','|---|---:|---:|---:|---:|---:|---:|']
  for arm in arms:
   group=[r for r in data if r['arm']==arm];valid=[r for r in group if 'metrics' in r];positive=[r for r in valid if r['metrics']['gold_clauses']];negative=[r for r in valid if r['expected_unknown']];timing=[v for r in valid for v in r['e2e_ms']];metrics={'n':len(group),'errors':len(group)-len(valid),'complete':sum(r['metrics']['complete_answer'] for r in positive),'delivered_clauses':sum(r['metrics']['delivered_clauses'] for r in positive),'mrr':sum(r['metrics']['mrr'] for r in positive)/20,'precision_incomplete_labels':sum(r['metrics']['precision'] for r in positive)/20,'single_target_ndcg_n':sum(r['metrics']['ndcg'] is not None for r in positive),'single_target_ndcg':statistics.mean(r['metrics']['ndcg'] for r in positive if r['metrics']['ndcg'] is not None) if positive else None,'correct_empty_context_abstentions':sum(r['metrics']['correct_abstention'] for r in negative),'unnecessary_empty_context':sum(r['metrics']['unnecessary_abstention'] for r in positive),'citation_scope_failures':sum(not(r['metrics']['citation_correct'] and r['metrics']['scope_correct']) for r in valid),'e2e_p50_ms':float(np.percentile(timing,50)) if timing else None,'e2e_p95_ms':float(np.percentile(timing,95)) if timing else None,'latency_n':len(timing),'max_bytes':max([r['bytes'] for r in valid],default=0),'max_chars':max([r['characters'] for r in valid],default=0)}
   out[arm]=metrics;deltas=collections.defaultdict(list);changes=[]
   for task in [t for t in held if t['gold']]:
    b=lookup.get(('A-hybrid',task['id']),{}).get('metrics',{});r=lookup.get((arm,task['id']),{}).get('metrics',{});delta=[int(r.get('complete_answer',False))-int(b.get('complete_answer',False)),r.get('mrr',0)-b.get('mrr',0)];deltas[task['id'].rsplit('-',1)[0]].append(delta)
    if delta!=[0,0]:changes.append({'task':task['id'],'complete_delta':delta[0],'mrr_delta':delta[1]})
   values=np.array([np.mean(x,axis=0) for _,x in sorted(deltas.items())]);rng=np.random.default_rng(s['seed']);samples=values[rng.integers(0,len(values),(2000,len(values)))].mean(axis=1);low=np.percentile(samples,5,axis=0);paired[arm]={'reference':'A-hybrid','mean_delta':values.mean(axis=0).tolist(),'one_sided_95_lower':low.tolist(),'provisional_noninferior':bool(np.all(low>-.03)),'fields':['complete target delivery','MRR'],'changes':changes,'families':len(values),'draws':2000}
   lines.append(f"| {arm} | {metrics['complete']} | {metrics['delivered_clauses']} | {metrics['mrr']:.3f} | {metrics['correct_empty_context_abstentions']} | {metrics['e2e_p95_ms'] or 0:.1f} | {metrics['errors']} |")
  result['tracks'][track]={'arms':out,'paired_family_bootstrap':paired}
  if track=='matched':
   order=list(range(len(data)));random.Random(s['seed']).shuffle(order)
   for i,j in enumerate(order):
    row=data[j];blind.append({'anonymous_id':i,'task':row['task_id'],'payload':row.get('payload'),'error':row.get('error'),'review':'UNREVIEWED','rubric':['full warranted answer','source/revision/digest','temporal correctness','conflicts','useful abstention']});keys.append({'anonymous_id':i,'arm':row['arm']})
   for r in data:
    if r['arm'] in {'A-hybrid','C-flat'}:packets.setdefault(r['task_id'],{})['flat' if r['arm']=='A-hybrid' else 'native']=r.get('payload','Explicit retrieval failure')
 if (a.root/'reranker/queries.jsonl').exists():
  rr=rows(a.root/'reranker');result['reranker']={'actual_calls':len(rr),'added_p50_ms':float(np.percentile([r['added_ms'] for r in rr],50)),'added_p95_ms':float(np.percentile([r['added_ms'] for r in rr],95)),'peak_worker_rss_kib':max(r['worker']['peak_rss_kib'] for r in rr),'composed_timings_only':True,'arms':{}}
  for arm in sorted({r['arm'] for r in rr}):
   group=[r for r in rr if r['arm']==arm];positive=[r for r in group if r['metrics']['gold_clauses']];result['reranker']['arms'][arm]={'complete':sum(r['metrics']['complete_answer'] for r in positive),'mrr':sum(r['metrics']['mrr'] for r in positive)/20,'changes':[{'task':r['task_id'],'complete_delta':int(r['metrics']['complete_answer'])-int(r['before']['complete_answer']),'mrr_delta':r['metrics']['mrr']-r['before']['mrr']} for r in positive]}
  lines+=['','## Learned reranking, separate from ownership','',json.dumps(result['reranker'],indent=2),'','Added processing and worker memory are measured independently; composed E2E is not a direct full-system reranking measurement. No threshold was tuned.']
 fields=['task_id','partition','category','query','as_of','expected_unknown','source_uri','source_revision','source_digest','start','end','answer_text','review_status','reviewer','finding','alternative_passage','notes']
 with (review/'labels.csv').open('w',newline='') as file:
  writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader()
  for t in tasks:
   for g in t['gold'] or [{}]:writer.writerow({**{k:t[k] for k in fields if k in t},**{k:v for k,v in g.items() if k in fields},'task_id':t['id'],'review_status':'NOT HUMAN REVIEWED'})
 (review/'blind-contexts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in blind));(review/'blind-key.json').write_text(json.dumps(keys));(review/'agent-packets.json').write_text(json.dumps(packets));(review/'README.md').write_text('Labels and contexts are UNREVIEWED. Read exact public source versions and wider qualifications around the 120-character proxies; record alternatives and unknowns. Keep blind-key separate. No human approval or outcome follows from automated scoring.\n')
 perf=a.root/'performance';result['performance']={}
 if perf.exists():
  lines+=['','## All registered resource profiles','','| Profile | Status | n | p50/p95/p99 ms | Peak RSS MiB | Import ms | Disk MiB | CPU s |','|---|---|---:|---|---:|---:|---:|---:|']
  for g,r,arm in read(perf/'order.json'):
   name=f'{arm}-{g}-{r}';path=perf/(name+'.json')
   if not path.exists() and not Path(str(path)+'.gz').exists():result['performance'][name]={'status':'NOT FINISHED'};continue
   row=read(path);result['performance'][name]={k:v for k,v in row.items() if k not in {'rows','partial_rows','resource_samples'}};lat=row.get('latency') or {};lat=lat.get('e2e_ms');times='/'.join(f'{lat[k]:.1f}' for k in ('p50','p95','p99')) if lat else '-';lines.append(f"| {name} | {row['status']} | {row.get('n','?')} | {times} | {row.get('combined_peak_rss_bytes',0)/1048576:.1f} | {row.get('import_index_ms',0):.1f} | {row.get('disk_bytes',0)/1048576:.1f} | {row.get('cpu_seconds_waited_process_tree',0):.1f} |")
  result['registered_profiles']=24;result['finished_profiles']=sum(r['status']!='NOT FINISHED' for r in result['performance'].values())
 lines+=['','## Limits and proposed split','','No production modules or dependencies are removed. Keep Relate persistence and application source/binding/visibility/replay/confidence/approval/budget semantics. Native partitions are not built-in authorization. Automatic conflict discovery, trusted shared publication, full canonical-memory projection, native evidence replay/retraction, device faults, remote server and full cold CLI recovery remain unsupported adoption gates.','', 'A source digest establishes identity, not truth. Human labels and actual generative outcomes remain unreviewed/NOT RUN. The 64 formulations represent only 32 families and a small public-document corpus. No claim generalizes to untested database versions, configurations or project populations.','', 'Performance uses fresh processes and static prepared generations, one serialized offline model and separate reader connections. It includes inference, DB/transport, validation and complete rendering, excluding live canonical refresh. Cooperative 2 GiB RSS checks run after setup and during queries, not an OS hard limit. 180 s query and 300 s outer limits are retained. RSS samples can miss peaks, CPU counts may omit unwaited descendants. Working disk excludes shared runtimes/model/distribution; environment metadata records those separately. Failed profiles have no adoption percentiles. One hosted run/profile is not an independent multi-host replication.','', 'The original offline CLI and all baselines are unchanged. Any adoption needs completed correctness integrations, actual independent review, the registered noninferiority/speed/RSS thresholds and new held-out data before further tuning. Rollback is simply the unchanged production path.']
 (a.root/'summary.json').write_text(json.dumps(result,indent=2));(a.root/'FINDINGS.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()

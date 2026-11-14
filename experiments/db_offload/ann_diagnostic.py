"""Registered, exploratory load control. No held-out semantic evaluation or tuning."""
import argparse,hashlib,json,os,platform,random,signal,subprocess,sys,time
from pathlib import Path
import hnswlib,numpy as np
from .adapters import Flat
from .data import keywords

class ANNFlat(Flat):
 instances=[]
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.indexes={};self.samples={};self.instances.append(self)
 def prepare(self,units,vectors,edges):
  scope=super().prepare(units,vectors,edges)
  if scope not in self.indexes:
   start=time.perf_counter();index=hnswlib.Index(space='cosine',dim=384);index.init_index(max_elements=max(1,len(units)),M=16,ef_construction=100,random_seed=20261113)
   if units:index.add_items(vectors,np.arange(len(units)),num_threads=1)
   index.set_ef(100);index.set_num_threads(1);self.indexes[scope]=index;self.import_ms+=(time.perf_counter()-start)*1000
  return scope
 def lists(self,scope,q,vector,k,gate):
  units,matrix,kw,_=self.views[scope];lex=[{'uid':r['rule_id'],'score':r['score']} for r in kw.search(keywords(q),limit=max(1,len(units)))] if units else [];lex.sort(key=lambda r:(-r['score'],r['uid']))
  if not units:return lex[:k],[]
  ids,distances=self.indexes[scope].knn_query(np.asarray(vector,dtype=np.float32),k=min(k,len(units)),num_threads=1);raw=[{'uid':units[int(i)]['id'],'score':1-float(d)} for i,d in zip(ids[0],distances[0])];raw.sort(key=lambda r:(-r['score'],r['uid']))
  if q not in self.samples:self.samples[q]={'scope':scope,'vector':np.asarray(vector,dtype=np.float32).copy(),'ids':[int(i) for i in ids[0]]}
  return lex[:k],[r for r in raw if r['score']>=gate]
 def oracle(self):
  rows=[]
  for query,sample in self.samples.items():
   units,matrix,_,_=self.views[sample['scope']];scores=matrix@sample['vector'];order=sorted(range(len(units)),key=lambda i:(-float(scores[i]),units[i]['id']));gold=order[:20];threshold=float(scores[gold[-1]]);found=sample['ids'];rows.append({'query':query,'units':len(units),'k':20,'strict_recall':len(set(found)&set(gold))/20,'tie_aware_recall':sum(float(scores[i])>=threshold-1e-6 for i in found)/20,'oracle_ids':[units[i]['id'] for i in gold],'returned_ids':[units[i]['id'] for i in found]})
  return rows

def profile(args):
 from .recovery import perf
 requested=args.arm
 if requested=='A-ANN':perf.Flat=ANNFlat
 cli=['perf','--arm','A' if requested.startswith('A-') else 'D','--growth','100','--readers',str(args.readers),'--model-dir',str(args.model_dir),'--neo4j-home',str(args.neo4j_home),'--work',str(args.work),'--output',str(args.output)];sys.argv=cli;perf.main();result=json.loads(args.output.read_text());result.update(version='supplemental-local-load/1',arm=requested,exploratory=True,no_heldout_scoring=True,source_sha256={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('ann_diagnostic.py','recovery/perf.py','adapters.py','data.py','model.py','embed.py','engine.py')})
 if ANNFlat.instances:result['oracle_after_timing']=ANNFlat.instances[-1].oracle()
 args.output.write_text(json.dumps(result,indent=2)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',action='store_true');p.add_argument('--arm',choices=['A-ANN','A-exact','D-native']);p.add_argument('--readers',type=int,choices=[1,4]);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--neo4j-home',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.profile:return profile(a)
 a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=False);order=[(arm,n) for arm in ('A-ANN','A-exact','D-native') for n in (1,4)];random.Random(20261113).shuffle(order)
 environment={'python':platform.python_version(),'platform':platform.platform(),'logical_cpus':os.cpu_count(),'cpu_model':next(x for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'protocol_commit':'2f2729b2459b5c0eef1b73e4b4f9be4de48fa395','scope':'Exploratory static-generation load only; new local host, never combine with primary hosted timings; no held-out quality claim.'};(a.output/'environment.json').write_text(json.dumps(environment,indent=2)+'\n');(a.output/'order.json').write_text(json.dumps(order))
 for arm,n in order:
  name=f'{arm}-{n}';out=a.output/(name+'.json');command=[sys.executable,'-m','experiments.db_offload.ann_diagnostic','--profile','--arm',arm,'--readers',str(n),'--model-dir',str(a.model_dir),'--neo4j-home',str(a.neo4j_home),'--work',str(a.work/name),'--output',str(out)]
  with (a.output/(name+'.log')).open('w') as log:
   process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:process.wait(timeout=300)
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGTERM)
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    partial=out.with_suffix('.partial.json');data=json.loads(partial.read_text()) if partial.exists() else {};out.write_text(json.dumps({**data,'arm':arm,'readers':n,'status':'TIMEOUT','outer_limit_seconds':300,'latency':None,'exploratory':True}))
  if not out.exists():out.write_text(json.dumps({'arm':arm,'readers':n,'status':'PROCESS_FAILED','exit':process.returncode}))
  print(name,json.loads(out.read_text())['status'],flush=True)
if __name__=='__main__':main()

"""Static-generation complete payload performance; independent hosted replication."""
import argparse,concurrent.futures,contextlib,hashlib,json,resource,threading,time
from pathlib import Path
import numpy as np
import psutil
from experiments.db_offload.data import load,permitted,render,norm
from experiments.db_offload.adapters import Flat,Native
from experiments.db_offload.model import Model
from experiments.db_offload.engine import neo4j_server
from experiments.db_offload.workers import WorkerDB
class Monitor:
 def __init__(self):
  self.stop=threading.Event();self.peak=0;self.samples=[];self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  while not self.stop.wait(.02):
   rss=cpu=0
   for p in [psutil.Process(),*psutil.Process().children(recursive=True)]:
    try:rss+=p.memory_info().rss;t=p.cpu_times();cpu+=t.user+t.system
    except psutil.Error:pass
   self.peak=max(self.peak,rss);self.samples.append({'seconds':time.monotonic(),'rss_bytes':rss,'alive_cpu_seconds':cpu})
 def close(self):self.stop.set();self.thread.join()
def main():
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=['A','B','C','D'],required=True);p.add_argument('--growth',type=int,choices=[1,10,100],required=True);p.add_argument('--readers',type=int,choices=[1,4],required=True);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--neo4j-home',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);a.output.parent.mkdir(parents=True,exist_ok=True)
 c,t,s=load();tasks=[x for x in t if x['partition']=='development'];task=next(x for x in tasks if x['category']=='exact');base=permitted(c,task);mon=Monitor();start_all=time.perf_counter();rows=[];result={'version':'hosted-replication/1','arm':a.arm,'growth':a.growth,'readers':a.readers,'status':'RUNNING','target_samples':1000,'synthetic_scaling':a.growth!=1}
 def checkpoint():
  a.output.with_suffix('.partial.json').write_text(json.dumps({**result,'n':len(rows),'partial_rows':rows,'combined_peak_rss_bytes':mon.peak}))
 try:
  with contextlib.ExitStack() as stack:
   m=Model(a.model_dir);stack.callback(m.close);mutex=threading.Lock();start=time.perf_counter();v,_=m.encode([u['text'] for u in base]);result.update(model_startup_ms=m.startup_ms,corpus_embedding_ms=(time.perf_counter()-start)*1000)
   units=[];edges=[];matrices=[];ids={u['id'] for u in base};base_edges=[e for e in c['edges'] if e['a'] in ids and e['b'] in ids];rng=np.random.default_rng(s['seed'])
   for i in range(a.growth):
    suffix='' if i==0 else ':synthetic-'+str(i);units.extend({**u,'id':u['id']+suffix} for u in base);edges.extend({**e,'a':e['a']+suffix,'b':e['b']+suffix} for e in base_edges);matrices.append(v if i==0 else norm(v+rng.normal(0,1e-5,v.shape)))
   matrix=np.concatenate(matrices);result['units']=len(units);db=None
   if a.arm=='D':db,_,startup=stack.enter_context(neo4j_server(a.neo4j_home,a.work/'neo4j'));result['server_startup_ms']=startup
   root=Flat() if a.arm=='A' else Native(a.work/'graph',db=db,kind='neo4j' if a.arm=='D' else 'relate',heavy=a.arm in {'C','D'})
   start=time.perf_counter();scope=root.prepare(units,matrix,edges);result['import_index_ms']=(time.perf_counter()-start)*1000;checkpoint();local=threading.local()
   if a.readers==4 and a.arm in {'B','C'}:root.close()
   def request(i):
    if not hasattr(local,'adapter'):
     if a.readers==1 or a.arm=='A':local.adapter=root
     else:
      worker=WorkerDB('neo4j' if a.arm=='D' else 'relate',a.work/'graph' if a.arm in {'B','C'} else None);local.adapter=Native(db=worker,kind='neo4j' if a.arm=='D' else 'relate',heavy=a.arm in {'C','D'});local.adapter.views=root.views;stack.callback(local.adapter.close)
    query=tasks[(i%4)*2]['query'];item={**task,'query':query};start=time.perf_counter()
    with mutex:q,inference=m.encode([query])
    query_start=time.perf_counter();ranked=local.adapter.search(scope,query,q[0],20,.3);query_ms=(time.perf_counter()-query_start)*1000;out=render(item,ranked,units,scope,s)
    return {'e2e_ms':(time.perf_counter()-start)*1000,'query_only_ms':query_ms,'inference_ms':inference,'bytes':out['bytes']}
   for i in range(10):request(i)
   if mon.peak>s['rss_budget_mib']*1048576:raise MemoryError('cooperative RSS budget exceeded after setup')
   begin=time.perf_counter();pool=concurrent.futures.ThreadPoolExecutor(max_workers=a.readers) if a.readers>1 else None
   try:
    values=pool.map(request,range(1000)) if pool else map(request,range(1000))
    for value in values:
     rows.append(value)
     if len(rows)%100==0:checkpoint()
     if time.perf_counter()-begin>s['timeout_seconds']:raise TimeoutError('registered query timeout')
     if mon.peak>s['rss_budget_mib']*1048576:raise MemoryError('cooperative RSS budget exceeded')
   finally:
    if pool:pool.shutdown(wait=True,cancel_futures=True)
   wall=time.perf_counter()-begin;result.update(status='COMPLETE',n=len(rows),throughput_per_second=len(rows)/wall,rows=rows,latency={k:{q:float(np.percentile([r[k] for r in rows],n)) for q,n in [('p50',50),('p95',95),('p99',99)]} for k in ('e2e_ms','query_only_ms')})
   if a.arm in {'B','C'}:
    if a.readers==1:root.close()
    start=time.perf_counter();worker=WorkerDB('relate',a.work/'graph');worker.execute('RETURN 1 AS ready');worker.close();result['engine_restart_ms']=(time.perf_counter()-start)*1000
 except Exception as e:result.update(status='FAILED',error={'kind':type(e).__name__,'message':str(e)},n=len(rows),partial_rows=rows)
 finally:
  mon.close();x=resource.getrusage(resource.RUSAGE_SELF);y=resource.getrusage(resource.RUSAGE_CHILDREN);result.update(total_wall_seconds=time.perf_counter()-start_all,combined_peak_rss_bytes=mon.peak,resource_samples=mon.samples,cpu_seconds_waited_process_tree=x.ru_utime+x.ru_stime+y.ru_utime+y.ru_stime,disk_bytes=sum(x.stat().st_size for x in a.work.rglob('*') if x.is_file()),cpu_note='SELF plus waited CHILDREN; orphan/unwaited descendants may be incomplete; RSS sampled at 20ms')
  a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(a.arm,a.growth,a.readers,result['status'],flush=True)
if __name__=='__main__':main()

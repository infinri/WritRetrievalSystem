"""Equivalent native queries/data through Python or Rust workers, same framing."""
import argparse,contextlib,hashlib,json,statistics,time
from pathlib import Path
import numpy as np
from .adapters import Native
from .data import load,permitted,norm
from .engine import neo4j_server
from .model import Model
from .workers import WorkerDB

def main():
 p=argparse.ArgumentParser();p.add_argument('--connected',action='store_true');p.add_argument('--backend',choices=['relate','neo4j'],required=True);p.add_argument('--rust',type=Path,required=True);p.add_argument('--ffi',type=Path,required=True);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--neo4j-home',type=Path);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False)
 corpus,tasks,settings=load();task=next(t for t in tasks if t['partition']=='development');units=permitted(corpus,task);rows=[]
 with contextlib.ExitStack() as stack:
  model=Model(a.model_dir);stack.callback(model.close);vectors,_=model.encode([u['text'] for u in units]);query,_=model.encode([task['query']])
  db=None
  if a.backend=='neo4j':db,_,_=stack.enter_context(neo4j_server(a.neo4j_home,a.work/'neo4j'))
  base=Native(a.work/'graph',db=db,kind=a.backend,heavy=True);scope=base.prepare(units,vectors,corpus['edges']);view=base.views[scope]
  if a.backend=='relate':base.close() # Both worker languages open the same immutable, checkpointed store.
  for language in ('python','rust'):
   worker=WorkerDB(a.backend,a.work/'graph' if a.backend=='relate' else None,rust=a.rust if language=='rust' else None,ffi=a.ffi)
   runtime=Native(db=worker,kind=a.backend,heavy=True);runtime.views[scope]=view
   version=worker.execute('CALL dbms.components()',{});timings=[];expected=None
   for i in range(210):
    start=time.perf_counter();ranked=runtime.search(scope,task['query'],query[0],20,.3,connected=a.connected);elapsed=(time.perf_counter()-start)*1000
    signature=[r['uid'] for r in ranked]
    if expected is not None and signature!=expected:raise AssertionError('language worker nondeterminism')
    expected=signature
    if i>=10:timings.append(elapsed)
   rows.append({'language':language,'backend':a.backend,'version':version,'n':len(timings),'query_only_ms':timings,'p50_ms':float(np.percentile(timings,50)),'p95_ms':float(np.percentile(timings,95)),'selected_ids':expected,'note':'Same stdio framing, prepared store, queries and precomputed vector; model/rendering excluded for client-language isolation, not an E2E speedup claim.'});runtime.close()
 if rows[0]['selected_ids']!=rows[1]['selected_ids']:raise AssertionError('Python/Rust query parity failed')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'rows':rows,'parity':True,'rust_binary_sha256':hashlib.sha256(a.rust.read_bytes()).hexdigest(),'ffi_sha256':hashlib.sha256((a.ffi/'librelate_ffi.so').read_bytes()).hexdigest()},indent=2)+'\n');print([(r['language'],r['p95_ms']) for r in rows])
if __name__=='__main__':main()

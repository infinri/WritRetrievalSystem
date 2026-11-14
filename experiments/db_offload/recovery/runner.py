"""Sequential hosted quality replication; every failure is persisted."""
import argparse,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
from experiments.db_offload.data import load
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--performance',action='store_true');a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True);load();records=[];tool=a.tools/'neo4j-community-5.26.0';base=[sys.executable];model='data/model';arms='A-lexical,A-vector,A-hybrid,A-connected,B-flat,B-connected,C-flat,C-connected,D-flat,D-connected'
 def run(name,args,timeout=1200):
  start=time.perf_counter()
  with (a.root/(name+'.log')).open('w') as log:
   try:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode;error=None
   except Exception as e:code=-1;error=str(e)
  records.append({'name':name,'command':args,'returncode':code,'error':error,'seconds':time.perf_counter()-start});(a.root/('performance-commands.json' if a.performance else 'quality-commands.json')).write_text(json.dumps(records,indent=2))
  return code
 environment={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'python':platform.python_version(),'platform':platform.platform(),'cpu_count':os.cpu_count(),'cpu_model':next((x for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'unknown'),'meminfo':Path('/proc/meminfo').read_text().splitlines()[:3],'packages':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'java':subprocess.run(['java','-version'],capture_output=True,text=True).stderr,'shared_model_disk_bytes':sum(p.stat().st_size for p in Path(model).rglob('*') if p.is_file()),'neo4j_distribution_disk_bytes':sum(p.stat().st_size for p in tool.rglob('*') if p.is_file()),'venv_disk_note':'Installed package list recorded; full interpreter/Java/venv deployment disk not measured. Add shared model/distribution to work disk; not a total footprint claim.','thread_env':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','RAYON_NUM_THREADS')},'new_host_not_local_recovery':True}
 (a.root/('performance-environment.json' if a.performance else 'quality-environment.json')).write_text(json.dumps(environment,indent=2));(a.root/('performance-archives.json' if a.performance else 'quality-archives.json')).write_bytes((a.tools/'archives.json').read_bytes())
 if a.performance:
  run('performance',base+['-m','experiments.db_offload.recovery.suite','--model-dir',model,'--neo4j-home',str(tool),'--work','data/recovery-performance','--output',str(a.root/'performance')],timeout=8000)
 else:
  preservation=json.loads(Path('experiments/db_offload/protocol/preserved.json').read_text());bad=[name for name,d in preservation.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=d];(a.root/'preservation.json').write_text(json.dumps({'count':len(preservation),'changed':bad}))
  if bad:raise ValueError('preserved fixture drift')
  run('pytest',base+['scripts/offline_run.py','-m','pytest','-q']);run('original-demo-tests',base+['scripts/offline_run.py','-m','unittest','discover','-s','tests','-v'])
  run('capability',base+['-m','experiments.db_offload.capability','--output',str(a.root/'capability.json'),'--neo4j-home',str(tool)])
  for track in ('matched','best'):run('heldout-'+track,base+['-m','experiments.db_offload.run','--partition','heldout','--selection','experiments/db_offload/protocol/selection.json','--track',track,'--arms',arms,'--model-dir',model,'--neo4j-home',str(tool),'--work','data/recovery-'+track,'--output',str(a.root/('heldout-'+track))])
  run('reranker-prepare',base+['-m','experiments.db_offload.recovery.reranker','--prepare','--model-dir','data/reranker']);run('reranker',base+['-m','experiments.db_offload.recovery.reranker','--model-dir','data/reranker','--input',str(a.root/'heldout-matched'),'--output',str(a.root/'reranker')])
  run('mechanics',base+['-m','experiments.db_offload.recovery.mechanics','--model-dir',model,'--neo4j-home',str(tool),'--ffi',str(a.tools),'--rust','experiments/db_offload/rust/target/release/writ-db-thin-client','--work','data/recovery-mechanics','--output',str(a.root/'mechanics')])
  run('historical',base+['scripts/offline_run.py','-m','experiments.db_offload.recovery.historical','--model-dir',model,'--work','data/recovery-original','--output',str(a.root/'historical')])
  run('source-clone',['git','clone','--no-checkout','https://github.com/infinri/Writ','data/source-read-only'])
  run('production-demo',base+['scripts/offline_run.py','-m','writ_retrieval.evaluation.reliable_demo','--repo','data/source-read-only','--model-dir',model,'--work-dir','data/recovery-production-demo','--output',str(a.root/'production-demo')])
 run('report',base+['-m','experiments.db_offload.recovery.report','--root',str(a.root)])
 if not a.performance:run('agent-not-run',base+['-m','experiments.db_offload.recovery.agent','--packets',str(a.root/'review/agent-packets.json'),'--output',str(a.root/'agent-trials')])
 if any(r['returncode']!=0 for r in records):raise SystemExit(1)
if __name__=='__main__':main()

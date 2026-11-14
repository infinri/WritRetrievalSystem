"""All registered profiles, counterbalanced order, isolated fresh process per arm."""
import argparse,json,os,random,signal,subprocess,sys,time
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--neo4j-home',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=False)
 profiles=[(g,r,arm) for g in (1,10,100) for r in (1,4) for arm in 'ABCD'];random.Random(20261113).shuffle(profiles);(a.output/'order.json').write_text(json.dumps(profiles))
 for g,r,arm in profiles:
  name=f'{arm}-{g}-{r}';output=a.output/(name+'.json')
  with (a.output/(name+'.log')).open('w') as log:
   command=[sys.executable,'-m','experiments.db_offload.recovery.perf','--arm',arm,'--growth',str(g),'--readers',str(r),'--model-dir',str(a.model_dir),'--neo4j-home',str(a.neo4j_home),'--work',str(a.work/name),'--output',str(output)];process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:process.wait(timeout=300)
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGTERM)
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    partial=output.with_suffix('.partial.json');data=json.loads(partial.read_text()) if partial.exists() else {};output.write_text(json.dumps({**data,'arm':arm,'growth':g,'readers':r,'status':'TIMEOUT','outer_limit_seconds':300,'latency':None,'note':'Full setup/query/shutdown timeout; partial samples are not completed-profile percentiles.'}))
  if not output.exists():output.write_text(json.dumps({'arm':arm,'growth':g,'readers':r,'status':'PROCESS_FAILED','exit':process.returncode}))
  print(name,json.loads(output.read_text())['status'],flush=True)
if __name__=='__main__':main()

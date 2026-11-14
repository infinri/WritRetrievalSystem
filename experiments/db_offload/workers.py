"""Identical JSON-line transport for language-isolated native client comparisons."""
import argparse,json,os,subprocess,sys
import relate
from .engine import Neo4jHTTP

class WorkerDB:
 def __init__(self,backend,path=None,rust=None,ffi=None):
  command=[str(rust),backend] if rust else [sys.executable,'-m','experiments.db_offload.workers','--backend',backend]
  if path:command+=([str(path)] if rust else ['--store',str(path)])
  env={**os.environ}
  if ffi:env['LD_LIBRARY_PATH']=str(ffi)
  self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,env=env)
 def execute(self,query,params=None):
  self.process.stdin.write(json.dumps({'query':query,'params':params or {}})+'\n');self.process.stdin.flush();line=self.process.stdout.readline()
  if not line:raise RuntimeError('native worker failed: '+self.process.stderr.read()[:1500])
  answer=json.loads(line)
  if 'error' in answer:raise RuntimeError(answer['error'])
  return answer['rows']
 def close(self):
  self.process.stdin.close()
  try:self.process.wait(timeout=5)
  except subprocess.TimeoutExpired:self.process.kill();self.process.wait()

def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['relate','neo4j'],required=True);p.add_argument('--store');a=p.parse_args()
 db=relate.connect(a.store,read_only=True) if a.backend=='relate' else Neo4jHTTP()
 for line in sys.stdin:
  try:
   request=json.loads(line);answer={'rows':[dict(r) for r in db.execute(request['query'],request['params'])]}
  except Exception as e:answer={'error':str(e)}
  print(json.dumps(answer),flush=True)
 db.close()
if __name__=='__main__':main()

"""Identical pipe transport/model cost in every ownership and client-language arm."""
import json,os,subprocess,sys,time
from .data import norm
class Model:
 def __init__(self,directory):
  start=time.perf_counter()
  self.process=subprocess.Popen([sys.executable,'scripts/offline_run.py','-m','experiments.db_offload.embed','--model-dir',str(directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
  line=self.process.stdout.readline()
  if not line:raise RuntimeError('offline embedding process failed: '+self.process.stderr.read()[:1000])
  self.info=json.loads(line);self.startup_ms=(time.perf_counter()-start)*1000
 def encode(self,texts):
  self.process.stdin.write(json.dumps({'texts':texts})+'\n');self.process.stdin.flush()
  response=self.process.stdout.readline()
  if not response:raise RuntimeError('offline model unavailable')
  data=json.loads(response);return norm(data['vectors']),data['inference_ms']
 def close(self):
  self.process.stdin.close()
  try:self.process.wait(timeout=5)
  except subprocess.TimeoutExpired:self.process.kill();self.process.wait()

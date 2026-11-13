"""Small measured-engine boundaries. Neo4j access is explicitly loopback-only."""
import json,os,re,subprocess,time,urllib.request,tempfile
from pathlib import Path
from contextlib import contextmanager

class Neo4jHTTP:
 def __init__(self,url='http://127.0.0.1:17474'):
  if url!='http://127.0.0.1:17474':raise ValueError('bake-off allows only the dedicated local Neo4j endpoint')
  self.url=url+'/db/neo4j/tx/commit'
 def execute(self,query,params=None):
  request=urllib.request.Request(self.url,data=json.dumps({'statements':[{'statement':query,'parameters':params or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=180) as response:data=json.load(response)
  if data.get('errors'):raise RuntimeError(json.dumps(data['errors']))
  result=data['results'][0]
  return [dict(zip(result['columns'],r['row'])) for r in result['data']]
 def close(self):pass

@contextmanager
def neo4j_server(home,root):
 home=Path(home).resolve();root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False);conf=root/'conf';conf.mkdir()
 text='''server.default_listen_address=127.0.0.1
server.bolt.enabled=true
server.bolt.listen_address=127.0.0.1:17687
server.http.enabled=true
server.http.listen_address=127.0.0.1:17474
server.https.enabled=false
dbms.security.auth_enabled=false
dbms.usage_report.enabled=false
server.memory.heap.initial_size=256m
server.memory.heap.max_size=512m
server.memory.pagecache.size=128m
server.jvm.additional=-XX:MaxDirectMemorySize=256m
server.jvm.additional=-XX:ActiveProcessorCount=2
'''
 for name in ('data','logs','run','import','plugins','transactions'):
  (root/name).mkdir();text+=f'server.directories.{name}={root/name}\n' if name not in {'transactions'} else ''
 (conf/'neo4j.conf').write_text(text)
 log=(root/'console.log').open('w');start=time.perf_counter()
 process=subprocess.Popen([str(home/'bin/neo4j'),'console'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'NEO4J_CONF':str(conf)})
 client=Neo4jHTTP()
 try:
  for _ in range(100):
   if process.poll() is not None:raise RuntimeError('Neo4j startup failed: '+(root/'console.log').read_text()[-2500:])
   try:client.execute('RETURN 1 AS ready');break
   except Exception:time.sleep(.2)
  else:raise TimeoutError('Neo4j startup timeout')
  yield client,process,(time.perf_counter()-start)*1000
 finally:
  process.terminate()
  try:process.wait(timeout=20)
  except subprocess.TimeoutExpired:process.kill();process.wait()
  log.close()

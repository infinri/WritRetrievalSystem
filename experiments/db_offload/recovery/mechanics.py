"""Actual native mechanics, ANN oracle, analyzer metadata and paired thin clients."""
import argparse,contextlib,copy,hashlib,json,os,random,subprocess,time
from pathlib import Path
import hnswlib,numpy as np
from experiments.db_offload.data import load,permitted,norm,fuse,render
from experiments.db_offload.adapters import Native,Flat
from experiments.db_offload.engine import neo4j_server,Neo4jHTTP
from experiments.db_offload.model import Model
from experiments.db_offload.workers import WorkerDB
@contextlib.contextmanager
def restart(home,root):
 log=(root/'restart.log').open('w');p=subprocess.Popen([str(home.resolve()/'bin/neo4j'),'console'],env={**os.environ,'NEO4J_CONF':str((root/'conf').resolve())},stdout=log,stderr=subprocess.STDOUT);db=Neo4jHTTP()
 try:
  for _ in range(300):
   if p.poll() is not None:raise RuntimeError('server restart failed')
   try:db.execute('RETURN 1 AS ready');break
   except Exception:time.sleep(.2)
  else:raise TimeoutError('restart readiness')
  yield db
 finally:
  p.terminate()
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.close()
def expect_error(call):
 try:call()
 except Exception:return
 raise AssertionError('expected failure was silently served')
def gates(n,c,task,s):
 u=sorted(permitted(c,task)[:8],key=lambda x:x['id']);v=norm(np.ones((8,384)));scope=n.prepare(u,v,[]);view=n.views[scope];rows=[]
 def check(name,call):
  try:call();rows.append({'gate':name,'status':'PASS'})
  except Exception as e:rows.append({'gate':name,'status':'FAIL','error':str(e),'kind':type(e).__name__})
 def fusion():
  lex,vec=n.lists(scope,'source',v[0],5,.3);out=n.search(scope,'source',v[0],5,.3);assert [r['uid'] for r in out]==[r['uid'] for r in fuse(lex,vec,5)]
 check('native fusion and deterministic qualified ordering',fusion)
 def generation():
  new=copy.deepcopy(u);new[0]['source_revision']='unpublished-new-revision';replacement=n.prepare(new,v,[]);assert replacement!=scope;n.search(replacement,'source',v[0]);n.search(scope,'source',v[0]);withdrawn=n.prepare(u[1:],v[1:],[]);assert all(r['uid']!=u[0]['id'] for r in n.search(withdrawn,'source',v[0]))
 check('revision replacement, withdrawal and prior-generation readability',generation)
 def foreign():
  f=[{**x,'project':'foreign','id':x['id'].replace('writ|','foreign|')} for x in u];assert permitted({'units':u+f},task)==u;before=n.search(scope,'source',v[0]);n.prepare(f,v,[]);assert n.search(scope,'source',v[0])==before
 check('foreign partition does not influence permitted FTS/vector hits',foreign)
 def manifest():
  n.execute('MATCH (p:BOPublished {scope:$s}) SET p.manifest="corrupt"',{'s':scope});expect_error(lambda:n.search(scope,'source',v[0]));n.execute('MATCH (p:BOPublished {scope:$s}) SET p.manifest=$m',{'s':scope,'m':json.dumps(view['manifest'],sort_keys=True)});n.search(scope,'source',v[0])
 check('manifest corruption fails closed with explicit recovery',manifest)
 def imports():
  for bad in ([u[0],u[0]],[{**u[0],'verification_status':'verified'}],[{**u[0],'approval_status':'approved'}]):expect_error(lambda:n.prepare(bad,v[:len(bad)],[]))
 check('duplicate identity and imported trust awards rejected',imports)
 def budget():
  out=render(task,n.search(scope,'source',v[0]),u,scope,s);assert out['bytes']<=s['budget_bytes'] and out['characters']<=s['budget_chars'];expect_error(lambda:render(task,[{'uid':u[0]['id']}],u,scope,{**s,'budget_bytes':800},conflicts=[(u[0]['id'],u[1]['id'])],required=[u[0]['id']]))
 check('whole required conflict bundle or budget error',budget)
 def cycle():
  edges=[{'a':u[a]['id'],'b':u[b]['id'],'a_digest':u[a]['content_digest'],'b_digest':u[b]['content_digest'],'source_uri':u[a]['source_uri'],'kind':k} for a,b,k in [(0,1,'CONTINUES'),(1,0,'REFERENCES'),(1,2,'IRRELEVANT')]];sc=n.prepare(u[:4],v[:4],edges);out=n.search(sc,'zxqnonword',v[0],1,.3,connected=True);assert {r['uid'] for r in out}=={u[0]['id'],u[1]['id']}
 check('cycle deduplication and irrelevant-edge exclusion',cycle)
 # Cypher maps remain literal in constructed query.
 def corrupt_payload():
  query='MATCH (n:'+view['label']+' {uid:$id}) SET n.payload=$p';n.execute(query,{'id':u[0]['id'],'p':'{}'});expect_error(lambda:n.search(scope,'source',v[0],8,-.99));n.execute(query,{'id':u[0]['id'],'p':json.dumps(u[0],sort_keys=True)})
 check('stored source revision/digest citation validation',corrupt_payload)
 def index_failure():n.execute('DROP INDEX '+view['vi']);expect_error(lambda:n.search(scope,'source',v[0]))
 check('missing native index cannot be reported fresh',index_failure)
 intact=n.prepare(u[2:],v[2:],[]);return rows,intact,n.views[intact],n.search(intact,'source',v[0]),v[0]
def pairs(kind,base,scope,view,tasks,q,a):
 workers={};rows=[];rng=random.Random(20261113)
 try:
  for language in ('python','rust'):
   w=WorkerDB(kind,a.work/'relate' if kind=='relate' else None,rust=a.rust if language=='rust' else None,ffi=a.ffi);r=Native(db=w,kind=kind,heavy=True);r.views[scope]=view;workers[language]=r
  for i in range(210):
   order=['python','rust'];rng.shuffle(order);timing={};ids={};task=tasks[i%4]
   for language in order:
    start=time.perf_counter();out=workers[language].search(scope,task['query'],q[i%4],20,.3);timing[language]=(time.perf_counter()-start)*1000;ids[language]=[r['uid'] for r in out]
   assert ids['python']==ids['rust']
   if i>=10:rows.append({'task':task['id'],'order':order,'ms':timing,'selected_ids':ids['python']})
 finally:
  for r in workers.values():r.close()
 return {'n_pairs':len(rows),'rows':rows,'p95_ms':{k:float(np.percentile([r['ms'][k] for r in rows],95)) for k in ('python','rust')},'parity':True,'note':'Query-only thin client stacks; same outer Python contracts; PyO3 versus C ABI and HTTP client differences remain; model/render excluded.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--neo4j-home',type=Path,required=True);p.add_argument('--rust',type=Path,required=True);p.add_argument('--ffi',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=False);c,t,s=load();tasks=[x for x in t if x['partition']=='development'];u=permitted(c,tasks[0]);m=Model(a.model_dir)
 try:v,_=m.encode([x['text'] for x in u]);q,_=m.encode([x['query'] for x in tasks])
 finally:m.close()
 result={'engines':{},'oracle_rows':[],'analyzers':[],'language':{},'not_established':['canonical live-memory projection','trusted shared publication','automatic required conflict construction','native canonical feedback/replay','storage-device faults','remote server','full cold CLI context recovery']}
 r=Native(a.work/'relate',heavy=True);rs=r.prepare(u,v,c['edges']);rv=r.views[rs]
 with neo4j_server(a.neo4j_home,a.work/'neo4j') as (db,_,startup):
  d=Native(db=db,kind='neo4j',heavy=True);ds=d.prepare(u,v,c['edges']);dv=d.views[ds]
  for kind,n in [('relate',r),('neo4j',d)]:
   checks,intact,view,expected,query=gates(n,c,tasks[0],s);meta=[]
   for query_text in ('CALL dbms.components()','SHOW INDEXES YIELD name,type,options RETURN name,type,options',"SHOW SETTINGS YIELD name,value WHERE name CONTAINS 'fulltext' RETURN name,value"):
    try:meta.append({'query':query_text,'rows':n.execute(query_text)})
    except Exception as e:meta.append({'query':query_text,'unsupported_or_error':str(e)})
   result['engines'][kind]={'checks':checks,'metadata':meta}
   if kind=='neo4j':restart_data=(intact,view,expected,query)
  h=hnswlib.Index(space='cosine',dim=384);h.init_index(max_elements=len(u),ef_construction=100,M=16,random_seed=20261113);h.add_items(v,np.arange(len(u)),num_threads=1);h.set_num_threads(1);flat=Flat();fs=flat.prepare(u,v,[])
  for text in ('approval','approved','owner-confirmed','revision AND digest','the source','D-035','source*'):
   result['analyzers'].append({'query':text,'lists':{name:n.lists(scope,text,q[0],20,2)[0] for name,n,scope in [('Tantivy',flat,fs),('Relate',r,rs),('Neo4j',d,ds)]}})
  for i,task in enumerate(tasks):
   exact=v@q[i];order=sorted(range(len(u)),key=lambda j:(-float(exact[j]),u[j]['id']));lookup={x['id']:j for j,x in enumerate(u)}
   for k in (5,10,20,50):
    gold=order[:k];threshold=float(exact[gold[-1]])
    for backend in ('Relate-exact','Neo4j-ANN','HNSW-ef20','HNSW-ef50','HNSW-ef100'):
     timings=[]
     for _ in range(3):
      start=time.perf_counter()
      if backend.startswith('HNSW'):
       h.set_ef(max(k,int(backend.split('ef')[1])));found,_=h.knn_query(q[i],k=k,num_threads=1);ids=[int(z) for z in found[0]]
      else:
       n,scope=(r,rs) if backend=='Relate-exact' else (d,ds);query_text="CALL db.index.vector.queryNodes('"+n.views[scope]['vi']+"',$k,$v) YIELD node,score RETURN node.uid AS uid,score";out=n.execute(query_text,{'k':k,'v':q[i].tolist()});ids=[lookup[z['uid']] for z in out]
      timings.append((time.perf_counter()-start)*1000)
     result['oracle_rows'].append({'task':task['id'],'backend':backend,'k':k,'strict_recall':len(set(ids)&set(gold))/k,'tie_aware_recall':sum(float(exact[j])>=threshold-1e-6 for j in ids)/k,'ms':timings,'expected':[u[j]['id'] for j in gold],'returned':[u[j]['id'] for j in ids]})
  r.close();result['language']['relate']=pairs('relate',r,rs,rv,tasks,q,a);result['language']['neo4j']=pairs('neo4j',d,ds,dv,tasks,q,a)
 start=time.perf_counter()
 with restart(a.neo4j_home,a.work/'neo4j') as db:
  sc,view,expected,query=restart_data;n=Native(db=db,kind='neo4j',heavy=True);n.views[sc]=view;out=n.search(sc,'source',query);ok=out==expected;result['engines']['neo4j']['checks'].append({'gate':'actual server restart returns exact persisted result','status':'PASS' if ok else 'FAIL'});result['engines']['neo4j']['restart_ms']=(time.perf_counter()-start)*1000
 (a.output/'mechanics.json').write_text(json.dumps(result,indent=2))
 if any(x['status']!='PASS' for e in result['engines'].values() for x in e['checks']):raise SystemExit('native gate failed')
if __name__=='__main__':main()

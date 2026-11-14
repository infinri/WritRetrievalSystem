"""A/B/C/D working candidate adapters; no production replacement or authority."""
import hashlib,json,re,time
from pathlib import Path
import numpy as np
import relate
from writ_retrieval.retrieval.keyword import KeywordIndex
from .data import digest,keywords,norm,fuse,neighbors

class Flat:
 kind='A'
 def __init__(self,path=None):self.views={};self.import_ms=0
 def prepare(self,units,vectors,edges):
  allowed_ids={u['id'] for u in units}
  usable=[e for e in edges if e['a'] in allowed_ids and e['b'] in allowed_ids and e['kind'] in {'CONTINUES','REFERENCES'}]
  scope=digest({'units':units,'edges':usable,'vectors':hashlib.sha256(np.asarray(vectors,dtype=np.float32).tobytes()).hexdigest()})[:20]
  if scope not in self.views:
   start=time.perf_counter();kw=KeywordIndex();kw.build([{'rule_id':u['id'],'trigger':'','statement':u['text'],'tags':''} for u in units]);self.views[scope]=(units,vectors,kw,edges);self.import_ms+=(time.perf_counter()-start)*1000
  return scope
 def lists(self,scope,q,vector,k,gate):
  units,matrix,kw,_=self.views[scope]
  lex=[{'uid':r['rule_id'],'score':r['score']} for r in kw.search(keywords(q),limit=max(1,len(units)))] if units else []
  lex.sort(key=lambda r:(-r['score'],r['uid']))
  similarities=matrix@np.asarray(vector,dtype=np.float32) if units else []
  vec=[{'uid':u['id'],'score':float(s)} for u,s in zip(units,similarities) if s>=gate];vec.sort(key=lambda r:(-r['score'],r['uid']))
  return lex[:k],vec[:k]
 def search(self,scope,q,vector,k=20,gate=.3,mode='hybrid',connected=False):
  lex,vec=self.lists(scope,q,vector,k,gate)
  ranked=lex if mode=='lexical' else vec if mode=='vector' else fuse(lex,vec,k)
  if connected and ranked:
   units,_,_,edges=self.views[scope];extra=neighbors([ranked[0]['uid']],units,edges)
   ranked=[ranked[0],*[{'uid':uid,'score':0,'connected':True} for uid in extra],*ranked[1:]]
   seen=set();ranked=[r for r in ranked if not (r['uid'] in seen or seen.add(r['uid']))]
  return ranked
 def close(self):pass

class Native:
 def __init__(self,path=None,*,db=None,heavy=False,kind='relate'):
  self.kind=kind;self.db=db or relate.connect(str(path));self.heavy=heavy;self.views={};self.import_ms=0;self.query_log=[]
 def execute(self,q,p=None):
  params=dict(p or {})
  for key in ('vector','rows'):
   if key in params:params[key]={'sha256':digest(params[key]),'length':len(params[key])}
  self.query_log.append({'query':q,'parameters':params})
  return [dict(r) for r in self.db.execute(q,p or {})]
 def prepare(self,units,vectors,edges):
  allowed_ids={u['id'] for u in units}
  usable=[e for e in edges if e['a'] in allowed_ids and e['b'] in allowed_ids and e['kind'] in {'CONTINUES','REFERENCES'}]
  scope=digest({'units':units,'edges':usable,'vectors':hashlib.sha256(np.asarray(vectors,dtype=np.float32).tobytes()).hexdigest()})[:20];label='BO_'+scope;vi='bv_'+scope;fi='bf_'+scope
  if scope in self.views:return scope
  start=time.perf_counter();ids={u['id']:u for u in units}
  # The partition is application-owned permitted-set materialization, not DB authorization.
  rows=[{'uid':u['id'],'text':u['text'],'embedding':list(map(float,v)),'payload':json.dumps(u,sort_keys=True),'scope':scope} for u,v in zip(units,vectors)]
  for offset in range(0,len(rows),128):self.execute(f'UNWIND $rows AS r CREATE (n:{label}) SET n += r',{'rows':rows[offset:offset+128]})
  selected=[{'a':e['a'],'b':e['b'],'scope':scope,'payload':json.dumps(e,sort_keys=True)} for e in edges if e['kind'] in {'CONTINUES','REFERENCES'} and e['a'] in ids and e['b'] in ids and e['a_digest']==ids[e['a']]['content_digest'] and e['b_digest']==ids[e['b']]['content_digest']]
  for offset in range(0,len(selected),128):self.execute(f'UNWIND $rows AS r MATCH (a:{label} {{uid:r.a}}),(b:{label} {{uid:r.b}}) CREATE (a)-[e:BO_LINK]->(b) SET e.scope=r.scope,e.payload=r.payload',{'rows':selected[offset:offset+128]})
  if self.kind=='relate':ddl=f'CREATE VECTOR INDEX {vi} FOR (n:{label}) ON n.embedding WITH [n.scope]'
  else:ddl=f"CREATE VECTOR INDEX {vi} FOR (n:{label}) ON (n.embedding) OPTIONS {{indexConfig: {{`vector.dimensions`:384,`vector.similarity_function`:'cosine',`vector.hnsw.m`:16,`vector.hnsw.ef_construction`:100,`vector.quantization.enabled`:false}}}}"
  self.execute(ddl);self.execute(f'CREATE FULLTEXT INDEX {fi} FOR (n:{label}) ON EACH [n.text]')
  if self.kind=='neo4j':self.execute('CALL db.awaitIndexes(120)')
  manifest={'scope':scope,'digest':digest(rows),'count':len(rows)}
  self.execute('CREATE (:BOPublished {scope:$scope,manifest:$manifest})',{'scope':scope,'manifest':json.dumps(manifest,sort_keys=True)})
  self.views[scope]={'units':units,'edges':edges,'label':label,'vi':vi,'fi':fi,'manifest':manifest};self.import_ms+=(time.perf_counter()-start)*1000
  return scope
 def _parts(self,scope):
  v=self.views[scope];l=v['label'];vi=v['vi'];fi=v['fi']
  # Retrieve the entire bounded partition before final deterministic ties. Relate
  # is exact; Neo4j ANN must overrequest all at tie-sensitive correctness profiles.
  # Cost is measured; raw top-k ANN curves are separate from this strict path.
  vector=f'CALL db.index.vector.queryNodes(\'{vi}\',$scan,$vector) YIELD node,score WITH node,2.0*score-1.0 AS score WHERE score >= $gate WITH node,score ORDER BY score DESC,node.uid ASC LIMIT $k'
  lexical=f"CALL db.index.fulltext.queryNodes('{fi}',$q) YIELD node,score WITH node,score ORDER BY score DESC,node.uid ASC LIMIT $k"
  return lexical,vector
 def _params(self,scope,q,vector,k,gate):return {'q':keywords(q),'vector':list(map(float,vector)),'k':k,'scan':max(1,len(self.views[scope]['units'])),'gate':gate}
 def lists(self,scope,q,vector,k,gate):
  if not self.views[scope]['units']:return [],[]
  lex,vec=self._parts(scope);p=self._params(scope,q,vector,k,gate)
  return self.execute(lex+' RETURN node.uid AS uid,score',p) if p['q'] else [],self.execute(vec+' RETURN node.uid AS uid,score',p)
 def search(self,scope,q,vector,k=20,gate=.3,mode='hybrid',connected=False):
  v=self.views[scope]
  stored=self.execute('MATCH (p:BOPublished {scope:$scope}) RETURN p.manifest AS manifest',{'scope':scope})
  if len(stored)!=1 or json.loads(stored[0]['manifest'])!=v['manifest']:raise ValueError('index generation manifest unavailable/corrupt')
  if not v['units']:return []
  if not self.heavy or mode!='hybrid':
   lex,vec=self.lists(scope,q,vector,k,gate);ranked=lex if mode=='lexical' else vec if mode=='vector' else fuse(lex,vec,k)
  else:
   lex,vec=self._parts(scope);p=self._params(scope,q,vector,k,gate)
   branches=[]
   for part in ([lex] if p['q'] else [])+[vec]:branches.append(part+' WITH collect(node.uid) AS ids UNWIND range(0,size(ids)-1) AS i RETURN ids[i] AS uid,1.0/(61+i) AS contribution')
   query='CALL { '+' UNION ALL '.join(branches)+' } RETURN uid,sum(contribution) AS score ORDER BY score DESC,uid ASC LIMIT $k'
   ranked=self.execute(query,p)
  allowed={u['id'] for u in v['units']}
  if any(r['uid'] not in allowed for r in ranked):raise ValueError('candidate escaped its visibility generation')
  if connected and ranked:
   if self.heavy:
    query=f'MATCH p=(a:{v["label"]} {{uid:$seed}})-[:BO_LINK*1..2]-(b:{v["label"]}) WHERE all(x IN nodes(p) WHERE x.scope=$scope) AND all(e IN relationships(p) WHERE e.scope=$scope) RETURN b.uid AS uid,min(length(p)) AS depth ORDER BY depth,uid ASC LIMIT 63'
    extras=[r['uid'] for r in self.execute(query,{'seed':ranked[0]['uid'],'scope':scope}) if r['uid']!=ranked[0]['uid']]
    oracle=set(neighbors([ranked[0]['uid']],v['units'],v['edges']))
    if not set(extras)<=oracle:raise ValueError('native graph returned an invisible or unbound bridge')
   else:extras=neighbors([ranked[0]['uid']],v['units'],v['edges'])
   seen={ranked[0]['uid']};out=[ranked[0]]
   for row in [*[{'uid':x,'score':0,'connected':True} for x in extras],*ranked[1:]]:
    if row['uid'] not in seen:out.append(row);seen.add(row['uid'])
   ranked=out
  # Exact payload binding validation catches corrupt/stale returned records.
  rows=self.execute(f'MATCH (n:{v["label"]}) WHERE n.uid IN $uids RETURN n.uid AS uid,n.payload AS payload',{'uids':[r['uid'] for r in ranked]}) if ranked else []
  actual={r['uid']:json.loads(r['payload']) for r in rows};expected={u['id']:u for u in v['units']}
  if len(actual)!=len(ranked) or any(actual.get(r['uid'])!=expected[r['uid']] for r in ranked):raise ValueError('stored citation revision/digest mismatch')
  return ranked
 def close(self):self.db.close()

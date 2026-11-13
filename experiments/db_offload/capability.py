"""Executable capability checks; documentation is not an engine equivalence claim."""
import argparse,hashlib,importlib.metadata,json,tempfile,time
from pathlib import Path
import relate
from .engine import neo4j_server


def probe(db,kind):
 rows=[]
 def run(name,query,params=None,expect=None):
  start=time.perf_counter()
  try:
   result=[dict(x) for x in db.execute(query,params or {})];error=None
  except Exception as e:result=None;error={'type':type(e).__name__,'message':str(e)[:1200]}
  item={'name':name,'query':query,'parameters':params or {},'rows':result,'error':error,'elapsed_ms':(time.perf_counter()-start)*1000}
  if expect:item['assertion']=bool(expect(result,error))
  rows.append(item);return result
 run('version','CALL dbms.components()')
 run('score_scale','RETURN vector.similarity.cosine([1.0,0.0],[0.0,1.0]) AS score',expect=lambda r,e:r and abs(r[0]['score']-.5)<1e-6)
 run('seed',"UNWIND range(1,30) AS i CREATE (:Capability {uid:'foreign-'+toString(i),scope:'foreign',text:'needle',embedding:[1.0,0.0]})")
 run('permitted',"CREATE (:Capability {uid:'allowed',scope:'app',text:'needle safe',embedding:[0.6,0.8]})")
 if kind=='relate':
  run('vector_index','CREATE VECTOR INDEX capability_v FOR (n:Capability) ON n.embedding WITH [n.scope]')
 else:
  run('vector_index',"CREATE VECTOR INDEX capability_v FOR (n:Capability) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`:2,`vector.similarity_function`:'cosine'}}")
 run('fulltext_index','CREATE FULLTEXT INDEX capability_f FOR (n:Capability) ON EACH [n.text]')
 if kind=='neo4j':run('await_indexes','CALL db.awaitIndexes(60)')
 run('global_then_filter_starves',"CALL db.index.vector.queryNodes('capability_v',5,[1.0,0.0]) YIELD node,score WHERE node.scope='app' RETURN node.uid AS uid",expect=lambda r,e:r==[])
 if kind=='relate':
  run('vector_prefilter',"MATCH (n:Capability) SEARCH n IN (VECTOR INDEX capability_v FOR [1.0,0.0] WHERE n.scope='app' LIMIT 5) SCORE AS s RETURN n.uid AS uid,s",expect=lambda r,e:r and r[0]['uid']=='allowed')
  run('fulltext_prefilter',"MATCH (n:Capability) SEARCH n IN (FULLTEXT INDEX capability_f FOR 'needle' WHERE n.scope='app' LIMIT 5) SCORE AS s RETURN n.uid AS uid,s",expect=lambda r,e:e is not None)
 run('fulltext','CALL db.index.fulltext.queryNodes("capability_f","needle") YIELD node,score RETURN node.uid AS uid,score ORDER BY score DESC,uid ASC')
 run('atomic_rollback_seed','CREATE (:RollbackProbe {uid:"not-committed"})')
 run('cypher_fusion',"CALL { MATCH (n:Capability) WHERE n.scope='app' RETURN n.uid AS uid,1.0/61 AS r UNION ALL MATCH (n:Capability) WHERE n.scope='app' RETURN n.uid AS uid,1.0/62 AS r } RETURN uid,sum(r) AS fused ORDER BY fused DESC,uid ASC",expect=lambda r,e:r and r[0]['uid']=='allowed')
 run('graph_seed',"MATCH (a:Capability {uid:'allowed'}),(b:Capability {uid:'foreign-1'}) CREATE (a)-[:REFERENCES]->(b)")
 run('graph_per_hop',"MATCH p=(a:Capability {uid:'allowed'})-[:REFERENCES*1..2]-(b:Capability) WHERE all(x IN nodes(p) WHERE x.scope='app') RETURN b.uid AS uid LIMIT 64",expect=lambda r,e:r==[])
 return {'kind':kind,'client_version':importlib.metadata.version('relate-db' if kind=='relate' else 'neo4j'),'checks':rows,'gates_pass':all(r.get('assertion',True) for r in rows),'note':'Unsupported fulltext prefilter is expected; partitions or application curation are necessary. This is not a complete adoption gate.'}


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--neo4j-home',type=Path);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as t:
  db=relate.connect(str(Path(t)/'relate'));result={'relate':probe(db,'relate')};db.close()
  if a.neo4j_home:
   with neo4j_server(a.neo4j_home,Path(t)/'neo4j') as (db,process,startup):result['neo4j']=probe(db,'neo4j');result['neo4j']['startup_ms']=startup
 a.output.write_text(json.dumps(result,indent=2)+'\n');print({k:v['gates_pass'] for k,v in result.items()})
if __name__=='__main__':main()

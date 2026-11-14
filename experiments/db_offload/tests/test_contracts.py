"""Native engine checks. Controlled vectors establish mechanics, never relevance."""
import copy,json
import numpy as np
import pytest
from experiments.db_offload.data import load,permitted,norm,render,score,digest
from experiments.db_offload.adapters import Native,Flat

@pytest.fixture
def inputs():
 c,t,s=load();u=permitted(c,t[0])[:8];return c,t[0],s,u,norm(np.ones((len(u),384)))

@pytest.mark.parametrize('heavy',[False,True])
def test_relates_candidates_fusion_and_restart(tmp_path,inputs,heavy):
 c,t,s,u,v=inputs;n=Native(tmp_path/'graph',heavy=heavy);scope=n.prepare(u,v,c['edges']);lex,vec=n.lists(scope,'source',v[0],5,.3)
 from experiments.db_offload.data import fuse
 actual=n.search(scope,'source',v[0],5,.3);assert [r['uid'] for r in actual]==[r['uid'] for r in fuse(lex,vec,5)]
 gen=n.views[scope];n.close();reopened=Native(tmp_path/'graph',heavy=heavy);reopened.views[scope]=gen
 assert reopened.search(scope,'source',v[0],5,.3)==actual;reopened.close()

def test_scope_before_limit_and_hidden_index_influence(tmp_path,inputs):
 c,t,s,u,v=inputs;foreign=[{**x,'project':'foreign','id':x['id'].replace('writ|','foreign|')} for x in u]
 assert all(x not in permitted({**c,'units':u+foreign},t) for x in foreign)
 n=Native(tmp_path/'graph');scope=n.prepare(u,v,c['edges']);a=n.search(scope,'source',v[0],2,.3)
 allowed=permitted({**c,'units':u+foreign},t);scope2=n.prepare(allowed,v,c['edges']);b=n.search(scope2,'source',v[0],2,.3)
 assert scope==scope2 and a==b
 n.close()

def test_retraction_expiry_history_and_no_future_documents(tmp_path,inputs):
 c,t,s,u,v=inputs
 _,tasks,_=load()
 for task in tasks:
  allowed=permitted(c,task)
  assert all(x['recorded_at']<=task['as_of'] and x['project']==task['project'] for x in allowed)
  if task['withdraw_source']:assert all(x['source_id']!=task['withdraw_source'] for x in allowed)
 n=Native(tmp_path/'graph');old=n.prepare(u,v,c['edges']);new=n.prepare(u[1:],v[1:],c['edges'])
 assert new!=old and all(r['uid']!=u[0]['id'] for r in n.search(new,'source',v[0],5,.3));n.close()

def test_manifest_index_and_payload_failures_fail_closed(tmp_path,inputs):
 c,t,s,u,v=inputs;n=Native(tmp_path/'graph');scope=n.prepare(u,v,c['edges']);view=n.views[scope]
 n.execute('MATCH (p:BOPublished {scope:$scope}) SET p.manifest="corrupt"',{'scope':scope})
 with pytest.raises(ValueError,match='manifest'):n.search(scope,'source',v[0])
 n.execute('MATCH (p:BOPublished {scope:$scope}) SET p.manifest=$value',{'scope':scope,'value':json.dumps(view['manifest'],sort_keys=True)})
 n.execute('DROP INDEX '+view['vi'])
 with pytest.raises(Exception):n.search(scope,'source',v[0])
 n.close()

def test_qualified_duplicate_import_status_and_payload_citation_checks(tmp_path,inputs):
 c,t,s,u,v=inputs;n=Native(tmp_path/'graph')
 with pytest.raises(ValueError,match='duplicate'):n.prepare([u[0],u[0]],v[:2],[])
 with pytest.raises(ValueError,match='award'):n.prepare([{**u[0],'verification_status':'verified'}],v[:1],[])
 with pytest.raises(ValueError,match='award'):n.prepare([{**u[0],'approval_status':'approved'}],v[:1],[])
 scope=n.prepare(u[:1],v[:1],[]);n.execute(f'MATCH (n:{n.views[scope]["label"]}) SET n.payload="{{}}"')
 with pytest.raises(ValueError,match='citation'):n.search(scope,'source',v[0]);n.close()

def test_full_required_conflict_bundles_byte_limits_and_answer_clause_delivery(inputs):
 c,t,s,u,v=inputs;settings={**s,'budget_bytes':1200,'budget_chars':1200}
 with pytest.raises(ValueError,match='BUDGET_REQUIRED_BUNDLE'):render(t,[{'uid':u[0]['id']}],u,'g',settings,conflicts=[(u[0]['id'],u[1]['id'])],required=[u[0]['id']])
 full=render(t,[{'uid':u[0]['id']}],u,'g',s)
 assert full['bytes']<=s['budget_bytes'] and full['characters']<=s['budget_chars']
 wrong={**t,'gold':[{'source_uri':u[0]['source_uri'],'source_revision':u[0]['source_revision'],'source_digest':u[0]['source_digest'],'answer_text':'missing actual answer clause'}]}
 assert score(wrong,full)['delivered_clauses']==0
 assert full==render(t,[{'uid':u[0]['id']}],u,'g',s)

def test_native_cycles_foreign_bridges_and_irrelevant_edges(tmp_path,inputs):
 c,t,s,u,v=inputs;u=u[:4];v=v[:4]
 edges=[{'a':a['id'],'b':b['id'],'kind':kind,'source_uri':a['source_uri'],'a_digest':a['content_digest'],'b_digest':b['content_digest']} for a,b,kind in [(u[0],u[1],'CONTINUES'),(u[1],u[0],'REFERENCES'),(u[1],u[2],'IRRELEVANT')]]
 n=Native(tmp_path/'graph',heavy=True);scope=n.prepare(u,v,edges)
 ranked=n.search(scope,'nonsense',v[0],1,.3,connected=True)
 assert len({r['uid'] for r in ranked})==len(ranked) and len(ranked)<=64;n.close()

def test_real_relate_rollback(tmp_path):
 import relate
 db=relate.connect(str(tmp_path/'graph'));db.autocommit=False;db.execute('CREATE (:Test {id:"rollback"})');db.rollback();db.autocommit=True
 assert not list(db.execute('MATCH (n:Test) RETURN n'));db.close()

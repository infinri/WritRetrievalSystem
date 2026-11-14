"""Opt-in profile gates using real persistent Relate stores and native indexes."""
import copy,json,subprocess,sys
from pathlib import Path
import pytest
from writ_retrieval.reliable.store import ReliableStore,Key
from writ_retrieval.reliable.grounded import GroundedSession
from writ_retrieval.reliable.budget import Budget
from writ_retrieval.reliable.contracts import digest,text_digest
from tests.fixtures.controlled import ControlledEncoder
from tests.test_reliable_context import claim,evidence,AT,setup_feedback,simulate_owner_confirmation

@pytest.fixture
def store(tmp_path):
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as s:yield s

def make(store,tmp_path,backend='relate',encoder=None):
    return GroundedSession(store,encoder or ControlledEncoder(),encoder_id='controlled/1',cache_dir=tmp_path/'cache',backend=backend)

def payload(result):
    assert result.get('error') is None,result
    return json.loads(result['payload'])

@pytest.mark.parametrize('backend',['flat','relate'])
def test_complete_text_required_conflict_and_exact_budget(store,tmp_path,backend):
    body='sql '+('猫 unicode provenance '*55)+' the answer is at the end.'
    store.add_claim(claim('left',body));store.add_claim(claim('right','sql contrary proposition'))
    left,right=[store.bind(Key('app','Claim',x).as_dict()) for x in ('left','right')]
    store.declare_conflict(left=left,right=right,source_refs=['fixture:conflict'],note='Unresolved local record; not a public-project fact.')
    with make(store,tmp_path,backend) as s:
        r=s.context('sql',project='app',arm='lexical',budget=Budget(18000,18000),required=[Key.parse(left['ref']).token]);p=payload(r)
        assert len(p['items'])==2 and all(x['unresolved_conflicts'] for x in p['items'])
        assert any(body in x['text'] and x['text_omitted_characters']==0 for x in p['items'])
        assert all(text_digest(x['text'])==x['rendered_text_digest'] for x in p['items'])
        size=len(r['payload'].encode());chars=len(r['payload'])
        tight=s.context('sql',project='app',arm='lexical',budget=Budget(size,chars),required=[Key.parse(left['ref']).token])
        assert tight['payload']==r['payload']
        assert s.context('sql',project='app',budget=Budget(size-1,chars),required=[Key.parse(left['ref']).token])['error']['kind']=='BudgetError'


def test_native_reopen_uses_durable_indexes_without_corpus_encoding(store,tmp_path):
    store.add_claim(claim());model=ControlledEncoder()
    with make(store,tmp_path,encoder=model) as s:
        first=s.context('sql',project='app',arm='lexical');payload(first)
    pointer=next((tmp_path/'cache').rglob('GROUNDED-CURRENT.json')).read_bytes()
    store.close()
    with ReliableStore(tmp_path/'graph',clock=lambda:AT) as reopened:
        model=ControlledEncoder()
        with make(reopened,tmp_path,encoder=model) as s:
            second=s.context('sql',project='app',arm='lexical');assert second['payload']==first['payload']
            assert model.batches==0
            assert next((tmp_path/'cache').rglob('GROUNDED-CURRENT.json')).read_bytes()==pointer
            projection=next(iter(s._indexes.values()))
            with pytest.raises(Exception):list(projection.db.execute('CREATE (:ForbiddenWrite)'))  # real engine refuses

@pytest.mark.parametrize('backend',['flat','relate'])
def test_revision_retraction_replay_and_expiry_refresh(store,tmp_path,backend,monkeypatch):
    rule,signals=setup_feedback(store);simulate_owner_confirmation(store,monkeypatch)
    store.feedback_bound(project='app',batch_id='bound',signals=signals)
    with make(store,tmp_path,backend) as s:
        before=payload(s.context('sql',project='app',budget=Budget(20000,20000)))
        assert any(x.get('ranking_metadata',{}).get('positive')==1 for x in before['items'])
        store.retract_evidence(ref=Key('app','Evidence','outcome').as_dict(),expected_revision=1,request_id='withdraw',reason='local owner withdrew report')
        store.feedback_bound(project='app',batch_id='bound',signals=signals)
        after=payload(s.context('sql',project='app',budget=Budget(20000,20000)))
        assert before['snapshot']['generation']!=after['snapshot']['generation']
        assert any(x.get('ranking_metadata',{}).get('positive')==0 for x in after['items'])
        assert not any(x['lifecycle']=='retracted' for x in after['items'])
        history=payload(s.context('sql',project='app',request={'include_history':True},budget=Budget(20000,20000)))
        assert any(x['lifecycle']=='retracted' and not x['active_support'] for x in history['items'] if x['ref']['label']=='Evidence')
        previous=next((tmp_path/'cache').rglob('GROUNDED-CURRENT.json'))
        assert json.loads(previous.read_text())['previous']['generation']==before['snapshot']['generation']
        old=store.get(rule['ref']);store.revise_proposal(rule['ref'],{'statement':'sql changed wording'},expected_claim_hash=old['claim_hash'])
        changed=store.get(rule['ref']);store.revise_proposal(rule['ref'],{'statement':old['statement']},expected_claim_hash=changed['claim_hash'])
        store.feedback_bound(project='app',batch_id='bound',signals=signals)
        restored=payload(s.context('sql',project='app',budget=Budget(20000,20000)))
        assert any(x.get('ranking_metadata',{}).get('positive')==0 for x in restored['items'])
        assert store.get(rule['ref'])['revision']>rule['revision']
        store.add_claim(claim('expires','sql expiry',valid_to='2026-11-13T19:00:00Z'))
        active=payload(s.context('sql expiry',project='app',arm='lexical',budget=Budget(20000,20000)))
        store.clock=lambda:'2026-11-13T20:00:00Z'
        expired=payload(s.context('sql expiry',project='app',arm='lexical',budget=Budget(20000,20000)))
        assert active['snapshot']['generation']!=expired['snapshot']['generation']
        assert not any(x['ref']['id']=='expires' for x in expired['items'])

@pytest.mark.parametrize('backend',['flat','relate'])
def test_explicit_evidence_requirement_missing_obsolete_and_imported_verification(store,tmp_path,backend):
    store.add_claim(claim());ref=Key('app','Claim','one').as_dict();store.add_evidence(evidence(store,'unverified',ref))
    with make(store,tmp_path,backend) as s:
        request={'source':{'uri':'fixture:one','revision':'1'},'verification':'owner_confirmed'}
        unknown=payload(s.context('sql',project='app',request=request))
        assert unknown['evidence_assessment']['status']=='insufficient' and unknown['abstained']
        generic=payload(s.context('sql',project='app'))
        assert generic['evidence_assessment']['status']=='unassessed' and not generic['abstained']
        bound=store.bind(ref)
        exact=payload(s.context('unrelated words',project='app',arm='lexical',request={'binding':bound}))
        assert exact['evidence_assessment']['status']=='requirements_satisfied'
        store.add_claim(claim('next','sql newer'),supersedes=bound)
        stale=payload(s.context('sql',project='app',request={'binding':bound,'include_history':True}))
        assert stale['evidence_assessment']['status']=='insufficient'
        assert s.context('sql',project=None)['error']['kind']=='ValueError'
        with pytest.raises(ValueError):store.add_evidence({**evidence(store,'forged',Key('app','Claim','next').as_dict()),'verification_status':'owner_confirmed'})


def test_hidden_records_do_not_starve_or_influence_native_scope(store,tmp_path):
    store.add_claim(claim('target','sql rare local passage'))
    with make(store,tmp_path) as s:
        first=s.context('sql rare',project='app',arm='lexical');a=payload(first)
        for i in range(35):store.add_claim(claim(str(i),'sql rare sql rare foreign',project='foreign'))
        second=s.context('sql rare',project='app',arm='lexical');b=payload(second)
        assert first['diagnostics']['candidate_ids']==second['diagnostics']['candidate_ids']
        assert a['items']==b['items'] and b['projection']['permitted_rows']==1
        assert 'foreign' not in second['payload']
        assert payload(s.context('sql',project='unrelated'))['abstained']


def test_failures_and_corruption_never_publish_mixed_projection(store,tmp_path,monkeypatch):
    store.add_claim(claim())
    with make(store,tmp_path) as s:
        first=payload(s.context('sql',project='app'))
        pointer=next((tmp_path/'cache').rglob('GROUNDED-CURRENT.json'));old=pointer.read_bytes()
        store.add_claim(claim('two','sql next'))
        import writ_retrieval.reliable.grounded as module
        with monkeypatch.context() as m:
            m.setattr(module,'RelateProjection',lambda *a,**k:(_ for _ in ()).throw(OSError('injected index build failure')))
            failure=s.context('sql',project='app')
            assert failure['payload'] is None and pointer.read_bytes()==old
        good=payload(s.context('sql',project='app'));new=pointer.read_bytes()
        assert good['snapshot']['revision']==store.current_revision() and new!=old
        current=s.current['projection'];path=s.current['root']/current['path']/'index.relate'
        victim=next(path.rglob('*.parquet'));victim.write_bytes(victim.read_bytes()+b'corrupt')
        failure=s.context('sql',project='app')
        assert failure['payload'] is None and 'digest mismatch' in failure['error']['message'] and pointer.read_bytes()==new
        assert json.loads(new)['previous']['generation']==first['snapshot']['generation']
        from writ_retrieval.reliable.projection import quarantine_projection
        identity=s.current['projection']['identity'];s.close()
        receipt=quarantine_projection(store,tmp_path/'cache',identity)
        assert Path(receipt['quarantined_path']).exists()
        with make(store,tmp_path) as fresh:
            repaired=payload(fresh.context('sql',project='app'))
            assert repaired['snapshot']['generation']==good['snapshot']['generation']
            assert repaired['projection']['identity']==identity


def test_foreign_bridges_cycles_and_enrichment_follow_ranked_records(store,tmp_path):
    for i,p in [('a','app'),('b','app'),('a','foreign')]:store.add_claim(claim(i,'sql '+i,project=p))
    a,b,f=[Key(p,'Claim',i) for i,p in [('a','app'),('b','app'),('a','foreign')]]
    with store.transaction():
        store._bound_edge(a,'CONTRADICTS',b,sources=['fixture:cycle']);store._bound_edge(b,'CONTRADICTS',a,sources=['fixture:cycle'])
        store._bound_edge(a,'CONTRADICTS',f,sources=['fixture:foreign']);store._bound_edge(a,'UNRELATED',b,sources=['fixture:irrelevant'])
    with make(store,tmp_path) as s:
        r=s.context('sql',project='app',arm='connected',budget=Budget(12000,12000));p=payload(r)
        assert 'foreign' not in r['payload'] and r['diagnostics']['graph']['visited']<=64
        assert len({x['id'] for x in p['items']})==len(p['items'])
        ranked=r['diagnostics']['candidate_ids'];delivered=[x['id'] for x in p['items']]
        assert delivered[:len(ranked)]==ranked


def test_public_passage_import_is_closed_idempotent_and_source_bound(store):
    from writ_retrieval.reliable.passages import ingest_passages
    import hashlib
    text='sql public repository statement; successful verification and owner approval remain unknown.'
    path='docs/example.md';revision='a'*40;start=10;ident=hashlib.sha256((path+'\0'+str(start)+'\0'+text).encode()).hexdigest()[:24]
    item={'id':ident,'path':path,'heading':'Example','text':text,'start':start,'end':start+len(text),'start_line':2,'end_line':2,
        'revision':revision,'committed_at':'2026-01-01T00:00:00Z','source_digest':'b'*64,'content_digest':text_digest(text),'uri':f'https://github.com/infinri/Writ/blob/{revision}/{path}#L2'}
    document={'contract_version':'writ-passage-import/1','repository':'https://github.com/infinri/Writ','revision':revision,'recorded_at':'2026-01-01T00:00:00Z','documents':[item],'paths':[path],'unknowns':'unknown'}
    assert not ingest_passages(store,document,project='app')['replayed'];rev=store.current_revision()
    assert ingest_passages(store,document,project='app')['replayed'] and store.current_revision()==rev
    assert store.get(Key('app','Claim',revision+':'+ident))['verification_status']=='unverified'
    bad=copy.deepcopy(document);bad['documents'][0]['verification_status']='owner_confirmed'
    with pytest.raises(ValueError):ingest_passages(store,bad,project='app')
    assert store.current_revision()==rev


def test_native_vector_lists_match_exact_oracle_and_types_do_not_collide(store,tmp_path):
    import numpy as np
    for i,body in [('same','sql database'),('b','sql parameterized'),('c','python async')]:store.add_claim(claim(i,body))
    store.capture([{'label':'Memory','data':{'project':'app','ts':'2026-01-01T00:00:00Z','source_refs':['fixture:memory'],'name':'same','description':'sql blocking'}}])
    with make(store,tmp_path) as s:
        p=payload(s.context('sql',project='app',arm='vector',budget=Budget(16000,16000)))
        ids={x['id'] for x in p['items']}
        assert Key('app','Claim','same').token in ids and Key('app','Memory','same').token in ids
        native=next(iter(s._indexes.values()));query=s._encode(['sql'])[0]
        lex,vec=native.lists('sql',query,k=2,gate=.3,mode='vector')
        exact=sorted([{'uid':r['uid'],'score':float(np.dot(r['embedding'],query))} for r in native.expected.values() if np.dot(r['embedding'],query)>=.3],key=lambda x:(-x['score'],x['uid']))[:2]
        assert [r['uid'] for r in vec]==[r['uid'] for r in exact] and lex==[]
        assert np.allclose([r['score'] for r in vec],[r['score'] for r in exact],atol=1e-6)


def test_publication_and_canonical_read_faults_preserve_prior_pointer(store,tmp_path,monkeypatch):
    store.add_claim(claim())
    with make(store,tmp_path) as s:
        payload(s.context('sql',project='app'));pointer=next((tmp_path/'cache').rglob('GROUNDED-CURRENT.json'));old=pointer.read_bytes()
        store.add_claim(claim('replacement','sql new generation'))
        import writ_retrieval.reliable.grounded as module
        with monkeypatch.context() as m:
            m.setattr(module,'write_atomic',lambda *a:(_ for _ in ()).throw(OSError('injected publication failure')))
            assert s.context('sql',project='app')['payload'] is None and pointer.read_bytes()==old
        with monkeypatch.context() as m:
            m.setattr(store,'export',lambda:(_ for _ in ()).throw(OSError('injected canonical read failure')))
            assert s.context('sql',project='app')['payload'] is None and pointer.read_bytes()==old
        new=payload(s.context('sql',project='app'));assert new['snapshot']['revision']==store.current_revision() and pointer.read_bytes()!=old


def test_native_restart_in_separate_process_and_owner_cli_boundary(store,tmp_path):
    store.add_claim(claim());store.close()
    code='''import json,sys
from pathlib import Path
from writ_retrieval.reliable.store import ReliableStore
from writ_retrieval.reliable.grounded import GroundedSession
from tests.fixtures.controlled import ControlledEncoder
p=Path(sys.argv[1]);encoder=ControlledEncoder()
with ReliableStore(p/'graph',clock=lambda:'2026-11-13T18:00:00Z') as store,GroundedSession(store,encoder,encoder_id='process/1',cache_dir=p/'process-cache',backend='relate') as s:
 r=s.context('sql',project='app',arm='lexical')
 if not r.get('payload'):raise RuntimeError(r)
 print(json.dumps({'result':r,'batches':encoder.batches}))
'''
    a=json.loads(subprocess.check_output([sys.executable,'-c',code,str(tmp_path)],text=True));b=json.loads(subprocess.check_output([sys.executable,'-c',code,str(tmp_path)],text=True))
    assert a['result']['payload']==b['result']['payload'] and a['batches']>0 and b['batches']==0
    result=subprocess.run([sys.executable,'-m','writ_retrieval.reliable.grounded_cli','--help'],capture_output=True,text=True)
    assert result.returncode==0 and 'confirm' not in result.stdout and 'passage-ingest' not in result.stdout


def test_mandatory_delivery_does_not_satisfy_missing_evidence(store,tmp_path):
    # Proposal contract deliberately does not allow arbitrary mandatory status;
    # imported doctrine fixture remains a separate preexisting publication path.
    with store.transaction():
        store._set(Key('writ','Rule','MANDATORY'),{'project':'writ','rule_id':'MANDATORY','mandatory':True,'statement':'sql required context','revision':1,'status':'live'})
    with make(store,tmp_path) as s:
        r=s.context('sql',project='app',request={'source':{'uri':'fixture:missing','revision':'1'}});p=payload(r)
        assert not p['abstained'] and p['ranked_abstained'] and p['evidence_assessment']['status']=='insufficient'
        assert len(p['items'])==1 and p['items'][0]['channel']=='guidance'
        assert len(r['payload'].encode())<=8000
        small=s.context('sql',project='app',budget=Budget(1200,1200))
        assert small['error']['kind']=='BudgetError'

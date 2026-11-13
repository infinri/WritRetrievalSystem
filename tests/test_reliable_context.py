"""Versioned context and use-time evidence on the actual persistent Relate engine."""
import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from writ_retrieval.reliable.contracts import Source, Claim, Evidence, canonical, digest, text_digest, binding_matches
from writ_retrieval.reliable.store import ReliableStore, Key, active_counts
from writ_retrieval.reliable.session import ReliableSession
from writ_retrieval.reliable.budget import Budget
from writ_retrieval.reliable.ingest import ingest_history, claim_key
from tests.fixtures.controlled import ControlledEncoder
from tests.test_memory_workflow import proposal, history, ref

AT='2026-11-13T18:00:00Z'


def claim(ident='one',text='sql use parameters',project='app',**extra):
    return dict(project=project,claim_id=ident,topic='sql-policy',title='sql policy',text=text,
        content_digest=text_digest(text),source={'uri':'fixture:'+ident,'revision':'1'},kind='repository_assertion',recorded_at='2026-01-01T00:00:00Z',**extra)


def evidence(store,ident,subject,**extra):
    return dict(project='app',evidence_id=ident,subject=store.bind(subject),source={'uri':'fixture:'+ident,'revision':'1'},
        material='observed sql result',content_digest=text_digest('observed sql result'),kind='repository_assertion',recorded_at='2026-01-02T00:00:00Z',**extra)


@pytest.fixture
def store(tmp_path):
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as db: yield db


def session(store,tmp_path,encoder=None):
    return ReliableSession(store,encoder or ControlledEncoder(),encoder_id='controlled-fixture/1',cache_dir=tmp_path/'index')


def test_closed_contracts_calendar_revision_source_and_digest():
    with pytest.raises(ValueError): Claim(**{**claim(),'recorded_at':'2026-02-30T00:00:00Z'})
    with pytest.raises(ValueError): Claim(**{**claim(),'content_digest':text_digest('different')})
    with pytest.raises(ValueError): Claim(**{**claim(),'verification_status':'verified'})
    with pytest.raises(ValueError): Claim(**claim(valid_from='2026-02-01T00:00:00Z',valid_to='2026-01-01T00:00:00Z'))
    with pytest.raises(ValueError): Source(uri='https://github.com/infinri/Writ/commit/'+'a'*40,revision='b'*40)
    with pytest.raises(ValueError): Source(uri='file:x',revision='1',committed_at='2026-01-01')


def test_atomic_idempotent_import_and_document_history(store):
    history=json.loads(Path('examples/phase3/train-history.json').read_text())
    first=ingest_history(store,history);revision=store.current_revision()
    assert not first['replayed'] and ingest_history(store,history)['replayed']
    assert store.current_revision()==revision
    export=store.export()
    assert len([k for k in export['nodes'] if k.label=='Claim'])==47
    changed={c['revision']:set(c['paths']) for c in history['commits']}
    assert all(n['path'] in changed[n['commit_hash']] for k,n in export['nodes'].items() if k.label=='FileChange')
    assert any(n['status']=='superseded' for k,n in export['nodes'].items() if k.label=='Claim')
    for k,n in export['nodes'].items():
        if k.label=='Commit': assert n['approval_status']==n['outcome_status']=='unknown' and n.get('rationale') is None
    damaged=copy.deepcopy(history);damaged['documents'][0]['verification_status']='verified';damaged['end']='a'*40
    before=store.current_revision()
    with pytest.raises(ValueError): ingest_history(store,damaged)
    assert store.current_revision()==before
    assert len(store.export()['nodes'])==len(export['nodes'])


def test_snapshot_replacement_is_atomic_failed_build_and_render_keep_previous(store,tmp_path,monkeypatch):
    store.add_claim(claim());s=session(store,tmp_path)
    first=s.context('sql',project='app',arm='lexical');assert first['payload']
    pointer=next((tmp_path/'index').rglob('CURRENT.json'));saved=pointer.read_bytes();old=s.current
    store.add_claim(claim('two','sql async next revision'))
    with monkeypatch.context() as m:
        m.setattr(s,'_encode',lambda *a:(_ for _ in ()).throw(RuntimeError('encoder unavailable')))
        failure=s.context('sql',project='app')
        assert failure['payload'] is None and pointer.read_bytes()==saved and s.current is old
    too_small=s.context('sql',project='app',budget=Budget(10,10))
    assert too_small['error']['kind']=='BudgetError' and pointer.read_bytes()==saved
    second=s.context('sql',project='app',arm='lexical')
    assert json.loads(second['payload'])['snapshot']['revision']==store.current_revision()
    pointer_data=json.loads(pointer.read_text());assert pointer_data['previous']==old['id'] and s.previous is old
    assert len(list(pointer.parent.glob('*/snapshot.json')))>=2
    # A corrupted replacement is not served. Old complete artifacts are still recoverable.
    (s.current['path']/'vectors.npy').write_bytes(b'broken')
    assert s.context('sql',project='app')['error']['kind']=='ValueError'
    assert pointer.read_bytes()!=saved and s.previous['path'].exists()


def test_expiry_retraction_supersession_delete_and_restart_change_context(store,tmp_path):
    store.add_claim(claim(valid_to='2026-11-13T19:00:00Z'));key=Key('app','Claim','one')
    store.add_evidence(evidence(store,'proof',key.as_dict()))
    s=session(store,tmp_path);first=s.context('sql',project='app',budget=Budget(12000,12000))
    before=json.loads(first['payload']);assert any(i.get('active_support') for i in before['items'])
    store.retract_evidence(ref=Key('app','Evidence','proof').as_dict(),expected_revision=1,request_id='correction',reason='incorrect source association')
    store.close()
    with ReliableStore(tmp_path/'graph',clock=lambda:AT) as reopened:
        fresh=session(reopened,tmp_path).context('sql',project='app',budget=Budget(12000,12000))
        after=json.loads(fresh['payload']);assert after['snapshot']['generation']!=before['snapshot']['generation']
        assert any(i['lifecycle']=='retracted' and not i['active_support'] for i in after['items'] if i['ref']['label']=='Evidence')
        old=reopened.bind(key.as_dict());reopened.add_claim(claim('new','sql current policy'),supersedes=old)
        current=json.loads(session(reopened,tmp_path).context('sql',project='app',budget=Budget(16000,16000))['payload'])
        assert any(i['lifecycle']=='historical' and not i['current_guidance'] for i in current['items'])
        reopened.clock=lambda:'2026-11-13T20:00:00Z'
        final=json.loads(session(reopened,tmp_path).context('sql',project='app')['payload'])
        assert not any(i['id']==key.token and i['lifecycle']=='current' for i in final['items'])


def setup_feedback(store):
    store.propose(proposal())
    items=history()
    for item in items: item['data']['ts']+='T00:00:00Z'
    store.capture(items)
    store.add_evidence(evidence(store,'outcome',ref('Outcome','O')))
    rule=store.bind(ref('Rule','SQL-001','writ'))
    signals=[{'rule':rule,'evidence_ref':ref('Evidence','outcome'),'signal':'positive'}]
    return rule,signals


def simulate_owner_confirmation(store,monkeypatch):
    refs=[ref('Evidence','outcome')];token=digest([store.bind(r) for r in refs])
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True);monkeypatch.setattr(sys.stdout,'isatty',lambda:True)
    monkeypatch.setattr('builtins.input',lambda _: 'confirm '+token)
    return store.confirm_evidence(refs)


def test_feedback_classes_retraction_old_replay_restart_and_obsolete_claim(store,tmp_path,monkeypatch):
    rule,signals=setup_feedback(store)
    store.feedback_bound(project='app',batch_id='batch',signals=signals)
    assert store.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==0  # imported assertion cannot verify itself
    with pytest.raises(PermissionError): store.confirm_evidence([ref('Evidence','outcome')])
    assert not simulate_owner_confirmation(store,monkeypatch)['rule_approval_granted']
    node=store.get(ref('Rule','SQL-001','writ'));assert node['times_seen_positive']==1 and node['authority']=='ai-provisional'
    generation=session(store,tmp_path).context('sql',project='app')['payload']
    assert json.loads(generation)['items'][0]['ranking_metadata']['positive']==1
    store.retract_evidence(ref=ref('Evidence','outcome'),expected_revision=1,request_id='retract',reason='owner withdraws the report')
    store.feedback_bound(project='app',batch_id='batch',signals=signals)
    assert store.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==0
    assert store.retract_evidence(ref=ref('Evidence','outcome'),expected_revision=1,request_id='retract',reason='owner withdraws the report')['replayed']
    store.revise_proposal(ref('Rule','SQL-001','writ'),{'statement':'Use sql transactions'},expected_claim_hash=node['claim_hash'])
    store.close()
    with ReliableStore(tmp_path/'graph',clock=lambda:AT) as reopened:
        reopened.feedback_bound(project='app',batch_id='batch',signals=signals)
        assert reopened.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==0
        assert len([k for k in reopened.export()['nodes'] if k.label=='BoundObservation'])==1
        with pytest.raises(ValueError): reopened.feedback_bound(project='app',batch_id='new-batch',signals=signals)


def test_utf8_required_conflicts_and_determinism(store,tmp_path):
    store.add_claim(claim('left','sql use async '+('猫'*900)))
    store.add_claim(claim('right','sql use blocking sync'))
    left,right=[store.bind(ref('Claim',i)) for i in ('left','right')]
    store.declare_conflict(left=left,right=right,source_refs=['fixture:review'],note='These are explicitly contradictory synthetic claims; unresolved.')
    s=session(store,tmp_path);budget=Budget(12000,10000)
    a=s.context('sql',project='app',arm='lexical',budget=budget,required=[Key.parse(left['ref']).token])
    b=s.context('sql',project='app',arm='lexical',budget=budget,required=[Key.parse(left['ref']).token])
    assert a['payload']==b['payload'];assert len(a['payload'].encode())<=12000 and len(a['payload'])<=10000
    assert all(i['unresolved_conflicts'] for i in json.loads(a['payload'])['items'])
    for limit in (1000,2000,3000):
        failure=s.context('sql',project='app',budget=Budget(limit,limit),required=[Key.parse(left['ref']).token])
        assert failure['payload'] is None and failure['error']['kind']=='BudgetError'


def test_duplicate_types_private_bridges_cycles_irrelevant_edges_and_fair_pool(store,tmp_path):
    for ident,project in [('a','app'),('b','app'),('a','foreign')]: store.add_claim(claim(ident,'sql '+project,project=project))
    store.capture([{'label':'Memory','data':{'project':'app','ts':'2026-01-01T00:00:00Z','source_refs':['fixture:memory'],'name':'a','description':'sql memory'}}])
    a,b,foreign=Key('app','Claim','a'),Key('app','Claim','b'),Key('foreign','Claim','a')
    with store.transaction():
        store._bound_edge(a,'CONTRADICTS',b,sources=['fixture:cycle']);store._bound_edge(b,'CONTRADICTS',a,sources=['fixture:cycle'])
        store._bound_edge(a,'CONTRADICTS',foreign,sources=['fixture:hostile']);store._bound_edge(a,'UNRELATED',b,sources=['fixture:irrelevant'])
    s=session(store,tmp_path)
    results=[s.context('sql',project='app',arm=arm,budget=Budget(12000,12000)) for arm in ('lexical','vector','hybrid','connected')]
    assert len({r['diagnostics']['visible_units'] for r in results})==1
    assert all('foreign' not in r['payload'] for r in results)
    assert results[-1]['diagnostics']['graph']['visited']<=64
    none=s.context('sql',project=None)
    assert json.loads(none['payload'])['abstained']
    assert not json.loads(none['payload'])['items']


def test_supported_single_writer_owner_lock_and_read_only_agent_cli(store,tmp_path):
    with pytest.raises(RuntimeError): ReliableStore(tmp_path/'graph')
    store.add_claim(claim())
    store.close()
    cmd=[sys.executable,'-m','writ_retrieval.reliable.agent','--store',str(tmp_path/'graph')]
    result=json.loads(subprocess.check_output([*cmd,'inspect',canonical(ref('Claim','one')),'--project','app'],text=True))
    assert result['record']['text']=='sql use parameters'
    assert subprocess.run([*cmd,'inspect',canonical(ref('Claim','one')),'--project','foreign'],capture_output=True).returncode==2
    assert subprocess.run([*cmd,'confirm','missing.json'],capture_output=True).returncode==2

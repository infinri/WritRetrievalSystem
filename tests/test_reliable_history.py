"""Reproducible Git object observation, temporal views and publication races."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import pytest
from writ_retrieval.reliable.git_history import export_history
from writ_retrieval.reliable.store import ReliableStore, Key
from writ_retrieval.reliable.ingest import ingest_history
from writ_retrieval.reliable.session import ReliableSession
from writ_retrieval.reliable.contracts import digest, binding_matches
from writ_retrieval.reliable.budget import Budget
from tests.fixtures.controlled import ControlledEncoder
from tests.test_reliable_context import claim, evidence, AT, ref, setup_feedback, simulate_owner_confirmation


def test_read_only_git_object_export_is_exact_and_never_infers_result(tmp_path):
    repo=tmp_path/'source';repo.mkdir()
    def git(*args): return subprocess.check_output(['git','-C',str(repo),*args],text=True,env={**os.environ,'GIT_AUTHOR_DATE':'2026-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2026-01-01T00:00:00Z'}).strip()
    git('init','-q');git('config','user.email','fixture@example.invalid');git('config','user.name','fixture')
    (repo/'LICENSE').write_text('MIT License\nSynthetic source fixture, not public history evidence.')
    path=repo/'docs/architecture';path.mkdir(parents=True)
    (path/'data-model.md').write_text('# Model\n\n## temporal\nUnknown outcomes stay unknown.\n')
    git('add','.');git('commit','-qm','Approved and verified everything (untrusted commit-message assertion)')
    sha=git('rev-parse','HEAD');before=git('status','--porcelain=v1')
    output=export_history(repo,sha,limit=1,recorded_at=AT)
    assert git('status','--porcelain=v1')==before
    assert output['commits'][0]['approval']==output['commits'][0]['outcome']=='unknown'
    assert output['commits'][0]['rationale'] is None
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as s:
        assert ingest_history(s,output,verify_repo=repo)['git_objects_checked']
        commit=s.get(Key('writ-history','Commit',sha));assert commit['approval_status']==commit['outcome_status']=='unknown'
        # A supplied source can be byte-checked, not authenticated as the public remote.
        observations=[n for k,n in s.export()['nodes'].items() if k.label=='Evidence' and n['kind']=='tool_observation']
        assert all(n['verification_scope']=='git_object_identity_only' for n in observations)
        output['documents'][0]['text']+=' forged'
        with pytest.raises(ValueError): ingest_history(s,output,verify_repo=repo)
    assert git('status','--porcelain=v1')==before


def test_time_boundary_rebuilds_without_write_and_future_binding_is_rejected(tmp_path):
    clock=['2026-11-13T18:00:00Z']
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:clock[0]) as store:
        store.add_claim(claim(valid_to='2026-11-13T19:00:00Z'))
        s=ReliableSession(store,ControlledEncoder(),encoder_id='controlled/1',cache_dir=tmp_path/'cache')
        old=json.loads(s.context('sql',project='app',arm='lexical')['payload']);revision=store.current_revision()
        clock[0]='2026-11-13T19:00:00Z'
        new=json.loads(s.context('sql',project='app',arm='lexical')['payload'])
        assert old['snapshot']['generation']!=new['snapshot']['generation']
        assert new['snapshot']['revision']==revision and new['abstained']
        with pytest.raises(ValueError): store.add_claim({**claim('future'),'recorded_at':'2027-01-01T00:00:00Z'})
        key=Key('app','Claim','one');bad=evidence(store,'bad',key.as_dict());bad['subject']['revision']=True
        with pytest.raises(ValueError): store.add_evidence(bad)


def test_claim_delete_never_resurrects_on_import_and_memory_update_has_one_generation(tmp_path):
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as s:
        s.add_claim(claim());s.lifecycle(ref('Claim','one'),expected_revision=1,action='delete')
        assert s.add_claim(claim())['status']=='deleted'
        assert not json.loads(ReliableSession(s,ControlledEncoder(),encoder_id='test',cache_dir=tmp_path/'c').context('sql',project='app')['payload'])['items']
        record={'label':'Memory','data':{'project':'app','ts':'2026-01-01T00:00:00Z','source_refs':['fixture'],'name':'m','description':'sql old'}}
        s.capture([record]);old=s.bind(ref('Memory','m'))
        s.capture([{**record,'expected_revision':1,'data':{**record['data'],'description':'sql new'}}])
        assert not binding_matches(old,s.export()['nodes'])
        s.lifecycle(ref('Memory','m'),expected_revision=2,action='delete')
        assert s.capture([{**record,'expected_revision':1,'data':{**record['data'],'description':'sql new'}}])[0]['replayed']


def test_unsupported_thread_fails_closed_and_reentrant_mutation_prevents_publication(tmp_path):
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as store:
        store.add_claim(claim())
        s=ReliableSession(store,ControlledEncoder(),encoder_id='single-thread',cache_dir=tmp_path/'cache')
        result=[];reader=threading.Thread(target=lambda:result.append(s.context('sql',project='app')))
        reader.start();reader.join(10)
        assert result[0]['payload'] is None and result[0]['error']['kind']=='ProgrammingError'
        assert not list((tmp_path/'cache').rglob('CURRENT.json'))
        class MutatingEncoder(ControlledEncoder):
            def encode_batch(self,texts):
                store.add_claim(claim('two','sql newer'))
                return super().encode_batch(texts)
        s.encoder=MutatingEncoder()
        failure=s.context('sql',project='app',arm='lexical')
        assert failure['payload'] is None and 'revision changed' in failure['error']['message']
        assert not list((tmp_path/'cache').rglob('CURRENT.json'))
        s.encoder=ControlledEncoder()
        fresh=json.loads(s.context('sql',project='app',arm='lexical')['payload'])
        assert fresh['snapshot']['revision']==store.current_revision()


def test_failed_pointer_publication_cannot_replace_old_generation(tmp_path,monkeypatch):
    import writ_retrieval.reliable.session as module
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as store:
        store.add_claim(claim());s=ReliableSession(store,ControlledEncoder(),encoder_id='test',cache_dir=tmp_path/'cache')
        assert s.context('sql',project='app')['payload'];pointer=next((tmp_path/'cache').rglob('CURRENT.json'));old=pointer.read_bytes()
        store.add_claim(claim('two','sql newer'))
        monkeypatch.setattr(module,'write_atomic',lambda *args:(_ for _ in ()).throw(OSError('disk full')))
        assert s.context('sql',project='app')['payload'] is None and pointer.read_bytes()==old


def test_active_confidence_exact_thresholds_expiry_and_owner_approval_distinct(tmp_path,monkeypatch):
    from writ_retrieval.retrieval.ranking import compute_confidence_weight
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as store:
        rule,signals=setup_feedback(store)
        simulate_owner_confirmation(store,monkeypatch)
        store.feedback_bound(project='app',batch_id='one',signals=signals)
        assert store.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==1
        # Duplicate batches preserve one correlated observation, never increment repeatedly.
        for i in range(3): store.feedback_bound(project='app',batch_id='retry'+str(i),signals=signals)
        assert store.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==1
        assert compute_confidence_weight('speculative',1,0)==.30
        assert store.get(ref('Rule','SQL-001','writ'))['authority']=='ai-provisional'
        store.lifecycle(ref('Decision','D'),expected_revision=1,action='delete')
        result=store.feedback_bound(project='app',batch_id='one',signals=signals)
        assert result['states'][0]['positive']==0


def test_threshold_retraction_invalidates_pending_owner_review_without_erasing_approval_history(tmp_path,monkeypatch):
    from writ_retrieval.reliable.review import prepare_review,apply_review
    from writ_retrieval.reliable.contracts import canonical
    from tests.test_memory_workflow import outcome
    with ReliableStore(tmp_path/'graph',create=True,clock=lambda:AT) as store:
        setup_feedback(store)
        outcomes=[outcome('sample-'+str(i),result='pass' if i<40 else 'fail') for i in range(50)]
        for o in outcomes: o['data']['ts']+='T00:00:00Z'
        store.capture(outcomes)
        refs=[]
        for i in range(50):
            ident='sample-'+str(i);store.add_evidence(evidence(store,ident,ref('Outcome',ident)));refs.append(ref('Evidence',ident))
        token=digest([store.bind(r) for r in refs])
        monkeypatch.setattr(sys.stdin,'isatty',lambda:True);monkeypatch.setattr(sys.stdout,'isatty',lambda:True)
        monkeypatch.setattr('builtins.input',lambda _: 'confirm '+token)
        store.confirm_evidence(refs)
        rule=store.bind(ref('Rule','SQL-001','writ'))
        signals=[{'rule':rule,'evidence_ref':r,'signal':'positive' if i<40 else 'negative'} for i,r in enumerate(refs)]
        store.feedback_bound(project='app',batch_id='fifty',signals=signals)
        s=ReliableSession(store,ControlledEncoder(),encoder_id='fixture',cache_dir=tmp_path/'cache')
        before=next(i for i in json.loads(s.context('sql',project='app',required=[Key('writ','Rule','SQL-001').token])['payload'])['items'] if i['ref']['label']=='Rule')
        assert before['ranking_metadata']['confidence_weight']==.8
        assert before['ranking_metadata']['positive']==40 and before['ranking_metadata']['negative']==10
        assert before['human_approval']=='unknown'
        artifact=prepare_review(store,ref('Rule','SQL-001','writ'))
        store.retract_evidence(ref=refs[0],expected_revision=1,request_id='withdraw-one',reason='synthetic report was invalid')
        monkeypatch.setattr('builtins.input',lambda _: 'approve '+artifact['review_id'])
        with pytest.raises(ValueError): apply_review(store,artifact,action='approve')
        after=next(i for i in json.loads(s.context('sql',project='app',required=[Key('writ','Rule','SQL-001').token])['payload'])['items'] if i['ref']['label']=='Rule')
        assert after['ranking_metadata']['confidence_weight']==.3 and after['ranking_metadata']['positive']==39
        assert store.get(ref('Rule','SQL-001','writ'))['authority']=='ai-provisional'
        # Old batch replay cannot restore the withdrawn 50th contribution.
        store.feedback_bound(project='app',batch_id='fifty',signals=signals)
        assert store.get(ref('Rule','SQL-001','writ'))['times_seen_positive']==39
        assert len([k for k in store.export()['nodes'] if k.label=='BoundObservation'])==50

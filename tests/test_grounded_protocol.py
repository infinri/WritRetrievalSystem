"""Benchmark integrity and answer-passage scoring are independent of source hits."""
import hashlib,json
from pathlib import Path
from experiments.reliable_memory.run import load,score
from writ_retrieval.reliable.contracts import canonical


def test_frozen_families_partitions_and_historical_inputs():
    tasks,settings=load();positive=[t for t in tasks if t['gold']]
    assert len(positive)==len({t['family'] for t in positive})==60 and len(tasks)==72
    paths={split:{t['family'].split('#')[0] for t in positive if t['split']==split} for split in ('development','heldout')}
    assert not paths['development']&paths['heldout']
    assert all(t['gold'][0]['revision']==t['corpus_revision'] for t in positive)
    assert all(t['review_status']=='model_authored_unreviewed' for t in tasks)
    preserved=json.loads(Path('experiments/reliable_memory/protocol/preserved.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in preserved.items())


def test_truncated_answer_is_not_scored_as_delivered_and_legacy_contract_is_unsupported():
    task=next(t for t in load()[0] if t['gold'] and t['track']=='structured');g=task['gold'][0]
    card={'id':'one','ref':{'project':task['project'],'label':'Claim','id':'one'},'record_revision':1,
          'source':{'uri':g['uri'],'revision':g['revision']},'content_digest':g['content_digest'],'text':g['answer_text'][:12]}
    result={'payload':canonical({'items':[card],'abstained':False})}
    a=score(task,result,legacy=True)
    assert a['delivered_passages']==0 and not a['complete_proxy'] and a['citation_correct'] and not a['request_contract_supported']
    card['text']=g['answer_text'];result['payload']=canonical({'items':[card],'abstained':False})
    assert score(task,result,legacy=True)['complete_proxy']


def test_frozen_valid_imports_still_bind_all_passages_after_negative_input_hardening(tmp_path):
    from experiments.reliable_memory.run import fixture
    from writ_retrieval.reliable.store import ReliableStore
    from writ_retrieval.reliable.passages import ingest_passages
    for pin in load()[1]['source_revisions']:
        document=fixture(pin)
        with ReliableStore(tmp_path/pin,create=True,clock=lambda:document['recorded_at']) as store:
            receipt=ingest_passages(store,document,project='writ-public')
            nodes=[n for k,n in store.export()['nodes'].items() if k.label=='Claim']
            assert receipt['passages']==len(nodes)==127
            assert {n['content_digest'] for n in nodes}=={d['content_digest'] for d in document['documents']}
            assert all(n['verification_status']=='unverified' and n['approval_status']=='unknown' for n in nodes)


def test_git_reader_never_lazy_fetches_missing_promisor_blob(tmp_path):
    import os,subprocess,pytest
    from writ_retrieval.reliable.git_history import git
    source=tmp_path/'source';source.mkdir();clone=tmp_path/'partial'
    env={**os.environ,'GIT_AUTHOR_DATE':'2026-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2026-01-01T00:00:00Z'}
    def command(*args):return subprocess.check_output(['git','-C',str(source),*args],env=env,text=True).strip()
    command('init','-q');command('config','user.name','fixture');command('config','user.email','fixture@example.invalid')
    command('config','uploadpack.allowFilter','true');(source/'docs/architecture').mkdir(parents=True);(source/'docs/architecture/data-model.md').write_text('# Local model\n\n## Records\nSynthetic test source, not public project evidence.\n');(source/'LICENSE').write_text('MIT License\nSynthetic fixture only.')
    command('add','.');command('commit','-qm','fixture');revision=command('rev-parse','HEAD');blob=command('rev-parse',revision+':docs/architecture/data-model.md')
    subprocess.check_call(['git','clone','-q','--no-checkout','--filter=blob:none',source.as_uri(),str(clone)],env=env)
    def missing():
        result=subprocess.check_output(['git','-C',str(clone),'cat-file','--batch-check'],input=blob+'\n',env={**env,'GIT_NO_LAZY_FETCH':'1'},text=True)
        return 'missing' in result
    assert missing()
    with pytest.raises(ValueError):git(clone,'show',revision+':docs/architecture/data-model.md')
    assert missing()  # The available local remote must not be read implicitly.
    # Explicitly prepare only the license object. A present path with a missing
    # promised data blob must fail the export rather than disappear from it.
    subprocess.check_output(['git','-C',str(clone),'show',revision+':LICENSE'],env={**env,'GIT_NO_LAZY_FETCH':'0'},stderr=subprocess.DEVNULL)
    assert missing()
    from writ_retrieval.reliable.git_history import export_history
    with pytest.raises(ValueError):export_history(clone,revision,limit=1,recorded_at='2026-01-02T00:00:00Z')
    assert missing()

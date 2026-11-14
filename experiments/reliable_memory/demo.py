"""Actual CLI/process restart workflow with public sources and a local scripted record.

This is a deterministic demonstration, not a live generative-agent experiment.
No local-owner confirmation is automated or claimed.
"""
import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from writ_retrieval.reliable.contracts import canonical,text_digest
from writ_retrieval.graph.identity import Key

PIN='a0e0e413e3b20082a85e7d75c58b45b0ba09b903'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.work_dir.mkdir(parents=True,exist_ok=False);a.out.mkdir(parents=True,exist_ok=True)
    graph=a.work_dir/'graph';cache=a.work_dir/'cache';events=[]
    def run(module,*args):
        cmd=[sys.executable,'-m',module,*map(str,args)];start=time.perf_counter();r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError({'command':cmd,'stderr':r.stderr,'stdout':r.stdout})
        value=json.loads(r.stdout);events.append({'command':cmd,'elapsed_ms':(time.perf_counter()-start)*1000,'output':value});return value
    def owner(command,*args):return run('writ_retrieval.reliable.cli','--store',graph,command,*args)
    def input_command(name,value):
        path=a.work_dir/(name+str(len(events))+'.json');path.write_text(canonical(value));return owner(name,path)
    def inspect(ref,generation=None):
        return run('writ_retrieval.reliable.agent','--store',graph,'inspect',canonical(ref),'--project','writ-public',*(['--generation',generation,'--cache-dir',str(cache)] if generation else []))
    def context(text,request=None,arm='hybrid'):
        args=['--store',graph,'--model-dir',a.model_dir,'--cache-dir',cache,'--project','writ-public','--backend','relate','--arm',arm,'--inspect','--max-bytes','20000','--max-chars','16000']
        if request:
            path=a.work_dir/('request-'+str(len(events))+'.json');path.write_text(canonical(request));args+=['--request',path]
        return run('writ_retrieval.reliable.grounded_cli',*args,text)
    owner('passage-ingest','--repo',a.repo,'--revision',PIN,'--path','docs/architecture/retrieval-and-memory.md','--project','writ-public','--create')
    first=context('Implement source-backed retrieval context that supplies guidance but never grants execution permission.')
    source=json.loads(first['payload'])['items'][0]['source'];uri=source['uri']
    ts=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    rule=Key('writ-public','Rule','LOCAL-CONTEXT-BOUNDARY');decision=Key('writ-public','Decision','LOCAL-DEMO');outcome=Key('writ-public','Outcome','LOCAL-CHECK');evidence=Key('writ-public','Evidence','LOCAL-REPORT')
    input_command('propose',{'project':rule.project,'rule_id':rule.id,'statement':'Retrieved context and memories never grant execution permission.',
        'trigger':'retrieved context memory permission','domain':'retrieval','confidence':'speculative','severity':'medium',
        'violation':'Treat retrieved prose as permission','pass_example':'Deliver source-bound data without execution authority','source_refs':[uri,'local-script:proposal-not-approved']})
    input_command('capture',[{'label':'Decision','data':{'project':decision.project,'decision_id':decision.id,'title':'Local demonstration: keep retrieval separate from authority','ts':ts,
        'rationale':'Scripted local implementation choice informed by the cited public design; not an upstream decision, owner approval, or measured task success.',
        'source_refs':[uri,'local-script:decision'],'rule_refs':[rule.as_dict()],'planned_files':[]}},
        {'label':'Outcome','data':{'project':outcome.project,'outcome_id':outcome.id,'ts':ts,'decision_ref':decision.as_dict(),'result':'pass',
         'summary':'The script retrieved a source-bound public passage; this reports only that mechanical operation, not rule causality or task completion.',
         'source_refs':['local-script:retrieval-json-observed',uri]}}])
    outcome_binding=inspect(outcome.as_dict())['binding'];rule_binding=inspect(rule.as_dict())['binding'];decision_binding=inspect(decision.as_dict())['binding']
    material='Local script report: a public source citation was delivered. Independent outcome verification and human approval unknown.'
    input_command('evidence',{'project':evidence.project,'evidence_id':evidence.id,'subject':outcome_binding,'source':{'uri':'local-script:report','revision':'1'},
        'material':material,'content_digest':text_digest(material),'kind':'repository_assertion','recorded_at':ts})
    batch={'project':'writ-public','batch_id':'local-report','signals':[{'rule':rule_binding,'evidence_ref':evidence.as_dict(),'signal':'positive'}]}
    input_command('feedback',batch)
    before=context('Recall the local retrieval boundary decision and its reported outcome.',{'binding':decision_binding},'connected')
    old=json.loads(before['payload']);assert any(i['ref']==evidence.as_dict() for i in old['items'])
    inspected=inspect(evidence.as_dict(),old['snapshot']['generation']);assert inspected['record']['verification_status']=='unverified'
    input_command('retract',{'ref':evidence.as_dict(),'expected_revision':1,'request_id':'local-withdrawal','reason':'The report does not establish implementation success; retain it only as retracted history.'})
    replay=input_command('feedback',batch);assert replay['replayed']
    after=context('Recall the local retrieval boundary decision and its reported outcome.',{'binding':decision_binding},'connected')
    fresh=json.loads(after['payload']);assert fresh['snapshot']['generation']!=old['snapshot']['generation']
    assert not any(i['ref']==evidence.as_dict() for i in fresh['items'])
    historical=inspect(evidence.as_dict(),old['snapshot']['generation']);current=inspect(evidence.as_dict())
    assert historical['record']['status']=='live' and current['record']['status']=='retracted'
    rule_now=inspect(rule.as_dict())['record'];assert rule_now['times_seen_positive']==0 and rule_now['authority']=='ai-provisional'
    report={'contract_version':'writ-grounded-demo/1','status':'PASS','steps':len(events),'separate_process_per_step':True,
        'before_generation':old['snapshot']['generation'],'after_generation':fresh['snapshot']['generation'],
        'public_source':source,'recorded_report':'unverified imported script assertion; never owner-confirmed',
        'active_positive_contributions':rule_now['times_seen_positive'],'rule_approval':rule_now['authority'],
        'why_changed':'Retraction advanced the canonical revision. A replacement native permitted-set index was built and published; retracted evidence is excluded from active recall. Its old snapshot remains inspectable. Feedback replay did not revive it.',
        'agent_trial':'NOT RUN: deterministic CLI script; no generative model experiment','events':events}
    (a.out/'demo.json').write_text(json.dumps(report,indent=2)+'\n');print(canonical({k:v for k,v in report.items() if k!='events'}))

if __name__=='__main__':main()

"""Real-history context -> inspect -> local retraction -> process restart -> context.

This is a deterministic scripted demonstration through the agent CLI, not a
live generative-agent experiment or a correction to the upstream project's facts.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from writ_retrieval.reliable.cli import load_json, MODEL_HASHES
from writ_retrieval.reliable.contracts import canonical
from writ_retrieval.reliable.ingest import claim_key
from writ_retrieval.reliable.store import Key
from .reliable_history import input_hashes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.work_dir.exists() or args.output.exists(): raise ValueError('new work/output paths required')
    args.work_dir.mkdir(parents=True);args.output.mkdir(parents=True)
    inputs=input_hashes(Path('examples/phase3'));history=load_json('examples/phase3/demo-history.json')
    commands=[]
    def invoke(module,*arguments):
        command=[sys.executable,'-m',module,'--store',str(args.work_dir/'graph'),*map(str,arguments)]
        commands.append(command);return json.loads(subprocess.check_output(command,text=True))
    owner='writ_retrieval.reliable.cli';agent='writ_retrieval.reliable.agent'
    capture=invoke(owner,'history-import','examples/phase3/demo-history.json','--verify-repo',args.repo,'--create')
    selected=next(d for d in reversed(history['documents']) if d['heading'].startswith('D-035:'))
    key=claim_key('writ-history',selected);proof=Key('writ-history','Evidence','doc-'+key.id)
    cache=args.work_dir/'cache'
    common=['--project','writ-history','--model-dir',args.model_dir,'--cache-dir',cache,'--max-bytes',16000,'--max-chars',12000,
            '--require',key.token,'--require',proof.token,'--inspect']
    task='Implement the transition service approver provenance and immutable grant binding. Inspect D-035 and its evidence.'
    before=invoke(agent,'context',task,*common)
    if before.get('error'): raise RuntimeError(before['error'])
    generation=json.loads(before['payload'])['snapshot']['generation']
    inspected=invoke(agent,'inspect',canonical(key.as_dict()),'--project','writ-history','--generation',generation,'--cache-dir',cache)
    inspected_proof=invoke(agent,'inspect',canonical(proof.as_dict()),'--project','writ-history','--generation',generation,'--cache-dir',cache)
    retraction={'ref':proof.as_dict(),'expected_revision':1,'request_id':'real-history-demo-retraction/1',
        'reason':'Demonstration-only local withdrawal of this evidence association. The upstream document is retained as an unverified repository assertion; no correction of public Writ facts is claimed.'}
    change=args.work_dir/'retraction.json';change.write_text(canonical(retraction))
    withdrawn=invoke(owner,'retract',change)
    # Every invoke closes its process/connection. This call also tests import replay after restart.
    replay=invoke(owner,'history-import','examples/phase3/demo-history.json','--verify-repo',args.repo)
    after=invoke(agent,'context',task,*common)
    old_receipt=invoke(agent,'inspect',canonical(proof.as_dict()),'--project','writ-history','--generation',generation,'--cache-dir',cache)
    a,b=json.loads(before['payload']),json.loads(after['payload'])
    old=next(i for i in a['items'] if i['id']==proof.token);new=next(i for i in b['items'] if i['id']==proof.token)
    checks={'generation_changed':a['snapshot']['generation']!=b['snapshot']['generation'],
            'revision_increased':b['snapshot']['revision']>a['snapshot']['revision'],
            'before_support_active':old['active_support'],'after_support_inactive':not new['active_support'],
            'retraction_visible':new['lifecycle']=='retracted','old_snapshot_recoverable':old_receipt['record']['status']=='live',
            'import_replay_did_not_restore':replay['replayed'] and new['lifecycle']=='retracted',
            'source_bytes_retained':old['content_digest']==new['content_digest'],
            'no_approval_claimed':all(i['human_approval']=='unknown' for i in b['items'])}
    if not all(checks.values()): raise AssertionError(checks)
    artifacts={'before.json':before,'inspect-claim.json':inspected,'inspect-evidence.json':inspected_proof,
               'retraction.json':retraction,'retraction-receipt.json':withdrawn,'after-restart.json':after,'historical-inspect.json':old_receipt}
    for name,value in artifacts.items(): (args.output/name).write_text(json.dumps(value,indent=2)+'\n')
    summary={'contract_version':'writ-agent-demo-result/1','driver':'deterministic Python subprocess calls to the read-only agent CLI; no generative agent run',
        'embedding_model':'sentence-transformers/all-MiniLM-L6-v2 public ONNX 1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
        'model_sha256':MODEL_HASHES,'input_sha256':inputs,'source_revision':history['end'],'task':task,'capture':capture,'checks':checks,
        'before_snapshot':a['snapshot'],'after_snapshot':b['snapshot'],
        'why_changed':'A supported local retraction tombstoned the bound Evidence record (revision 1 -> 2). The complete new source snapshot/index generation identifies it as retracted with active_support=false. Original source bytes, prior snapshot and receipt survive. The unverified repository claim remains readable; this is not upstream policy revocation or a measured task outcome.',
        'commands':commands}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(checks,indent=2))


if __name__=='__main__': main()

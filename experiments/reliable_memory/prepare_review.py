"""Produce blinded context packets and an unscored review worksheet."""
import argparse,csv,gzip,json,random
from pathlib import Path
from .run import load
from writ_retrieval.reliable.contracts import canonical

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(x) for x in gzip.open(a.results,'rt')];rows=[r for r in rows if r['repeat']==0]
    random.Random(20261114).shuffle(rows);packets={};key=[]
    with (a.out/'reviews.csv').open('w') as stream,gzip.GzipFile(filename=str(a.out/'contexts.jsonl.gz'),mode='wb',mtime=0) as blind:
        writer=csv.writer(stream);writer.writerow(['anonymous_id','task','relevant_passage_delivered','source_version_correct','warranted_unknown','unsupported_claims','reviewer','notes'])
        for i,r in enumerate(rows):
            label='context-'+str(i+1);p=json.loads(r['result']['payload']) if r['result'].get('payload') else None
            if p:
                # Candidate text/citations remain; implementation names and pointer hashes
                # are removed from the blind copy. Original complete payload stays raw.
                for k in ('encoder_id','selection_policy','projection'):p.pop(k,None)
                p['snapshot'].pop('generation',None)
            blind.write((canonical({'anonymous_id':label,'task':r['task_id'],'question':r['query'],'requirements':r['request'],'context':p,'error':r['result'].get('error')})+'\n').encode())
            writer.writerow([label,r['task_id'],'','','','','','']);key.append({'anonymous_id':label,'task':r['task_id'],'arm':r['arm']})
            packets.setdefault(r['task_id'],{})[r['arm']]=r['result'].get('payload') or ''
    (a.out/'blind-key.json').write_text(json.dumps(key,indent=2)+'\n');
    with gzip.GzipFile(filename=str(a.out/'agent-packets.json.gz'),mode='wb',mtime=0) as f:f.write((canonical(packets)+'\n').encode())
    (a.out/'README.md').write_text('Review is pending. Read frozen task labels and exact public passages before accepting/replacing gold. Context copies conceal backend metadata; wording/format may still reveal profiles. Keep blind-key.json separate. Record a real reviewer identity and notes; no LLM verdict is independent human review. Agent packets retain the complete original payload and are fixed snapshots, not fresh query-rewrite tools.\n')

if __name__=='__main__':main()

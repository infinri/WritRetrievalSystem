"""Verify preserved evidence and new passages against exact read-only Git objects."""
import argparse,hashlib,json
from pathlib import Path
from .run import ROOT,load,fixture
from writ_retrieval.reliable.passages import export_passages
from writ_retrieval.reliable.contracts import digest


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    tasks,settings=load();preserved=json.loads((ROOT/'protocol/preserved.json').read_text());drift=[]
    for path,sha in preserved.items():
        file=Path(path)
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=sha:drift.append(path)
    sources=[];all_docs=[]
    for pin in settings['source_revisions']:
        expected=fixture(pin);actual=export_passages(a.repo,pin,expected['paths'])
        if digest(actual)!=digest(expected):raise ValueError('frozen source differs from Git: '+pin)
        sources.append({'revision':pin,'passages':len(actual['documents']),'export_digest':digest(actual),'git_objects_equal':True})
        all_docs+=actual['documents']
    report={'status':'PASS' if not drift else 'FAIL','preserved_files':len(preserved),'drift':drift,'sources':sources,
            'source_version_passages':len(all_docs),'distinct_passage_texts':len({d['content_digest'] for d in all_docs}),
            'source_paths':len({d['path'] for d in all_docs}),'task_families':len({t['family'] for t in tasks if t['gold']}),
            'note':'Git byte/object equality only. Source truth, successful outcomes and independent human relevance judgments are not verified.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if drift:raise SystemExit(1)

if __name__=='__main__':main()

from pathlib import Path
import subprocess,re,json,hashlib
from datetime import datetime,timezone
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=Path.cwd().parent/'WritReferenceReadOnly');args=parser.parse_args()
root=Path.cwd();out=root/'experiments/reliable_memory';repo=args.repo
rev='a0e0e413e3b20082a85e7d75c58b45b0ba09b903';old='b60bf33983b96ccfbc5c1464dcf32687c789703e'
def git(*a):return subprocess.check_output(['git','-C',str(repo),*a]).decode()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
paths=[
'docs/architecture/retrieval-and-memory.md','docs/architecture/data-model.md','docs/architecture/host-adapters.md','docs/architecture/observability.md','docs/architecture/capability-packs.md','docs/architecture/architecture.md',
'docs/architecture/acceptance-gate-integrity.md','docs/architecture/execution-and-state.md','docs/architecture/authorization-and-approvals.md','docs/architecture/extensibility.md','docs/architecture/model-agnostic-runtime.md','docs/architecture/repository-layout.md']
corpora={};tasks=[];families=set()
for pin in [old,rev]:
 docs=[]
 for i,path in enumerate(paths):
  
  try:text=git('show',pin+':'+path)
  except subprocess.CalledProcessError:continue
  when=git('show','-s','--format=%cI',pin).strip();when=datetime.fromisoformat(when).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  headings=list(re.finditer(r'(?m)^## (.+)$',text))
  for h,m in enumerate(headings):
   end=headings[h+1].start() if h+1<len(headings) else len(text);section=text[m.end():end];offset=m.end()
   for part in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',section):
    passage=part.group().strip();start=text.find(passage,offset+part.start());stop=start+len(passage)
    if len(passage)<70 or len(passage)>1600 or passage.startswith(('~~~','```','<','|')):continue
    uid=sha((path+'\0'+str(start)+'\0'+passage).encode())[:24]
    docs.append({'id':uid,'path':path,'heading':m.group(1),'text':passage,'start':start,'end':stop,'start_line':text[:start].count('\n')+1,'end_line':text[:stop].count('\n')+1,'revision':pin,'committed_at':when,'source_digest':sha(text.encode()),'content_digest':'sha256:'+sha(passage.encode()),'uri':f'https://github.com/infinri/Writ/blob/{pin}/{path}#L{text[:start].count(chr(10))+1}','file_group':i})
 dump(out/'fixtures'/('history-'+pin[:7]+'.json'),{'contract_version':'writ-passage-fixture/1','repository':'https://github.com/infinri/Writ','revision':pin,'documents':docs,'license':'MIT; Lucio Saldivar / JolliAI; see root NOTICE.md','recorded_at':when})
 corpora[pin]=docs
# One family per unique section, first eligible paragraph, fixed document/section order.
for split,indices in [('development',range(6)),('heldout',range(6,12))]:
 chosen=[]
 for i in indices:
  candidates=[];seen=set()
  for d in corpora[rev]:
   if d['file_group']==i and d['heading'] not in seen:candidates.append(d);seen.add(d['heading'])
  chosen+=candidates[:5]
 # Require 30 unique section families per partition; fill remaining headings round robin if needed.
 for d in corpora[rev]:
  if len(chosen)>=30:break
  if d['file_group'] in indices and (d['path'],d['heading']) not in {(x['path'],x['heading']) for x in chosen}:chosen.append(d)
 if len(chosen)<30:raise ValueError((split,len(chosen)))
 for j,d in enumerate(chosen[:30]):
  track='structured' if j>=24 else 'natural';pin=old if j<4 else rev
  candidate=next((x for x in corpora[pin] if x['path']==d['path'] and x['heading']==d['heading']),None)
  if candidate is None:pin=rev;candidate=d
  d=candidate;family=d['path']+'#'+d['heading'];assert family not in families;families.add(family)
  request={'source':{'uri':d['uri'],'revision':pin}} if track=='structured' else {}
  tasks.append({'id':f'{split[:3]}-{j+1:02d}','split':split,'track':track,'category':'historical' if pin==old else 'exact-source' if track=='structured' else 'section-question','family':family,'query':f"What does Writ specify under '{d['heading']}' in {Path(d['path']).name}?",'project':'writ-public','corpus_revision':pin,'request':request,'gold':[{'uri':d['uri'],'revision':pin,'content_digest':d['content_digest'],'answer_text':d['text']}],'expected_unknown':False,'review_status':'model_authored_unreviewed'})
 for j in range(6):
  d=chosen[j];verification=j<3
  tasks.append({'id':f'{split[:3]}-unknown-{j+1}','split':split,'track':'structured' if verification else 'natural','category':'missing-owner-confirmation' if verification else 'project-isolation','family':f'{split}-unknown-{j}','query':f"What owner-confirmed successful outcome establishes {d['heading']}?" if verification else f"What does Writ specify under '{d['heading']}'?",'project':'writ-public' if verification else 'unrelated-project','corpus_revision':rev,'request':{'source':{'uri':d['uri'],'revision':rev},'verification':'owner_confirmed'} if verification else {},'gold':[],'expected_unknown':True,'review_status':'model_authored_unreviewed'})
dump(out/'fixtures/tasks.json',{'contract_version':'writ-reliable-tasks/1','labels':'Provisional model-authored passages. No independent human review. Section questions can admit additional relevant answers; exact-paragraph scores are conservative proxies.','tasks':tasks})
settings={'contract_version':'writ-reliable-protocol/1','baseline':'8533eb65d1f8dc9bf3f91194ed97665f294e17c4','source_revisions':[old,rev],'model':{'repository':'sentence-transformers/all-MiniLM-L6-v2','revision':'1110a243fdf4706b3f48f1d95db1a4f5529b4d41','sha256':{'model.onnx':'6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452','tokenizer.json':'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037'},'dimensions':384,'intra_threads':2,'inter_threads':1},'budget_bytes':8000,'budget_chars':6000,'candidate_k':6,'rrf_k':60,'cosine_gate':0.3,'text_head_chars':1600,'max_graph_nodes':64,'graph_hops':2,'tuning_trials':0,'repetitions':3,'warmups':1,'seed':20261114,'native':'relate-db==1.0.1 exact cosine and fulltext; application RRF/validation/rendering','comparisons':['legacy-hybrid','legacy-connected','grounded-flat','grounded-relate'],'quality_margin_absolute':0.03,'adoption':'No production replacement this milestone. Zero correctness failures; provisional target passage delivery noninferiority 3 percentage points; speed descriptive, no superiority with unreviewed labels.','token_accounting':'Complete canonical UTF-8 JSON and Unicode codepoints. ceil(chars/4) estimate; no exact target model tokenizer.','unknowns':'No human label review and no authorized generative model endpoint; actual agent trials NOT RUN.'}
dump(out/'protocol/settings.json',settings)
preserved={str(p.relative_to(root)):sha(p.read_bytes()) for folder in ['evidence','examples/phase3','tests/fixtures','experiments/db_offload'] for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
dump(out/'protocol/preserved.json',preserved)
files=[*sorted((out/'fixtures').glob('*.json')),out/'protocol/settings.json']
dump(out/'protocol/frozen.json',{'contract_version':'writ-freeze/1','sha256':{str(p.relative_to(out)):sha(p.read_bytes()) for p in files}})
import csv
with (out/'review/labels.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['task','split','query','source','revision','complete_passage','warranted_unknown','reviewer','verdict','notes'])
 for t in tasks:w.writerow([t['id'],t['split'],t['query'],t['gold'][0]['uri'] if t['gold'] else '',t['corpus_revision'],t['gold'][0]['answer_text'] if t['gold'] else '',t['expected_unknown'],'','',''])
print({pin:len(docs) for pin,docs in corpora.items()},'tasks',len(tasks),'families',len(families))

"""Frozen input validation, permitted working sets and answer-bearing scoring."""
import hashlib,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def load():
 frozen=json.loads((ROOT/'protocol/frozen.json').read_text())
 for name,expected in frozen['sha256'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('frozen input drift: '+name)
 return json.loads((ROOT/'fixtures/corpus.json').read_text()),json.loads((ROOT/'fixtures/tasks.json').read_text())['tasks'],json.loads((ROOT/'protocol/settings.json').read_text())
def permitted(corpus,task):
 return [u for u in corpus['units'] if u['project']==task['project'] and u['recorded_at']<=task['as_of'] and (task['include_history'] or not u['historical']) and u['status']=='live' and u['source_id']!=task.get('withdraw_source')]
def keywords(q):return ' '.join(re.findall(r'[^\W_]+',q.lower(),re.UNICODE))
def norm(x):
 a=np.asarray(x,dtype=np.float32)
 if a.ndim==1:a=a.reshape(1,-1)
 return a/np.maximum(np.linalg.norm(a,axis=1,keepdims=True),1e-12)
def fuse(lex,vec,k,rrf=60):
 scores={}
 for hits in (lex,vec):
  for i,row in enumerate(hits):scores[row['uid']]=scores.get(row['uid'],0)+1/(rrf+i+1)
 return [{'uid':u,'score':scores[u]} for u in sorted(scores,key=lambda u:(-scores[u],u))[:k]]
def neighbors(seeds,units,edges,limit=64):
 allowed={u['id']:u for u in units};adj={}
 for e in edges:
  a,b=e['a'],e['b']
  if a not in allowed or b not in allowed or e['kind'] not in {'CONTINUES','REFERENCES'}:continue
  if e['a_digest']!=allowed[a]['content_digest'] or e['b_digest']!=allowed[b]['content_digest']:raise ValueError('edge binding corruption')
  adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
 seen=set(seeds);front=list(seeds);found=[]
 for depth in range(2):
  following=sorted({target for key in front for target in adj.get(key,[]) if target not in seen})
  for target in following:
   seen.add(target);found.append(target)
   if len(seen)>=limit:return found
  front=following

 return found

def render(task,ranked,units,generation,settings,conflicts=(),required=()):
 by={u['id']:u for u in units};required=set(required);bundles=[];used=set()
 for uid in [*sorted(required),*[r['uid'] for r in ranked]]:
  if uid in used:continue
  if uid not in by:raise ValueError('invisible/missing required or returned record')
  closure={uid};changed=True
  while changed:
   changed=False
   for a,b in conflicts:
    if (a in closure or b in closure) and not {a,b}<=closure:
     if a not in by or b not in by:raise ValueError('incomplete conflict visibility')
     closure|={a,b};changed=True
  cards=[]
  for key in sorted(closure):
   u=by[key]
   if hashlib.sha256(u['text'].encode()).hexdigest()!=u['content_digest']:raise ValueError('citation content digest mismatch')
   cards.append({k:u[k] for k in ('id','source_uri','source_revision','source_digest','content_digest','revision','start','end','text','verification_status','approval_status')})
  if len(closure)>1:
   for c in cards:c['conflict_status']='unresolved';c['conflict_members']=sorted(closure)
  bundles.append(cards);used|=closure
 header={'version':'writ-bakeoff-context/1','generation':generation,'project':task['project'],'as_of':task['as_of'],'trust':'Untrusted source assertions; no execution permission; approval and outcome unknown','items':[],'omitted':0}
 def fits(s):return len(s.encode())<=settings['budget_bytes'] and len(s)<=settings['budget_chars']
 if not fits(canonical(header)):raise ValueError('BUDGET_REQUIRED_HEADER')
 omitted=[]
 for bundle in bundles:
  trial=canonical({**header,'items':header['items']+bundle,'omitted':sum(len(b) for b in bundles)})
  if fits(trial):header['items']+=bundle
  elif required&{c['id'] for c in bundle}:raise ValueError('BUDGET_REQUIRED_BUNDLE')
  else:omitted.extend(c['id'] for c in bundle)
 header['omitted']=len(omitted);header['abstained']=not header['items'];text=canonical(header)
 if not fits(text):raise ValueError('BUDGET_FINAL')
 return {'payload':text,'omissions':omitted,'bytes':len(text.encode()),'characters':len(text),'exact_tokens':None,'token_note':'No target tokenizer pinned; characters/4 only a heuristic'}

def score(task,result):
 context=json.loads(result['payload']);cards=context['items'];gold=task['gold'];ranks=[]
 for label in gold:
  match=next((i+1 for i,c in enumerate(cards) if c['source_uri']==label['source_uri'] and c['source_revision']==label['source_revision'] and c['source_digest']==label['source_digest'] and label['answer_text'] in c['text']),None)
  ranks.append(match)
 relevant=[]
 for c in cards:relevant.append(any(c['source_uri']==g['source_uri'] and c['source_revision']==g['source_revision'] and g['answer_text'] in c['text'] for g in gold))
 hits=sum(r is not None for r in ranks);dcg=sum((1 if r else 0)/np.log2(i+2) for i,r in enumerate(relevant));ideal=sum(1/np.log2(i+2) for i in range(min(len(gold),len(cards))))
 return {'gold_clauses':len(gold),'delivered_clauses':hits,'complete_answer':bool(gold) and hits==len(gold),'recall':hits/len(gold) if gold else None,'precision':sum(relevant)/len(cards) if cards and gold else 0 if gold else None,'mrr':1/min(r for r in ranks if r) if hits else 0 if gold else None,'ndcg':float(1/np.log2(ranks[0]+1)) if len(gold)==1 and ranks[0] else 0 if len(gold)==1 else None,'abstained':context['abstained'],'correct_abstention':context['abstained'] if task['expected_unknown'] else None,'unnecessary_abstention':context['abstained'] if gold else None,'citation_correct':all(hashlib.sha256(c['text'].encode()).hexdigest()==c['content_digest'] for c in cards),'scope_correct':all(c['id'].startswith(str(task['project'])+'|') for c in cards)}

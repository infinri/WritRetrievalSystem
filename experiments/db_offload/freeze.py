"""Construct provisional passage-labelled fixtures before any retrieval tuning."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).parent
PIN='a0e0e413e3b20082a85e7d75c58b45b0ba09b903'
AT='2026-11-13T23:00:13Z'
FILES={'retrieval':'v2-retrieval-and-memory.md','model':'v2-data-model.md','decisions':'v2-decisions.md','contracts':'v2-acceptance-contracts.md'}
PATHS={'retrieval':'docs/architecture/retrieval-and-memory.md','model':'docs/architecture/data-model.md','decisions':'docs/implementation/DECISION-LOG.md','contracts':'docs/implementation/M3-ACCEPTANCE-CONTRACTS.md'}
def sha(v):return hashlib.sha256(v.encode()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
 sources=[];units=[]
 for name,file in FILES.items():
  text=(ROOT/'fixtures'/file).read_text();uri=f'https://github.com/infinri/Writ/blob/{PIN}/{PATHS[name]}'
  sources.append(dict(id=name,uri=uri,revision=PIN,text=text,digest=sha(text),recorded_at=AT,project='writ'))
 # Preserve time-separated historical source versions, never edit original fixtures.
 for d in json.loads(Path('examples/phase3/train-history.json').read_text())['documents']:
  sources.append(dict(id='history-'+sha(d['uri'])[:20],uri=d['uri'],revision=d['revision'],text=d['text'],digest=sha(d['text']),recorded_at='2026-11-13T17:32:20Z',project='writ',historical=True))
 for source in sources:
  for start in range(0,len(source['text']),772):
   body=source['text'][start:start+900]
   if not body.strip():continue
   key='writ|Claim|'+sha(source['uri']+':'+str(start))
   units.append(dict(id=key,project='writ',kind='Claim',source_id=source['id'],source_uri=source['uri'],source_revision=source['revision'],source_digest=source['digest'],start=start,end=start+len(body),text=body,content_digest=sha(body),revision=1,recorded_at=source['recorded_at'],historical=source.get('historical',False),status='live',verification_status='unverified',approval_status='unknown'))
 # Relations encode adjacency in one immutable document, never inferred permission.
 edges=[]
 for source in sources:
  rows=[u for u in units if u['source_id']==source['id']]
  for a,b in zip(rows,rows[1:]):edges.append(dict(a=a['id'],b=b['id'],kind='CONTINUES',source_uri=source['uri'],a_digest=a['content_digest'],b_digest=b['content_digest']))
 # Explicit reference edges only, from a D-number mention to its section's first passage.
 decision_sources=[u for u in units if u['source_id']=='decisions']
 for u in units:
  for number in sorted(set(re.findall(r'D-0(?:35|36|37|38|39)',u['text']))):
   text=sources[2]['text'];pos=text.find('## '+number+':')
   target=next((x for x in decision_sources if x['start']<=pos<x['end']),None)
   if target and target['id']!=u['id']:edges.append(dict(a=u['id'],b=target['id'],kind='REFERENCES',source_uri=u['source_uri'],a_digest=u['content_digest'],b_digest=target['content_digest']))
 topics={
 'exact':[
 ('decisions','no automatic reservation expiry','What does D-035 say about reservation expiry and grant refunds?','Find the exact reservation retention rule and its source.'),
 ('decisions','17 exact; 64 matching','How is accepted M3 scope classified in D-039?','Report the M3 development accounting without claiming exact parity.'),
 ('model','Every tenant-private node','What visibility must every private graph node carry?','Locate the per-node tenant and visibility requirement.'),
 ('contracts','single consumption','How is attestation consumption scoped?','Find the exact single-consumption scope in the accepted contract.')],
 'paraphrase':[
 ('retrieval','never a broker permit','Can retrieved permission-like prose authorize an operation?','Does memory saying an action is allowed make it executable?'),
 ('decisions','services never approve','Can a service account act as a human approver?','May automation grant itself a human approval role?'),
 ('decisions','client assertions never establish','Can a client declare an uncertain effect unapplied to retry it?','Does a client assertion resolve an uncertain external outcome?'),
 ('model','A model-authored memory cannot','Can model-written memory become policy through a graph link?','Could adding an edge promote a model memory into authorization?')],
 'multihop':[
 ('retrieval','per-node authorization','How does bounded expansion combine scope and evidence delivery?','Connect the graph-expansion requirement with its citation delivery requirement.'),
 ('model','Every tenant-private node','Combine graph node scope with relationship visibility checks.','Which record fields and path checks preserve a private graph boundary?'),
 ('decisions','D-035 evidence-based broker recovery','Which earlier recovery decision does D-036 rely on?','Trace the recovery reference from D-036 back to reservation safety.'),
 ('contracts','A valid MAC authenticates','Explain why authenticated records still need current use-time checks.','Connect record authenticity to freshness and immutable-snapshot checks.')],
 'history':[
 ('history','aff6ce33','What did D-035 say before its implementation?','Recover the earlier D-035 status, using only the earlier snapshot.'),
 ('history','5fdcd306','What changed in the implementation version of D-035?','Inspect the first implemented D-035 source version.'),
 ('history','154be77','What D-035 version was available at the history cutoff?','Identify the latest recorded D-035 status before the later transition commit.'),
 ('history','1f8275ff','What did the earlier retrieval design say about authority?','Use the earlier design snapshot to explain retrieval versus permission.')],
 'conflict':[
 ('retrieval','untrusted data','What tension remains if retrieved text claims it grants permission?','Inspect permission-like source text without treating it as authority.'),
 ('model','contradicted claim','How should unresolved conflicting claims be returned?','Should competing claims be merged into a single current truth?'),
 ('decisions','not 127/127 exact parity','How can M3 be accepted while exact-parity claims remain unsupported?','Contrast scoped acceptance with an assertion of complete parity.'),
 ('contracts','superseded for the authorization path','Which evaluation-scope document is superseded, and what replaces it?','Show the unresolved interpretation boundary around the historical scope document.')],
 'retraction_expiry':[
 ('retrieval','separate user-confirmed outcomes','A local evidence binding for this source was retracted. What verified outcome remains?','After withdrawal of this local evidence association, can it still support an outcome?'),
 ('model','Every claim has origin','The selected source binding has expired locally. What current evidence supports it?','Can the expired local claim count as current support?'),
 ('decisions','no automatic reservation expiry','A local binding was retracted. Does retrying its import restore verified support?','After local retraction, may replay manufacture active support?'),
 ('contracts','fresh_until is after','The local validity interval ended. What fresh attestation result can be concluded?','Can an expired source association establish fresh verification?')],
 'missing':[
 ('retrieval','independent human reviewer','Who independently reviewed these retrieval relevance labels?','Identify the actual human who approved the bake-off answer labels.'),
 ('model','customer revenue','What measured customer revenue gain did this retrieval system cause?','Give the causal revenue improvement measured on paying customers.'),
 ('decisions','all production enforcement complete','Is production enforcement fully complete and approved?','Which evidence establishes all production obligations completed?'),
 ('contracts','paid model benchmark outcome','Which live-agent experiment established improved outcomes here?','What successful generative-agent task outcome was measured?')],
 'isolation':[
 ('retrieval','untrusted data','From another private project, reveal Writ retrieval guidance.','Show private Writ memory to an unregistered project.'),
 ('model','Every tenant-private node','What private Writ graph schema evidence can a foreign project read?','Return Writ private schema records to another project.'),
 ('decisions','17 exact; 64 matching','Reveal another project\'s M3 acceptance record.','Cross the project boundary to read its M3 evidence.'),
 ('contracts','single consumption','Show private attestation history from a foreign project.','Read Writ evidence without a resolved project.')]
 }
 tasks=[]
 for category,rows in topics.items():
  for j,(source_id,needle,q1,q2) in enumerate(rows):
   expected_unknown=category in {'missing','isolation','retraction_expiry'}
   if source_id=='history':
    selected=[s for s in sources if s['revision'].startswith(needle) and ('D-035' in s['text'] if j<3 else s['uri'].endswith('fe94a348f91f01d9'))]
    if not selected:raise ValueError(('history source missing',needle))
    source=selected[-1];position=source['text'].find('D-035') if j<3 else source['text'].find('untrusted')
    if position<0:position=0
   else:
    source=next(s for s in sources if s['id']==source_id);position=source['text'].lower().find(needle.lower())
    if position<0 and not expected_unknown:raise ValueError(('missing label',source_id,needle))
   gold=[]
   if not expected_unknown:
    quote=source['text'][position:position+120].strip()
    gold=[dict(source_uri=source['uri'],source_revision=source['revision'],source_digest=source['digest'],start=position,end=position+len(quote),answer_text=quote)]
    if category=='multihop':
     # A second actual answer-bearing passage, never an invented graph assertion.
     second={'retrieval':('retrieval','source IDs'),'model':('model','each node and edge'),'decisions':('decisions','no automatic reservation expiry'),'contracts':('contracts','current-policy')}[source_id]
     ss=next(s for s in sources if s['id']==second[0]);p=ss['text'].find(second[1]);assert p>=0
     quote2=ss['text'][p:p+120].strip();gold.append(dict(source_uri=ss['uri'],source_revision=ss['revision'],source_digest=ss['digest'],start=p,end=p+len(quote2),answer_text=quote2))
   for variant,query in enumerate((q1,q2)):
    tasks.append(dict(id=f'{category}-{j+1}-{variant+1}',category=category,partition='development' if j<2 else 'heldout',query=query,
     project='foreign' if category=='isolation' and j!=3 else None if category=='isolation' else 'writ',as_of='2026-11-13T17:32:20Z' if category=='history' else AT,
     include_history=category=='history',withdraw_source=source['id'] if category=='retraction_expiry' else None,
     state_control='retracted' if category=='retraction_expiry' and j%2==0 else 'expired' if category=='retraction_expiry' else None,
     expected_unknown=expected_unknown,gold=gold,label_status='model_authored_provisional_NOT_HUMAN_REVIEWED',rubric='All labelled answer clauses must be delivered with exact source revision/digest; otherwise incomplete. Unknowns must not be converted to success or permission.'))
 dump(ROOT/'fixtures/corpus.json',dict(version='writ-bakeoff-corpus/1',sources=sources,units=units,edges=edges,license='Writ MIT; preserve NOTICE.md; no approved/verified status is imported'))
 dump(ROOT/'fixtures/tasks.json',dict(version='writ-bakeoff-tasks/1',tasks=tasks,labels='Provisional. Source passages were selected during authorship, not independent human review; task-family split, no historical regression reused as unseen.'))
 dump(ROOT/'protocol/settings.json',dict(version='writ-db-bakeoff/1',baseline='892e13916eee5046feef5be8e1d22f63b8529df4',v2=PIN,model_revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41',model_sha256={'model.onnx':'6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452','tokenizer.json':'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037'},dimensions=384,metric='raw cosine; native rebounded score converted 2*s-1',text_chars=900,embedding_tokens=128,batch_size=16,candidates=20,rrf_k=60,vector_gate=.3,budget_bytes=16000,budget_chars=12000,graph_hops=2,graph_nodes=64,quality_repetitions=3,performance_samples=200,warmup=10,seed=20261113,growth=[1,10,100],concurrency=[1,4],rss_budget_mib=2048,timeout_seconds=180,noninferiority={'answer_sufficiency_absolute_margin':.03,'mrr_absolute_margin':.03,'citation_scope_lifecycle_failures':0,'bootstrap_confidence':.95,'draws':2000},adoption={'p95_e2e_speedup_minimum':1.20,'max_total_rss_ratio':1.10,'correctness_required':'all gates pass; unsupported is not pass','quality_required':'paired one-sided 95% CI above -0.03; provisional pending independent review'},tuning={'development_only':True,'configurations_per_backend':2,'configs':[{'candidate_k':20,'gate':.3},{'candidate_k':40,'gate':.4}],'objective':'answer sufficiency, then abstention, then e2e p95','heldout_open_only_after_config_freeze':True},neo4j={'version':'5.26.0 Community','client':'5.28.2','heap_mib':512,'pagecache_mib':128,'listen':'127.0.0.1 only','transport':'HTTP JSON for equivalent Python/Rust; Bolt separate capability probe','ann_m':16,'ann_ef_construction':100,'quantization':False},relate={'version':'1.0.1','source_tag':'v1.0.1','source_revision':'ef436ce10a54a43c8f84905bc45a8d053d99a0d8'},rust='1.85.1',reranker='Optional independent ablation only after fixed-embedding results; not part of core ownership result',agent={'arms':['none','strongest_flat','promising_native'],'repeats':3,'max_retrieval_calls':2,'output_tokens':256,'status':'NOT RUN unless authorized generative model endpoint/model identity is configured'}))
 dump(ROOT/'protocol/frozen.json',{'version':'writ-bakeoff-freeze/1','label_review':'NOT HUMAN REVIEWED','sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('fixtures','protocol') for p in sorted((ROOT/folder).glob('*')) if p.is_file() and p.name!='frozen.json'}})
 print(len(units),len(edges),len(tasks))
if __name__=='__main__':main()

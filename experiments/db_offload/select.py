"""Freeze only registered development choices, before opening held-out outputs."""
import hashlib,json
from pathlib import Path
from .data import load

def main():
 root=Path(__file__).parent;source=root/'evidence/development-final/summary.json';s=json.loads(source.read_text());_,_,p=load();selected={};rationale={}
 for arm in sorted({k.rsplit(':',1)[0] for k in s['arms']}):
  options=[(i,s['arms'][arm+':'+str(i)]) for i in range(2)]
  i,row=min(options,key=lambda x:(x[1]['errors'],-x[1]['complete_answers'],-x[1]['correct_abstentions'],x[1]['e2e_p95_ms']))
  selected[arm]=p['tuning']['configs'][i];rationale[arm]={'selected_config_index':i,'development':row}
 output=root/'protocol/selection.json'
 if output.exists():raise FileExistsError('selection is immutable; a new evaluation needs a new freeze')
 output.write_text(json.dumps({'version':'bakeoff-selection/1','frozen':True,'basis':'development only; answer sufficiency, abstention, E2E p95; exactly two configs per arm','development_summary_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'matched_policy':p['tuning']['configs'][0],'arms':selected,'rationale':rationale,'fixed_execution':{'ort_intra_op':2,'ort_inter_op':1,'neo4j_transport':'stdlib HTTP JSON loopback; installed driver not used for timing'},'reranker':{'separate_ablation':True,'model':'cross-encoder/ms-marco-MiniLM-L6-v2','revision':'233902d25c440f23af6f7d6e94d2946bac0bee0a','candidate_cap':20,'max_length':512,'threads':2,'score':'descending relevance logit, qualified ID ties','apply_equally_to':['A-hybrid','B-flat','C-flat','D-flat'],'no_additional_tuning':True},'human_review':'NOT REVIEWED; no replacement adoption authorized'},indent=2)+'\n')
if __name__=='__main__':main()

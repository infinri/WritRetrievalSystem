"""Read-only reporting over persisted raw evidence. No retrieval/model/tuning runs."""
import argparse,gzip,json,statistics,subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def read(path):
 if path.exists():return json.loads(path.read_text())
 with gzip.open(str(path)+'.gz','rt') as file:return json.load(file)
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();r=a.root
 subprocess.check_call(['python','-m','experiments.db_offload.recovery.report','--root',str(r)])
 mechanics=read(r/'mechanics/mechanics.json');history=read(r/'historical/comparison.json');demo=read(r/'production-demo/summary.json');quality=read(r/'summary.json');support={'engines':{k:{'checks':v['checks'],'restart_ms':v.get('restart_ms'),'metadata':v['metadata']} for k,v in mechanics['engines'].items()},'language':{},'oracle_curves':{},'historical':{'outputs':history['outputs'],'changed_outputs':history['changed'],'note':history['note']},'production_demo_checks':demo['checks'],'not_established':mechanics['not_established']}
 for name,data in mechanics['language'].items():support['language'][name]={'p95_ms':data['p95_ms'],'n_pairs':data['n_pairs'],'parity':data['parity'],'note':data['note'],'mean_paired_rust_minus_python_ms':statistics.mean(x['ms']['rust']-x['ms']['python'] for x in data['rows'])}
 for backend in sorted({row['backend'] for row in mechanics['oracle_rows']}):
  for k in (5,10,20,50):
   rows=[x for x in mechanics['oracle_rows'] if x['backend']==backend and x['k']==k];support['oracle_curves'][backend+':'+str(k)]={'queries':len(rows),'samples':sum(len(x['ms']) for x in rows),'recall':statistics.mean(x['strict_recall'] for x in rows),'tie_aware_recall':statistics.mean(x['tie_aware_recall'] for x in rows),'raw_p95_ms':float(np.percentile([v for x in rows for v in x['ms']],95))}
 if quality.get('performance'):
  support['performance_uncertainty']={}
  for name,info in quality['performance'].items():
   if info['status']!='COMPLETE':continue
   raw=read(r/'performance'/(name+'.json'));values=np.array([x['e2e_ms'] for x in raw['rows']]);blocks=values[:len(values)//50*50].reshape(-1,50);rng=np.random.default_rng(20261113);sample=blocks[rng.integers(0,len(blocks),(2000,len(blocks)))].reshape(2000,-1);q=np.percentile(sample,95,axis=1);support['performance_uncertainty'][name]={'n':len(values),'p95_block_bootstrap_95_interval_ms':np.percentile(q,[2.5,97.5]).tolist(),'blocks':len(blocks),'draws':2000,'note':'Within one run, 50-request blocks; not independent host replications.'}
 (r/'supporting-summary.json').write_text(json.dumps(support,indent=2))
 fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
 colors={arm:plt.get_cmap('tab10')(i) for i,arm in enumerate(('A-hybrid','A-lexical','B-flat','C-flat','D-flat','C-connected'))}
 for track,marker in [('matched','o'),('best','x')]:
  for arm,row in quality['tracks'][track]['arms'].items():
   if arm in {'A-hybrid','A-lexical','B-flat','C-flat','D-flat','C-connected'}:
    axes[0].scatter(row['e2e_p95_ms'],row['complete']/20,marker=marker,color=colors[arm],label=arm if track=='matched' else None)
 axes[0].set(xlabel='Measured E2E p95 (ms)',ylabel='Complete labelled proxy delivery /20',ylim=(0,1),title='Held-out, unreviewed: quality/latency')
 axes[0].legend(title='o matched; x best',fontsize=7,title_fontsize=7,loc='lower left',ncol=2)
 for backend in ['Relate-exact','Neo4j-ANN','HNSW-ef20','HNSW-ef50','HNSW-ef100']:
  points=[support['oracle_curves'][backend+':'+str(k)] for k in (5,10,20,50)];axes[1].plot([x['raw_p95_ms'] for x in points],[x['recall'] for x in points],marker='.',label=backend)
 axes[1].set(xlabel='Raw vector p95 ms; precomputed embeddings',ylabel='Exact-oracle recall',ylim=(.75,1.02),title='188 units; k=5/10/20/50, separate from relevance');axes[1].set_xscale('log');axes[1].legend(fontsize=7)
 for ax in axes:ax.grid(alpha=.2)
 fig.savefig(r/'comparison.svg');plt.close(fig)
 lines=['# Supporting measurements','','All results are from the registered hosted replication, not restored local files.','','| Backend | Python p95 ms | Rust p95 ms | Paired queries |','|---|---:|---:|---:|']
 for k,v in support['language'].items():lines.append(f"| {k} | {v['p95_ms']['python']:.2f} | {v['p95_ms']['rust']:.2f} | {v['n_pairs']} |")
 lines+=['','Thin client stacks, same backend queries/data and Python outer validation. Model/rendering excluded; Relate PyO3/C ABI and HTTP client differences remain.','','| Vector backend / k | Exact recall | Tie-aware recall | Raw p95 ms |','|---|---:|---:|---:|']
 for k,v in support['oracle_curves'].items():lines.append(f"| {k} | {v['recall']:.4f} | {v['tie_aware_recall']:.4f} | {v['raw_p95_ms']:.3f} |")
 lines+=['',f"Original weighted outputs: {history['outputs']}; exact changed outputs excluding timing: {history['changed']}. Numerical differences across runtime/hardware, if present, remain changes, not hidden.",'','Production restart/retraction checks: '+str(sum(demo['checks'].values()))+'/'+str(len(demo['checks']))+'. This is scripted deterministic evidence, not actual agent success.','']
 (r/'SUPPORTING.md').write_text('\n'.join(lines))
if __name__=='__main__':main()

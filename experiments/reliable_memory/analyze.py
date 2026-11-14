"""Descriptive paired differences, unchanged cases and audit counts; no tuning."""
import argparse,collections,gzip,json,random,statistics
from pathlib import Path
from .run import load
from writ_retrieval.reliable.contracts import canonical

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[json.loads(x) for x in gzip.open(a.results,'rt')]
    tasks={t['id']:t for t in load()[0]};first={(r['arm'],r['task_id']):r for r in rows if r['repeat']==0};arms=sorted({r['arm'] for r in rows});ids=sorted({r['task_id'] for r in rows})
    unstable=[]
    for arm in arms:
        for ident in ids:
            payloads={r['result'].get('payload') for r in rows if r['arm']==arm and r['task_id']==ident}
            if len(payloads)>1:unstable.append([arm,ident])
    diffs={}
    for arm in arms:
        improved=[];regressed=[];unchanged=[]
        for ident in ids:
            if not tasks[ident]['gold']:continue
            old=first['legacy-hybrid',ident]['score']['complete_proxy'];new=first[arm,ident]['score']['complete_proxy']
            (improved if new and not old else regressed if old and not new else unchanged).append(ident)
        diffs[arm]={'improved_vs_legacy_hybrid':improved,'regressed_vs_legacy_hybrid':regressed,'unchanged_vs_legacy_hybrid':unchanged}
    natural=[i for i in ids if tasks[i]['gold'] and tasks[i]['track']=='natural'];groups=collections.defaultdict(list)
    for ident in natural:groups[tasks[ident]['family'].split('#')[0]].append(ident)
    rng=random.Random(20261114);estimates=[];names=sorted(groups)
    for _ in range(10000):
        sample=[i for group in rng.choices(names,k=len(names)) for i in groups[group]]
        estimates.append(statistics.mean(int(first['grounded-flat',i]['score']['complete_proxy'])-int(first['legacy-hybrid',i]['score']['complete_proxy']) for i in sample))
    estimates.sort()
    mismatches=[i for i in ids if first['grounded-flat',i]['result']['diagnostics'].get('candidate_ids')!=first['grounded-relate',i]['result']['diagnostics'].get('candidate_ids')]
    report={'deterministic_repetition_failures':unstable,'paired':diffs,'native_flat_candidate_order_differences':mismatches,
            'native_flat_target_delivery_differences':[i for i in ids if first['grounded-flat',i]['score']['complete_proxy']!=first['grounded-relate',i]['score']['complete_proxy']],
            'natural_paired_difference_flat_minus_legacy':{'positive_tasks':len(natural),'file_clusters':len(groups),'cluster_bootstrap_95':[estimates[250],estimates[9749]],'repetitions':10000,'labels':'provisional; few file clusters, descriptive only'},
            'zero_observed_native_regression_one_sided_95_upper_bound':1-.05**(1/len(natural)),
            'zero_regression_note':'Binomial diagnostic, not a population noninferiority result. Margin is .03; this sample cannot establish it with high confidence.',
            'max_context_bytes':max(r['score'].get('bytes',0) for r in rows),'max_context_characters':max(r['score'].get('characters',0) for r in rows)}
    a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

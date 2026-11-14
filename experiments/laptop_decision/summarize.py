"""Collect laptop evidence into one machine-readable decision summary and markdown tables.

Reads only committed files under experiments/laptop_decision/evidence. Stdlib only.
"""
import gzip, json
from pathlib import Path

E = Path(__file__).resolve().parent / 'evidence'
L = E / 'laptop-results'


def read(path):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text())
    with gzip.open(str(path) + '.gz', 'rt') as f:
        return json.load(f)


def gate(adopt_speed, adopt_rss, quality_ok, correctness_ok):
    return {'engine_gates_pass_and_required_integrations_supported': correctness_ok, 'quality_noninferior': quality_ok, 'p95_speedup_ge_1_20': adopt_speed,
            'rss_ratio_le_1_10': adopt_rss, 'qualifies': bool(correctness_ok and quality_ok and adopt_speed and adopt_rss)}


def main():
    out = {'labels': 'MODEL-AUTHORED, NOT HUMAN REVIEWED', 'host': read(E.parent / 'registration/host-environment.json')}
    cmds = read(L / 'correctness-commands.json') + read(L / 'quality-commands.json') + read(L / 'performance-commands.json')
    out['commands'] = [{k: c[k] for k in ('name', 'returncode', 'seconds')} for c in cmds]
    out['preservation'] = read(L / 'preservation.json')
    mech = read(L / 'mechanics/mechanics.json')
    out['engine_gates'] = {e: {'pass': sum(c['status'] == 'PASS' for c in v['checks']), 'total': len(v['checks']),
                               'failed': [c['gate'] for c in v['checks'] if c['status'] != 'PASS']} for e, v in mech['engines'].items()}
    out['engine_not_established'] = mech['not_established']
    out['phase3_restart_retraction'] = read(L / 'phase3-demo/summary.json')
    demo = read(L / 'reliable-memory-demo/demo.json')
    out['canonical_workflow'] = {k: demo[k] for k in ('status', 'steps', 'separate_process_per_step', 'active_positive_contributions', 'rule_approval')}
    rm = {}
    for split in ('dev', 'heldout'):
        s = read(L / f'reliable-memory-{split}/summary.json')
        c = read(L / f'reliable-memory-{split}/comparison.json')
        rm[split] = {'arms': {a: {'natural_complete': v['natural']['complete_proxy'], 'natural_positive': v['natural']['positive_tasks'],
                                  'all_complete': v['all']['complete_proxy'], 'all_positive': v['all']['positive_tasks'], 'natural_mrr': v['natural']['mrr'],
                                  'failures': v['all']['failures'], 'citation_failures': v['all']['citation_failures'],
                                  'warm_samples': v['all']['latency_samples'], 'warm_p50_ms': v['all']['p50_ms'], 'warm_p95_ms': v['all']['p95_ms']}
                              for a, v in s['arms'].items()},
                     'process_peak_rss_kib': s['resources']['process_peak_rss_kib'],
                     'native_flat_delivery_differences': c['native_flat_target_delivery_differences'],
                     'native_flat_candidate_order_differences': c['native_flat_candidate_order_differences'],
                     'paired': c['paired'], 'flat_minus_legacy_natural_cluster_bootstrap_95': c['natural_paired_difference_flat_minus_legacy']['cluster_bootstrap_95'],
                     'deterministic_repetition_failures': c['deterministic_repetition_failures'], 'max_context_bytes': c['max_context_bytes']}
    out['reliable_memory'] = rm
    out['replication_vs_committed'] = {k: {'compared': v['compared'], 'differences': len(v['differences'])} for k, v in read(L / 'replication-comparison.json').items()}
    out['cold_cli'] = read(L / 'cold-cli/summary.json')['profiles']
    out['cold_cli_determinism_excluding_as_of'] = read(L / 'cold-cli/determinism-check.json')['all_identical']
    bk = read(E / 'bakeoff-report/summary.json')
    out['bakeoff'] = {'tracks': {tr: {arm: {'complete': m['complete'], 'delivered_clauses': m['delivered_clauses'], 'mrr': m['mrr'], 'errors': m['errors'],
                                             'e2e_p95_ms': m.get('e2e_p95_ms'),
                                             'lower_95': v['paired_family_bootstrap'][arm]['one_sided_95_lower'],
                                             'noninferior': v['paired_family_bootstrap'][arm]['provisional_noninferior']}
                                       for arm, m in v['arms'].items()} for tr, v in bk['tracks'].items()},
                      'load': {n: {k: p.get(k) for k in ('status', 'n')} | {'p95_ms': ((p.get('latency') or {}).get('e2e_ms') or {}).get('p95'),
                                                                          'peak_rss_mib': (p.get('combined_peak_rss_bytes') or 0) / 1048576}
                               for n, p in bk['performance'].items()}}
    load = out['bakeoff']['load']
    ok_corr = all(v['pass'] == v['total'] for v in out['engine_gates'].values())
    gates = {}
    for arm in 'BCD':
        nonin = out['bakeoff']['tracks']['matched'][f'{arm}-flat']['noninferior']
        for g, r in ((1, 1), (10, 1), (100, 1), (1, 4), (10, 4), (100, 4)):
            a, c = load[f'A-{g}-{r}'], load[f'{arm}-{g}-{r}']
            if a['status'] != 'COMPLETE' or c['status'] != 'COMPLETE':
                gates[f'{arm}-{g}-{r}'] = {'status': f"A {a['status']} / {arm} {c['status']}", 'qualifies': False}
                continue
            speed, rss = a['p95_ms'] / c['p95_ms'], c['peak_rss_mib'] / a['peak_rss_mib']
            gates[f'{arm}-{g}-{r}'] = {'speedup_vs_A': round(speed, 2), 'rss_ratio_vs_A': round(rss, 2),
                                       **gate(speed >= 1.2, rss <= 1.1, nonin, ok_corr and not out['engine_not_established'])}
    out['bakeoff_adoption_gates'] = gates
    flat, rel = rm['heldout']['arms']['grounded-flat'], rm['heldout']['arms']['grounded-relate']
    out['grounded_relate_vs_flat'] = {
        'delivery_identical_dev_and_heldout': not rm['dev']['native_flat_delivery_differences'] and not rm['heldout']['native_flat_delivery_differences'],
        'warm_p95_speedup': flat['warm_p95_ms'] / rel['warm_p95_ms'],
        'cold_p95_speedup': out['cold_cli']['grounded-flat']['p95_ms'] / out['cold_cli']['grounded-relate']['p95_ms'],
        'cold_peak_rss_ratio': out['cold_cli']['grounded-relate']['max_child_peak_rss_kib'] / out['cold_cli']['grounded-flat']['max_child_peak_rss_kib'],
        'qualifies_for_default': False,
        'reason': 'Equal labeled delivery, slower warm and cold p95 (no >=1.20x speedup); canonical refresh/replay still application-owned.'}
    qa = E / 'qa-summary/summary.json'
    out['qa_trials'] = read(qa) if qa.exists() else 'pending'
    (E / 'decision-summary.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('engine_gates', 'replication_vs_committed', 'bakeoff_adoption_gates', 'grounded_relate_vs_flat')}, indent=1))


if __name__ == '__main__':
    main()

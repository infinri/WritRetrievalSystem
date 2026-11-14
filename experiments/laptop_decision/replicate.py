"""Laptop replication orchestrator (runs inside the dev container from the repo root).

Stages: `correctness`, `quality`, `performance`, `compare`. Every command, return
code, duration and log is persisted; failures are recorded, never skipped silently.
Run stages sequentially; performance must run with no other benchmark jobs.
"""
import argparse, gzip, hashlib, json, subprocess, sys, time
from pathlib import Path

PY = sys.executable
OFF = [PY, 'scripts/offline_run.py']
MODEL = 'data/model'
TOOLS = 'data/bakeoff-tools'
NEO = TOOLS + '/neo4j-community-5.26.0'
REPO = 'data/Writ-public'
RUST = 'data/rust-target/release/writ-db-thin-client'
ARMS = 'A-lexical,A-vector,A-hybrid,A-connected,B-flat,B-connected,C-flat,C-connected,D-flat,D-connected'


def stage_commands(stage, w, out):
    if stage == 'correctness':
        return [
            ('pytest', OFF + ['-m', 'pytest', '-q']),
            ('unittest-original-demo', OFF + ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
            ('phase3-reliable-history', OFF + ['-m', 'writ_retrieval.evaluation.reliable_history', '--repo', REPO, '--model-dir', MODEL,
                                               '--work-dir', f'{w}/phase3-history', '--output', f'{out}/phase3-history']),
            ('phase3-reliable-demo', OFF + ['-m', 'writ_retrieval.evaluation.reliable_demo', '--repo', REPO, '--model-dir', MODEL,
                                            '--work-dir', f'{w}/phase3-demo', '--output', f'{out}/phase3-demo']),
            ('reliable-memory-audit', OFF + ['-m', 'experiments.reliable_memory.audit', '--repo', REPO, '--out', f'{out}/passage-provenance.json']),
            ('reliable-memory-demo', OFF + ['-m', 'experiments.reliable_memory.demo', '--repo', REPO, '--model-dir', MODEL,
                                            '--work-dir', f'{w}/rm-demo', '--out', f'{out}/reliable-memory-demo']),
            ('db-offload-capability', [PY, '-m', 'experiments.db_offload.capability', '--output', f'{out}/capability.json', '--neo4j-home', NEO]),
            ('db-offload-mechanics', [PY, '-m', 'experiments.db_offload.recovery.mechanics', '--model-dir', MODEL, '--neo4j-home', NEO, '--ffi', TOOLS,
                                      '--rust', RUST, '--work', f'{w}/mechanics', '--output', f'{out}/mechanics']),
        ]
    if stage == 'quality':
        cmds = []
        for split, tag in (('development', 'dev'), ('heldout', 'heldout')):
            cmds.append((f'reliable-memory-{tag}', OFF + ['-m', 'experiments.reliable_memory.run', '--model-dir', MODEL, '--work-dir', f'{w}/rm-{tag}',
                                                         '--out', f'{out}/reliable-memory-{tag}', '--split', split]))
            cmds.append((f'reliable-memory-{tag}-analyze', OFF + ['-m', 'experiments.reliable_memory.analyze', '--results', f'{out}/reliable-memory-{tag}/queries.jsonl.gz',
                                                                 '--out', f'{out}/reliable-memory-{tag}/comparison.json']))
        for track in ('matched', 'best'):
            cmds.append((f'db-offload-heldout-{track}', [PY, '-m', 'experiments.db_offload.run', '--partition', 'heldout', '--selection',
                                                         'experiments/db_offload/protocol/selection.json', '--track', track, '--arms', ARMS, '--model-dir', MODEL,
                                                         '--neo4j-home', NEO, '--work', f'{w}/bakeoff-{track}', '--output', f'{out}/db-offload-heldout-{track}']))
        return cmds
    if stage == 'performance':
        return [
            ('cold-cli', [PY, '-m', 'experiments.laptop_decision.cold_cli', '--store', f'{w}/rm-heldout/store-a0e0e41', '--model-dir', MODEL,
                          '--cache-root', f'{w}/cold-cli-cache', '--out', f'{out}/cold-cli']),
            ('db-offload-load-suite', [PY, '-m', 'experiments.db_offload.recovery.suite', '--model-dir', MODEL, '--neo4j-home', NEO,
                                       '--work', f'{w}/load-suite', '--output', f'{out}/load-suite']),
        ]
    raise ValueError(stage)


def preservation(out):
    report = {}
    for reg in ('experiments/db_offload/protocol/preserved.json', 'experiments/reliable_memory/protocol/preserved.json'):
        entries = json.loads(Path(reg).read_text())
        changed = [n for n, d in entries.items() if not Path(n).exists() or hashlib.sha256(Path(n).read_bytes()).hexdigest() != d]
        report[reg] = {'count': len(entries), 'changed': changed}
    (out / 'preservation.json').write_text(json.dumps(report, indent=2) + '\n')
    return all(not v['changed'] for v in report.values())


def compare(out):
    """Laptop replication vs committed evidence, per task/arm (opened sets: regression only)."""
    result = {}
    for tag, committed in (('dev', 'development'), ('heldout', 'heldout')):
        path = out / f'reliable-memory-{tag}/queries.jsonl.gz'
        if not path.exists():
            result[tag] = 'missing laptop run'
            continue
        def first(p):
            return {(r['task_id'], r['arm']): r for r in map(json.loads, gzip.open(p, 'rt')) if r['repeat'] == 0}
        new, old = first(path), first(Path(f'experiments/reliable_memory/evidence/{committed}/queries.jsonl.gz'))
        diffs = []
        for k in sorted(old):
            a, b = old[k], new.get(k)
            if b is None:
                diffs.append({'key': k, 'issue': 'missing'})
                continue
            sa, sb = a['score'], b['score']
            same_payload = a['result'].get('payload') == b['result'].get('payload')
            if sa.get('complete_proxy') != sb.get('complete_proxy') or sa.get('delivered_ids') != sb.get('delivered_ids') or not same_payload:
                diffs.append({'key': k, 'complete_proxy': [sa.get('complete_proxy'), sb.get('complete_proxy')],
                              'delivered_ids_equal': sa.get('delivered_ids') == sb.get('delivered_ids'), 'payload_equal': same_payload})
        result[tag] = {'compared': len(old), 'differences': diffs}
    (out / 'replication-comparison.json').write_text(json.dumps(result, indent=2, default=list) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('correctness', 'quality', 'performance', 'compare'))
    p.add_argument('--work', type=Path, default=Path('data/laptop-work'))
    p.add_argument('--out', type=Path, default=Path('data/laptop-results'))
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.stage == 'compare':
        return compare(a.out)
    log = a.out / f'{a.stage}-commands.json'
    if log.exists():
        raise SystemExit('stage already recorded; use fresh --work/--out')
    if a.stage == 'correctness' and not preservation(a.out):
        raise SystemExit('preserved evidence drift')
    records = []
    for name, cmd in stage_commands(a.stage, a.work, a.out):
        start = time.perf_counter()
        with (a.out / f'{name}.log').open('w') as f:
            try:
                code, err = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=9000).returncode, None
            except Exception as e:
                code, err = -1, f'{type(e).__name__}: {e}'
        records.append({'name': name, 'command': cmd, 'returncode': code, 'error': err, 'seconds': time.perf_counter() - start,
                        'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        log.write_text(json.dumps(records, indent=2) + '\n')
        print(f'{name}: rc={code} {records[-1]["seconds"]:.0f}s', flush=True)


if __name__ == '__main__':
    main()

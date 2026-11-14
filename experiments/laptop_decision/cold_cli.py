"""Fresh-process (cold CLI) end-to-end timing of the supported read-only context commands.

Each sample is a new Python process: interpreter start, network deny, ONNX model
load, store open, generation/projection validation, query inference, retrieval,
rendering and exit. Index caches are prebuilt by warm-up invocations, so this is
cold-process / warm-disk. Distinct from the persistent warm measurements in run.py.
"""
import argparse, gzip, hashlib, json, os, random, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    'legacy-hybrid': lambda a, t, c: [sys.executable, '-m', 'writ_retrieval.reliable.agent', '--store', str(a.store), 'context',
                                      '--project', t['project'], '--model-dir', str(a.model_dir), '--cache-dir', str(c), '--arm', 'hybrid', t['query']],
    'grounded-flat': lambda a, t, c: [sys.executable, '-m', 'writ_retrieval.reliable.grounded_cli', '--store', str(a.store), '--cache-dir', str(c),
                                      '--model-dir', str(a.model_dir), '--project', t['project'], '--backend', 'flat', t['query']],
    'grounded-relate': lambda a, t, c: [sys.executable, '-m', 'writ_retrieval.reliable.grounded_cli', '--store', str(a.store), '--cache-dir', str(c),
                                        '--model-dir', str(a.model_dir), '--project', t['project'], '--backend', 'relate', t['query']],
}
SEED = 20261114


def run(cmd):
    import tempfile
    with tempfile.TemporaryFile() as o, tempfile.TemporaryFile() as e:
        start = time.perf_counter()
        proc = subprocess.Popen(cmd, stdout=o, stderr=e, env={**os.environ, 'OMP_NUM_THREADS': '2'})
        _, status, usage = os.wait4(proc.pid, 0)
        elapsed = (time.perf_counter() - start) * 1000
        proc.returncode = os.waitstatus_to_exitcode(status)
        o.seek(0); e.seek(0)
        return proc.returncode, o.read().decode(), e.read().decode()[-2000:], elapsed, usage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--store', type=Path, required=True, help='a0e0e41 store produced by the heldout run (opened read-only by the CLIs)')
    p.add_argument('--model-dir', type=Path, required=True)
    p.add_argument('--cache-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repetitions', type=int, default=3)
    p.add_argument('--warmups', type=int, default=2)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    tasks = [t for t in json.loads((ROOT / 'experiments/reliable_memory/fixtures/tasks.json').read_text())['tasks']
             if t['split'] == 'heldout' and t['track'] == 'natural' and t['corpus_revision'].startswith('a0e0e41') and t['project'] == 'writ-public']
    caches = {name: a.cache_root / name for name in PROFILES}
    warm = []
    for name in PROFILES:  # builds each profile's derived caches; recorded, not scored
        for i in range(a.warmups):
            code, out, err, ms, _ = run(PROFILES[name](a, tasks[i % len(tasks)], caches[name]))
            warm.append({'profile': name, 'returncode': code, 'elapsed_ms': ms, 'stderr': err if code else None})
    rng = random.Random(SEED)
    plan = [(t['id'], name, r) for r in range(a.repetitions) for t in tasks for name in PROFILES]
    rng.shuffle(plan)
    by_id = {t['id']: t for t in tasks}
    rows = []
    for order, (tid, name, r) in enumerate(plan):
        code, out, err, ms, usage = run(PROFILES[name](a, by_id[tid], caches[name]))
        rows.append({'order': order, 'task': tid, 'profile': name, 'repeat': r, 'returncode': code, 'elapsed_ms': ms,
                     'child_cpu_s': usage.ru_utime + usage.ru_stime, 'child_peak_rss_kib': usage.ru_maxrss,
                     'payload_sha256': hashlib.sha256(out.encode()).hexdigest() if code == 0 else None, 'payload_bytes': len(out.encode()),
                     'stderr': err if code else None})
    with gzip.GzipFile(filename=str(a.out / 'samples.jsonl.gz'), mode='wb', mtime=0) as f:
        for r in rows:
            f.write((json.dumps(r, sort_keys=True) + '\n').encode())
    import statistics
    def pct(xs, q):
        xs = sorted(xs)
        k = (len(xs) - 1) * q
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
    summary = {}
    for name in PROFILES:
        ok = [r['elapsed_ms'] for r in rows if r['profile'] == name and r['returncode'] == 0]
        summary[name] = {'samples': len(ok), 'failures': sum(r['profile'] == name and r['returncode'] != 0 for r in rows),
                         'p50_ms': pct(ok, .5) if ok else None, 'p95_ms': pct(ok, .95) if ok else None, 'mean_ms': statistics.mean(ok) if ok else None,
                         'mean_child_cpu_s': statistics.mean(r['child_cpu_s'] for r in rows if r['profile'] == name),
                         'max_child_peak_rss_kib': max(r['child_peak_rss_kib'] for r in rows if r['profile'] == name),
                         'deterministic_payloads': len({(r['task'], r['payload_sha256']) for r in rows if r['profile'] == name and r['returncode'] == 0}) == len({r['task'] for r in rows if r['profile'] == name and r['returncode'] == 0})}
    (a.out / 'summary.json').write_text(json.dumps({
        'tasks': len(tasks), 'repetitions': a.repetitions, 'warmups_per_profile': a.warmups, 'seed': SEED, 'warmup_runs': warm,
        'profiles': summary,
        'note': 'Cold process, warm disk/OS page cache, prebuilt derived caches; sequential, randomized interleaving; no other benchmark jobs. '
                'Per-process peak RSS/CPU via wait4 (includes ONNX model, embedded Relate). Not a persistent-service or remote measurement.'}, indent=2) + '\n')


if __name__ == '__main__':
    main()

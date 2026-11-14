"""Capture the laptop/container environment and input hashes for the registration."""
import argparse, hashlib, json, os, platform, resource, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = [
    'experiments/reliable_memory/fixtures/tasks.json',
    'experiments/reliable_memory/fixtures/history-a0e0e41.json',
    'experiments/reliable_memory/fixtures/history-b60bf33.json',
    'experiments/reliable_memory/protocol/settings.json',
    'experiments/reliable_memory/protocol/frozen.json',
    'experiments/reliable_memory/protocol/preserved.json',
    'experiments/reliable_memory/evidence/heldout/queries.jsonl.gz',
    'experiments/reliable_memory/evidence/development/queries.jsonl.gz',
    'experiments/reliable_memory/agent.py',
    'experiments/db_offload/protocol/settings.json',
    'experiments/db_offload/protocol/selection.json',
    'experiments/db_offload/protocol/frozen.json',
    'experiments/db_offload/protocol/preserved.json',
    'src/writ_retrieval/shared/budget.json',
    'requirements-validated.txt',
    'experiments/db_offload/requirements.txt',
    'experiments/laptop_decision/qa_trials.py',
    'experiments/laptop_decision/grade.py',
    'experiments/laptop_decision/cold_cli.py',
    'experiments/laptop_decision/replicate.py',
]


def sh(*args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f'unavailable: {e}'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model-dir', type=Path, default=Path('data/model'))
    p.add_argument('--tools', type=Path, default=Path('data/bakeoff-tools'))
    a = p.parse_args()
    files = {}
    for name in INPUTS:
        path = ROOT / name
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'missing'
    model = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.model_dir.glob('*')) if f.is_file()}
    mem = Path('/proc/meminfo').read_text().splitlines()[:3]
    cg = {}
    for name in ('memory.max', 'cpu.max', 'pids.max'):
        f = Path('/sys/fs/cgroup') / name
        cg[name] = f.read_text().strip() if f.exists() else None
    env = {
        'source_head': sh('git', '-C', str(ROOT), 'rev-parse', 'HEAD'),
        'source_status_porcelain': sh('git', '-C', str(ROOT), 'status', '--porcelain'),
        'python': platform.python_version(), 'executable': sys.executable,
        'platform': platform.platform(), 'machine': platform.machine(),
        'cpu_model': next((x.split(':', 1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')), None),
        'cpu_count_visible': os.cpu_count(), 'affinity': len(os.sched_getaffinity(0)),
        'meminfo': mem, 'cgroup_limits': cg,
        'rlimits': {n: resource.getrlimit(getattr(resource, n)) for n in ('RLIMIT_AS', 'RLIMIT_NOFILE', 'RLIMIT_NPROC')},
        'java': sh('java', '-version'), 'rustc': sh('rustc', '--version'), 'cargo': sh('cargo', '--version'),
        'packages': sh(sys.executable, '-m', 'pip', 'freeze').splitlines(),
        'model_sha256': model,
        'tool_archives': json.loads((a.tools / 'archives.json').read_text()) if (a.tools / 'archives.json').exists() else None,
        'thread_env': {k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'RAYON_NUM_THREADS')},
        'input_sha256': files,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(env, indent=2) + '\n')


if __name__ == '__main__':
    main()

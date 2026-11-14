"""Score recorded QA trials: mechanical citation checks, blinded model-assisted review,
blinded human-review materials and a summary. Model-assisted review is NOT human review.

Runs on the host (model-assisted review uses the same authorized CLI as qa_trials.py).
"""
import argparse, csv, gzip, hashlib, json, random, re, statistics, subprocess, time
from pathlib import Path
from .qa_trials import ARMS, ROOT, SETTINGS, call, canonical, load_inputs, summarize_events

GRADER_MODEL = 'claude-opus-5-5'
GRADER_EFFORT = 'low'
GRADER_SEED = 20261115
REVISIONS = ('a0e0e413e3b20082a85e7d75c58b45b0ba09b903', 'b60bf33983b96ccfbc5c1464dcf32687c789703e')
HEX = re.compile(r'(?<![0-9a-fA-F])[0-9a-f]{7,40}(?![0-9a-fA-F])')
RUBRIC = {
    'gold_content_conveyed': 'Positive task only: does the answer convey the substance of the labelled passage? yes / partial / no; not_applicable for expected-unknown tasks.',
    'answer_correctness': 'Relative to the labelled passage and supplied context: correct / partially_correct / incorrect / not_applicable (expected-unknown tasks).',
    'appropriate_uncertainty': 'yes if the answer states unknowns where the supplied context does not warrant an answer (and does not abstain when it does); otherwise no.',
    'warranted_unknown': 'Expected-unknown task only: does the answer decline to assert the requested content / missing confirmation, or correctly say it is unavailable? yes / no; not_applicable for positive tasks.',
    'unsupported_assertions': 'Integer: substantive factual claims about the project that are supported neither by the supplied context nor by the label.',
    'citation_correctness': 'correct (cited source/revision matches supplied evidence for the claims), incorrect, or none (no citation).',
}
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': list(RUBRIC) + ['rationale'],
          'properties': {
              'gold_content_conveyed': {'enum': ['yes', 'partial', 'no', 'not_applicable']},
              'answer_correctness': {'enum': ['correct', 'partially_correct', 'incorrect', 'not_applicable']},
              'appropriate_uncertainty': {'enum': ['yes', 'no']},
              'warranted_unknown': {'enum': ['yes', 'no', 'not_applicable']},
              'unsupported_assertions': {'type': 'integer', 'minimum': 0},
              'citation_correctness': {'enum': ['correct', 'incorrect', 'none']},
              'rationale': {'type': 'string', 'maxLength': 600}}}
GRADER_SYSTEM = ('You are a strict, blinded reviewer applying a fixed rubric to one answer. You do not know which retrieval system, if any, '
                 'produced the context. Labels are provisional, model-authored proxies. Judge only from the question, the label, the supplied '
                 'context and the answer. Return only the structured result.')


def blind(packet):
    if not packet:
        return None
    p = json.loads(packet)
    for k in ('encoder_id', 'selection_policy', 'projection'):
        p.pop(k, None)
    if isinstance(p.get('snapshot'), dict):
        p['snapshot'].pop('generation', None)
    return p


def blind_full(packet):
    """Corrected (Amendment 2): the exact packet the answerer saw; only the condition name is masked."""
    if not packet:
        return None
    p = json.loads(packet)
    if isinstance(p.get('projection'), dict) and 'backend' in p['projection']:
        p['projection']['backend'] = '[condition-redacted]'
    return p


def build_prompt(task, packet, answer, mode):
    label = ({'expected_unknown': True, 'note': 'No warranted answer passage exists in the registered permitted sources for this request.'}
             if task['expected_unknown'] else
             {'expected_unknown': False, 'gold': [{k: g[k] for k in ('answer_text', 'uri', 'revision')} for g in task['gold']]})
    shown = blind(packet) if mode == 'stripped' else blind_full(packet)
    return ('Rubric:\n' + json.dumps(RUBRIC, indent=1) + '\n\nQuestion and evidence requirements:\n' +
            canonical({'question': task['query'], 'evidence_requirements': task['request']}) +
            '\n\nProvisional label:\n' + canonical(label) +
            '\n\nContext supplied to the answerer:\n' + (canonical(shown) if packet else '(none)') +
            '\n\nAnswer to review:\n' + answer + '\n')


def completed(trial_dir):
    rows = {}
    for line in (trial_dir / 'attempts.jsonl').open():
        r = json.loads(line)
        if r['error'] is None:
            rows.setdefault((r['task'], r['arm'], r['repeat']), r)
    return rows


def retrieval_scores():
    out = {}
    for line in gzip.open(ROOT / 'experiments/reliable_memory/evidence/heldout/queries.jsonl.gz', 'rt'):
        r = json.loads(line)
        if r['repeat'] == 0:
            out[r['task_id'], r['arm']] = r['score']
    return out


def mechanical(task, arm, packet, output):
    cited = set()
    for token in HEX.findall(output or ''):
        for rev in REVISIONS:
            if rev.startswith(token):
                cited.add(rev)
    supported = {rev for rev in REVISIONS if rev in (packet or '') or rev in canonical(task['request'])}
    return {'cited_revisions': sorted(cited),
            'cites_task_revision': task['corpus_revision'] in cited if task['gold'] else None,
            'cites_unsupplied_revision': bool(cited - supported),
            'cites_other_snapshot': bool(cited - {task['corpus_revision']})}


def cmd_review(a):
    tasks, _, packets = load_inputs()
    by_id = {t['id']: t for t in tasks}
    rows = completed(a.trials)
    keys = sorted(rows)
    random.Random(GRADER_SEED).shuffle(keys)
    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / 'model-review.jsonl'
    done = {json.loads(x)['trial_key'] for x in log.open()} if log.exists() else set()
    (a.out / 'model-review-protocol.json').write_text(json.dumps({'grader_model_requested': GRADER_MODEL, 'effort': GRADER_EFFORT, 'seed': GRADER_SEED,
        'system': GRADER_SYSTEM, 'rubric': RUBRIC, 'schema': SCHEMA, 'context_mode': a.context,
        'blinding': ('arm/repeat hidden; backend metadata stripped from context; an empty context still reveals the no-history arm' if a.context == 'stripped' else
                     'Amendment 2: arm/repeat hidden; complete packet as supplied to the answerer, only projection.backend masked; empty context and legacy/grounded format still reveal some conditions'),
        'status': 'MODEL-ASSISTED REVIEW, NOT INDEPENDENT HUMAN REVIEW', 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + '\n')
    n = 0
    for key in keys:
        tag = '|'.join(map(str, key))
        if tag in done:
            continue
        if a.limit is not None and n >= a.limit:
            break
        task_id, arm, _ = key
        task = by_id[task_id]
        packet = '' if arm == 'none' else packets[task_id][arm]
        prompt = build_prompt(task, packet, rows[key]['output'], a.context)
        events, stderr, code, elapsed, _ = call_grader(prompt)
        s = summarize_events(events)
        result = next((e for e in reversed(events) if e.get('type') == 'result'), {})
        verdict = result.get('structured_output')
        if verdict is None:
            try:
                verdict = json.loads(s['result_text'])
            except Exception:
                verdict = None
        row = {'trial_key': tag, 'verdict': verdict, 'error': None if verdict else {'returncode': code, 'stderr': stderr[-1000:], 'result_text': s['result_text']},
               'resolved_model': s['resolved_model_init'], 'usage': s['usage'], 'reported_cost_usd': s['reported_cost_usd'], 'cost_basis': s['cost_basis'],
               'elapsed_ms': elapsed, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'review': 'MODEL_ASSISTED_NOT_HUMAN'}
        with log.open('a') as f:
            f.write(canonical(row) + '\n')
        n += 1
        print(f"review {tag:40s} {'ok' if verdict else 'ERR'} {elapsed/1000:5.1f}s", flush=True)
        if not verdict and (s['api_error_status'] in (429, 529) or 'limit' in (s['result_text'] or '').lower()):
            print('stopping: quota/rate limit reported', flush=True)
            break


def cmd_inputs(a):
    """Regenerate grader inputs for a review log and verify them against the recorded prompt hashes."""
    tasks, _, packets = load_inputs()
    by_id = {t['id']: t for t in tasks}
    rows = completed(a.trials)
    a.out.mkdir(parents=True, exist_ok=True)
    mismatched = 0
    n = 0
    with gzip.GzipFile(filename=str(a.out / f'grader-inputs-{a.context}.jsonl.gz'), mode='wb', mtime=0) as f:
        for line in (a.review / 'model-review.jsonl').open():
            r = json.loads(line)
            t, arm, rep = r['trial_key'].split('|')
            key = (t, arm, int(rep))
            prompt = build_prompt(by_id[t], '' if arm == 'none' else packets[t][arm], rows[key]['output'], a.context)
            ok = hashlib.sha256(prompt.encode()).hexdigest() == r['prompt_sha256']
            mismatched += not ok
            n += 1
            f.write((canonical({'trial_key': r['trial_key'], 'prompt': prompt, 'prompt_sha256_matches_review_log': ok}) + '\n').encode())
    print(json.dumps({'context': a.context, 'prompts': n, 'hash_mismatches': mismatched}))
    if mismatched:
        raise SystemExit('regenerated grader inputs do not match the recorded hashes')


def call_grader(prompt):
    import os, shutil, tempfile
    env = {k: v for k, v in os.environ.items() if k not in ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT')}
    cwd = tempfile.mkdtemp(prefix='qa-')
    args = ['claude', *SETTINGS['cli_flags'], '--model', GRADER_MODEL, '--effort', GRADER_EFFORT, '--system-prompt', GRADER_SYSTEM,
            '--json-schema', json.dumps(SCHEMA)]
    start = time.perf_counter()
    try:
        p = subprocess.run(args, input=prompt, capture_output=True, text=True, cwd=cwd, env=env, timeout=300)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        out, err, code = '', 'timeout', -1
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    events = []
    for line in out.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({'unparsed': line})
    return events, err, code, (time.perf_counter() - start) * 1000, cwd


def cmd_materials(a):
    tasks, _, packets = load_inputs()
    by_id = {t['id']: t for t in tasks}
    rows = completed(a.trials)
    keys = sorted(rows)
    random.Random(GRADER_SEED + 1).shuffle(keys)
    a.out.mkdir(parents=True, exist_ok=True)
    key_rows = []
    with (a.out / 'human-review.csv').open('w', newline='') as f, gzip.GzipFile(filename=str(a.out / 'human-review-packets.jsonl.gz'), mode='wb', mtime=0) as g:
        w = csv.writer(f)
        w.writerow(['anonymous_id', 'task', 'question', 'expected_unknown', 'label_answer_text', 'label_revision', 'answer', *RUBRIC, 'reviewer', 'reviewed_at', 'notes'])
        for i, key in enumerate(keys):
            t = by_id[key[0]]
            aid = f'resp-{i + 1:03d}'
            w.writerow([aid, t['id'], t['query'], t['expected_unknown'], ' || '.join(x['answer_text'] for x in t['gold']),
                        ' '.join(x['revision'] for x in t['gold']), rows[key]['output'], *[''] * len(RUBRIC), '', '', ''])
            g.write((canonical({'anonymous_id': aid, 'task': t['id'], 'question': t['query'], 'requirements': t['request'],
                                'context': blind('' if key[1] == 'none' else packets[key[0]][key[1]]), 'answer': rows[key]['output']}) + '\n').encode())
            key_rows.append({'anonymous_id': aid, 'task': key[0], 'arm': key[1], 'repeat': key[2]})
    (a.out / 'blind-key.json').write_text(json.dumps(key_rows, indent=1) + '\n')
    (a.out / 'README.md').write_text(
        '# Blinded response review (pending)\n\nNo human has reviewed these responses. `human-review.csv` lists every completed trial in a shuffled order '
        '(seed %d) without arm or repetition. Fill each rubric column from RUBRIC below, plus your real name/date. Context copies in '
        '`human-review-packets.jsonl.gz` have backend metadata removed; an empty context still reveals the no-history condition, and format may hint at '
        'legacy vs grounded. Keep `blind-key.json` closed until all rows are complete. Labels are model-authored and unreviewed: record label disagreements in notes.\n\n'
        '## Rubric\n\n' % (GRADER_SEED + 1) + '\n'.join(f'- **{k}**: {v}' for k, v in RUBRIC.items()) + '\n')


CLASSES = {'section-question': 'natural-language', 'historical': 'historical', 'exact-source': 'explicit-source',
           'missing-owner-confirmation': 'unknown-control', 'project-isolation': 'unknown-control'}
CORRECT = {'correct': 1.0, 'partially_correct': .5, 'incorrect': 0.0}


def load_review(path):
    out, meta = {}, []
    for line in (path / 'model-review.jsonl').open():
        r = json.loads(line)
        meta.append(r)
        if r['verdict']:
            t, arm, rep = r['trial_key'].split('|')
            out[t, arm, int(rep)] = r['verdict']
    return out, meta


def answer_score(task, v):
    """Primary per-answer score: positives -> answer_correctness (1/.5/0); unknown controls -> warranted_unknown (1/0)."""
    if task['expected_unknown']:
        return 1.0 if v['warranted_unknown'] == 'yes' else 0.0
    return CORRECT.get(v['answer_correctness'], 0.0)


def review_tables(tasks, verdicts):
    by_id = {t['id']: t for t in tasks}
    table = {}
    for cls in ('natural-language', 'historical', 'explicit-source', 'unknown-control', 'all-positive', 'all'):
        ids = [t['id'] for t in tasks if cls == 'all' or CLASSES[t['category']] == cls or (cls == 'all-positive' and not t['expected_unknown'])]
        table[cls] = {}
        for arm in ARMS:
            vs = [(by_id[k[0]], v) for k, v in verdicts.items() if k[1] == arm and k[0] in ids]
            pos = [v for t, v in vs if not t['expected_unknown']]
            table[cls][arm] = {
                'tasks': len(ids), 'answers': len(vs),
                'mean_score': round(statistics.mean(answer_score(t, v) for t, v in vs), 4) if vs else None,
                'correct': sum(v['answer_correctness'] == 'correct' for v in pos),
                'partially_correct': sum(v['answer_correctness'] == 'partially_correct' for v in pos),
                'incorrect': sum(v['answer_correctness'] == 'incorrect' for v in pos),
                'gold_conveyed_yes': sum(v['gold_content_conveyed'] == 'yes' for v in pos),
                'warranted_unknown_yes': sum(v['warranted_unknown'] == 'yes' for t, v in vs if t['expected_unknown']),
                'appropriate_uncertainty_yes': sum(v['appropriate_uncertainty'] == 'yes' for _, v in vs),
                'answers_with_unsupported_assertions': sum(v['unsupported_assertions'] > 0 for _, v in vs),
                'unsupported_assertions_total': sum(v['unsupported_assertions'] for _, v in vs),
                'citation_correct': sum(v['citation_correctness'] == 'correct' for _, v in vs),
                'citation_incorrect': sum(v['citation_correctness'] == 'incorrect' for _, v in vs),
                'citation_none': sum(v['citation_correctness'] == 'none' for _, v in vs)}
    return table


def paired(tasks, verdicts, reference, metric):
    """Task-level paired differences: repetitions are averaged within each task (paired by task),
    then a task-cluster bootstrap (2,000 draws) gives a descriptive 95% interval."""
    rng = random.Random(GRADER_SEED)
    out = {}
    for cls in ('natural-language', 'historical', 'explicit-source', 'unknown-control', 'all-positive'):
        ids = [t for t in tasks if CLASSES[t['category']] == cls or (cls == 'all-positive' and not t['expected_unknown'])]
        out[cls] = {}
        for arm in ARMS:
            if arm == reference:
                continue
            diffs, rep_pairs = {}, []
            for t in ids:
                a = [metric(t, verdicts[t['id'], arm, r]) for r in range(3) if (t['id'], arm, r) in verdicts]
                b = [metric(t, verdicts[t['id'], reference, r]) for r in range(3) if (t['id'], reference, r) in verdicts]
                if a and b:
                    diffs[t['id']] = statistics.mean(a) - statistics.mean(b)
                rep_pairs += [metric(t, verdicts[t['id'], arm, r]) - metric(t, verdicts[t['id'], reference, r])
                              for r in range(3) if (t['id'], arm, r) in verdicts and (t['id'], reference, r) in verdicts]
            vals = list(diffs.values())
            boots = sorted(statistics.mean(rng.choices(vals, k=len(vals))) for _ in range(2000)) if vals else []
            out[cls][arm] = {'reference': reference, 'tasks': len(vals), 'mean_task_difference': round(statistics.mean(vals), 4) if vals else None,
                             'task_bootstrap_95': [round(boots[50], 4), round(boots[1949], 4)] if boots else None,
                             'tasks_better': sorted(k for k, d in diffs.items() if d > 0), 'tasks_worse': sorted(k for k, d in diffs.items() if d < 0),
                             'tasks_equal': sum(d == 0 for d in vals), 'repetition_pairs': len(rep_pairs),
                             'repetition_pairs_better': sum(d > 0 for d in rep_pairs), 'repetition_pairs_worse': sum(d < 0 for d in rep_pairs)}
    return out


def usage(meta):
    rows = [m for m in meta]
    tok = lambda m, k: ((m.get('usage') or {}).get(k) or 0)
    return {'calls': len(rows), 'errors': sum(m['error'] is not None for m in rows),
            'resolved_models': sorted({m.get('resolved_model') or m.get('resolved_model_init') for m in rows} - {None}),
            'input_tokens': sum(tok(m, 'input_tokens') for m in rows), 'cache_read_input_tokens': sum(tok(m, 'cache_read_input_tokens') for m in rows),
            'cache_creation_input_tokens': sum(tok(m, 'cache_creation_input_tokens') for m in rows), 'output_tokens': sum(tok(m, 'output_tokens') for m in rows),
            'reported_list_cost_usd': round(sum(m.get('reported_cost_usd') or 0 for m in rows), 4),
            'cost_basis': sorted({b for m in rows for b in (m.get('cost_basis') or [])}),
            'elapsed_p50_ms': pct([m['elapsed_ms'] for m in rows], .5), 'elapsed_p95_ms': pct([m['elapsed_ms'] for m in rows], .95),
            'note': 'Reported list-price estimates from the CLI result event; not an invoice. Actual subscription billing is unknown.'}


def cmd_compare(a):
    tasks, _, _ = load_inputs()
    orig, orig_meta = load_review(a.original)
    corr, corr_meta = load_review(a.review)
    answer_meta = [json.loads(x) for x in gzip.open(a.trials / 'attempts.jsonl.gz', 'rt')]
    unsupported = lambda t, v: float(v['unsupported_assertions'] > 0)
    report = {'status': 'MODEL-ASSISTED REVIEW (claude-opus-5-5), NOT INDEPENDENT HUMAN REVIEW; labels model-authored and unreviewed',
              'class_definitions': CLASSES, 'primary_score': answer_score.__doc__,
              'original_registered': {'context_mode': 'stripped', 'tables': review_tables(tasks, orig),
                                      'paired_vs_grounded_flat': paired(tasks, orig, 'grounded-flat', answer_score),
                                      'paired_vs_legacy_hybrid': paired(tasks, orig, 'legacy-hybrid', answer_score)},
              'corrected_amendment_2': {'context_mode': 'full', 'tables': review_tables(tasks, corr),
                                        'paired_vs_grounded_flat': paired(tasks, corr, 'grounded-flat', answer_score),
                                        'paired_vs_legacy_hybrid': paired(tasks, corr, 'legacy-hybrid', answer_score),
                                        'paired_unsupported_rate_vs_legacy_hybrid': paired(tasks, corr, 'legacy-hybrid', unsupported)},
              'verdict_changes_original_to_corrected': {
                  field: sum(orig[k][field] != corr[k][field] for k in orig if k in corr)
                  for field in ('answer_correctness', 'gold_content_conveyed', 'warranted_unknown', 'appropriate_uncertainty', 'citation_correctness')}
              | {'unsupported_assertions': sum(orig[k]['unsupported_assertions'] != corr[k]['unsupported_assertions'] for k in orig if k in corr),
                 'compared': sum(k in corr for k in orig)},
              'usage': {'answerer': usage([{**m, 'resolved_model': m['resolved_model_init']} for m in answer_meta]),
                        'grader_original': usage(orig_meta), 'grader_corrected': usage(corr_meta)}}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'qa-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Fixed-context QA: original and corrected model-assisted review', '',
             'Model-assisted review by claude-opus-5-5, **not independent human review**. Labels are model-authored and unreviewed. '
             'Primary score: positives 1 / .5 / 0 for correct / partial / incorrect; unknown controls 1 if the answer warrantedly declines. '
             'Paired differences average the three repetitions within each task, then bootstrap over tasks (descriptive 95%).', '']
    for name in ('original_registered', 'corrected_amendment_2'):
        lines += [f'## {name}', '', '| Class | Arm | Answers | Mean score | Correct / partial / incorrect | Warranted unknown | Answers with unsupported claims | Citation correct / incorrect / none |', '|---|---|---:|---:|---|---:|---:|---|']
        for cls, arms in report[name]['tables'].items():
            for arm, v in arms.items():
                lines.append(f"| {cls} | {arm} | {v['answers']} | {v['mean_score']} | {v['correct']} / {v['partially_correct']} / {v['incorrect']} | {v['warranted_unknown_yes']} | {v['answers_with_unsupported_assertions']} | {v['citation_correct']} / {v['citation_incorrect']} / {v['citation_none']} |")
        lines += ['', '| Class | Arm vs grounded-flat | Tasks | Mean task diff | 95% task bootstrap | Better / worse tasks |', '|---|---|---:|---:|---|---|']
        for cls, arms in report[name]['paired_vs_grounded_flat'].items():
            for arm, v in arms.items():
                lines.append(f"| {cls} | {arm} | {v['tasks']} | {v['mean_task_difference']} | {v['task_bootstrap_95']} | {len(v['tasks_better'])} / {len(v['tasks_worse'])} |")
        lines.append('')
    lines += ['## Usage and reported cost', '', '```json', json.dumps(report['usage'], indent=1), '```', '']
    (a.out / 'QA-RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: report[k] for k in ('verdict_changes_original_to_corrected', 'usage')}, indent=1))


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def cmd_summary(a):
    tasks, _, packets = load_inputs()
    by_id = {t['id']: t for t in tasks}
    attempts = [json.loads(x) for x in (a.trials / 'attempts.jsonl').open()]
    rows = completed(a.trials)
    retr = retrieval_scores()
    reviews = {}
    if (a.review / 'model-review.jsonl').exists():
        for line in (a.review / 'model-review.jsonl').open():
            r = json.loads(line)
            if r['verdict']:
                reviews[tuple(r['trial_key'].split('|')[:2]) + (int(r['trial_key'].split('|')[2]),)] = r['verdict']
    per = []
    for key, r in sorted(rows.items()):
        t = by_id[key[0]]
        packet = '' if key[1] == 'none' else packets[key[0]][key[1]]
        rs = retr.get((key[0], key[1]), {}) if key[1] != 'none' else {}
        per.append({'task': key[0], 'arm': key[1], 'repeat': key[2], 'category': t['category'], 'track': t['track'], 'expected_unknown': t['expected_unknown'],
                    'gold_passage_in_context': bool(rs.get('complete_proxy')) if t['gold'] else None,
                    **mechanical(t, key[1], packet, r['output']), 'model_review': reviews.get(key),
                    'input_tokens': (r['usage'] or {}).get('input_tokens'), 'cache_read_tokens': (r['usage'] or {}).get('cache_read_input_tokens'),
                    'cache_creation_tokens': (r['usage'] or {}).get('cache_creation_input_tokens'), 'output_tokens': (r['usage'] or {}).get('output_tokens'),
                    'reported_cost_usd': r['reported_cost_usd'], 'elapsed_ms': r['elapsed_ms'], 'resolved_model': r['resolved_model_init']})
    summary = {'status': 'RECORDED; MODEL-ASSISTED REVIEW ONLY; NOT HUMAN REVIEWED', 'planned_trials': len(tasks) * len(ARMS) * SETTINGS['repetitions'],
               'completed_trials': len(rows), 'attempts': len(attempts), 'failed_attempts': sum(r['error'] is not None for r in attempts),
               'resolved_models': sorted({r['resolved_model'] for r in per}), 'arms': {}}
    for arm in ARMS:
        rs = [r for r in per if r['arm'] == arm]
        pos = [r for r in rs if not r['expected_unknown']]
        unk = [r for r in rs if r['expected_unknown']]
        rev = [r['model_review'] for r in rs if r['model_review']]
        revpos = [r['model_review'] for r in pos if r['model_review']]
        revunk = [r['model_review'] for r in unk if r['model_review']]
        summary['arms'][arm] = {
            'trials': len(rs), 'positive_trials': len(pos), 'unknown_trials': len(unk),
            'gold_passage_in_context': sum(bool(r['gold_passage_in_context']) for r in pos),
            'cites_task_revision': sum(bool(r['cites_task_revision']) for r in pos),
            'cites_unsupplied_revision': sum(r['cites_unsupplied_revision'] for r in rs),
            'model_reviewed': len(rev),
            'mr_gold_conveyed_yes': sum(v['gold_content_conveyed'] == 'yes' for v in revpos),
            'mr_gold_conveyed_partial': sum(v['gold_content_conveyed'] == 'partial' for v in revpos),
            'mr_correct': sum(v['answer_correctness'] == 'correct' for v in revpos),
            'mr_partially_correct': sum(v['answer_correctness'] == 'partially_correct' for v in revpos),
            'mr_incorrect': sum(v['answer_correctness'] == 'incorrect' for v in revpos),
            'mr_warranted_unknown_yes': sum(v['warranted_unknown'] == 'yes' for v in revunk),
            'mr_appropriate_uncertainty_yes': sum(v['appropriate_uncertainty'] == 'yes' for v in rev),
            'mr_unsupported_assertions_total': sum(v['unsupported_assertions'] for v in rev),
            'mr_trials_with_unsupported_assertions': sum(v['unsupported_assertions'] > 0 for v in rev),
            'mr_citation_correct': sum(v['citation_correctness'] == 'correct' for v in rev),
            'mr_citation_incorrect': sum(v['citation_correctness'] == 'incorrect' for v in rev),
            'input_tokens_total_incl_cache': sum((r['input_tokens'] or 0) + (r['cache_read_tokens'] or 0) + (r['cache_creation_tokens'] or 0) for r in rs),
            'output_tokens_total': sum(r['output_tokens'] or 0 for r in rs),
            'reported_list_cost_usd_total': round(sum(r['reported_cost_usd'] or 0 for r in rs), 4),
            'model_elapsed_p50_ms': pct([r['elapsed_ms'] for r in rs], .5), 'model_elapsed_p95_ms': pct([r['elapsed_ms'] for r in rs], .95)}
    # Paired per-task majority (over repetitions) vs grounded-flat, model-assisted correctness on positives.
    def major(arm, tid):
        vs = [r['model_review'] for r in per if r['arm'] == arm and r['task'] == tid and r['model_review']]
        return statistics.mean({'correct': 1, 'partially_correct': .5, 'incorrect': 0}.get(v['answer_correctness'], 0) for v in vs) if vs else None
    pos_ids = sorted({t['id'] for t in tasks if not t['expected_unknown']})
    summary['paired_mean_correctness_vs_grounded_flat'] = {arm: {
        'better': [t for t in pos_ids if None not in (major(arm, t), major('grounded-flat', t)) and major(arm, t) > major('grounded-flat', t)],
        'worse': [t for t in pos_ids if None not in (major(arm, t), major('grounded-flat', t)) and major(arm, t) < major('grounded-flat', t)]} for arm in ARMS if arm != 'grounded-flat'}
    a.out.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(a.out / 'per-trial-scores.jsonl.gz'), mode='wb', mtime=0) as f:
        for r in per:
            f.write((canonical(r) + '\n').encode())
    (a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('review', 'materials', 'summary', 'inputs', 'compare'):
        s = sub.add_parser(name)
        s.add_argument('--trials', type=Path, required=True)
        s.add_argument('--out', type=Path, required=True)
        s.add_argument('--limit', type=int)
        s.add_argument('--review', type=Path)
        s.add_argument('--original', type=Path)
        s.add_argument('--context', choices=('stripped', 'full'), default='stripped')
    a = p.parse_args()
    {'review': cmd_review, 'materials': cmd_materials, 'summary': cmd_summary, 'inputs': cmd_inputs, 'compare': cmd_compare}[a.cmd](a)


if __name__ == '__main__':
    main()

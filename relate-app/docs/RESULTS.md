# Results, measurements and limitations

Machine: laptop with AMD Ryzen 9 7940HS (16 threads) and 30 GiB RAM, Docker container on
Debian with glibc 2.41. Build: Rust 1.88.0, `relate` 1.0.1, release profile. All
measurements are local and loopback-free (embedded engine); none are remote-server
numbers. Timings were taken with no other benchmark jobs running.
Raw files are in `relate-app/evidence/`.

## Correctness on the real engine (18 Rust tests, CI)

`cargo test --release --locked`: all pass. There are no mocks of engine capability.

| Contract | Test |
|---|---|
| Relate 1.0.1 capabilities the design relies on: vector scope prefilter, full-text `WHERE` rejected, per-label IDF isolation, Cypher RRF, bounded traversal without hidden bridges, rollback, writer lease, read-only open, restart | `engine_capabilities.rs` (4) |
| Qualified identities, exact source URI/revision/digest, rendered-text digest, idempotent import | `exact_identity_and_citations_are_delivered` |
| Imported or captured text cannot award verification or approval; bad digests rejected | `imports_cannot_award_trust_and_reject_bad_bindings` |
| Scope filtered before limits (20 better foreign matches); shared-guidance bridge cannot leak a foreign decision | `scope_is_filtered_before_limits_and_hidden_bridges_do_not_leak` |
| Supersession, expiry, retraction, replay no-op, request-id reuse refused, retracted association never reactivated, restored wording never rebinds old observations | `supersession_expiry_retraction_replay_and_no_rebinding` |
| Indivisible conflict bundles, required records, hard UTF-8 byte/codepoint limits (multibyte text) | `conflict_bundles_required_records_and_hard_utf8_budget` |
| Explicit source requirement satisfied; owner confirmation insufficient; unknown project abstains | `explicit_source_and_owner_confirmation_requirements` |
| Tampered row detected by `verify` and refused at render | `tampered_records_are_detected_and_never_rendered` |
| Failed write rolls back (separate process), restart sees committed data, damaged store files fail closed | `failed_write_rolls_back_restart_and_corruption_fail_closed` |
| Offline boundary: TCP/UDP sockets denied, Unix sockets allowed | `read_only_surfaces_deny_network` |
| Single-writer lease across processes; read-only open beside a writer | `single_writer_lease_is_enforced_across_processes` |
| Rust embeddings match the Python reference (20 cases): worst cosine **0.9999995**, worst \|Δ\| **4.3e-7** (tolerance 0.99999 / 2e-4) | `embedding_reference.rs` |
| Rust extractor reproduces both committed passage fixtures byte-for-byte (254 passages) | `extract_reference.rs` (CI clones public Writ) |

End-to-end demo (`evidence/demo/`): 13 separate processes and **15/15 checks pass**. They
cover capture, retraction, refused reactivation, replay no-op, supersession, restart
visibility, history and verify.

## Retrieval regression (opened tasks; not unseen evaluation)

72 frozen reliable-memory tasks, both Git snapshots, 8,000-byte / 6,000-codepoint
budget, k=6, RRF 60, cosine gate 0.30. Labels are **model-authored and unreviewed**. These
tasks were opened before this work, so they are regression data. No setting was tuned on
them.

| Natural-language target delivery (/24) | Development | Held-out |
|---|---:|---:|
| Python legacy hybrid (committed) | 17 | 19 |
| Python grounded flat / grounded Relate (committed) | 15 | 20 |
| **Rust writ-relate** (Cypher or Rust fusion) | **19** | **21** |

The Rust run also delivered all-positive 25/30 (development) and 27/30 (held-out),
correctly handled 6/6 unknown controls in each split, and had 0 errors, 0 citation or
scope failures, and a maximum payload of 5,996 of 6,000 characters.

**Separating ownership, language and rendering:**

- **Fusion ownership (Cypher RRF vs Rust RRF over the same native lists):** identical
  delivered passages on **72/72** tasks. Warm p50 58.6 ms (Cypher) vs 57.0–57.5 ms (Rust).
  Cypher is the default as an ownership choice; it is not faster.
- **Language and storage layout (Rust single store with per-scope indexes vs Python
  grounded-relate with per-partition projection files):** identical fused candidate
  rankings, in the same order, on **54/54** natural-track tasks. The 18 structured tasks
  differ because the Python reference pads explicit lookups with other records, while Rust
  delivers the requested record as required. Both satisfy the requirement.
- **Rendering:** with identical rankings, Rust fits about **2.68** complete records per
  payload vs **1.5** for Python. The Python items carry more metadata per record. This
  accounts for all Rust gains (dev-04, dev-05, dev-07, dev-22, hel-07 vs grounded-relate;
  dev-02, dev-11, dev-27, dev-29, hel-06, hel-07, hel-28, hel-29, hel-30 vs legacy). **No
  task regressed against either reference.** This is a payload-format effect, not better
  retrieval.
- **Policy correction, disclosed:** the first Rust runs cut each list to k before fusion,
  unlike the reference policy. That gave 11/72 identical candidate sets and one regression
  (`hel-11`). It was corrected to rank the full permitted partition per list, as
  `grounded.py` does. The pre-correction run is preserved in
  `evidence/eval-initial-per-list-k6/`. An earlier identical-policy run without candidate
  diagnostics was discarded and replaced by that preserved run. Its summary numbers were the
  same.

## Cost

| Measurement | Value |
|---|---|
| Warm end-to-end per query (inference + Relate search/fusion + enrichment + validation + rendering), 108 samples per split | p50 57–59 ms, p95 62–67 ms |
| Model load (tract optimize) | about 250 ms |
| Import 127 passages (includes 127 embeddings) | 6.7–6.8 s (eval), 7.7 s (demo, separate process) |
| Capture / supersede (one process, includes model load) | 0.40–0.47 s |
| Retract / inspect / verify (no model) | 71 / 36 / 39 ms |
| Restart visibility | Every demo step is a new process; each write is visible to the next |
| Eval process peak RSS (two stores, model, 864 queries) | 198 MiB |
| Binary size | 57 MB (links libc, libm and libgcc_s only) |
| Demo store on disk | about 1 MB |

**Paired fresh-process comparison** (same machine, same model, same 127-passage snapshot,
2 queries × 30 interleaved samples, 2 warm-ups; `evidence/bench-cold/`):

| CLI | p50 ms | p95 ms | Peak RSS MiB | CPU s |
|---|---:|---:|---:|---:|
| **Rust `writ-relate context`** | **344–345** | **362–383** | **198** | **0.35** |
| Python grounded_cli `--backend relate` | 916–917 | 1004–1030 | 235 | 2.29 |
| Python grounded_cli (flat) | 808–809 | 926–929 | 281 | 2.23 |

These are whole-CLI differences: language, runtime imports, inference engine (tract vs
onnxruntime) and implementation all differ, so no language-only speedup is claimed.
Native Relate retrieval keeps the lower cold-process memory seen in the earlier Python
measurements (Relate CLIs 198–235 MiB vs Python flat 281 MiB).

## Agent interface

`evidence/mcp-trace/` contains one real Claude Code 2.1.325 session (Claude Sonnet 5.5,
existing login) with exactly two MCP tools (`writ_context`, `writ_inspect`). It made one
`writ_context` call and gave a correct, cited answer; the reported list cost was
$0.03. This is a single demonstration, not an agent experiment, and it shows nothing
about task success.

## Unsupported or not established

- Multi-writer or multi-process writes (single writer only; read-only opens are supported).
- Owner confirmation and approval: deliberately absent from every command. Confidence
  thresholds are not implemented and are reported as "not established".
- Remote or shared server, Neo4j (not used), authenticated tenancy (project scope is a
  local convention, not authorization).
- Power-loss and device-fault durability beyond Relate's WAL design. Corrupt stores fail
  closed with no automatic repair; rebuild from seeds and fixtures.
- Scaling: exact vector scan of the permitted partition and one full-text index per scope
  are measured only at 127–254 records and one or two scopes.
- Offline enforcement on non-Linux platforms (seccomp is Linux-only; other platforms report
  `unsupported`).
- Payloads include the request time (`as_of`), so byte-identical outputs need `--as-of`.
- New-source import requires Markdown under `## ` headings. Other formats are not
  extracted.
- Labels are unreviewed. No independent human review and no generative-agent outcome
  experiment was run for this application.

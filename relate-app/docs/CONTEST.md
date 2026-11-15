# Relate by Neo4j Hackathon: requirements audit

Read on 2026-11-14 from https://relate.devpost.com/ (homepage) and
https://relate.devpost.com/rules (Official Rules; banner "Updated Nov 13, 2026: the public
repository must be tagged with the GitHub topic relate"). Deadline: Dec 11, 2026, 6:00 PM
PST. The project must be started on or after Nov 11, 2026. This repository's first
commit is 2026-11-13.

## Submission checklist

| Requirement (source) | Status in this branch |
|---|---|
| Public GitHub repository (rules §3) | Met: `infinri/WritRetrievalSystem` is public |
| **GitHub topic `relate` (rules §3, §4; homepage "required")** | **Not met.** Current topics are `relate-hackathon`, `agent-memory`, `semantic-search`. The owner must add `relate` (and optionally `relate-neo4j-hackathon`). This PR does not change repository settings. |
| Open-source license encouraged (rules §3) | Met: MIT (root `LICENSE`) |
| README answering "how are you using Relate, and why", including the mode (homepage) | Met: `relate-app/README.md`, "How it uses Relate" (directory mode and why) |
| Persistent store judges can inspect (homepage) | Met: `relate-app/demo-store/` (Relate directory store, about 1 MB) |
| Working code with Relate actually running (homepage) | Met: Rust binary plus CI on the real engine |
| Setup instructions a judge can follow (rules §4) | Met: `relate-app/README.md` (Rust toolchain, curl and sha256sum; no Python) |
| Demo video up to 2 minutes, or a working-demo link (rules §4) | **Not produced.** Storyboard in `DEMO-SCRIPT.md`; recording and publishing are owner actions |
| Statement of Product capabilities, third-party tools and AI tools used (rules §4) | Drafted in `REUSE-MAP.md`; the owner must copy it into the Devpost form |
| Disclose reuse of own earlier code (rules §3) | Drafted in `REUSE-MAP.md` and root `NOTICE.md` |
| Describe significant AI use (rules §3) | Drafted in `REUSE-MAP.md` |
| Meaningful use of Relate (rules §3) | Embedded crate: native vector and full-text indexes, Cypher fusion and traversal, transactions, directory persistence |

Nothing was submitted, published or sent to organizers.

## Discrepancy: judging criteria

- **Homepage "Judging Criteria" (point weights):** Creativity 10, Relate and connected
  context 30, Functionality and completeness 25, Usefulness 20, Documentation and
  reproducibility 15 (total 100).
- **Official Rules §5:** "Judges will score each eligible entry on the following criteria,
  **weighted equally**": Creativity, Usefulness, Completeness, **Clarity** ("the quality of
  the written explanation, demo, and visual presentation"), and Effective use of connected
  context.

The two lists use different names (Clarity vs Documentation and reproducibility) and
different weights (equal vs 10/30/25/20/15). The rules also say the Official Rules
control over Devpost terms, but they do not say which of the two lists governs judging.

**Clarification question for the owner to send if desired (not sent by us):**

> The homepage lists judging criteria with point weights (Creativity 10, Relate and
> connected context 30, Functionality 25, Usefulness 20, Documentation and reproducibility 15),
> while Official Rules §5 lists five equally weighted criteria including "Clarity" rather
> than "Documentation and reproducibility". Which list and weighting will judges apply?

Implementation continued without waiting for an answer. Both lists emphasize working
end-to-end use of Relate's connected context and clear setup instructions.

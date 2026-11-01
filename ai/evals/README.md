# AI evaluation workspace

This directory reserves the evaluation workspace described in
[`spec/ai/verification.md`](../../spec/ai/verification.md) and
[ADR 0007](../../spec/ai/decisions/0007-evaluation-design-policy.md). The local synthetic
fixture and comparison method follows
[ADR 0009](../../spec/ai/decisions/0009-ai-evaluation-method.md).

- `inputs/` is reserved for information that a model may receive.
- `expectations/` is reserved for expected or forbidden outcomes and review notes. Its
  contents must not enter model prompts or retrieval inputs.

Future local synthetic cases use paired JSON files in these directories. Each pair has the
same `case_id` and `version`; a loader must reject mismatches, duplicates, and orphans. The
input side keeps its execution payload distinct from case, split, and source-group control
metadata. Only that execution payload may reach the model. Expectations, review information,
and control metadata must not enter prompts, retrieval queries, or tool inputs.

## Candidate case format

Candidate shape for local synthetic cases. Files are `inputs/{case_id}.v{version}.json` and
`expectations/{case_id}.v{version}.json`. A pair is matched by file name; duplicates and
mismatches are detected by the `case_id` and `version` inside the files.

```json
// inputs/q-0003.v1.json
{"case_id": "q-0003", "version": 1,
 "control": {"kind": "question", "split": "dev", "source_group": "sg-shop-01", "synthetic": true},
 "payload": {}}

// expectations/q-0003.v1.json
{"case_id": "q-0003", "version": 1,
 "allowed": [{"id": "a1", "purpose": "..."}],
 "forbidden": [{"id": "f1", "reason": "...", "type": "..."}],
 "grader_controls": [{"kind": "allowed", "output": "..."}],
 "review": {"status": "unreviewed", "author": null, "reviewer": null,
            "reviewed_at": null, "pending_notes": []}}
```

- `control.kind` is `evidence`, `question`, `flow` or `report`; `split` is `dev` or `holdout`.
- `payload` is the only part a model may receive. The loader passes it through without
  interpreting it; its shape per kind is defined with the cases.
- `grader_controls[].kind` is `allowed`, `forbidden`, `ambiguous`, `invalid_ref` or `tool_failure`.
- `review.status` is `unreviewed`, `approved`, `pending` or `invalid`. Reviewer names and dates
  stay `null` until a person other than the author has actually checked the case.
- This shape is local to synthetic fixtures. It is not a database or public API schema.
- `evals/eval_cases.py` loads the pairs and rejects orphans, duplicates, mismatched file names,
  unknown keys (so expectations cannot sit in an input file), non-synthetic cases, a source group
  used in both `dev` and `holdout`, and `approved` reviews that lack a reviewer other than the author.
- `evals/grader_check.py` tries a grader on approved cases' control outputs and counts correct,
  false accept, false reject, abstained and error per control kind. The grader never sees the
  control kind. The expected verdict per kind is an author assumption pending team review.

## Case review (author proposal, pending team confirmation)

After a case is written and before any model run, someone other than the author checks that its
allowed and forbidden outcomes match the source text and approved policy. One reviewer per case.
If they disagree the case becomes `pending` with both sides' reasons in `pending_notes`; a third
team member then picks one of: widen the allowed outcomes, rewrite as a new version, or invalidate.
A case counts as reviewed with one approval and no open `pending`, recorded in `review`. Who
reviews is assigned when the cases are written; until then `reviewer` stays `null`.

No JSON cases, loaders, real datasets, examples, answers, or evaluation harnesses are
included yet. These directories are not part of the runtime package or its built distributions.

Future cases derived from the same source must remain in one source group. Development and
holdout sets must use different source groups. Once a holdout case informs implementation or
policy changes, it becomes regression material and must retain its usage history; renaming or
copying it does not make it unused holdout evidence.

Do not commit real user material or undisclosed holdout answers here. Store temporary evaluation
output in the ignored `ai/report/` path.

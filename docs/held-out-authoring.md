# Authoring the held-out release corpus

The forty decision-rule templates are now authored in `scenarios/held-out/`.
See [their scope and relationship review](held-out-corpus.md). The rules below
continue to govern subsequent corpora. Existing development fixtures,
renamed copies, paraphrases, and descendants of their workflow templates cannot
become held-out data. Do not create forty copies merely to obtain 400 rows.
The current development catalogue and its recorded treatment variants remain
in the development split.

## Required files

Place the new tasks beneath a dedicated suite directory, using the existing
schema-3 task format. Each task includes trusted contracts, pristine resources,
independent state/output predicates, one clean authored script, and exactly four
attacks: instruction override, authority spoofing, action redirection, and data
disclosure. Payload insertion is currently document-body append. Tool-result
field insertion is not implemented and must not be claimed.

The suite manifest uses `split: "held_out"` and lists forty relative JSON paths.
The development runner and ordinary application loader reject that split. Only
the frozen release workflow can schedule it.

A separate lineage JSON has this structure (illustrative, not runnable):

```json
{
  "schema_version": 1,
  "suite_id": "held-out-v1",
  "held_out_model_runs_before_freeze": 0,
  "author_knowledge": "Self-authored with coding-agent assistance; authors know the policies and graders.",
  "limitations": ["No independent external benchmark or semantic split certification."],
  "tasks": [
    {
      "id": "new-workflow-id",
      "family": "new-workflow-family",
      "template_id": "distinct-template-id",
      "development_ancestors": [],
      "distinct_workflow": "Explain the workflow structure and why its closest development task is not a template ancestor."
    }
  ]
}
```

All forty entries must be present. Related held-out templates retain their shared
family; unique IDs do not imply independent families. If a task has any development
ancestor, keep it in development. Shared tool primitives alone do not establish
ancestry, but changed names, prose, data values, or combinations of existing
templates alone do not establish independence either.

## Review before the freeze

Check the natural-language request against every strict predicate. Exact string
requirements must be visible to the user/model, while answers, canaries, attack
objectives, and graders stay outside model scope. Inspect clean authored actions
and adversarial scripts using the deterministic store/grader; do not use live
held-out results to tune task wording or defenses. Record corrections and their
reason before declaring the final freeze.

The automated audit scans all historical development task JSON, including the
original schema-1 scenario, and pins the file hashes. It rejects shared task IDs
or family labels, duplicate template IDs, exact text duplicates, text similarity
at or above 0.85 (Python SequenceMatcher), declared development ancestors, prior
model trials, and missing attack families. The text heuristic can miss paraphrases
and can flag legitimately similar wording. It supplements the written relationship
review; it does not certify an untouched semantic split. The zero-prior-trials
field is an author declaration, not a tamper-proof experiment registry.

Task-level bootstrap intervals retain each task's clean and attacked trials across
profiles. Related templates can remain correlated beyond that unit; disclose the
family counts and interpret intervals descriptively. There is no family-bootstrap
or independent unseen-attack guarantee in the current analyzer.

Once the corpus is reviewed, run the commands in [the release runbook](release-evaluation.md).
Do not overwrite a freeze, silently retry unfavorable trials, relax graders after
seeing outcomes, or discard timeouts. Preserve the first evaluation and identify
later tuned experiments separately.

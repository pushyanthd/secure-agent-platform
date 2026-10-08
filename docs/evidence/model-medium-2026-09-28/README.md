# Qwen3.5-9B utility screen: rejected for futility

14 of 32 planned trials recorded; 18 not run. The stop rule was frozen before any generation. Neither prompt arm could reach its declared utility threshold even if every remaining trial succeeded. This is partial development evidence, not a complete comparison or release result.

Checklist: clean 3/4, attacked 1/4. Original wording: clean 0/3, attacked 0/3. All 14 trials completed; no observed attacker wins in seven attacked trials. Missing ticket effects and incorrect decisions remain. Zero observed wins do not establish general security.

Every saved outcome was independently regraded from a SQLite checkpoint before publication. See [outcomes](screening-result.json), [model calls](model-calls.json), [pre-generation stop policy](execution-policy.json), and [provenance](publication.json). The original 400-trial release remains FAIL. Model timings reflect uncontrolled host load.

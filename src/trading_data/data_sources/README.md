# data_sources

Smallest-unit data source interfaces live here.

Boundary:

- A data source module talks to one provider/source family or normalizes one provider/source output shape.
- It should expose reusable fetch/clean/save primitives for that source-level output.
- It should not own model-input orchestration, cross-source feature assembly, or manager-facing model bundle logic.

Manager-facing orchestration belongs in `trading_data.data_bundles`.

Current caveat: several historical acquisition runners still expose CLIs here for compatibility. New model-input generation must go under `data_bundles`, and existing source CLIs should be wrapped/migrated behind bundle runners as their manager contracts are hardened.

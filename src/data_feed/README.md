# data_feed

Smallest-unit data feed interfaces live here.

Boundary:

- A data feed module talks to one provider/API/web/file family or normalizes one feed output shape.
- It should expose reusable fetch/clean/save primitives for that feed-level output.
- It should not own model-input orchestration, cross-source feature assembly, or manager-facing model feed logic.

Manager-facing orchestration belongs in `data_sources`.

Current caveat: several historical acquisition runners still expose CLIs here for compatibility. New model-input generation must go under `data_sources`, and existing feed CLIs should be wrapped/migrated behind feed runners as their manager contracts are hardened.

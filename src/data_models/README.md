# data_models

`data_models` is the structural catalog for the `trading-data` M01-M06
ownership surface.

It answers one maintenance question: for each current model, what does this
repository own in `docs/`, `src/`, CLI entrypoints, and tests?

The catalog must not create fake symmetry. M03 and M04 currently have no
dedicated deterministic `trading-data` source package because their inputs come
from reviewed evidence, model outputs, replay state, and control-plane context.
The catalog records that explicitly so the absence is intentional and testable.

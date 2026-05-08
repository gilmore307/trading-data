# data_layers

`data_layers` is the structural catalog for the `trading-data` layer spine.

It answers one maintenance question: for each model layer, what does this repository
own in `docs/`, `src/`, CLI entrypoints, and tests?

The catalog must not create fake symmetry. Layers 5-7 currently have no dedicated
`trading-data` source because their inputs belong to `trading-model`, control-plane,
risk/cost, or execution-state boundaries. The catalog records that explicitly so the
absence is intentional and testable.

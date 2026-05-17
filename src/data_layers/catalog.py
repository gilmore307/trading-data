"""Authoritative layer-to-repository-structure catalog.

This catalog keeps the visible repository structure aligned with the accepted
model stack without creating fake symmetry-only source or feature packages. A
layer with no new `trading-data` acquisition or deterministic feature surface
must say so here and in its docs; a layer with a source/feature surface must
name the package and CLI command that owns it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerDataContract:
    """Repository structure owned by `trading-data` for one model layer."""

    layer: int
    slug: str
    model_name: str
    doc_path: str
    owns_dedicated_data_surface: bool
    source_packages: tuple[str, ...] = ()
    feature_packages: tuple[str, ...] = ()
    feed_packages: tuple[str, ...] = ()
    cli_commands: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    no_source_reason: str = ""

    @property
    def layer_key(self) -> str:
        return f"layer_{self.layer:02d}_{self.slug}"


LAYER_CONTRACTS: tuple[LayerDataContract, ...] = (
    LayerDataContract(
        layer=1,
        slug="market_regime",
        model_name="MarketRegimeModel",
        doc_path="docs/10_layer_01_market_regime.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.source_01_market_regime",),
        feature_packages=("data_feature.feature_01_market_regime",),
        cli_commands=("trading-data-source-01-market-regime", "trading-data-feature-01-market-regime"),
        test_paths=(
            "tests/data_source/test_numbered_data_sources.py",
            "tests/test_market_regime_feature_generator.py",
        ),
    ),
    LayerDataContract(
        layer=2,
        slug="sector_context",
        model_name="SectorContextModel",
        doc_path="docs/11_layer_02_sector_context.md",
        owns_dedicated_data_surface=True,
        feature_packages=("data_feature.feature_02_sector_context",),
        cli_commands=("trading-data-feature-02-sector-context",),
        test_paths=(
            "tests/test_sector_context_feature_generator.py",
        ),
    ),
    LayerDataContract(
        layer=3,
        slug="target_state_vector",
        model_name="TargetStateVectorModel",
        doc_path="docs/12_layer_03_target_state_vector.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.source_02_target_candidate_holdings", "data_source.source_03_target_state"),
        feature_packages=("data_feature.feature_03_target_state_vector",),
        cli_commands=(
            "trading-data-source-02-target-candidate-holdings",
            "trading-data-source-03-target-state",
            "trading-data-feature-03-target-state-vector",
        ),
        test_paths=(
            "tests/data_source/test_target_candidate_holdings_pipeline.py",
            "tests/test_source_03_target_state.py",
            "tests/test_target_state_vector_feature_generator.py",
            "tests/test_target_state_vector_sql.py",
        ),
    ),
    LayerDataContract(
        layer=4,
        slug="event_failure_risk",
        model_name="EventFailureRiskModel",
        doc_path="docs/13_layer_04_event_failure_risk.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_layer_structure_catalog.py",),
        no_source_reason=(
            "Consumes reviewed event/strategy-failure gates and PIT evidence references owned by model/manager boundaries; "
            "trading-data must not create a raw-event or symmetry-only Layer 4 source/feature surface."
        ),
    ),
    LayerDataContract(
        layer=5,
        slug="alpha_confidence",
        model_name="AlphaConfidenceModel",
        doc_path="docs/14_layer_05_alpha_confidence.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_layer_structure_catalog.py",),
        no_source_reason=(
            "Consumes reviewed Layer 1/2/3 state artifacts, Layer 4 event-failure-risk conditioning, and labels/evaluation artifacts; "
            "no new provider/source acquisition or deterministic trading-data feature surface is owned by trading-data."
        ),
    ),
    LayerDataContract(
        layer=6,
        slug="position_projection",
        model_name="PositionProjectionModel",
        doc_path="docs/15_layer_06_position_projection.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_layer_structure_catalog.py",),
        no_source_reason=(
            "Consumes alpha confidence plus position/risk/cost context owned by model/control-plane/execution boundaries; "
            "no new trading-data source or feature surface is accepted."
        ),
    ),
    LayerDataContract(
        layer=7,
        slug="underlying_action",
        model_name="UnderlyingActionModel",
        doc_path="docs/16_layer_07_underlying_action.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_layer_structure_catalog.py",),
        no_source_reason=(
            "Direct-underlying action thesis is model/control-plane work; trading-data supplies only upstream observed inputs and deterministic features from owned source layers."
        ),
    ),
    LayerDataContract(
        layer=8,
        slug="trading_guidance",
        model_name="TradingGuidanceModel / OptionExpressionModel",
        doc_path="docs/17_layer_08_trading_guidance.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.source_05_option_expression", "data_source.source_06_position_execution"),
        feature_packages=("data_feature.feature_08_option_expression",),
        feed_packages=(
            "data_feed.09_feed_thetadata_option_selection_snapshot",
            "data_feed.10_feed_thetadata_option_primary_tracking",
            "data_feed.11_feed_thetadata_option_event_timeline",
        ),
        cli_commands=(
            "trading-data-source-05-option-expression",
            "trading-data-source-06-position-execution",
            "trading-data-feature-08-option-expression",
            "trading-data-09-feed-thetadata-option-selection-snapshot",
            "trading-data-10-feed-thetadata-option-primary-tracking",
            "trading-data-11-feed-thetadata-option-event-timeline",
        ),
        test_paths=(
            "tests/data_source/test_numbered_data_sources.py",
            "tests/test_option_expression_feature_generator.py",
            "tests/data_feed/test_thetadata_option_selection_snapshot_pipeline.py",
            "tests/data_feed/test_thetadata_option_primary_tracking_pipeline.py",
            "tests/data_feed/test_thetadata_option_event_timeline_pipeline.py",
        ),
    ),
    LayerDataContract(
        layer=9,
        slug="event_risk_governor",
        model_name="EventRiskGovernor / EventIntelligenceOverlay",
        doc_path="docs/18_layer_09_event_risk_governor.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.source_09_event_risk_governor",),
        feature_packages=("data_feature.feature_09_event_risk_governor",),
        cli_commands=("trading-data-source-09-event-risk-governor", "trading-data-feature-09-event-risk-governor"),
        test_paths=(
            "tests/data_source/test_numbered_data_sources.py",
            "tests/data_source/test_equity_abnormal_activity_pipeline.py",
            "tests/test_event_overlay_feature_generator.py",
        ),
    ),
)


def contracts_by_layer() -> dict[int, LayerDataContract]:
    """Return layer contracts keyed by numeric layer."""

    return {contract.layer: contract for contract in LAYER_CONTRACTS}

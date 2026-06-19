"""Authoritative M01-M06 data-surface catalog for trading-data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDataContract:
    """Repository structure owned by `trading-data` for one current model."""

    model: int
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
    def model_key(self) -> str:
        return f"model_{self.model:02d}_{self.slug}"

    @property
    def model_marker(self) -> str:
        return f"M{self.model:02d}"


MODEL_CONTRACTS: tuple[ModelDataContract, ...] = (
    ModelDataContract(
        model=1,
        slug="background_context",
        model_name="BackgroundContextModel",
        doc_path="docs/10_model_01_background_context_data.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.m01_market_regime_data_acquisition",),
        feature_packages=(
            "data_feature.m01_market_regime_feature_generation",
            "data_feature.m02_sector_context_feature_generation",
        ),
        cli_commands=(
            "trading-data-m01-market-regime-data-acquisition",
            "trading-data-m01-market-regime-feature-generation",
            "trading-data-m02-sector-context-feature-generation",
        ),
        test_paths=(
            "tests/data_source/test_numbered_data_sources.py",
            "tests/test_market_regime_feature_generator.py",
            "tests/test_sector_context_feature_generator.py",
        ),
    ),
    ModelDataContract(
        model=2,
        slug="target_state",
        model_name="TargetStateModel",
        doc_path="docs/12_model_02_target_state_data.md",
        owns_dedicated_data_surface=True,
        source_packages=(
            "data_source.m03_target_state_vector_data_acquisition",
            "data_source.option_chain_state_source",
        ),
        feature_packages=("data_feature.m03_target_state_vector_feature_generation",),
        cli_commands=(
            "trading-data-m03-target-state-vector-data-acquisition",
            "trading-data-m03-target-state-vector-feature-generation",
        ),
        test_paths=(
            "tests/test_m03_target_state_vector_data_acquisition.py",
            "tests/test_target_state_vector_feature_generator.py",
            "tests/test_target_state_vector_sql.py",
        ),
    ),
    ModelDataContract(
        model=3,
        slug="event_state",
        model_name="EventStateModel",
        doc_path="docs/19_model_06_residual_event_governance.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_model_structure_catalog.py",),
        no_source_reason=(
            "Consumes reviewed event observations, event-family evidence, and residual governance outputs; "
            "trading-data must not create a raw-event symmetry package for M03."
        ),
    ),
    ModelDataContract(
        model=4,
        slug="unified_decision",
        model_name="UnifiedDecisionModel",
        doc_path="docs/30_model_inputs.md",
        owns_dedicated_data_surface=False,
        test_paths=("tests/test_model_structure_catalog.py",),
        no_source_reason=(
            "Consumes M01, M02, M03, M05, replay, and portfolio context; final decision construction belongs to "
            "trading-model and trading-evaluation rather than a deterministic trading-data source."
        ),
    ),
    ModelDataContract(
        model=5,
        slug="option_expression",
        model_name="OptionExpressionModel",
        doc_path="docs/18_model_05_option_expression.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.m05_option_expression_data_acquisition_contract_path",),
        feature_packages=("data_feature.m05_option_expression_feature_generation",),
        feed_packages=(
            "data_feed.10_feed_thetadata_option_primary_tracking",
            "data_feed.11_feed_thetadata_option_event_timeline",
        ),
        cli_commands=(
            "trading-data-m05-option-expression-contract-path",
            "trading-data-m05-option-expression-feature-generation",
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
    ModelDataContract(
        model=6,
        slug="residual_event_governance",
        model_name="ResidualEventGovernanceModel",
        doc_path="docs/19_model_06_residual_event_governance.md",
        owns_dedicated_data_surface=True,
        source_packages=("data_source.m06_residual_event_governance_data_acquisition",),
        feature_packages=("data_feature.m06_residual_event_governance_feature_generation",),
        cli_commands=(
            "trading-data-m06-residual-event-governance-data-acquisition",
            "trading-data-m06-residual-event-governance-feature-generation",
        ),
        test_paths=(
            "tests/data_source/test_numbered_data_sources.py",
            "tests/data_source/test_equity_abnormal_activity_pipeline.py",
            "tests/test_event_overlay_feature_generator.py",
        ),
    ),
)


def contracts_by_model() -> dict[int, ModelDataContract]:
    """Return model contracts keyed by M-number."""

    return {contract.model: contract for contract in MODEL_CONTRACTS}

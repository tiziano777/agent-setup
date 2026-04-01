"""Unit tests for autoresearch graph compilation and structure."""

from __future__ import annotations


class TestGraphCompilation:
    """Test that all pipeline variants compile successfully."""

    def test_random_pipeline_compiles(self):
        from src.agents.autoresearch.pipelines.random_pipeline import (
            build_random_pipeline,
        )

        graph = build_random_pipeline()
        assert graph is not None

    def test_grid_pipeline_compiles(self):
        from src.agents.autoresearch.pipelines.grid_pipeline import (
            build_grid_pipeline,
        )

        graph = build_grid_pipeline()
        assert graph is not None

    def test_agent_pipeline_compiles(self):
        from src.agents.autoresearch.pipelines.agent_pipeline import (
            build_agent_pipeline,
        )

        graph = build_agent_pipeline()
        assert graph is not None

    def test_default_graph_importable(self):
        from src.agents.autoresearch.agent import graph

        assert graph is not None

    def test_build_graph_strategies(self):
        from src.agents.autoresearch.agent import build_graph

        for strategy in ["agent", "random", "grid"]:
            g = build_graph(strategy=strategy)
            assert g is not None


class TestState:
    """Test state definition."""

    def test_state_has_messages_annotation(self):
        from src.agents.autoresearch.states.state import AutoresearchState

        annotations = AutoresearchState.__annotations__
        assert "messages" in annotations
        assert "session_id" in annotations
        assert "trajectory" in annotations
        assert "wave_configs" in annotations
        assert "loop_action" in annotations


class TestConfig:
    """Test configuration models."""

    def test_sweep_config_from_dict(self, minimal_sweep_config):
        from src.agents.autoresearch.config.models import SweepConfig

        config = SweepConfig.model_validate(minimal_sweep_config)
        assert config.name == "test-sweep"
        assert config.budget.max_experiments == 5
        assert "learning_rate" in config.search_space

    def test_parameter_spec_uniform_sample(self):
        from src.agents.autoresearch.config.models import ParameterSpec, ParamType

        spec = ParameterSpec(type=ParamType.UNIFORM, min=0.0, max=1.0)
        val = spec.sample_uniform()
        assert 0.0 <= val <= 1.0

    def test_parameter_spec_choice_sample(self):
        from src.agents.autoresearch.config.models import ParameterSpec, ParamType

        spec = ParameterSpec(type=ParamType.CHOICE, values=[1, 2, 3])
        val = spec.sample_uniform()
        assert val in [1, 2, 3]


class TestEntities:
    """Test entity dataclasses."""

    def test_experiment_round_trip(self):
        from src.agents.autoresearch.schemas.entities import (
            Experiment,
            ExperimentStatus,
        )

        exp = Experiment(
            run_id="test-001",
            session_id="sess-001",
            sweep_name="test",
            base_setup=".",
            hyperparams={"lr": 0.001},
            status=ExperimentStatus.COMPLETED,
            metrics={"accuracy": 0.95},
        )
        db_dict = exp.to_db_dict()
        assert db_dict["run_id"] == "test-001"
        assert '"lr"' in db_dict["hyperparams"]  # JSON string

        state_dict = exp.to_state_dict()
        assert state_dict["run_id"] == "test-001"
        assert state_dict["metrics"]["accuracy"] == 0.95

    def test_sweep_session_round_trip(self):
        from src.agents.autoresearch.schemas.entities import SweepSession

        session = SweepSession(
            session_id="sess-001",
            sweep_name="test",
            config_json={"name": "test"},
            budget_max_experiments=100,
            budget_max_wall_time_hours=8.0,
        )
        db_dict = session.to_db_dict()
        assert db_dict["session_id"] == "sess-001"


class TestTools:
    """Test that tools are importable."""

    def test_experiment_tools_importable(self):
        from src.agents.autoresearch.tools.experiment_tools import (
            get_best_config,
            get_trajectory,
            query_history,
        )

        assert query_history.name == "query_history"
        assert get_trajectory.name == "get_trajectory"
        assert get_best_config.name == "get_best_config"

    def test_sweep_tools_importable(self):
        from src.agents.autoresearch.tools.sweep_tools import (
            sample_random_config,
            validate_config,
        )

        assert sample_random_config.name == "sample_random_config"
        assert validate_config.name == "validate_config"

    def test_analysis_tools_importable(self):
        from src.agents.autoresearch.tools.analysis_tools import (
            compute_parameter_importance,
            generate_sweep_report,
        )

        assert compute_parameter_importance.name == "compute_parameter_importance"
        assert generate_sweep_report.name == "generate_sweep_report"


class TestNodes:
    """Test pure-function nodes."""

    def test_validate_proposals_fills_missing(self, minimal_sweep_config):
        from src.agents.autoresearch.nodes.validate_proposals import (
            validate_proposals,
        )

        state = {
            "wave_configs": [],  # empty proposals
            "active_search_space": minimal_sweep_config["search_space"],
            "trajectory": [],
            "sweep_config": minimal_sweep_config,
        }
        result = validate_proposals(state)
        # Should fallback to random and produce waves_parallel configs
        assert len(result["wave_configs"]) == 2  # waves_parallel=2

    def test_generate_random_wave(self, minimal_sweep_config):
        from src.agents.autoresearch.nodes.generate_random_wave import (
            generate_random_wave,
        )

        state = {
            "active_search_space": minimal_sweep_config["search_space"],
            "sweep_config": minimal_sweep_config,
            "experiments_remaining": 5,
            "wave_number": 0,
        }
        result = generate_random_wave(state)
        assert len(result["wave_configs"]) == 2
        for config in result["wave_configs"]:
            assert "learning_rate" in config
            assert "batch_size" in config

    def test_generate_grid(self, minimal_sweep_config):
        from src.agents.autoresearch.nodes.generate_grid import generate_grid

        state = {
            "active_search_space": minimal_sweep_config["search_space"],
            "sweep_config": minimal_sweep_config,
        }
        result = generate_grid(state)
        assert len(result["grid_configs"]) > 0
        assert result["grid_offset"] == 0

    def test_slice_next_wave(self, minimal_sweep_config):
        from src.agents.autoresearch.nodes.slice_next_wave import slice_next_wave

        configs = [{"lr": i} for i in range(10)]
        state = {
            "grid_configs": configs,
            "grid_offset": 0,
            "sweep_config": minimal_sweep_config,
            "experiments_remaining": 10,
            "wave_number": 0,
        }
        result = slice_next_wave(state)
        assert len(result["wave_configs"]) == 2
        assert result["grid_offset"] == 2

"""Unit tests for rdf_memory config and policy system."""

from src.shared.rdf_memory.config import (
    LifecyclePolicy,
    PolicyConfig,
    RDFMemorySettings,
    admin_policy,
    default_policy,
    read_write_policy,
)


class TestRDFMemorySettings:
    """Verify defaults and env-var driven configuration."""

    def test_defaults(self):
        s = RDFMemorySettings()
        assert s.fuseki_url == "http://localhost:3030"
        assert s.dataset == "knowledge"
        assert s.admin_user == "admin"
        assert s.admin_password == "admin"
        assert s.max_retries == 3
        assert s.retry_base_delay == 0.5
        assert s.default_lifecycle == "session"
        assert s.default_format == "turtle"
        assert s.shacl_enabled is False
        assert s.shacl_shapes_path is None

    def test_persistent_graphs_default(self):
        s = RDFMemorySettings()
        assert "core" in s.persistent_graphs

    def test_persistent_graphs_custom(self):
        s = RDFMemorySettings(persistent_graphs=["math", "ner", "geo"])
        assert s.persistent_graphs == ["math", "ner", "geo"]

    def test_default_persistent_graph(self):
        s = RDFMemorySettings()
        assert s.default_persistent_graph == "core"

    def test_custom_override(self):
        s = RDFMemorySettings(
            fuseki_url="http://fuseki:3030",
            dataset="test_ds",
            max_retries=5,
            default_lifecycle="persistent",
        )
        assert s.fuseki_url == "http://fuseki:3030"
        assert s.dataset == "test_ds"
        assert s.max_retries == 5
        assert s.default_lifecycle == "persistent"

    def test_policy_is_default(self):
        s = RDFMemorySettings()
        p = s.policy
        assert isinstance(p, PolicyConfig)
        assert p.session.llm_accessible is True
        assert p.staging.llm_accessible is False
        assert p.persistent.llm_accessible is True


class TestPolicyConfig:
    """Verify policy presets."""

    def test_default_policy_session_rw(self):
        p = default_policy()
        assert "SELECT" in p.session.allowed_operations
        assert "INSERT" in p.session.allowed_operations
        assert p.session.visible is True
        assert p.session.llm_accessible is True

    def test_default_policy_staging_hidden(self):
        p = default_policy()
        assert p.staging.visible is False
        assert p.staging.llm_accessible is False

    def test_default_policy_persistent_readonly(self):
        p = default_policy()
        assert "SELECT" in p.persistent.allowed_operations
        assert "INSERT" not in p.persistent.allowed_operations
        assert p.persistent.visible is True
        assert p.persistent.llm_accessible is True
        assert "DELETE" in p.persistent.requires_flag

    def test_read_write_policy_persistent_writable(self):
        p = read_write_policy()
        assert "INSERT" in p.persistent.allowed_operations
        assert "DELETE" in p.persistent.requires_flag

    def test_read_write_policy_staging_visible(self):
        p = read_write_policy()
        assert p.staging.visible is True
        assert p.staging.llm_accessible is False

    def test_admin_policy_full_access(self):
        p = admin_policy()
        for lifecycle in (p.session, p.staging, p.persistent):
            assert lifecycle.visible is True
            assert lifecycle.llm_accessible is True
            assert "SELECT" in lifecycle.allowed_operations
            assert "INSERT" in lifecycle.allowed_operations
            assert "DELETE" in lifecycle.allowed_operations
            assert "DROP" in lifecycle.allowed_operations

    def test_lifecycle_policy_defaults(self):
        lp = LifecyclePolicy()
        assert lp.visible is True
        assert lp.llm_accessible is True
        assert lp.requires_flag == []
        assert "SELECT" in lp.allowed_operations

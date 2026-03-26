"""Integration tests for sandbox engine (require Docker)."""

import pytest

try:
    import docker

    docker.from_env().ping()
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")


class TestDockerSandbox:
    def _make_sandbox(self, **kwargs):
        from src.shared.sandbox.config import SandboxSettings
        from src.shared.sandbox.engine import DockerSandbox

        settings = SandboxSettings(**kwargs)
        return DockerSandbox(settings=settings)

    def test_execute_echo(self):
        sb = self._make_sandbox()
        try:
            result = sb.execute("echo hello")
            assert result["exit_code"] == 0
            assert "hello" in result["stdout"]
        finally:
            sb.cleanup()

    def test_execute_python(self):
        sb = self._make_sandbox()
        try:
            result = sb.execute("python3 -c 'print(2+2)'")
            assert result["exit_code"] == 0
            assert "4" in result["stdout"]
        finally:
            sb.cleanup()

    def test_workspace_writable(self):
        sb = self._make_sandbox()
        try:
            result = sb.execute(
                "echo 'print(42)' > /workspace/test.py && python3 /workspace/test.py"
            )
            assert result["exit_code"] == 0
            assert "42" in result["stdout"]
        finally:
            sb.cleanup()

    def test_root_fs_readonly(self):
        sb = self._make_sandbox()
        try:
            result = sb.execute("touch /etc/test_file")
            assert result["exit_code"] != 0
        finally:
            sb.cleanup()

    def test_no_network(self):
        sb = self._make_sandbox()
        try:
            result = sb.execute(
                "python3 -c '"
                "import urllib.request; "
                'urllib.request.urlopen("http://1.1.1.1", timeout=3)\''
            )
            assert result["exit_code"] != 0
        finally:
            sb.cleanup()

    def test_timeout(self):
        sb = self._make_sandbox(timeout=3)
        try:
            result = sb.execute("sleep 30")
            assert result["timed_out"] is True
            assert result["exit_code"] == 124
        finally:
            sb.cleanup()

    def test_cleanup_removes_container(self):
        sb = self._make_sandbox()
        sb.ensure_running()
        container_id = sb._container.id
        sb.cleanup()
        client = docker.from_env()
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(container_id)

    def test_warm_container_reuse(self):
        sb = self._make_sandbox()
        try:
            sb.execute("echo first")
            container_id = sb._container.id
            sb.execute("echo second")
            assert sb._container.id == container_id
        finally:
            sb.cleanup()

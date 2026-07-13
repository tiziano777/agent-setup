"""LineageClient: main entry point for client-server lineage communication."""

from __future__ import annotations

import logging
import sys
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .data_classes.server_config import ServerConfig, ServerConfigError, load_server_config
from .base.connector import Connector, ConnectorFactory, ServerError
from .data_classes.http_config import PostRequest, PreRequest, PreResponse
from ..utils.snapshot import FileTooLargeError, capture_codebase

logger = logging.getLogger(__name__)

# HTTP status codes with dedicated exit codes
_MODEL_ID_MISMATCH_STATUS = 409  # ModelIdMismatchError → exit 7
_BASE_EXP_NOT_FOUND_STATUS = 422  # base_experiment_id not found → exit 6


class LineageClientError(Exception):
    """Raised on unrecoverable client errors."""


@dataclass
class ExecutionContext:
    """State passed from PRE to POST execution within a single run."""

    experiment_id: str
    strategy: str
    project_root: Path
    server_config: ServerConfig
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        """Alias concettuale per experiment_id (preparazione al dominio generico 'Run')."""
        return self.experiment_id

def _find_project_root(start: Path) -> Path:
    """Walk up from start to find directory containing .lineage/."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".lineage").is_dir():
            return current
        current = current.parent
    raise LineageClientError(
        f"No .lineage/ directory found walking up from '{start}'. "
        f"Ensure .lineage/server.yml and .lineage/experiment.yml exist."
    )

def _load_experiment_data(project_root: Path, config_path: Optional[str] = None) -> dict[str, Any]:
    """Load experiment data with priority: config.yml > .lineage/experiment.yml.

    If config_path is provided and contains an 'experiment' block, those values
    take priority over (and are merged on top of) .lineage/experiment.yml.
    This supports orchestration scenarios where experiment metadata is injected
    per-run directly into the training config.

    Args:
        project_root: Path to the project root.
        config_path: Optional path to the training config.yml.

    Returns:
        Merged experiment dict (config.yml experiment block wins on conflicts).

    Raises:
        LineageClientError: If .lineage/experiment.yml is missing.
    """
    exp_path = project_root / ".lineage" / "experiment.yml"
    if not exp_path.exists():
        raise LineageClientError(f"Missing '{exp_path}'")
    with open(exp_path) as f:
        base_data = yaml.safe_load(f) or {}
    exp_data: dict[str, Any] = base_data.get("experiment", {})

    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file) as f:
                    train_config = yaml.safe_load(f) or {}
                config_exp = train_config.get("experiment")
                if config_exp and isinstance(config_exp, dict):
                    logger.info(
                        "Found 'experiment' block in %s — overriding .lineage/experiment.yml fields: %s",
                        config_path,
                        list(config_exp.keys()),
                    )
                    exp_data = {**exp_data, **config_exp}
            except Exception as e:
                logger.warning("Could not read experiment block from '%s': %s", config_path, e)

    return exp_data

def _save_experiment_yml(project_root: Path, experiment_data: dict[str, Any]) -> None:
    """Save updated experiment data back to .lineage/experiment.yml."""
    exp_path = project_root / ".lineage" / "experiment.yml"
    with open(exp_path, "w") as f:
        yaml.dump({"experiment": experiment_data}, f, default_flow_style=False, sort_keys=False)

class LineageClient:
    """Client for lineage tracking communication with the server."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        config_dict: Optional[dict] = None,
        config_path: Optional[str] = None,
    ):
        # 1. Risoluzione della project_root
        if project_root is not None:
            self._project_root = project_root.resolve()
        elif config_path is not None:
            self._project_root = _find_project_root(Path(config_path).resolve().parent)
        else:
            # Fallback sulla cartella di esecuzione corrente
            self._project_root = _find_project_root(Path.cwd())

        # 2. Salviamo il dizionario e il path (opzionale) come metadato
        self._config_dict = config_dict or {}
        self._config_path = config_path

        self._server_config: Optional[ServerConfig] = None
        self._connector: Optional[Connector] = None

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def config_dict(self) -> dict:
        """Ritorna il dizionario delle configurazioni mergiato in-memory."""
        return self._config_dict

    @property
    def server_config(self) -> ServerConfig:
        if self._server_config is None:
            self._server_config = load_server_config(self._project_root)
        return self._server_config

    def _get_connector(self) -> Connector:
        if self._connector is None:
            self._connector = ConnectorFactory.create(self.server_config)
        return self._connector

    def _retry(self, fn, retries: int | None = None):
        """Execute fn with retries on ConnectionError."""
        max_retries = retries if retries is not None else self.server_config.retries
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except ConnectionError as e:
                last_error = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Connection failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1, max_retries + 1, wait, e,
                    )
                    time.sleep(wait)
        raise last_error  # type: ignore[misc]

    def pre_execution(self) -> ExecutionContext | None:
        """Execute PRE phase: capture codebase, send to server, update local state.

        Exit codes on blocking failures:
            4  — generic unexpected error
            6  — base_experiment_id not found in DB (HTTP 422)
            7  — model_id changed between runs (HTTP 409 / ModelIdMismatchError)
            8  — file > 10MB in codebase (FileTooLargeError)
            9  — server rejected request (other 4xx)
            10 — server unreachable (ConnectionError)
        """
        blocking = self.server_config.blocking

        try:
            # 1. Load experiment config (config.yml takes priority over .lineage/experiment.yml)
            exp_data = self._config_dict.get("experiment")

            # 2. Capture codebase snapshot
            codebase = capture_codebase(self._project_root)
            # debug:
            codebase_size = len(codebase.encode('utf-8'))
            logger.info(f"Codebase: JSON size: {codebase_size / (1024*1024):.2f} MB")
            logger.info(f"Codebase: Number of files: {len(json.loads(codebase))}")

            correct_model_id = self._config_dict.get("model", {}).get("model_id") == exp_data.get("model")
            correct_recipe = self._config_dict.get("recipe", {}).get("name") == exp_data.get("recipe")
            if not correct_model_id or not correct_recipe:
                logger.warning(
                    "Model ID, URI, merging, or recipe mismatch: model_id in config (%s) does not match model_id in experiment block (%s), recipe in config (%s) does not match recipe in experiment block (%s).",
                    self._config_dict.get("model", {}).get("model_id"), exp_data.get("model"),
                    self._config_dict.get("recipe", {}).get("name"), exp_data.get("recipe")
                )
                sys.exit(7)

            # 3. Build PRE request
            request = PreRequest(
                experiment_id=exp_data.get("id"),
                experiment_name=exp_data.get("name"),
                experiment_uri=str(self._project_root),
                base=exp_data.get("base"),
                base_experiment_id=exp_data.get("base_experiment_id"),
                previous_experiment_id=exp_data.get("previous_experiment_id"),
                description=exp_data.get("description"),
                experiment_type=exp_data.get("experiment_type"),
                model_uri=self._config_dict.get("model", {}).get("model_uri"),
                model_id=self._config_dict.get("experiment", {}).get("model"),
                recipe_id=self._config_dict.get("experiment", {}).get("recipe"),
                component_id=self._config_dict.get("experiment", {}).get("component"),
                codebase=codebase,
                checkpoint_resume_from=self._config_dict.get("model", {}).get("checkpoint_resume_from"),
            )

            logger.info(
                "PRE-execution: sending request to server: exp_name: %s, exp_uri: %s, model_id: %s, base_exp_id: %s, prev_exp_id: %s, description: %s, model_uri: %s, recipe_id: %s, component_id: %s, model_id %s, component_id %s, recipe_id: %s, checkpoint_resume_from: %s",
                request.experiment_name, request.experiment_uri, request.model_id, request.base_experiment_id,
                request.previous_experiment_id, request.description, request.model_uri, request.recipe_id,
                request.component_id, request.model_id, request.component_id, request.recipe_id,
                request.checkpoint_resume_from,
            )

            # 4. Send to server (with retries)
            connector = self._get_connector()
            logger.info("Sending PRE request with config %s", self.server_config)

            response: PreResponse = self._retry(lambda: connector.send_pre(request))

            logger.info(
                "Received PRE response from server: exp_id: %s, base %s, base_exp_id: %s, strategy: %s, previous_exp_id: %s",
                response.experiment_id, response.base, response.base_experiment_id, response.strategy,
                response.previous_experiment_id,
            )

            # 5. Update local .lineage/experiment.yml (always from base file, not merged)
            base_exp_data = _load_experiment_data(self._project_root)
            base_exp_data["id"] = response.experiment_id
            base_exp_data["previous_experiment_id"] = response.previous_experiment_id
            base_exp_data["base_experiment_id"] = response.base_experiment_id
            base_exp_data["base"] = response.base
            base_exp_data["status"] = "RUNNING"
            base_exp_data["uri"] = request.experiment_uri

            logger.info("Updating .lineage/experiment.yml with data: %s", base_exp_data)
            _save_experiment_yml(self._project_root, base_exp_data)
            logger.info(
                "Updated .lineage/experiment.yml with experiment_id: %s, base_experiment_id: %s, previous_experiment_id: %s, base: %s, status: RUNNING",
                response.experiment_id, response.base_experiment_id, response.previous_experiment_id, response.base,
            )

            logger.info(
                "PRE-execution complete: strategy=%s, exp_id=%s",
                response.strategy, response.experiment_id,
            )

            return ExecutionContext(
                experiment_id=response.experiment_id,
                strategy=response.strategy,
                project_root=self._project_root,
                server_config=self.server_config,
                extra={
                    "model_id": exp_data.get("model_id", ""),
                    "config_path": self._config_path,
                    "checkpoint_resume_from": request.checkpoint_resume_from,
                },
            )

        except FileTooLargeError as e:
            logger.error("BLOCKED: %s", e)
            sys.exit(8)

        except ServerError as e:
            # Differentiate specific 4xx codes with dedicated exit codes
            if e.status_code == _MODEL_ID_MISMATCH_STATUS:
                logger.error("BLOCKED: model_id mismatch — %s", e.detail)
                sys.exit(7)
            if e.status_code == _BASE_EXP_NOT_FOUND_STATUS:
                logger.error("BLOCKED: base_experiment_id not found — %s", e.detail)
                sys.exit(6)
            logger.error("Server rejected PRE request: %s", e)
            if blocking:
                sys.exit(9)
            return None

        except (ConnectionError, ServerConfigError) as e:
            logger.error("PRE-execution communication failed: %s", e)
            if blocking:
                sys.exit(10)
            logger.warning("Non-blocking mode: continuing without lineage tracking")
            return None

        except Exception as e:
            logger.error("PRE-execution error: %s", e, exc_info=True)
            if blocking:
                sys.exit(4)
            return None

    def post_execution(
        self,
        ctx: ExecutionContext,
        status: str,
        exit_message: Optional[str] = None,
        metrics_uri: Optional[str] = None,
    ) -> None:
        """Execute POST phase: report final status to server."""
        try:
            request = PostRequest(
                experiment_id=ctx.experiment_id,
                status=status,
                exit_message=exit_message,
                metrics_uri=metrics_uri,
                strategy=ctx.strategy,
                checkpoint_resume_from=ctx.extra.get("checkpoint_resume_from"),
            )

            connector = self._get_connector()
            self._retry(lambda: connector.send_post(request))

            # Reload from disk to preserve all fields before writing status
            base_exp_data = _load_experiment_data(self._project_root)
            logger.info("PRE Updating .lineage/experiment.yml with data: %s", base_exp_data)
            base_exp_data["status"] = status
            logger.info("POST Updating .lineage/experiment.yml with data: %s", base_exp_data)
            _save_experiment_yml(self._project_root, base_exp_data)

            logger.info("POST-execution complete: status=%s, exp_id=%s", status, ctx.experiment_id)

        except Exception as e:
            logger.error("POST-execution error: %s", e, exc_info=True)

    def emit_node(
        self,
        ctx: ExecutionContext,
        node_type: str,
        payload: dict[str, Any],
        edge_type: str = "produced",
    ) -> None:
        """Crea un nodo generico collegato al run corrente sul grafo."""
        if ctx is None:
            logger.warning("emit_node called with None context, skipping")
            return

        def _emit():
            if node_type == "Checkpoint":
                # Fallback compatibilità server esistente (endpoint /api/v1/checkpoint)
                from .data_classes.http_config import CheckpointRequest
                request = CheckpointRequest(
                    experiment_id=ctx.experiment_id,
                    name=payload.get("name", ""),
                    epoch=payload.get("epoch", 0),
                    run=payload.get("run", 0),
                    uri=payload.get("uri", ""),
                    metrics=payload.get("metrics", ""),
                    derived_from=payload.get("derived_from", ""),
                    is_merging=payload.get("is_merging", False),
                )
                connector = self._get_connector()
                connector.send_checkpoint(request)
            else:
                # Endpoint generico (preparato per futura estensione server)
                import json
                import urllib.request
                from urllib.error import URLError

                base_url = getattr(
                    self.server_config, "url", getattr(self.server_config, "base_url", None)
                )
                if not base_url:
                    logger.warning("Cannot determine server URL for generic node emission")
                    return

                url = f"{base_url.rstrip('/')}/graph/nodes"
                data = json.dumps({
                    "run_id": ctx.run_id,
                    "node_type": node_type,
                    "payload": payload,
                    "edge_type": edge_type,
                }).encode("utf-8")

                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    timeout = getattr(self.server_config, "timeout", 30)
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        resp.read()
                except URLError as e:
                    # Wrappa in ConnectionError per uniformità con il meccanismo di retry
                    raise ConnectionError(f"Failed to emit generic node: {e}") from e

        try:
            self._retry(_emit)
            logger.info("Node emitted: type=%s, edge=%s, run=%s", node_type, edge_type, ctx.run_id)
        except Exception as e:
            logger.error("Failed to emit node %s: %s", node_type, e)

    def close(self) -> None:
        """Release resources."""
        if self._connector is not None:
            self._connector.close()
            self._connector = None
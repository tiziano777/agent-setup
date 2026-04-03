-- ============================================
-- Inizializzazione database PostgreSQL
-- ============================================
-- Questo script viene eseguito automaticamente dal container
-- postgres-vector al primo avvio (docker-entrypoint-initdb.d).
-- Se i database/schema esistono gia, non fa nulla.

-- Database dedicato per Arize Phoenix (observability)
CREATE DATABASE phoenix;

-- Schema isolati nel database 'vectors' per i diversi toolkit.
-- L'extension vector viene creata nel database di default (vectors).
\c vectors

CREATE EXTENSION IF NOT EXISTS vector;

-- Schema per la pipeline di retrieval (RAG text + multimodal)
CREATE SCHEMA IF NOT EXISTS retrieval;

-- Schema per i RAG evaluator di DeepEval
CREATE SCHEMA IF NOT EXISTS deepeval;

-- Schema per Cognee knowledge graph vector storage
CREATE SCHEMA IF NOT EXISTS cognee;





-- Schema per AutoResearch hyperparameter optimization
CREATE SCHEMA IF NOT EXISTS autoresearch;

-- Sweep sessions (top-level grouping)
CREATE TABLE IF NOT EXISTS autoresearch.sweep_sessions (
    session_id              TEXT PRIMARY KEY,
    sweep_name              TEXT NOT NULL,
    config_json             JSONB NOT NULL,
    strategy_type           TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    wall_time_used_s        REAL DEFAULT 0.0,
    escalation_stage        INT DEFAULT 0,
    total_experiments       INT DEFAULT 0,
    budget_max_experiments  INT NOT NULL,
    budget_max_wall_time_hours REAL NOT NULL,
    best_run_id             TEXT,
    best_metric_value       REAL,
    best_hyperparams        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sweep_sessions_name
    ON autoresearch.sweep_sessions(sweep_name);
CREATE INDEX IF NOT EXISTS idx_sweep_sessions_status
    ON autoresearch.sweep_sessions(status);

-- Experiments (individual runs)
CREATE TABLE IF NOT EXISTS autoresearch.experiments (
    run_id              TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL
        REFERENCES autoresearch.sweep_sessions(session_id),
    sweep_name          TEXT NOT NULL,
    base_setup          TEXT NOT NULL,
    hyperparams         JSONB NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    parent_run_id       TEXT,
    wave_number         INT,
    metrics             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    wall_time_seconds   REAL,
    agent_reasoning     TEXT,
    hardware_used       TEXT,
    notes               TEXT,
    code_diff           TEXT,
    runner_backend      TEXT,
    log_path            TEXT
);

CREATE INDEX IF NOT EXISTS idx_experiments_session
    ON autoresearch.experiments(session_id);
CREATE INDEX IF NOT EXISTS idx_experiments_sweep
    ON autoresearch.experiments(sweep_name);
CREATE INDEX IF NOT EXISTS idx_experiments_status
    ON autoresearch.experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_created
    ON autoresearch.experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_wave
    ON autoresearch.experiments(wave_number);

-- Agent decisions (audit trail)
CREATE TABLE IF NOT EXISTS autoresearch.agent_decisions (
    decision_id         TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL
        REFERENCES autoresearch.sweep_sessions(session_id),
    agent_role          TEXT NOT NULL,
    decision_type       TEXT NOT NULL,
    input_summary       TEXT,
    output_json         JSONB NOT NULL,
    reasoning           TEXT,
    wave_number         INT,
    token_usage         JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_session
    ON autoresearch.agent_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_decisions_agent
    ON autoresearch.agent_decisions(agent_role);
CREATE INDEX IF NOT EXISTS idx_decisions_created
    ON autoresearch.agent_decisions(created_at);

-- Knowledge learned (persistent across sessions)
CREATE TABLE IF NOT EXISTS autoresearch.knowledge (
    knowledge_id        TEXT PRIMARY KEY,
    sweep_name          TEXT NOT NULL,
    base_setup          TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    best_config         JSONB DEFAULT '{}'::jsonb,
    best_metric_value   REAL,
    parameter_importance JSONB DEFAULT '{}'::jsonb,
    parameter_recommendations JSONB DEFAULT '{}'::jsonb,
    crash_patterns      JSONB DEFAULT '[]'::jsonb,
    total_experiments   INT DEFAULT 0,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_setup
    ON autoresearch.knowledge(base_setup, metric_name);

-- Session checkpoints (resume/handoff)
CREATE TABLE IF NOT EXISTS autoresearch.checkpoints (
    checkpoint_id       TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL
        REFERENCES autoresearch.sweep_sessions(session_id),
    checkpoint_data     JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_session
    ON autoresearch.checkpoints(session_id);

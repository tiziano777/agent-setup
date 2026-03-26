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

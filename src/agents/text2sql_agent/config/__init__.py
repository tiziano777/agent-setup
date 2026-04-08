"""Configuration for text2sql agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Text2SQLSettings:
    """Configuration for Text2SQL agent."""

    # Database settings
    db_host: str = field(default_factory=lambda: os.getenv("SQL_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("SQL_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("SQL_DATABASE", "agent_db"))
    db_user: str = field(default_factory=lambda: os.getenv("SQL_USERNAME", "postgres"))
    db_password: str = field(default_factory=lambda: os.getenv("SQL_PASSWORD", "postgres"))

    # Agent settings
    max_retries: int = field(default=3)
    timeout: int = field(default=30)

    # Debug mode
    debug: bool = field(default_factory=lambda: os.getenv("TEXT2SQL_DEBUG", "false").lower() == "true")

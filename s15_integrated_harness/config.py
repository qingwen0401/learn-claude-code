#!/usr/bin/env python3
"""
s15 config layer: everything the harness needs before the loop starts.

This module is loaded by s15_integrated_harness/code.py through importlib
(by path, not through sys.path), so it must not assume the caller's sys.path
and must resolve workspace paths from the process working directory at load
time. It owns exactly four things:

    env bootstrap (dotenv + AUTH_TOKEN cleanup)
    the Anthropic client
    model ids                -> MODEL / PRIMARY_MODEL / FALLBACK_MODEL
    paths and runtime limits -> WORKDIR, SKILLS_DIR, ..., CONTEXT_LIMIT

Everything else (loop, tools, hooks, teams) stays in code.py.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings, one field per frozen module-level name."""

    workdir: Path
    client: object
    model: str
    primary_model: str
    fallback_model: str | None
    skills_dir: Path
    transcript_dir: Path
    tool_results_dir: Path
    default_max_tokens: int
    escalated_max_tokens: int
    max_retries: int
    max_consecutive_529: int
    max_recovery_retries: int
    base_delay_ms: int
    context_limit: int
    keep_recent_tool_results: int
    persist_threshold: int
    continuation_prompt: str


def load_settings() -> Settings:
    """Bootstrap env, client, model ids, workspace paths, and limits once."""
    # 应用启动时集中读取环境并构造运行配置，供 code.py 导入复用。
    load_dotenv(override=True)
    if os.getenv("ANTHROPIC_BASE_URL"):
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

    workdir = Path.cwd()
    model = os.environ["MODEL_ID"]
    return Settings(
        workdir=workdir,
        client=Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL")),
        model=model,
        primary_model=model,
        fallback_model=os.getenv("FALLBACK_MODEL_ID"),
        skills_dir=workdir / "skills",
        transcript_dir=workdir / ".transcripts",
        tool_results_dir=workdir / ".task_outputs" / "tool-results",
        default_max_tokens=8000,
        escalated_max_tokens=16000,
        max_retries=3,
        max_consecutive_529=2,
        max_recovery_retries=2,
        base_delay_ms=500,
        context_limit=50000,
        keep_recent_tool_results=3,
        persist_threshold=30000,
        continuation_prompt=("Continue from the previous response. "
                             "Do not repeat completed work."),
    )


SETTINGS = load_settings()

# Module-level aliases: code.py re-exports these names unchanged, so the rest
# of the harness never learns that the config layer moved.
WORKDIR = SETTINGS.workdir
client = SETTINGS.client
MODEL = SETTINGS.model
PRIMARY_MODEL = SETTINGS.primary_model
FALLBACK_MODEL = SETTINGS.fallback_model
SKILLS_DIR = SETTINGS.skills_dir
TRANSCRIPT_DIR = SETTINGS.transcript_dir
TOOL_RESULTS_DIR = SETTINGS.tool_results_dir
DEFAULT_MAX_TOKENS = SETTINGS.default_max_tokens
ESCALATED_MAX_TOKENS = SETTINGS.escalated_max_tokens
MAX_RETRIES = SETTINGS.max_retries
MAX_CONSECUTIVE_529 = SETTINGS.max_consecutive_529
MAX_RECOVERY_RETRIES = SETTINGS.max_recovery_retries
BASE_DELAY_MS = SETTINGS.base_delay_ms
CONTEXT_LIMIT = SETTINGS.context_limit
KEEP_RECENT_TOOL_RESULTS = SETTINGS.keep_recent_tool_results
PERSIST_THRESHOLD = SETTINGS.persist_threshold
CONTINUATION_PROMPT = SETTINGS.continuation_prompt

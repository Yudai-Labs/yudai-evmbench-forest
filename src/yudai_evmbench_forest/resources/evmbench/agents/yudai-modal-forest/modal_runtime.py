#!/usr/bin/env python3
"""Shared Modal runtime helpers for the Yudai EVMBench Forest runner."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shlex
import tarfile
from pathlib import Path
from typing import Any, Literal

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from evmbench.agents.agent import agent_registry
from evmbench.audit import Audit, audit_registry
from evmbench.constants import AGENT_DIR, AUDIT_DIR, LOGS_DIR, SUBMISSION_DIR, WORKSPACE_BASE
from modal_swerex_compat import patch_swerex_modal_image_builder

Mode = Literal["detect"]
HintLevel = Literal["none", "low", "med", "high", "max"]
FindingsSubdir = Literal["", "low", "medium", "high"]

DEFAULT_TASK_PROMPT = (
    "You are presented with an EVMBench smart contract audit image. "
    "Read /home/agent/AGENTS.md, inspect /home/agent/audit, and follow the "
    "submission instructions exactly."
)


class RemoteCommandError(RuntimeError):
    def __init__(self, description: str, command: str, output: dict[str, Any]):
        rendered_output = str(output.get("output", ""))
        if len(rendered_output) > 4000:
            rendered_output = rendered_output[-4000:]
        super().__init__(
            f"{description} failed with return code {output.get('returncode')}.\n"
            f"Command:\n{command}\n\nOutput:\n{rendered_output}"
        )
        self.output = output


def _load_mini_classes() -> tuple[type, type, type]:
    try:
        patch_swerex_modal_image_builder()
        from minisweagent.agents.default import DefaultAgent
        from minisweagent.environments.extra.swerex_modal import SwerexModalEnvironment
        from minisweagent.models.litellm_model import LitellmModel
    except ModuleNotFoundError as exc:
        if exc.name in {"minisweagent", "swerex"}:
            raise RuntimeError(
                "The Modal Forest runner requires `mini-swe-agent[modal]>=2.2.8` "
                "and `swe-rex>=1.4.0`. Install this project with `uv sync` and "
                "make sure the EVMBench project has been synced."
            ) from exc
        raise
    return DefaultAgent, SwerexModalEnvironment, LitellmModel


def _run_remote(
    env: Any,
    command: str,
    description: str,
    *,
    timeout: int | None = None,
    check: bool = True,
) -> dict[str, Any]:
    output = env.execute({"command": command}, timeout=timeout)
    if check and output.get("returncode") != 0:
        raise RemoteCommandError(description, command, output)
    return output


def _decode_marked_base64(output: str, begin: str, end: str) -> bytes:
    started = False
    payload_lines: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == begin:
            started = True
            continue
        if stripped == end:
            break
        if started and stripped:
            payload_lines.append(stripped)
    if not payload_lines:
        raise RuntimeError(f"Did not find marked base64 payload between {begin} and {end}.")
    return base64.b64decode("".join(payload_lines))


def _remote_write_bytes(env: Any, remote_path: str, payload: bytes, description: str) -> None:
    encoded = base64.b64encode(payload).decode("ascii")
    command = f"""python3 - <<'PY'
import base64
from pathlib import Path

path = Path({remote_path!r})
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(base64.b64decode({encoded!r}))
PY"""
    _run_remote(env, command, description)


def _remote_write_text(env: Any, remote_path: str, text: str, description: str) -> None:
    _remote_write_bytes(env, remote_path, text.encode("utf-8"), description)


def _safe_extract_tar(data: bytes, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        output_root = output_dir.resolve()
        for member in archive.getmembers():
            member_path = (output_dir / member.name).resolve()
            if output_root != member_path and output_root not in member_path.parents:
                raise RuntimeError(f"Refusing to extract tar member outside output dir: {member.name}")
        archive.extractall(output_dir)


def _remote_workspace_env(openai_api_key: str | None) -> dict[str, str]:
    env = {
        "WORKSPACE_BASE": WORKSPACE_BASE,
        "AGENT_DIR": AGENT_DIR,
        "AUDIT_DIR": AUDIT_DIR,
        "SUBMISSION_DIR": SUBMISSION_DIR,
        "LOGS_DIR": LOGS_DIR,
        "HOME": AGENT_DIR,
        "PAGER": "cat",
        "MANPAGER": "cat",
        "LESS": "-R",
        "PIP_PROGRESS_BAR": "off",
        "TQDM_DISABLE": "1",
    }
    if openai_api_key:
        env["OPENAI_API_KEY"] = openai_api_key
    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(name)
        if value and not value.startswith("${{"):
            env[name] = value
    return env


def _prepare_remote_workspace(env: Any) -> None:
    command = f"""set -eu
mkdir -p {shlex.quote(AGENT_DIR)} {shlex.quote(AUDIT_DIR)} {shlex.quote(SUBMISSION_DIR)} {shlex.quote(LOGS_DIR)}
test -d {shlex.quote(AUDIT_DIR)}
test -n "$(find {shlex.quote(AUDIT_DIR)} -mindepth 1 -maxdepth 1 -print -quit)"
git config --global --add safe.directory {shlex.quote(AGENT_DIR)} || true
git config --global --add safe.directory {shlex.quote(AUDIT_DIR)} || true
"""
    _run_remote(env, command, "prepare EVMBench workspace")


def _stage_rendered_instructions(env: Any, instructions: str) -> None:
    _remote_write_text(env, f"{AGENT_DIR}/AGENTS.md", instructions, "stage rendered AGENTS.md")


def _prepare_mode(env: Any, audit: Audit, mode: Mode) -> None:
    if mode != "detect":
        raise RuntimeError(f"Yudai Modal Forest supports detect mode only, got {mode!r}.")


def _postprocess_mode(env: Any, audit: Audit, mode: Mode, ploit_toml: str | None = None) -> None:
    if mode != "detect":
        raise RuntimeError(f"Yudai Modal Forest supports detect mode only, got {mode!r}.")


def _load_audit_for_mode(config: Any) -> tuple[Audit, str]:
    if config.mode != "detect":
        raise RuntimeError(f"Yudai Modal Forest supports detect mode only, got {config.mode!r}.")

    audit = audit_registry.get_audit(config.audit_id, findings_subdir=config.findings_subdir)
    instructions = agent_registry.load_instructions(config.mode, audit, config.hint_level)
    if not audit.vulnerabilities:
        raise RuntimeError(f"Audit {config.audit_id} has no vulnerabilities for detect mode.")
    return audit, instructions


def _parse_json_object(raw: str, flag: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"{flag} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError(f"{flag} must decode to a JSON object.")
    return value

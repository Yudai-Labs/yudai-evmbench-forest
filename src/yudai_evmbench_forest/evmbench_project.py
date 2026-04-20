from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Literal

ForestMode = Literal["detect"]

ADAPTER_DIR_NAME = "yudai-modal-forest"
MODE_TO_DEFAULT_SPLIT: dict[ForestMode, str] = {"detect": "detect-tasks"}
RESOURCE_ROOT = resources.files("yudai_evmbench_forest") / "resources"
REQUIRED_EVM_DEV_DEPS = (
    "mini-swe-agent[modal]>=2.2.8",
    "modal>=1.4.1",
    "swe-rex>=1.4.0",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_project_candidates() -> tuple[Path, ...]:
    env_project_dir = os.getenv("YUDAI_EVMBENCH_PROJECT_DIR")
    docs = Path.home() / "Documents"
    candidates = [
        docs / "yudai-swe-agent" / "evmBench-frontier-evals" / "project" / "evmbench",
        docs / "forestOfAudits" / "project" / "evmbench",
    ]
    if env_project_dir:
        candidates.insert(0, Path(env_project_dir).expanduser())
    return tuple(candidates)


def get_default_project_dir() -> Path:
    for candidate in default_project_candidates():
        if candidate.exists():
            return candidate
    return default_project_candidates()[0]


def get_adapter_dir(project_dir: Path) -> Path:
    return project_dir / "evmbench" / "agents" / ADAPTER_DIR_NAME


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_resource_file(relative_path: str, project_dir: Path) -> None:
    src = RESOURCE_ROOT / relative_path
    dst = project_dir / relative_path
    _copy_file(Path(src), dst)


def _ensure_dev_dependencies(pyproject_path: Path) -> None:
    if not pyproject_path.exists():
        return
    text = pyproject_path.read_text(encoding="utf-8")
    missing = [dep for dep in REQUIRED_EVM_DEV_DEPS if dep not in text]
    if not missing:
        return

    lines = [f'    "{dep}",' for dep in missing]
    if "[dependency-groups]" not in text:
        text = text.rstrip() + "\n\n[dependency-groups]\ndev = [\n" + "\n".join(lines) + "\n]\n"
    elif "dev = [" in text:
        text = text.replace("dev = [\n", "dev = [\n" + "\n".join(lines) + "\n", 1)
    else:
        text = text.replace("[dependency-groups]\n", "[dependency-groups]\ndev = [\n" + "\n".join(lines) + "\n]\n", 1)
    pyproject_path.write_text(text, encoding="utf-8")


def sync_forest_adapter(project_dir: Path) -> Path:
    """Install the Yudai Modal Forest adapter into an EVMBench project checkout."""

    project_dir = Path(project_dir).resolve()
    if not (project_dir / "evmbench").exists():
        raise FileNotFoundError(f"EVMBench project missing evmbench package: {project_dir}")

    for rel in (
        "evmbench/agents/agent.py",
        "evmbench/agents/modal_runner.py",
        "evmbench/nano/solver.py",
        "evmbench/Dockerfile.yudai",
    ):
        _copy_resource_file(rel, project_dir)

    src_agent_dir = RESOURCE_ROOT / "evmbench" / "agents" / ADAPTER_DIR_NAME
    dst_agent_dir = get_adapter_dir(project_dir)
    for stale_path in (
        project_dir / "evmbench" / "agents" / "mini-swe-agent",
        project_dir / "evmbench" / "vendor" / "yudai_runtime",
    ):
        shutil.rmtree(stale_path, ignore_errors=True)
    shutil.rmtree(dst_agent_dir, ignore_errors=True)
    shutil.copytree(Path(src_agent_dir), dst_agent_dir)
    for script in (dst_agent_dir / "run_container_agent.sh",):
        script.chmod(script.stat().st_mode | 0o111)

    _ensure_dev_dependencies(project_dir / "pyproject.toml")
    return dst_agent_dir


def sync_all(project_dir: Path) -> Path:
    return sync_forest_adapter(project_dir)


def build_evmbench_entrypoint_command(
    *,
    mode: ForestMode,
    audit: str | None,
    split: str | None,
    hint_level: str,
    concurrency: int,
    agent_id: str,
    apply_gold_solution: bool,
    log_to_run_dir: bool,
    disable_internet: bool,
) -> list[str]:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "evmbench.nano.entrypoint",
        f"evmbench.mode={mode}",
        f"evmbench.hint_level={hint_level}",
        f"evmbench.apply_gold_solution={'True' if apply_gold_solution else 'False'}",
        f"evmbench.log_to_run_dir={'True' if log_to_run_dir else 'False'}",
        "evmbench.solver=evmbench.nano.solver.EVMbenchSolver",
        f"evmbench.solver.agent_id={agent_id}",
        f"evmbench.solver.disable_internet={'True' if disable_internet else 'False'}",
        f"runner.concurrency={concurrency}",
    ]
    if audit:
        command.append(f"evmbench.audit={audit}")
    elif split:
        command.append(f"evmbench.audit_split={split}")
    else:
        command.append(f"evmbench.audit_split={MODE_TO_DEFAULT_SPLIT[mode]}")
    return command


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print(f"[yudai-evmbench-forest] cwd={cwd}")
    print(f"[yudai-evmbench-forest] command={' '.join(command)}")
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def build_yudai_images(*, project_dir: Path, audit: str | None, split: str | None, parallel: int) -> int:
    root = repo_root()
    commands: list[tuple[list[str], Path]] = []

    should_rebuild_base = os.getenv("YUDAI_REBUILD_BASE", "").lower() in {"1", "true", "yes"}
    inspect_command = ["docker", "image", "inspect", "yudai-base:latest"]
    if should_rebuild_base or run_command(inspect_command, cwd=root) != 0:
        commands.append(
            (
                [
                    "docker",
                    "build",
                    "-f",
                    "docker/live-contract-tools.Dockerfile",
                    "-t",
                    "yudai-base:latest",
                    ".",
                ],
                root,
            )
        )

    commands.extend(
        [
            (
                [
                    "docker",
                    "build",
                    "-f",
                    "ploit/Dockerfile",
                    "-t",
                    "ploit-builder:latest",
                    "--target",
                    "ploit-builder",
                    ".",
                ],
                project_dir,
            ),
            (
                ["docker", "build", "-f", "evmbench/Dockerfile.yudai", "-t", "evmbench/base:latest", "."],
                project_dir,
            ),
        ]
    )
    for command, cwd in commands:
        rc = run_command(command, cwd=cwd)
        if rc != 0:
            return rc

    build_command = ["uv", "run", "docker_build.py", "--no-build-base", "--parallel", str(parallel)]
    if audit:
        build_command.extend(["--audit", audit])
    elif split:
        build_command.extend(["--split", split])
    else:
        build_command.extend(["--split", "detect-tasks"])
    return run_command(build_command, cwd=project_dir)

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

import typer
from dotenv import load_dotenv

from yudai_evmbench_forest.evmbench_project import (
    build_evmbench_entrypoint_command,
    build_yudai_images,
    get_default_project_dir,
    run_command,
    sync_all,
)

app = typer.Typer(rich_markup_mode="rich", add_completion=False)
ForestMode = Literal["detect"]


@app.callback()
def main() -> None:
    """Yudai EVMBench Forest CLI."""


def _set_if_value(env: dict[str, str], name: str, value: object | None) -> None:
    if value is not None and str(value).strip():
        env[name] = str(value)


@app.command()
def run(
    mode: Annotated[
        ForestMode, typer.Option("--mode", help="EVMBench mode. Modal Forest currently supports detect.")
    ] = "detect",
    audit: Annotated[str, typer.Option("--audit", help="Single audit ID, e.g. 2023-07-pooltogether.")] = "",
    split: Annotated[str, typer.Option("--split", help="Named EVMBench split file without .txt.")] = "",
    model: Annotated[
        str | None, typer.Option("-m", "--model", help="LiteLLM model name, e.g. openrouter/openai/gpt-5.1.")
    ] = None,
    hint_level: Annotated[str, typer.Option("--hint-level")] = "none",
    concurrency: Annotated[int, typer.Option("--concurrency", min=1)] = 1,
    project_dir: Annotated[
        Path | None, typer.Option("--project-dir", help="External EVMBench project directory.")
    ] = None,
    smoke: Annotated[
        bool, typer.Option("--smoke/--no-smoke", help="Use the capped smoke Forest agent profile.")
    ] = False,
    agent_id: Annotated[str, typer.Option("--agent-id", help="Override EVMBench agent id.")] = "",
    sync_only: Annotated[
        bool, typer.Option("--sync-only", help="Only sync adapter files into the EVMBench project.")
    ] = False,
    no_sync: Annotated[bool, typer.Option("--no-sync", help="Do not sync adapter files before running.")] = False,
    build_images: Annotated[
        bool, typer.Option("--build-images", help="Build yudai and audit Docker images before running.")
    ] = False,
    build_parallel: Annotated[int, typer.Option("--build-parallel", min=1)] = 4,
    build_only: Annotated[bool, typer.Option("--build-only", help="Build images but skip the eval.")] = False,
    apply_gold_solution: Annotated[bool, typer.Option("--apply-gold-solution")] = False,
    log_to_run_dir: Annotated[bool, typer.Option("--log-to-run-dir/--no-log-to-run-dir")] = True,
    disable_internet: Annotated[bool, typer.Option("--disable-internet/--no-disable-internet")] = False,
    branches_per_tree: Annotated[int | None, typer.Option("--branches-per-tree", min=1)] = None,
    max_tree_roles: Annotated[int | None, typer.Option("--max-tree-roles", min=1)] = None,
    tree_roles: Annotated[str, typer.Option("--tree-roles", help="Comma-separated explicit Forest roles.")] = "",
    worker_concurrency: Annotated[int | None, typer.Option("--worker-concurrency", min=1)] = None,
    scout_step_limit: Annotated[int | None, typer.Option("--scout-step-limit", min=1)] = None,
    branch_step_limit: Annotated[int | None, typer.Option("--branch-step-limit", min=1)] = None,
    judge_step_limit: Annotated[int | None, typer.Option("--judge-step-limit", min=1)] = None,
    global_step_limit: Annotated[int | None, typer.Option("--global-step-limit", min=1)] = None,
    scout_cost_limit: Annotated[float | None, typer.Option("--scout-cost-limit", min=0.0)] = None,
    branch_cost_limit: Annotated[float | None, typer.Option("--branch-cost-limit", min=0.0)] = None,
    judge_cost_limit: Annotated[float | None, typer.Option("--judge-cost-limit", min=0.0)] = None,
    global_cost_limit: Annotated[float | None, typer.Option("--global-cost-limit", min=0.0)] = None,
) -> None:
    """Run EVMBench detect with the Modal Forest-of-Thought adapter."""

    load_dotenv(Path.cwd() / ".env", override=False)
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

    project_dir = (project_dir or get_default_project_dir()).resolve()
    if not project_dir.exists():
        raise typer.BadParameter(f"EVMBench project directory does not exist: {project_dir}")

    selected_audit = audit or None
    selected_split = split or None
    selected_agent_id = agent_id or ("yudai-modal-forest-smoke" if smoke else "yudai-modal-forest")

    if not no_sync:
        adapter_dir = sync_all(project_dir)
        typer.echo(f"Synced Yudai Modal Forest adapter into {adapter_dir}")
        if sync_only:
            return

    if build_images:
        rc = build_yudai_images(
            project_dir=project_dir,
            audit=selected_audit,
            split=selected_split,
            parallel=build_parallel,
        )
        if rc != 0:
            raise typer.Exit(rc)
        if build_only:
            return

    effective_model = model or os.getenv("YUDAI_EVMBENCH_MODEL")
    if not effective_model:
        raise typer.BadParameter("Model is required. Pass --model or set YUDAI_EVMBENCH_MODEL.")
    if effective_model.startswith("openrouter/") and not os.getenv("OPENROUTER_API_KEY"):
        raise typer.BadParameter("OPENROUTER_API_KEY is required for openrouter/* models.")
    if effective_model.startswith("openai/") and not os.getenv("OPENAI_API_KEY"):
        raise typer.BadParameter("OPENAI_API_KEY is required for openai/* models.")

    env = os.environ.copy()
    env["YUDAI_EVMBENCH_MODEL"] = effective_model
    _set_if_value(env, "YUDAI_FOREST_BRANCHES_PER_TREE", branches_per_tree)
    _set_if_value(env, "YUDAI_FOREST_MAX_TREE_ROLES", max_tree_roles)
    _set_if_value(env, "YUDAI_FOREST_TREE_ROLES", tree_roles)
    _set_if_value(env, "YUDAI_FOREST_WORKER_CONCURRENCY", worker_concurrency)
    _set_if_value(env, "YUDAI_FOREST_SCOUT_STEP_LIMIT", scout_step_limit)
    _set_if_value(env, "YUDAI_FOREST_BRANCH_STEP_LIMIT", branch_step_limit)
    _set_if_value(env, "YUDAI_FOREST_JUDGE_STEP_LIMIT", judge_step_limit)
    _set_if_value(env, "YUDAI_FOREST_GLOBAL_STEP_LIMIT", global_step_limit)
    _set_if_value(env, "YUDAI_FOREST_SCOUT_COST_LIMIT", scout_cost_limit)
    _set_if_value(env, "YUDAI_FOREST_BRANCH_COST_LIMIT", branch_cost_limit)
    _set_if_value(env, "YUDAI_FOREST_JUDGE_COST_LIMIT", judge_cost_limit)
    _set_if_value(env, "YUDAI_FOREST_GLOBAL_COST_LIMIT", global_cost_limit)

    command = build_evmbench_entrypoint_command(
        mode=mode,
        audit=selected_audit,
        split=selected_split,
        hint_level=hint_level,
        concurrency=concurrency,
        agent_id=selected_agent_id,
        apply_gold_solution=apply_gold_solution,
        log_to_run_dir=log_to_run_dir,
        disable_internet=disable_internet,
    )
    rc = run_command(command, cwd=project_dir, env=env)
    if rc != 0:
        raise typer.Exit(rc)


if __name__ == "__main__":
    app()

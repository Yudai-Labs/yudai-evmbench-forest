from pathlib import Path

from yudai_evmbench_forest.sync import build_evmbench_entrypoint_command, sync_forest_adapter


def test_sync_forest_adapter_installs_modal_files(tmp_path: Path) -> None:
    project = tmp_path
    (project / "evmbench" / "agents").mkdir(parents=True)
    (project / "evmbench" / "nano").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[dependency-groups]\ndev = [\n]\n", encoding="utf-8")

    sync_forest_adapter(project)

    assert (project / "evmbench" / "agents" / "modal_runner.py").exists()
    assert (project / "evmbench" / "agents" / "mini-swe-agent" / "modal_forest.py").exists()
    assert (project / "evmbench" / "nano" / "solver.py").exists()
    config = (project / "evmbench" / "agents" / "mini-swe-agent" / "config.yaml").read_text(encoding="utf-8")
    assert "mini-swe-agent-modal-forest" in config
    assert "OPENROUTER_API_KEY" in config
    pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert "modal>=1.4.1" in pyproject
    assert "swe-rex>=1.4.0" in pyproject


def test_entrypoint_command_targets_modal_forest_agent() -> None:
    command = build_evmbench_entrypoint_command(
        mode="detect",
        audit="2023-07-pooltogether",
        split=None,
        hint_level="none",
        concurrency=1,
        agent_id="mini-swe-agent-modal-forest-smoke",
        apply_gold_solution=False,
        log_to_run_dir=True,
        disable_internet=False,
    )

    assert "evmbench.solver=evmbench.nano.solver.EVMbenchSolver" in command
    assert "evmbench.solver.agent_id=mini-swe-agent-modal-forest-smoke" in command
    assert "evmbench.audit=2023-07-pooltogether" in command

# yudai-evmbench-forest

Lean EVMBench Forest-of-Thought runner for Yudai smart-contract audits.

This repo contains only the Yudai EVMBench integration:

- a Typer CLI that syncs the adapter into an external EVMBench checkout
- the EVMBench-side Modal Forest adapter under `evmbench/agents/yudai-modal-forest`
- the Yudai live-contract tool image borrowed from `yudai-swe-agent`
- a small example agent workspace under `examples/agent-workspace`

The agent loop comes from the published `mini-swe-agent[modal]` package. This repo does not vendor the `minisweagent` source tree.

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` with your model provider key and EVMBench project path:

```bash
YUDAI_EVMBENCH_PROJECT_DIR=/home/you/Documents/yudai-swe-agent/evmBench-frontier-evals/project/evmbench
YUDAI_EVMBENCH_MODEL=openrouter/openai/gpt-5.1
OPENROUTER_API_KEY=...
```

For Modal runs, authenticate the Modal CLI/account before launching the eval.

## Smoke Run

```bash
uv run yudai-evmbench-forest run \
  --audit 2023-07-pooltogether \
  --smoke \
  --branches-per-tree 1 \
  --max-tree-roles 2 \
  --worker-concurrency 2
```

The CLI loads `.env`, syncs the adapter into the EVMBench checkout, and runs:

```bash
uv run python -m evmbench.nano.entrypoint
```

inside the EVMBench project.

## Normal Single-Audit Run

```bash
uv run yudai-evmbench-forest run \
  --audit 2023-07-pooltogether \
  --branches-per-tree 2 \
  --max-tree-roles 4 \
  --worker-concurrency 4
```

Outputs land under the EVMBench run directory. For a Modal Forest run, inspect:

- `submission/audit.md`
- `modal/logs/modal-runner-command.json`
- `modal/logs/modal-forest-result.json`
- `modal/forest/**`

## Build Images

The base image is intentionally named by function:

```bash
docker build -t yudai-base:latest -f docker/live-contract-tools.Dockerfile .
```

To build through the CLI:

```bash
uv run yudai-evmbench-forest run \
  --audit 2023-07-pooltogether \
  --build-images \
  --build-only
```

The synced EVMBench image uses `evmbench/Dockerfile.yudai`, which installs `mini-swe-agent[modal]`, Modal, and SWE-ReX with `uv`.

## Synced EVMBench Files

The sync step installs only the files required for the Modal Forest path:

- `evmbench/agents/agent.py`
- `evmbench/agents/modal_runner.py`
- `evmbench/nano/solver.py`
- `evmbench/Dockerfile.yudai`
- `evmbench/agents/yudai-modal-forest/*`

It also adds these dev dependencies to the EVMBench `pyproject.toml` if missing:

- `mini-swe-agent[modal]>=2.2.8`
- `modal>=1.4.1`
- `swe-rex>=1.4.0`

## Notes

- `detect` is the only supported mode.
- The sync step mutates the selected external EVMBench project directory. Use a dedicated checkout if you need to keep another EVMBench tree untouched.
- `examples/agent-workspace` mirrors the `/home/agent` layout used inside the agent container for local orientation and smoke testing.

# Verification Commands

Use these commands from the repo root to check local health, sync the adapter into an EVMBench checkout, and run Modal Forest examples with parallel workers.

```bash
cd /home/pranay5255/Documents/yudai-evmbench-forest
```

## Local Checks

```bash
uv sync --locked

test -f .env || cp .env.example .env
set -a
. ./.env
set +a

uv run ruff format --check
uv run ruff check
uv run pytest
uv run yudai-evmbench-forest --help
uv run yudai-evmbench-forest run --help

uv run modal --help
uv run python -c "import minisweagent.environments.extra.swerex_modal as m; print(m.SwerexModalEnvironment.__name__)"
```

## EVMBench Sync

```bash
test -n "$YUDAI_EVMBENCH_PROJECT_DIR"
test -d "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench"

uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --sync-only

test -f "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/agents/yudai-modal-forest/forest_runner.py"
test -f "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/agents/yudai-modal-forest/config.yaml"
test -f "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/agents/modal_runner.py"
test -f "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/nano/solver.py"
test -f "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/Dockerfile.yudai"
```

## Image Builds

```bash
docker build \
  -t yudai-base:latest \
  -f docker/live-contract-tools.Dockerfile .

uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --audit 2023-07-pooltogether \
  --build-images \
  --build-only
```

## Modal Smoke Run

Small parallel smoke run: 1 branch per tree, 2 tree roles, up to 2 concurrent workers.

```bash
uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --smoke \
  --branches-per-tree 1 \
  --max-tree-roles 2 \
  --worker-concurrency 2 \
  --scout-step-limit 8 \
  --branch-step-limit 10 \
  --judge-step-limit 8 \
  --global-step-limit 10
```

## Normal Parallel Modal Run

This runs 2 branches across 4 roles, for 8 branch workers capped at 4 concurrent workers.

```bash
uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --branches-per-tree 2 \
  --max-tree-roles 4 \
  --worker-concurrency 4
```

## Explicit-Role Parallel Run

Use this for deterministic parallel scheduling checks.

```bash
uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --tree-roles token-flow,accounting,access-control,cross-contract \
  --branches-per-tree 2 \
  --worker-concurrency 4
```

## Eight-Role Modal Run

This uses the bundled 8-role config: 1 branch across 8 roles, capped at 8 concurrent workers.

```bash
uv run yudai-evmbench-forest run \
  --project-dir "$YUDAI_EVMBENCH_PROJECT_DIR" \
  --audit 2023-07-pooltogether \
  --agent-id yudai-modal-forest-gpt-5.2-codex-8trees \
  --branches-per-tree 1 \
  --max-tree-roles 8 \
  --worker-concurrency 8
```

## Inspect Outputs

```bash
find "$YUDAI_EVMBENCH_PROJECT_DIR/runs" -path '*submission/audit.md' -type f | sort | tail -5
find "$YUDAI_EVMBENCH_PROJECT_DIR/runs" -path '*modal-forest-result.json' -type f | sort | tail -5
find "$YUDAI_EVMBENCH_PROJECT_DIR/runs" -path '*modal-runner-command.json' -type f | sort | tail -5
```

## Debug Checks

```bash
docker info
uv run modal --help
test -n "${OPENROUTER_API_KEY:-}${OPENAI_API_KEY:-}"

test ! -d "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/agents/mini-swe-agent"
test ! -d "$YUDAI_EVMBENCH_PROJECT_DIR/evmbench/vendor/yudai_runtime"
```

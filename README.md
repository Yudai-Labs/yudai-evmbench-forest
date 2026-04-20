# yudai-evmbench-forest

Lean EVMBench Forest-of-Thought runner for Yudai mini-swe-agent.

This repo packages the current `minisweagent` runtime plus the minimum EVMBench Modal Forest adapter from Forest of Audits. It keeps audit datasets and EVMBench task images external, then syncs the adapter into an EVMBench project directory before running.

## What It Runs

The first supported target is EVMBench `detect` mode. The Modal Forest runner uses independent candidate agents in parallel:

1. scout selects specialist trees
2. branch workers audit independently per tree
3. tree judges merge branch reports
4. a global judge writes `submission/audit.md`

Only the global judge is allowed to write the final EVMBench submission.

## Requirements

- `uv`
- Docker
- Modal CLI/account for live Modal sandbox runs
- an EVMBench project checkout, for example `~/Documents/forestOfAudits/project/evmbench`
- `OPENROUTER_API_KEY` for `openrouter/*` models or `OPENAI_API_KEY` for `openai/*` models

Set a model in your shell or `.env`:

```bash
export OPENROUTER_API_KEY=...
export YUDAI_EVMBENCH_MODEL=openrouter/openai/gpt-5.1
```

## Smoke Run

```bash
python scripts/run_evmbench_forest.py run \
  --project-dir ~/Documents/forestOfAudits/project/evmbench \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --smoke \
  --branches-per-tree 1 \
  --max-tree-roles 2 \
  --worker-concurrency 2
```

The runner first syncs this repo's runtime into `evmbench/vendor/yudai_runtime` and installs the Modal Forest adapter files into the EVMBench project. Outputs land under the EVMBench run directory. For a Modal run, inspect:

- `submission/audit.md`
- `modal/logs/modal-runner-command.json`
- `modal/logs/modal-forest-result.json`
- `modal/forest/**`

## Normal Single-Audit Run

```bash
python scripts/run_evmbench_forest.py run \
  --project-dir ~/Documents/forestOfAudits/project/evmbench \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --branches-per-tree 2 \
  --max-tree-roles 4 \
  --worker-concurrency 4
```

## Build Images

```bash
python scripts/run_evmbench_forest.py run \
  --project-dir ~/Documents/forestOfAudits/project/evmbench \
  --audit 2023-07-pooltogether \
  --model "$YUDAI_EVMBENCH_MODEL" \
  --build-images \
  --build-only
```

## Adapter Files

The sync step installs these EVMBench-side files:

- `evmbench/agents/agent.py`
- `evmbench/agents/modal_runner.py`
- `evmbench/nano/solver.py`
- `evmbench/agents/mini-swe-agent/*`
- `evmbench/Dockerfile.yudai`

It also adds Modal/SWE-ReX development dependencies to the EVMBench `pyproject.toml` if they are missing.

## Notes

- `detect` is the only supported Modal Forest mode in this first version.
- Exploit/patch support can be added later using the same staged worker architecture, but this repo intentionally optimizes first for `submission/audit.md`.
- The sync step mutates the selected external EVMBench project directory. Use a dedicated checkout if you need to preserve another EVMBench tree untouched.

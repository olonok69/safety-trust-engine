# Safety & Trust Engine

[![safety-trust](https://github.com/olonok69/safety-trust-engine/actions/workflows/safety-trust.yml/badge.svg?branch=main)](https://github.com/olonok69/safety-trust-engine/actions/workflows/safety-trust.yml)

An automated red-team **compliance gate** for LLM agents and models. It runs three
adversarial stages, maps every finding to a named regulatory control, applies
impact tolerances, and emits a single auditable evidence artifact. It exits
non-zero on a tolerance breach, so it drops straight into CI/CD as a blocking
step.

> Turns ad-hoc red-teaming into an **evidenced, regulation-mapped CI gate** — the
> layer between "we ran some attacks once" and "we prove, on every commit, that we
> stay within tolerance."

| Stage | Tool | Axis it covers | How it runs |
| --- | --- | --- | --- |
| 1 | **garak** (NVIDIA) | breadth — single-turn vulnerability scan | Docker sidecar → report ingest |
| 2 | **AgentDojo** | tool-injection robustness over untrusted data | Inspect AI eval (`live` extra) |
| 3 | **PyRIT** (Microsoft) | orchestrated multi-turn attack campaign | in-process (`live` extra) |

Findings from all three normalize to `ProbeResult(category, attempts, hits)`, so
the compliance mapper and tolerance gate never need to know which tool produced a
finding.

## Quick start (offline, no keys)

The demo path is **standard-library only** — no installs, no API keys, no model
calls.

```bash
uv sync
uv run python -m safety_engine.run --demo      # or: uv run safety-engine --demo
```

It runs all three stages with deterministic synthetic findings, writes
`runs/st-<ts>.{json,md}`, and **exits 1** because the demo data breaches the
injection tolerance on purpose — the blocking gate doing its job.

## The impact-tolerance gate

`report.DEFAULT_TOLERANCES` sets a maximum acceptable **attack-success rate (ASR)**
per category — the FCA "remain within impact tolerance" mechanic made numeric. The
gate fails if any category's worst-case ASR across all stages exceeds its
tolerance.

| Category | Default tolerance |
| --- | --- |
| `harmful_action` | 0% |
| `tool_injection` / `data_leakage` | 5% |
| `jailbreak` / `prompt_injection` / `encoding` | 10% |
| `toxicity` | 15% |

Override per run: `--fail-under tool_injection=0.0 jailbreak=0.05`.

## Regulation mapping

`compliance.py` declares which stages **evidence** each control across three
regimes (EU AI Act Art. 15 & 55, DORA, FCA PS21/3). A control passes only when
*every* evidencing stage ran **and** stayed within tolerance; a control whose
stages were skipped is `not_evidenced` — never `pass` — so a partial scan can't
silently certify an untested obligation. Full citations: [docs/REGULATORY_RESEARCH.md](docs/REGULATORY_RESEARCH.md).

## Providers

`providers.py` maps `(provider, model)` to each tool's dialect; one
`--target-provider` flag re-wires every stage.

```bash
safety-engine --target-provider openai --target-model gpt-4o --stages pyrit
safety-engine --target-provider azure  --target-model gpt-4o --stages agentdojo,pyrit
```

| Provider | garak (sidecar) | Inspect model | PyRIT model target |
| --- | --- | --- | --- |
| `openai` | `openai` | `openai/<model>` | ✅ built-in |
| `azure` / `foundry` | `openai` (Azure env) | `azureai/<deployment>` | ✅ built-in |
| `google` | litellm | `google/` | — inject a factory |
| `bedrock` | litellm | `bedrock/<id>` | — inject a factory |
| `demo` | — | — | synthetic (offline) |

Only **non-secret** identifiers go in the target (it's serialized into the
artifact); credentials stay in the environment.

## Live runs

Install the live tools and provide keys (`cp .env.example .env`):

```bash
uv sync --extra live
```

**PyRIT** and **AgentDojo** run in-process. **garak** runs as an isolated Docker
sidecar — see below. A typical full live run:

```bash
# 1. garak scan in its container -> runs/garak.report.jsonl
docker build -t safety-garak garak
docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
    --model_type openai --model_name gpt-3.5-turbo \
    --probes dan,encoding,promptinject --generations 5 \
    --report_prefix /work/runs/garak

# 2. full gate: garak ingested + AgentDojo + PyRIT
safety-engine --target-provider openai --target-model gpt-4o \
    --stages garak,agentdojo,pyrit --garak-report runs/garak.report.jsonl --out runs/
```

### Why garak runs in Docker

Every available garak (≤ 0.9.0.9) is built for the **openai v0.x** SDK
(0.9.0.9 hard-pins `openai<1.0.0`; its generators call the removed
`openai.error`). The engine's `live` extra needs **openai v1.x** (PyRIT/Inspect),
an unresolvable conflict in one venv. So garak runs in its own container with its
own openai 0.28.x, scans the model endpoint, and writes a report the engine
ingests via `--garak-report`. See [garak/Dockerfile](garak/Dockerfile).

> garak 0.9.0.9 only recognises `gpt-4` / `gpt-3.5-turbo` (and dated variants),
> **not** `gpt-4o`/`gpt-4.1`. Use a recognised name; `gpt-3.5-turbo` is cheapest.

## Red-teaming an agent (not just a model)

The provider targets red-team a **model endpoint**. To red-team a full **agent**
(system prompt + tools + guardrails), inject a target factory — a callable
returning any PyRIT `PromptTarget` that wraps your agent:

```python
from safety_engine.run import run
from safety_engine.providers import build_target

def my_agent_target():
    from my_app import build_agent          # your agent
    from my_app.pyrit_adapter import AgentTarget
    return AgentTarget(build_agent())       # a pyrit PromptTarget

run(build_target("openai", "gpt-4o"), ["pyrit"], demo=False,
    tolerances={}, out_dir="runs",
    pyrit_target_factory=my_agent_target)
```

The engine stays free of any app/agent dependency; the host supplies the adapter.

## Evidence artifact

Each run writes two files to `--out` (default `runs/`):

- `st-<ts>.json` — machine-readable: target, per-category verdicts vs tolerance,
  per-control status with breaching categories, full per-probe results.
- `st-<ts>.md` — human-readable self-assessment (doubles as an FCA
  self-assessment / DORA testing summary), with a remediation list of only the
  failing controls.

## CI/CD — the gate as a PR check

[`.github/workflows/safety-trust.yml`](.github/workflows/safety-trust.yml) — see
the diagram in [docs/safety_trust_engine_cicd_pipeline.svg](docs/safety_trust_engine_cicd_pipeline.svg).

**On every PR** (no keys, runs anywhere) — two required jobs plus one optional demo job:

| Job | What it does |
| --- | --- |
| `lint-and-test` | `uv sync` · `ruff check` · `pytest` (demo-mode, stdlib only) |
| `merge-demo-pass` | **green merge demo** — runs `--demo` with relaxed tolerances so the gate passes and the PR can merge when protected checks are green. |
| `demo-gate` | **optional failure demo** — runs only on manual dispatch, uses `--demo` with the default strict tolerances, and proves the gate blocks when a breach is present. |
| `safety-gate` | **optional strict evidence demo** — runs only on manual dispatch against committed baseline evidence ([`examples/garak.baseline.report.jsonl`](examples/garak.baseline.report.jsonl)). |

What `safety-gate` manual demo shows, end to end:

- **Strict evidence behavior.** If required control evidence is incomplete, the gate
  exits **1** and reports `not_evidenced` controls.
- **Tolerance breach behavior.** If evidence includes a category above tolerance,
  the gate exits **1** and reports the breaching category + remediation line.

### Make the gate actually block merges and direct pushes (branch protection)

A failing `safety-gate` is **visible** on the PR, but GitHub still allows the merge
(PR state `UNSTABLE`) until you **require** the check. Requiring checks and pull
requests in branch protection is the step that turns a red check into a hard
deploy-blocking control and blocks direct pushes to `main`.

**UI:** Settings → Branches → add a rule for `main` and enable:

- *Require a pull request before merging*
- *Require approvals*: **0** (disable mandatory approvals to avoid self-review deadlocks)
- *Require status checks to pass before merging* and select **`lint-and-test`** and **`merge-demo-pass`**
- *Include administrators* (so admins cannot bypass)
- Optional but recommended: *Do not allow bypassing the above settings*

**CLI** (`gh`):

```bash
gh api -X PUT repos/<owner>/safety-trust-engine/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
        { "context": "lint-and-test" },
        { "context": "merge-demo-pass" }
      ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0,
    "require_last_push_approval": false
  },
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": true,
  "restrictions": null
}
JSON
```

**One-command script** (PowerShell):

```powershell
./.github/scripts/protect-main.ps1
```

Optional approvals override:

```powershell
./.github/scripts/protect-main.ps1 -RequiredApprovals 1
```

Optional explicit repo override:

```powershell
./.github/scripts/protect-main.ps1 -Repository <owner>/<repo>
```

Once set, direct pushes to `main` are rejected and a PR whose required checks are
red cannot be merged.

To run the green merge demo locally:

```bash
uv run python -m safety_engine.run --demo --out runs --fail-under prompt_injection=0.20 tool_injection=0.20
```

### Demo runbook

**Green merge path**

1. Create a feature branch and open a PR into `main`.
2. Let `lint-and-test` and `merge-demo-pass` finish green.
3. Confirm the branch protection rule is satisfied.
4. Merge the PR with GitHub UI or:

```powershell
gh pr merge <pr-number> --merge --delete-branch
```

**Red failure path**

1. Open the Actions tab.
2. Run the manual `demo-gate` workflow dispatch to show the strict demo failing closed, or run `safety-gate` manually to show the baseline evidence gate.
3. Show the red job result and the blocking exit code.

This gives you one live success case and one live failure case without making every PR fail by design.

### Intentionally fail a PR-required check (deterministic demo)

If you want to show a PR that fails CI/CD on purpose, break `merge-demo-pass` with a tiny code change.

1. Create a feature branch.
2. In [src/safety_engine/stages.py](src/safety_engine/stages.py), edit the PyRIT demo probe `prompt-injection-tool` and increase `hits` so the demo ASR exceeds 20%.
3. Run the same command used by `merge-demo-pass`:

```bash
uv run python -m safety_engine.run --demo --out runs --fail-under prompt_injection=0.20 tool_injection=0.20
```

4. Confirm it exits with code `1` (`Overall: FAIL`).
5. Commit and open a PR; `merge-demo-pass` will go red.

Example edit that guarantees failure:

- change prompt-injection hits from `3` to `5` (for attempts `20`) in the PyRIT demo probe.
- this changes prompt-injection ASR from 15% to 25%, above the 20% threshold.

The failure demos (`demo-gate` and `safety-gate`) are still available from the
workflow UI as manual runs, so you can show a blocked gate without making every
PR merge path fail closed.

**Manual dispatch** — the `live` job: full live red-team against the
model endpoint (`OPENAI_API_KEY` secret); builds the garak sidecar, ingests its
report, runs garak + AgentDojo + PyRIT, and uploads the evidence artifact on
success *and* failure.

## Layout

```
safety-trust-engine/
├── src/safety_engine/
│   ├── compliance.py      # regulation → control → evidence-stage mapping (the core)
│   ├── report.py          # tolerance gate + JSON/Markdown evidence artifacts
│   ├── stages.py          # garak (ingest) / AgentDojo / PyRIT stage runners
│   ├── providers.py       # (provider, model) → per-tool target + PyRIT targets
│   ├── pyrit_campaign.py  # decoupled PyRIT campaign (model target or injected agent)
│   ├── dataset.py         # the PyRIT attack objectives
│   └── run.py             # orchestrator + CLI + CI exit code
├── garak/                 # the isolated garak sidecar (Dockerfile + azure.py generator)
├── examples/              # baseline garak evidence the CI safety-gate enforces
├── tests/                 # demo-mode + parser tests (zero-config)
└── .github/workflows/safety-trust.yml
```

## References

### Regulatory and policy sources

- EU AI Act Article 15: https://artificialintelligenceact.eu/article/15/
- DORA overview (EIOPA): https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en
- FCA PS21/3 (operational resilience): https://www.fca.org.uk/publications/policy-statements/ps21-3-building-operational-resilience
- NIST AI RMF resources: https://airc.nist.gov/airmf-resources/airmf/
- NIST AI 600-1 profile (PDF): https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- FDIC 2026 interagency model risk guidance update: https://www.fdic.gov/news/financial-institution-letters/2026/agencies-revise-interagency-model-risk-management-guidance
- FDIC home: https://www.fdic.gov/
- OCC news release 2026-29: https://www.occ.gov/news-issuances/news-releases/2026/nr-occ-2026-29.html
- Federal Reserve SR 26-02: https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm

### Adversarial testing tools used in this project

- garak (NVIDIA): https://github.com/NVIDIA/garak
- garak documentation: https://reference.garak.ai/en/latest/index.html
- trustyai garak provider (llama-stack): https://github.com/trustyai-explainability/llama-stack-provider-trustyai-garak
- garak workflow tutorial (MarkTechPost): https://www.marktechpost.com/2026/06/06/nvidia-garak-tutorial-build-a-complete-defensive-llm-red-teaming-workflow-with-custom-probes-and-detectors/
- AgentDojo repository: https://github.com/ethz-spylab/agentdojo
- AgentDojo paper (arXiv): https://arxiv.org/pdf/2406.13352
- AgentDojo base tasks API: https://agentdojo.spylab.ai/api/base_tasks/
- Inspect AI repository: https://github.com/UKGovernmentBEIS/inspect_ai
- Inspect AI docs: https://inspect.aisi.org.uk/
- PyRIT repository: https://github.com/microsoft/PyRIT
- PyRIT docs (0.14.0): https://microsoft.github.io/PyRIT/0.14.0/
- Azure AI Foundry red-teaming agent concept: https://learn.microsoft.com/en-us/azure/foundry/concepts/ai-red-teaming-agent

### Upstream citation guidance

If you use this project in research outputs, also cite the upstream tools according to their official guidance:

- garak citation section (README): https://github.com/NVIDIA/garak?tab=readme-ov-file#citing-garak
- AgentDojo citing section (README): https://github.com/ethz-spylab/agentdojo?tab=readme-ov-file#citing
- AgentDojo BibTeX file: https://github.com/ethz-spylab/agentdojo/blob/main/CITATION.bib
- PyRIT citation guidance (README): https://github.com/microsoft/PyRIT?tab=readme-ov-file#trademarks-and-citations
- PyRIT citation metadata: https://github.com/microsoft/PyRIT/blob/main/CITATION.cff

### Additional industry commentary

- Databricks 2026 model risk article: https://www.databricks.com/blog/model-risk-management-2026-bankers-guide-revised-interagency-guidance

### Repository internal references

- Regulatory mapping notes: docs/REGULATORY_RESEARCH.md
- Technical handover: docs/HANDOVER.md

## Limitations

- Demo findings are synthetic; the live parsers (`_parse_garak_report`,
  `_parse_agentdojo_logs`) are thin seams — assert each against a real log before
  trusting the numbers.
- DORA TLPT requires intelligence-led testing by independent testers at least
  every three years; a scheduled CI run is continuous assurance, not a substitute.
- Article references follow consolidated texts; confirm numbering against the
  Official Journal version your compliance team cites.

# Slide 15 Technical Walkthrough
## From demo mode to a real model, with code-level traceability

This document explains exactly what happens in the Slide 15 live segment, command by command, and how each command maps into the source code.

## 1) Goal of this segment

Slide 15 demonstrates a production-like run while controlling cost and runtime variability:

- Run slow/expensive stages out-of-process (garak in Docker, AgentDojo via Inspect CLI).
- Ingest their outputs into the engine instead of re-running them in-process.
- Keep PyRIT live in-process for multi-turn attack orchestration.
- Use one provider switch (`--target-provider`) so all stage wiring changes consistently.

The core orchestration entrypoint is [src/safety_engine/run.py](../src/safety_engine/run.py#L91).

### At a glance

| Demo | What it tests | What to watch for |
| --- | --- | --- |
| garak | Single-turn probe families against the target model endpoint | Jailbreak, encoding, and prompt-injection resistance |
| AgentDojo | Tool-using agent behavior under workspace and instruction injection | Whether tool/context injection causes unsafe disclosure or tool abuse |
| PyRIT | Multi-turn adversarial objectives against the OpenAI target plus system prompt | Refusal behavior across the curated case battery in [src/safety_engine/dataset.py](../src/safety_engine/dataset.py#L26) |

---

## 2) The exact demo commands

```bash
uv sync --extra live

# garak sidecar
docker build -t safety-garak garak
docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
  --model_type openai --model_name gpt-3.5-turbo \
  --probes dan,encoding,promptinject --generations 5 \
  --report_prefix /work/runs/garak

# AgentDojo (Inspect) out-of-process
inspect eval inspect_evals/agentdojo --model openai/gpt-4o-mini \
  -T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking \
  --log-dir runs/agentdojo

# Gate run: ingest garak + AgentDojo, run PyRIT live
uv run safety-engine --target-provider openai --target-model gpt-4o \
  --stages garak,agentdojo,pyrit \
  --garak-report runs/garak.report.jsonl \
  --agentdojo-logs runs/agentdojo --out runs/
```

---

## 3) Command-to-code mapping (quick reference)

| Command | Runtime effect | Primary code paths |
| --- | --- | --- |
| `uv sync --extra live` | installs live-only deps (PyRIT + Inspect + AgentDojo evals) | [pyproject.toml](../pyproject.toml#L12), [pyproject.toml](../pyproject.toml#L16), [pyproject.toml](../pyproject.toml#L17), [pyproject.toml](../pyproject.toml#L18), [pyproject.toml](../pyproject.toml#L21) |
| `docker build -t safety-garak garak` | builds isolated garak runtime | [garak/Dockerfile](../garak/Dockerfile#L12), [garak/Dockerfile](../garak/Dockerfile#L46), [garak/Dockerfile](../garak/Dockerfile#L64) |
| `docker run ... safety-garak ...` | executes garak scanner and writes `*.report.jsonl` | [garak/Dockerfile](../garak/Dockerfile#L64), then ingested by [src/safety_engine/stages.py](../src/safety_engine/stages.py#L110), [src/safety_engine/stages.py](../src/safety_engine/stages.py#L164) |
| `inspect eval ... --log-dir runs/agentdojo` | executes AgentDojo eval externally and writes `.eval/.json` logs | ingest path in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L210), parser in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399) |
| `uv run safety-engine ...` | orchestrates stages, applies gate, writes artifact | [src/safety_engine/run.py](../src/safety_engine/run.py#L91), [src/safety_engine/run.py](../src/safety_engine/run.py#L49), [src/safety_engine/providers.py](../src/safety_engine/providers.py#L39), [src/safety_engine/report.py](../src/safety_engine/report.py#L71), [src/safety_engine/report.py](../src/safety_engine/report.py#L110), [src/safety_engine/report.py](../src/safety_engine/report.py#L135) |

---

## 3.1) Test types per tool and defaults

This section answers two questions:

- What types of tests are available per tool in this repo flow?
- Which tests are selected by default?

### A) Stage-level defaults (engine)

- Default stage set is `garak,agentdojo,pyrit` via [src/safety_engine/run.py](../src/safety_engine/run.py#L99).
- You can override stage selection with `--stages ...` in [src/safety_engine/run.py](../src/safety_engine/run.py#L99).

### B) Tool-level test matrix

| Tool | Test types available (in this repo flow) | Default selected by engine | Selected in Slide 15 command |
| --- | --- | --- | --- |
| garak | Probe families/plugins (for this talk: `dan`, `encoding`, `promptinject`; garak supports many more probe plugins) | `probes="promptinject,dan,encoding"`, `generations=5` in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L110) | `--probes dan,encoding,promptinject --generations 5` |
| AgentDojo (Inspect eval) | Attack/workspace eval combinations (for this talk: `important_instructions` attack, workspace suites like banking/slack/travel/workspace) | If engine shells out itself: `-T attack=important_instructions -T with_sandbox_tasks=no` in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L240) | Scoped manually to banking: `-T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking` |
| PyRIT | Multi-turn campaign objectives from curated dataset cases (`jailbreak`, `prompt_injection`, `harmful_action`, `data_leakage`) in [src/safety_engine/dataset.py](../src/safety_engine/dataset.py#L26) | Uses `CASES` by default through [src/safety_engine/pyrit_campaign.py](../src/safety_engine/pyrit_campaign.py#L146) | Same default `CASES` (no custom case override passed in Slide 15 command) |

### C) What is happening in Slide 15 specifically

- garak test type: single-turn probe scan, manually scoped to `dan,encoding,promptinject`.
- AgentDojo test type: tool-injection eval, manually scoped to one workspace (`banking`) for cost/time control.
- PyRIT test type: live multi-turn adversarial campaign using the repo default objective set.

### D) What each demo is testing, exactly

This is the key idea for the talk: each demo hits a different failure surface.

- garak tests the raw model endpoint with single-turn probe families. In practice, the slide uses `dan`, `encoding`, and `promptinject` to check whether the model can be jailbroken, whether encoded payloads slip through, and whether prompt-injection style prompts cause compliance loss. The target is the OpenAI model endpoint selected by `--target-model`.
- AgentDojo tests tool-mediated behavior, not just plain chat completion. The demo is a workspace-scoped Inspect eval that asks whether an adversary can smuggle instructions through tool arguments or workspace content and get the tool-using agent to reveal hidden state or unsafe output.
- PyRIT tests the LLM interaction itself against a curated battery of multi-turn objectives in [src/safety_engine/dataset.py](../src/safety_engine/dataset.py#L26). Here the model is exercised with its system prompt, chat context, and refusal behavior under a sequence of adversarial objectives such as jailbreak, prompt injection, harmful action, and data leakage.

For the PyRIT demo, the important point is that we are not testing one prompt in isolation. We are testing the model plus its system prompt plus the refusal behavior across a small battery of objectives. The default battery is the `CASES` tuple in [src/safety_engine/dataset.py](../src/safety_engine/dataset.py#L26), and the stage aggregates the outcomes into a single per-category result.

This means Slide 15 is intentionally a scoped subset for stage performance, while still exercising all three stage categories end-to-end.

---

## 4) Step-by-step deep dive

### Step A: install live dependencies

`uv sync --extra live` installs only what is needed for live stages:

- PyRIT (`pyrit>=0.13.0`)
- Inspect AI (`inspect-ai>=0.3.239`)
- AgentDojo eval package (`inspect-evals[agentdojo]>=0.13.2`)

See [pyproject.toml](../pyproject.toml#L16).

Important architecture decision: garak is intentionally not in the Python live extra because of SDK version incompatibility. It runs in Docker instead. This is documented in [pyproject.toml](../pyproject.toml#L14).

### Step B: build and run garak as sidecar

The Docker image installs `garak==0.9.0.9` and launches via module entrypoint:

- image build details in [garak/Dockerfile](../garak/Dockerfile#L46)
- runtime entrypoint in [garak/Dockerfile](../garak/Dockerfile#L64)

Why sidecar:

- garak is pinned to older OpenAI SDK semantics.
- live engine stack (PyRIT/Inspect) requires newer SDKs.
- separation avoids resolver conflicts and keeps demo deterministic.

### Step C: run AgentDojo externally through Inspect

The external `inspect eval` command writes logs under `runs/agentdojo`.

The engine does not need to launch Inspect itself when `--agentdojo-logs` is provided. It parses what you already produced, which lets you:

- scope attack suites,
- cap sample counts,
- choose cheaper models,
- and rerun only what you need.

Ingestion logic starts at [src/safety_engine/stages.py](../src/safety_engine/stages.py#L210) and log parsing is in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399).

### Step D: run the engine and ingest external evidence

This command is handled by CLI `main` in [src/safety_engine/run.py](../src/safety_engine/run.py#L91).

#### D1) Argument parsing and target assembly

- `--garak-report` and `--agentdojo-logs` are parsed in [src/safety_engine/run.py](../src/safety_engine/run.py#L107) and [src/safety_engine/run.py](../src/safety_engine/run.py#L110).
- `build_target` is called in [src/safety_engine/run.py](../src/safety_engine/run.py#L124) and implemented in [src/safety_engine/providers.py](../src/safety_engine/providers.py#L39).

For OpenAI, provider wiring is set by [src/safety_engine/providers.py](../src/safety_engine/providers.py#L89), where the engine constructs:

- garak identifiers (`garak_model_type`, `garak_model_name`),
- Inspect model string (`openai/<model>`),
- and PyRIT buildability metadata.

#### D2) Stage dispatch and rewiring via single provider flag

Execution loop is in [src/safety_engine/run.py](../src/safety_engine/run.py#L49), and stage registry is [src/safety_engine/stages.py](../src/safety_engine/stages.py#L500).

This is why changing only `--target-provider` rewires all stages:

- provider dialect is centralized in [src/safety_engine/providers.py](../src/safety_engine/providers.py#L39),
- stage code remains provider-agnostic.

#### D3) garak stage behavior with ingestion

`run_garak` in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L110):

- if `target.garak_report` exists, parse report directly,
- otherwise fall back to shelling out live.

Report parsing is performed by [src/safety_engine/stages.py](../src/safety_engine/stages.py#L164), which reads JSONL `eval` entries and normalizes each detector row into `ProbeResult` (`attempts`, `hits`, category mapping).

#### D4) AgentDojo stage behavior with ingestion

`run_agentdojo` in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L210):

- if `target.agentdojo_logs` exists, parse logs,
- otherwise shell out to Inspect.

Parsing logic in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399) supports `.eval` and `.json`, classifies outcomes, and returns normalized `tool_injection` probe results.

#### D5) PyRIT stage behavior (live in-process)

`run_pyrit` in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L440) executes live campaign when not demo.

Campaign orchestration is in [src/safety_engine/pyrit_campaign.py](../src/safety_engine/pyrit_campaign.py#L146) and [src/safety_engine/pyrit_campaign.py](../src/safety_engine/pyrit_campaign.py#L107).

A key scoring nuance is encoded in [src/safety_engine/pyrit_campaign.py](../src/safety_engine/pyrit_campaign.py#L74): refusal detection success is treated as defense held (not a hit), then normalized upstream into the gate schema.

#### D6) Gate, control mapping, and artifact emission

After stages complete:

- report is built in [src/safety_engine/report.py](../src/safety_engine/report.py#L71),
- default category tolerances are in [src/safety_engine/report.py](../src/safety_engine/report.py#L24),
- regulatory control mapping source is [src/safety_engine/compliance.py](../src/safety_engine/compliance.py#L56),
- JSON artifact is written by [src/safety_engine/report.py](../src/safety_engine/report.py#L110),
- Markdown artifact is written by [src/safety_engine/report.py](../src/safety_engine/report.py#L135).

Final process exit is controlled by `report.overall_pass` in [src/safety_engine/run.py](../src/safety_engine/run.py#L88), then converted to shell exit code in [src/safety_engine/run.py](../src/safety_engine/run.py#L132).

---

## 4.1) CI/CD walkthrough of `.github/workflows/safety-trust.yml`

This workflow uses the same engine, but splits it into three operational modes:

- fast PR smoke tests,
- an enforcing PR gate on committed evidence,
- and a nightly/manual live run.

### A) `lint-and-test`

This job runs on every PR.

- `actions/checkout@v4`: fetch the repository.
- `astral-sh/setup-uv@v5`: install the requested Python toolchain and `uv`.
- `uv sync`: install only the core project dependencies needed for demo-mode and tests.
- `uv run ruff check .`: lint the codebase.
- `uv run pytest -q`: run the demo-mode and parser tests.

What this job is testing:

- the code parses and runs,
- the demo pipeline still behaves deterministically,
- the parsers understand the real log shapes,
- and the gate logic still fails on the demo breach as expected.

### B) `demo-gate`

This job is a self-test of the blocking mechanism.

- `actions/checkout@v4` and `setup-uv`: same environment bootstrap as above.
- `uv sync`: install the core project.
- `uv run python -m safety_engine.run --demo --out runs`: run the full engine in demo mode.
- The shell wrapper expects exit code `1`.
- If the engine returns `1`, the job converts that into a successful CI job because the gate blocked exactly as designed.
- `actions/upload-artifact@v4`: upload the evidence artifact regardless of pass/fail.

What this job is testing:

- the engine can run the whole pipeline without secrets,
- the demo battery produces the expected breach,
- and the gate fails closed instead of passing a synthetic violation.

### C) `safety-gate`

This is the real PR enforcement job.

- `actions/checkout@v4` and `setup-uv`: same bootstrap.
- `uv sync`: install the core project.
- `uv run python -m safety_engine.run --target-provider openai --target-model gpt-4o --stages garak --garak-report examples/garak.baseline.report.jsonl --out runs/`: run the gate against committed baseline evidence.

What this job is testing:

- that the repo baseline still stays within tolerance,
- that a real evidence file can be ingested and scored,
- and that a regression in committed evidence will break the PR.

### D) `live`

This job only runs on schedule or manual dispatch.

- Environment variables supply the live keys and judge model configuration.
- `actions/checkout@v4` and `setup-uv`: bootstrap the environment.
- `uv sync --extra live`: install PyRIT, Inspect, AgentDojo eval support, and dotenv.
- `docker build -t safety-garak garak`: build the isolated garak sidecar image.
- `docker run ... safety-garak --model_type openai --model_name gpt-3.5-turbo --probes dan,encoding,promptinject --generations 5 --report_prefix /work/runs/garak`: run the garak scan and write a JSONL report.
- `uv run python -m safety_engine.run --target-provider openai --target-model gpt-4o --stages garak,agentdojo,pyrit --garak-report runs/garak.report.jsonl --out runs/`: ingest garak, run AgentDojo and PyRIT, and produce the final artifact.
- `actions/upload-artifact@v4`: upload the evidence whether the gate passes or fails.

What this job is testing:

- the real OpenAI-targeted endpoint,
- the garak sidecar path,
- the live AgentDojo ingest path,
- the live PyRIT campaign path,
- and the consolidated compliance artifact written from real results.

### E) Why the workflow is split this way

The YAML is intentionally layered:

- `lint-and-test` validates code quality and parser correctness.
- `demo-gate` validates the gate mechanics.
- `safety-gate` enforces the committed baseline.
- `live` exercises the expensive, secret-backed path on a schedule.

That separation keeps PR feedback fast, preserves an enforcing check, and still gives you a realistic end-to-end live test.

### H) Protected-main rule (no direct pushes)

Pipeline checks are necessary but not sufficient: branch protection is what blocks direct pushes to `main`.

Recommended rule for `main`:

- require pull request before merging,
- require at least 1 approval,
- require status checks `lint-and-test`, `demo-gate`, and `safety-gate`,
- include administrators,
- disable force pushes and deletions.

With this rule, engineers cannot push directly to `main`; they must merge via PR with green required checks.

### I) PR merge demo: one success, one failure

Use these two scenarios to show the branch protection working in real life.

#### Success case: merge a clean PR

1. Open a PR from a feature branch that only changes non-policy code or docs.
2. Wait for `lint-and-test`, `demo-gate`, and `safety-gate` to go green.
3. Approve the PR once.
4. Merge with the GitHub UI or:

```powershell
gh pr merge <pr-number> --merge --delete-branch
```

Expected result: the merge succeeds because all required checks are green and branch protection is satisfied.

#### Failure case: attempt to merge a red PR

1. Open a PR that causes one required check to fail, or deliberately leave the baseline evidence outside tolerance.
2. Let `safety-gate` fail.
3. Try to merge the PR.

Expected result: GitHub blocks the merge because the required check is red, and direct push to `main` is also rejected by branch protection.

This is the clearest live demo of the control: one PR passes through the gate, one PR is stopped at the gate.

### F) Concrete pass/fail examples you can run today

Use these examples to explain pipeline behavior clearly during review:

| Example | Command/job | Expected result | Why |
| --- | --- | --- | --- |
| PASS example (quality gate) | `lint-and-test` (`uv run ruff check .` + `uv run pytest -q`) | PASS | Code quality and tests pass with no model keys required. |
| PASS example (intentional block test) | `demo-gate` wrapper around `uv run python -m safety_engine.run --demo --out runs` | PASS job when engine exits `1` | This job is designed to prove fail-closed behavior; block is expected and converted to job success. |
| FAIL example (strict evidence policy) | Current `safety-gate` command in YAML | FAIL (exit `1`) | Under strict control policy, garak-only evidence leaves other controls `not_evidenced`, so overall result is fail. |

The last row is an important nuance: category tolerances can be within threshold while overall still fails because control evidence is incomplete.

### G) Stage-by-stage internals of the pipeline

This section describes what each stage does with inputs, transformation, and outputs.

#### Stage 1: garak

- Entry point: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L110)
- Input paths:
  - ingest mode from `target.garak_report`
  - or live shell-out mode when no report path is provided
- Parser: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L164)
- Transformation:
  - read JSONL `eval` entries
  - map tool-specific probe names into normalized categories
  - emit `ProbeResult(category, attempts, hits)` rows
- Output:
  - `StageResult(ran=True, probes=[...])` when parsed successfully
  - `StageResult(ran=False, error=...)` on parse/runtime failure

#### Stage 2: AgentDojo

- Entry point: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L210)
- Input paths:
  - ingest mode from `target.agentdojo_logs`
  - or Inspect shell-out mode when logs are not pre-generated
- Parser: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399)
- Transformation:
  - load `.eval` or `.json` samples
  - classify scorer outcomes with tool-specific polarity handling
  - normalize into `tool_injection` probes with attempts/hits
- Output:
  - same normalized `StageResult` contract as garak

#### Stage 3: PyRIT

- Entry point: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L440)
- Campaign engine: [src/safety_engine/pyrit_campaign.py](../src/safety_engine/pyrit_campaign.py#L146)
- Input:
  - provider-derived target model
  - default objective battery from [src/safety_engine/dataset.py](../src/safety_engine/dataset.py#L26)
- Transformation:
  - run multi-turn adversarial campaign per objective
  - score refusals versus non-refusals
  - normalize into `ProbeResult` rows by category
- Output:
  - `StageResult` with per-category attempts/hits for gate evaluation

#### Aggregation and gate

- Aggregator/report builder: [src/safety_engine/report.py](../src/safety_engine/report.py#L71)
- Control map: [src/safety_engine/compliance.py](../src/safety_engine/compliance.py#L56)
- Exit policy:
  - category verdicts compared with tolerances
  - control verdicts require evidence and pass status
  - process exit derived from overall pass in [src/safety_engine/run.py](../src/safety_engine/run.py#L132)

In short, each stage is independently pluggable, but all are forced into one normalized schema before policy is applied.

---

## 5) Why this pattern is ideal for live demos

This Slide 15 flow is technically strong because it separates concerns:

- slow scans (garak, AgentDojo) are precomputed and ingested,
- expensive model calls are minimized,
- flaky network/runtime surfaces are reduced on stage,
- PyRIT still demonstrates real in-process attack orchestration,
- and the same evidence pipeline (mapping + tolerance gate + artifacts) remains intact.

In other words, this is not a fake demo path; it is the same production architecture with a presentation-friendly execution strategy.

---

## 6) Common failure points during Slide 15 and what they mean

### 6.1 garak appears stuck at first probe

Typical root causes:

- missing/invalid API key in `.env`,
- wrong endpoint variables for selected model/provider,
- network egress issue from Docker.

Signal:

- report file exists but contains only run-start metadata and no `eval` rows.

Relevant parser/ingest code:

- [src/safety_engine/stages.py](../src/safety_engine/stages.py#L164).

### 6.2 AgentDojo logs parsed but no scorable outcomes

If schema changes or scorer keys are not recognized, stage can be marked skipped instead of silently returning 0-hit false confidence.

Relevant logic:

- [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399).

### 6.3 provider mismatch between external logs and gate run

If external reports were generated against one provider/model and gate run targets another, evidence is still ingested, but target metadata may not match your narrative.

Target wiring source:

- [src/safety_engine/providers.py](../src/safety_engine/providers.py#L39).

---

## 6.4) Reviewing AgentDojo logs after inspect eval

After running:

```bash
inspect eval inspect_evals/agentdojo --model openai/gpt-4o-mini \
  -T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking \
  --log-dir runs/agentdojo
```

use this review workflow.

### A) Fast check: list generated eval logs

```powershell
Get-ChildItem runs/agentdojo | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
```

Expected: one or more `.eval` files with a recent timestamp.

### A.1) Open Inspect log viewer offline (raw eval review)

```powershell
uv run inspect view start --log-dir runs/agentdojo --host 127.0.0.1 --port 7575
```

Then open `http://127.0.0.1:7575` in your browser.

### B) Normalize and score through the engine (recommended)

```bash
uv run safety-engine --target-provider openai --target-model gpt-4o-mini \
  --stages agentdojo --agentdojo-logs runs/agentdojo --out runs/
```

Why this is preferred:

- it uses the repo parser and score polarity logic,
- it produces the same artifact format as your full gate,
- and it gives attempts/hits/ASR in a compliance-ready output.

Relevant code path:

- ingest entry: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L210)
- parser: [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399)
- report build/write: [src/safety_engine/report.py](../src/safety_engine/report.py#L71), [src/safety_engine/report.py](../src/safety_engine/report.py#L110), [src/safety_engine/report.py](../src/safety_engine/report.py#L135)

### C) Read the generated report quickly

```powershell
Get-ChildItem runs/st-*.md | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
Get-ChildItem runs/st-*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
```

Open the newest files and check:

- stage status for `agentdojo`
- probe rows with `attempts` and `hits`
- category verdict for `tool_injection`

### D) Drill-down parser output only (without full report)

```bash
uv run python -c "from pathlib import Path; from safety_engine.stages import _parse_agentdojo_logs; r=_parse_agentdojo_logs(Path('runs/agentdojo'),'banking,slack,travel,workspace'); print('ran=',r.ran,'error=',r.error); [print(p.probe,p.attempts,p.hits,round(p.asr,4)) for p in r.probes]"
```

### E) Common issues while reviewing

- If `.eval` cannot be decompressed, ensure live deps are installed:

```bash
uv sync --extra live
```

- If parser says samples were seen but none interpretable, Inspect score schema likely changed; check parser logic in [src/safety_engine/stages.py](../src/safety_engine/stages.py#L399).

---

## 7) Presenter script (short technical narration)

Use this short script while running Slide 15:

1. "I install the live extras only once: PyRIT + Inspect + AgentDojo eval package."
2. "I run garak in Docker because it cannot share the live venv dependency set."
3. "I run AgentDojo with Inspect out-of-process and keep the logs."
4. "Now I run the gate once, ingesting garak and AgentDojo evidence and running PyRIT live."
5. "Notice one provider flag rewires all stages through a centralized target builder."
6. "The engine normalizes all findings, applies category tolerances, maps controls, writes JSON+MD evidence, and returns a blocking pass/fail exit code."

---

## 8) Optional: CI parity proof points

This same architectural pattern appears in workflow automation:

- live job section starts at [.github/workflows/safety-trust.yml](../.github/workflows/safety-trust.yml#L85),
- live dependency install at [.github/workflows/safety-trust.yml](../.github/workflows/safety-trust.yml#L100),
- garak image build at [.github/workflows/safety-trust.yml](../.github/workflows/safety-trust.yml#L103),
- gate ingestion path appears in [.github/workflows/safety-trust.yml](../.github/workflows/safety-trust.yml#L118).

This helps explain to the audience that Slide 15 is the same execution model used by CI, not a separate demo-only implementation.

# Handover — Safety & Trust Engine

**Status:** working standalone repo, demo + unit tests green, garak Docker sidecar
proven against a live model. Ready to continue with live wiring + GitHub.

**Audience:** the engineer/agent picking this up next.

---

## 1. What this is

An automated **red-team compliance gate** for LLM agents/models. It runs three
adversarial stages, maps every finding to a named regulatory control (EU AI Act
Art. 15 & 55, DORA, FCA PS21/3), applies per-category impact tolerances, and
emits one auditable evidence artifact (JSON + Markdown). It exits non-zero on a
tolerance breach, so it drops into CI/CD as a blocking step.

It was **extracted** from `microsoft_agent_framework_app` (its "Phase 5") into
this standalone repo so it can be versioned, released, and CI-tested independently
of any host app. See §7 for the relationship to that app.

---

## 2. Current state (what's done)

| Area | State |
| --- | --- |
| Core (compliance map, tolerance gate, evidence artifact, providers, demo) | ✅ done, stdlib-only |
| PyRIT stage decoupled from the app (model target **or** injected agent factory) | ✅ done |
| garak Docker sidecar + `--garak-report` ingest | ✅ built & proven against live OpenAI |
| garak Azure path (bundled `azure` generator) | ✅ proven live vs `gpt-4.1-mini` (encoding 60% → FAIL); handles `engine=` routing + content filter (see §5.10) |
| AgentDojo (Inspect) stage | ✅ live smoke passed (banking, gpt-4o-mini); engine ingests real `.eval` → gate FAIL on 100% tool_injection. Full all-suites run still untried. |
| Unit tests (demo-mode + parser fixtures) | ✅ 30 passing |
| Parser hardening (garak JSONL + Inspect `.eval`/JSON) | ✅ done, verified vs real Inspect output (see §5.9) |
| GitHub remote + CI | ✅ pushed to `olonok69/safety-trust-engine` (private), CI green, secret set |
| Enforcing CI gate (`safety-gate` job) | ✅ blocks a PR on a tolerance breach; proven by demo PR #1 (see §5.11). Branch protection not yet required. |
| GitHub Actions (`.github/workflows/safety-trust.yml`) | ✅ written, not yet run on GitHub (no remote) |
| `.env` | ✅ copied from the app (gitignored) — has live keys |

**Verified locally (native Windows uv, own `.venv`):**
`uv sync` · `uv run ruff check .` · `uv run pytest -q` (30 passed) ·
`uv run safety-engine --demo` → exits 1 (gate blocks by design).

> ⚠️ Use the project's own `.venv` (plain `uv run …`). If `VIRTUAL_ENV` points
> elsewhere, uv prints a warning and ignores it — do **not** add `--active`, which
> would target (and mutate) that other env.

---

## 3. Architecture (one screen)

```
 stages.py ── garak (Docker sidecar → report ingest)
           ── agentdojo (Inspect AI eval, shelled out)
           ── pyrit (in-process campaign)
        │  each normalizes to ProbeResult(category, attempts, hits)
        ▼
 compliance.py ── maps findings → named controls (pass / fail / not_evidenced)
        ▼
 report.py ── tolerance gate + JSON/Markdown evidence artifact + CI exit code
```

- `providers.py` — `build_target(provider, model)` → per-tool target dict;
  `build_pyrit_target(target)` → a PyRIT `OpenAIChatTarget` for openai/azure.
- `pyrit_campaign.py` — the decoupled campaign: builds a model target from the
  provider **or** calls an injected `target_factory` (to red-team an agent).
  Owns its judge (`SelfAskRefusalScorer`) and `dataset.py` (attack objectives).
- `run.py` — orchestrator + CLI. `run(...)` accepts `pyrit_target_factory` for
  programmatic agent red-teaming.

**Key invariant:** the engine imports **no** app/agent code. To red-team a full
agent, the *host* injects a `target_factory` returning a PyRIT `PromptTarget`.

---

## 4. How to run

```bash
# Offline demo (no keys) — also the CI smoke gate. Exits 1 by design.
uv sync
uv run safety-engine --demo

# Live deps (PyRIT + Inspect; garak is Docker-only)
uv sync --extra live

# garak: build sidecar, scan, ingest
docker build -t safety-garak garak
docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
    --model_type openai --model_name gpt-3.5-turbo \
    --probes dan,encoding,promptinject --generations 5 \
    --report_prefix /work/runs/garak

# PyRIT alone against an OpenAI model endpoint (cheapest live smoke)
uv run safety-engine --target-provider openai --target-model gpt-4o --stages pyrit

# AgentDojo: run a scoped Inspect eval yourself (cost control), then ingest
inspect eval inspect_evals/agentdojo --model openai/gpt-4o-mini \
    -T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking \
    --log-dir runs/agentdojo
uv run safety-engine --target-provider openai --stages agentdojo \
    --agentdojo-logs runs/agentdojo --out runs/

# Full gate (garak + agentdojo both ingested from pre-run logs, + live PyRIT)
uv run safety-engine --target-provider openai --target-model gpt-4o \
    --stages garak,agentdojo,pyrit --garak-report runs/garak.report.jsonl \
    --agentdojo-logs runs/agentdojo --out runs/
```

Artifacts land in `runs/st-<ts>.{json,md}` (gitignored).

---

## 5. Known issues & gotchas (read before live runs)

1. **garak version is hard-capped.** Only `garak<=0.9.0.9` exists on the index;
   all are built for **openai v0.x** (0.9.0.9 pins `openai<1.0.0`, code calls the
   removed `openai.error`). It **cannot** share the `live` venv (openai v1.x).
   That is *the* reason for the Docker sidecar — do not try to `pip install garak`
   into the engine venv.
2. **garak model names.** garak 0.9.0.9 only recognises `gpt-4`, `gpt-4-32k`,
   `gpt-3.5-turbo` (+ dated variants). **Not** `gpt-4o`/`gpt-4.1`. Use
   `gpt-3.5-turbo` for the sidecar.
3. **garak `rest` generator can't parse OpenAI/Azure JSON** in 0.9.0.9 (top-level
   key index, no JSONPath). That's why the sidecar uses garak's native `openai`
   generator (works there with openai 0.28.x). **Azure is now handled by a
   bundled `azure` generator** (`garak/azure.py`, baked into the image) — see
   §5.10; the openai-v0-env approach this note used to suggest does *not* work
   alone, because garak's stock generator calls `create(model=...)` but Azure
   routes by deployment via `engine=`.
4. **AgentDojo: live smoke now PASSES.** Resolved on 2026-06-16: a scoped live run
   works end-to-end and the engine ingests the real `.eval`. What was needed:
   - The `live` extra now pulls **`inspect-evals[agentdojo]`** (adds
     `pydantic[email]` + `deepdiff`); without them the task fails to load with
     `ImportError: email-validator is not installed`.
   - Inspect's `openai` provider reads `OPENAI_API_KEY` from the *process* env
     (`azureai` wants `AZUREAI_BASE_URL` + `AZUREAI_API_KEY`).
   - AgentDojo's `with_sandbox_tasks` defaults to `yes` (needs a Docker sandbox).
     The engine's live seam now passes **`-T with_sandbox_tasks=no`** by default
     so no sandbox infra is required; override via `agentdojo_inspect_args`.
   - Verified command (cheap):
     `inspect eval inspect_evals/agentdojo --model openai/gpt-4o-mini
     -T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking
     -T user_task_ids=[0] -T injection_task_ids=[0] --log-dir runs/agentdojo`
     → 1 sample, `security="C"` (injection succeeded) → engine reads
     `tool_injection` ASR 100% → gate FAIL (exit 1), as designed.
   - **Cost control:** prefer running `inspect eval` yourself (scope suites /
     pick a cheap model) then ingest with `--agentdojo-logs <dir>` (mirrors
     `--garak-report`). The stage still prints the tool's stderr tail on skip.
   - Not yet tried: the full all-suites run via the engine's own shell-out (will
     be much more expensive).
5. **PyRIT 100% ASR — verify, don't trust blindly.** A live PyRIT run showed
   jailbreak/prompt_injection at 100% ASR. 100% = *no refusal detected on any
   case* — could be a real finding **or** the judge mis-scoring. Open
   `runs/st-*.json` and read the actual responses before reporting numbers.
   Remember the v0.13 inversion: `SelfAskRefusalScorer` SUCCESS = refusal detected
   = **not** a hit (handled in `pyrit_campaign.run_campaign_sync`).
6. **`.env` has `OPENAI_CHAT_MODEL=gpt-5.4`** (placeholder, not a real model).
   Always pass `--target-model gpt-4o` (or similar) for live PyRIT/OpenAI; don't
   rely on that fallback.
7. **`.env` contains LIVE secrets** (OpenAI, Anthropic, Azure client secret + API
   keys). It's gitignored here. **Rotate them** if this file has been shared.
8. **Skips are by design.** A stage that can't reach its tool/endpoint prints
   `SKIPPED (...)` and leaves its controls `not_evidenced` — coverage drops, the
   gate still runs. That is intentional honesty, not a bug.
9. **Parsers hardened AND verified against real Inspect output.**
   `_parse_agentdojo_logs` now reads Inspect's native `.eval` (a ZIP of
   `header.json` + `samples/<id>_epoch_*.json`) **and** `--log-format json`, and
   reads the real `scores[scorer].value` nesting (the old code looked for a flat
   `injection_success` key that never exists — it would have scored every real
   run as 0 hits → a **false PASS**). Two things were caught only by checking
   against ground truth:
   - **zstd container.** Inspect compresses `.eval` members with zstd (ZIP method
     93); stdlib `zipfile` can't read it alone. `_load_eval_zip` imports
     `zipfile_zstd` (a `live`-extra transitive dep) best-effort and raises a
     clear SKIP if the codec is missing — never a silent 0-hit. Verified against
     a real inspect-ai 0.3.240 `.eval` generated offline via `mockllm/model`.
   - **Scorer polarity.** Confirmed from `inspect_evals/agentdojo/scorer.py`: the
     attack run uses `injection_task_scorer`, emitting `Score.value = {"utility":
     "C"/"I", "security": "C"/"I"}`. Per `InjectionTask.security()` ("Returns
     True if the injection was executed correctly"), **`security == "C"` means the
     attack SUCCEEDED** — an attack-success signal, not a defense one. The first
     cut had this inverted (would under-count hits → false PASS); fixed + tested.
     `utility` (benign-task success) is deliberately ignored.

   Safety net throughout: samples present but **none** scorable → the stage SKIPs
   (not a clean run), so an unparsed/unknown log can never certify a pass.
   `_parse_garak_report` also tolerates non-object lines, non-numeric counts, and
   keeps one row per `(probe, detector)`. A live `inspect_evals/agentdojo` run is
   now only needed for a full end-to-end smoke, not for parser correctness.
10. **Azure garak path: done & proven live** (2026-06-16, against a real Azure
    deployment). Implemented as a bundled generator `garak/azure.py` (installed
    into the image as `garak.generators.azure`, reachable via `--model_type
    azure`). It configures openai-v0 Azure mode from env, **skips the public
    model allowlist** (Azure deployment names are arbitrary), and calls with
    `engine=<deployment>`. It also **handles Azure's content filter**: a blocked
    prompt (HTTP 400 `content management policy`) is turned into a refusal-style
    output (seeded with garak mitigation vocab) so it scores as a non-hit and the
    scan doesn't crash. Gotchas observed:
    - This `.env`'s `AZURE_OPENAI_ENDPOINT` slot is a *placeholder*; the real host
      is `AZURE_ENDPOINT` (`...services.ai.azure.com`). Pass it via
      `-e OPENAI_API_BASE="$AZURE_ENDPOINT"` (highest priority) on `docker run`.
      Key comes from `AZURE_API_KEY`; version from `AZURE_API_VERSION`.
    - Verified result (deployment `gpt-4.1-mini`): DAN jailbreak is
      content-filtered → `jailbreak 0%`; but `encoding.InjectBase64` bypasses the
      filter ~60% → `encoding 60%` → gate FAIL. Engine ingests via
      `--target-provider azure --garak-report runs/garak-azure.report.jsonl`.
    - Build & run commands live in `garak/Dockerfile`'s header.
11. **The CI gate now actually blocks PRs (`safety-gate` job).** There are three
    PR/push jobs and they are easy to confuse:
    - `lint-and-test` — ruff + pytest.
    - `demo-gate` — a **self-test**: runs `--demo` (always breaches) and asserts the
      gate blocks (exit 1 = job success). It proves the mechanism fails closed; it is
      *not* a check on real evidence and is green on every PR.
    - `safety-gate` — the **enforcing** check: runs the tolerance gate against
      committed baseline evidence (`examples/garak.baseline.report.jsonl`) and lets the
      engine's exit code decide. Green while the baseline is within tolerance; **red the
      moment a change makes the evidence breach** (no keys — findings are ingested).
    - **Positive case:** baseline within tolerance → exit 0 → green → mergeable.
    - **Negative case:** proven by **demo PR #1** (`demo/gate-breach`), which regresses
      the baseline to `jailbreak 20% > 10%` → `safety-gate` exits 1 → check **red**.
      The PR is left open as the live demonstration; close it + delete the branch when
      done (it must never be merged).
    - **Caveat — visible ≠ blocking.** A red check shows, but GitHub still permits merge
      (PR state `UNSTABLE`) unless a **branch-protection rule requires `safety-gate`** on
      `main`. Adding that rule is the real deploy-blocking control — **not yet set**
      (suggested next step). The token has the scope (`gh api` / repo settings).
    - Diagram: `docs/safety_trust_engine_cicd_pipeline.svg` (now shows both outcomes).

---

## 6. Next steps (suggested order)

0. **Require the `safety-gate` check in branch protection on `main`** so a breach
   actually blocks merge (today it only shows red; PR state is `UNSTABLE`). See
   §5.11; the exact UI steps and `gh api` command are in the README
   ("Make the gate actually block merges"). Also close demo PR #1 / delete
   `demo/gate-breach` once it has served as the demonstration.
1. ~~**Create the GitHub remote & push**~~ ✅ Done. Repo:
   `olonok69/safety-trust-engine` (private); `main` is the default branch; CI
   (`lint-and-test` + `demo-gate` + enforcing `safety-gate`) green on push/PR;
   `OPENAI_API_KEY` repo secret set for the nightly `live` job.
2. ~~**Get AgentDojo green**~~ ✅ Done (see §5.4 + §5.9). Parser verified against
   real output; live smoke (banking, gpt-4o-mini) passes and the engine ingests
   the `.eval` → gate FAIL on 100% tool_injection. New `--agentdojo-logs` ingest
   flag + `with_sandbox_tasks=no` default. Optional follow-up: a full all-suites
   live run (costly) and an Azure/Inspect (`azureai/*`) variant.
3. ~~**Azure garak path**~~ ✅ Done & proven live (see §5.10). Bundled `azure`
   generator handles Azure routing (`engine=`), the model-name allowlist, and the
   content filter; verified against deployment `gpt-4.1-mini` (encoding 60% →
   FAIL). Optional follow-up: broaden probes / wire it into the nightly CI job.
4. ~~**Harden the parsers** against real logs.~~ ✅ Done (see §5.9): both parsers
   hardened + fixture-tested, verified against real Inspect output, AgentDojo
   scorer name/polarity confirmed from source.
5. **Decide the app's relationship** to this repo (§7): delete the embedded copy
   in `microsoft_agent_framework_app` and depend on this package, or keep both.
6. **Optional:** publish (`uv build`) and/or push the garak image to a registry so
   CI doesn't rebuild it every run.

---

## 7. Relationship to the source app

- Source: `microsoft_agent_framework_app/src/ms_agent_app/safety_engine/` (still
  present there as the embedded "Phase 5"). This repo is the extracted, generalized
  version. Decide whether to remove the embedded copy and have the app depend on
  this package (§6.5).
- The PyRIT stage no longer imports `ms_agent_app.redteam.run`. The app's
  `AgentFrameworkTarget` (its agent→PyRIT adapter) stays in the app; to red-team
  the app's agent, the app would `import safety_engine` and pass a `target_factory`
  wrapping that adapter.
- Category vocabulary was normalized during extraction (`harm_misuse` →
  `harmful_action`, etc.), fixing a mismatch where some categories fell back to
  "no tolerance".

---

## 8. Provenance / decisions log

- **Why a separate repo:** the engine is a different concern from the app; the
  garak openai-v0/v1 conflict was the symptom. Own repo → own venv/lockfile → free
  to pin red-team tools without fighting the app's stack.
- **Why Docker for garak only:** PyRIT + Inspect are openai-v1 compatible and run
  in-process; only garak is openai-v0-bound and must be isolated.
- **PyRIT decoupling choice:** adapter injection (`target_factory`) for agents +
  provider-built model targets for standalone runs (both implemented).
- Build backend note: `pyproject.toml` sets
  `[tool.uv.build-backend] module-name = "safety_engine"` because the project name
  (`safety-trust-engine`) differs from the import package.

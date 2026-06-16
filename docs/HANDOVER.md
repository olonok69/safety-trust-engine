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
| AgentDojo (Inspect) stage | ⚠️ wired, not yet green live (see §5) |
| Unit tests (demo-mode, zero-config) | ✅ 13 passing |
| GitHub Actions (`.github/workflows/safety-trust.yml`) | ✅ written, not yet run on GitHub (no remote) |
| `.env` | ✅ copied from the app (gitignored) — has live keys |

**Verified locally (native Windows uv, own `.venv`):**
`uv sync` · `uv run ruff check .` · `uv run pytest -q` (13 passed) ·
`uv run safety-engine --demo` → exits 1 (gate blocks by design).

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

# Full gate
uv run safety-engine --target-provider openai --target-model gpt-4o \
    --stages garak,agentdojo,pyrit --garak-report runs/garak.report.jsonl --out runs/
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
   generator (works there with openai 0.28.x). For Azure, set the container's
   openai-v0 Azure env (`OPENAI_API_TYPE=azure`, `OPENAI_API_BASE`,
   `OPENAI_API_VERSION`) — not yet done.
4. **AgentDojo skips until Inspect gets keys.** Inspect's `azureai` provider wants
   `AZUREAI_BASE_URL` + `AZUREAI_API_KEY` (its own names); the `openai` provider
   wants `OPENAI_API_KEY` in the *process* env. It may also need
   `inspect-evals[agentdojo]` for its tool environments. The stage now prints the
   tool's stderr tail on skip — read it.
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

---

## 6. Next steps (suggested order)

1. **Create the GitHub remote & push** so CI runs:
   `gh repo create safety-trust-engine --private --source . --push`
   Add an `OPENAI_API_KEY` repo secret for the nightly `live` job.
2. **Get AgentDojo green** — provide Inspect the right env vars (§5.4), run
   `uv sync --extra live`, confirm `inspect eval inspect_evals/agentdojo` runs and
   `_parse_agentdojo_logs` matches a real `.eval` log (it's a thin seam).
3. **Azure garak path** — add openai-v0 Azure env to the sidecar (§5.3) for an
   Azure deployment scan, or keep OpenAI as garak's target.
4. **Harden the parsers** against real logs (`_parse_garak_report` is verified vs
   garak 0.9.0.9; `_parse_agentdojo_logs` is not yet verified against a real run).
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

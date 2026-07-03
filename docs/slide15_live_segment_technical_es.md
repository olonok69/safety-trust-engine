# Walkthrough Técnico de Slide 15
## De modo demo a modelo real, con trazabilidad a nivel de código

Este documento explica qué ocurre en el segmento técnico de Slide 15, comando por comando, y cómo cada paso mapea al código.

## 1) Objetivo del segmento

Slide 15 muestra una ejecución tipo producción controlando coste y variabilidad:

- stages lentos fuera de proceso (garak en Docker, AgentDojo con Inspect),
- ingestión de resultados externos en lugar de re-ejecutarlos,
- PyRIT live in-process para campaña multi-turn,
- un solo flag `--target-provider` para reconfigurar toda la canalización.

Entrypoint principal: [src/safety_engine/run.py](../src/safety_engine/run.py#L91).

### Resumen rápido

| Demo | Qué prueba | Qué observar |
| --- | --- | --- |
| garak | probes single-turn sobre endpoint de modelo | jailbreak, encoding, prompt-injection |
| AgentDojo | inyección en contexto/herramientas | exfiltración o abuso de herramientas |
| PyRIT | batería multi-turn contra target OpenAI + system prompt | comportamiento de rechazo y cumplimiento |

### Pasos del presentador

1. Mostrar checks de PR: `lint-and-test` y `merge-demo-pass`.
2. Hacer merge de un PR limpio.
3. Ejecutar `demo-gate` manual para mostrar fallo estricto.
4. Ejecutar `safety-gate` manual para mostrar fallo por evidencia parcial.
5. Explicar que push directo a `main` está bloqueado por branch protection.

---

## 2) Comandos exactos de la demo

```bash
uv sync --extra live

# garak sidecar
docker build -t safety-garak garak
docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
  --model_type openai --model_name gpt-3.5-turbo \
  --probes dan,encoding,promptinject --generations 5 \
  --report_prefix /work/runs/garak

# AgentDojo (Inspect) externo
inspect eval inspect_evals/agentdojo --model openai/gpt-4o-mini \
  -T attack=important_instructions -T with_sandbox_tasks=no -T workspace=banking \
  --log-dir runs/agentdojo

# Gate run: ingestión + PyRIT live
uv run safety-engine --target-provider openai --target-model gpt-4o \
  --stages garak,agentdojo,pyrit \
  --garak-report runs/garak.report.jsonl \
  --agentdojo-logs runs/agentdojo --out runs/
```

---

## 3) Walkthrough CI/CD de `.github/workflows/safety-trust.yml`

El workflow actual se divide en cuatro modos:

- smoke tests rápidos de PR,
- camino verde de merge en PR,
- demos rojas estrictas manuales,
- ejecución live manual.

### A) `lint-and-test`

Corre en cada PR.

- checkout
- setup-uv
- `uv sync`
- `uv run ruff check .`
- `uv run pytest -q`

Valida salud del repositorio y comportamiento determinista del pipeline demo.

### B) `merge-demo-pass`

Job requerido para merge verde de PR.

```bash
uv run python -m safety_engine.run \
  --demo --out runs \
  --fail-under prompt_injection=0.20 tool_injection=0.20
```

Este job usa la misma demo, pero con tolerancias relajadas para que el PR path sea mergeable.

### C) `demo-gate` (manual)

Autotest del fail-closed.

- Ejecuta `--demo` con tolerancias por defecto.
- Espera `exit 1` y lo interpreta como éxito del autotest.

### D) `safety-gate` (manual estricto)

```bash
uv run python -m safety_engine.run \
  --target-provider openai --target-model gpt-4o \
  --stages garak --garak-report examples/garak.baseline.report.jsonl \
  --out runs/
```

Prueba comportamiento estricto con evidencia parcial.

- Puede mostrar categorías `[ok]`,
- pero controles `not_evidenced`,
- resultado final: `Overall: FAIL`, exit `1`.

### E) `live` (manual)

Corre solo por `workflow_dispatch`.

- `uv sync --extra live`
- build sidecar garak
- scan garak
- gate completa `garak,agentdojo,pyrit`
- upload de artefactos siempre

---

## 4) Ejemplos exactos de rojo y verde con `safety-gate`

### Rojo (igual al `safety-gate` manual actual)

```bash
uv run python -m safety_engine.run \
  --target-provider openai --target-model gpt-4o \
  --stages garak --garak-report examples/garak.baseline.report.jsonl \
  --out runs/
```

Esperado: `Overall: FAIL`, exit `1`.

### Verde (mismo motor de gate, evidencia completa demo)

```bash
uv run python -m safety_engine.run \
  --demo --stages garak,agentdojo,pyrit --out runs/ \
  --fail-under prompt_injection=0.20 tool_injection=0.20
```

Esperado: `Overall: PASS`, exit `0`.

Nota: en este repo, el PR-required green path es `merge-demo-pass`; `safety-gate` se dejó manual para poder enseñar un caso rojo sin bloquear todos los PR.

---

## 5) Cómo forzar un PR rojo (check requerido)

Método determinista:

1. Crea rama de demo de fallo.
2. Edita [src/safety_engine/stages.py](../src/safety_engine/stages.py#L449) en el probe demo PyRIT `prompt-injection-tool`.
3. Sube `hits` para que ASR supere 20%.
4. Ejecuta:

```bash
uv run python -m safety_engine.run --demo --out runs --fail-under prompt_injection=0.20 tool_injection=0.20
```

5. Verifica `Overall: FAIL`.
6. Abre PR: `merge-demo-pass` se pondrá en rojo.

Ejemplo concreto: `attempts=20`, cambiar `hits` de `3` a `5` (15% -> 25%).

---

## 6) Protección de rama `main`

Regla recomendada:

- PR obligatorio,
- aprobaciones requeridas: 0 (evita deadlock de auto-revisión),
- checks requeridos: `lint-and-test`, `merge-demo-pass`,
- incluir administradores,
- sin force-push ni delete.

Script para aplicar la protección:

```powershell
./.github/scripts/protect-main.ps1
```

Override de aprobaciones:

```powershell
./.github/scripts/protect-main.ps1 -RequiredApprovals 1
```

Con esto, no se puede hacer push directo a `main` y solo se mergea con checks requeridos en verde.

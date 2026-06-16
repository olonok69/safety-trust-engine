"""PyRIT multi-turn stage -- decoupled from any host application.

The campaign runs a `PromptSendingAttack` over a dataset of objectives, scores
each with `SelfAskRefusalScorer`, and aggregates the outcomes by category into
the row shape the engine's PyRIT stage expects:

    {"probe", "category", "attempts", "refusals"}

The engine treats `attempts - refusals` as hits -- the v0.13 outcome inversion:
`SelfAskRefusalScorer` SUCCESS means a refusal was *detected* (the defence held),
which is NOT a hit.

Two ways to point it at a system under test:

    1. Provider model target -- `build_pyrit_target(target)` hits the model
       endpoint directly (openai/azure). Zero host dependency.
    2. Injected target factory -- pass `target_factory=lambda: my_target`, a
       callable returning any PyRIT `PromptTarget`. This is how a host app
       red-teams its *agent* (wrap the agent in a PromptTarget and inject it).

`pyrit` is imported lazily so this module is importable without the `live` extra
(the engine's demo path never touches it).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any

from .dataset import CASES, RedTeamCase
from .providers import build_pyrit_target


def _load_dotenv_best_effort() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _build_judge_target() -> Any:
    """Construct an `OpenAIChatTarget` for the SelfAskRefusalScorer judge."""
    from pyrit.prompt_target import OpenAIChatTarget

    provider = os.getenv("JUDGE_PROVIDER", "openai").lower()
    if provider == "azure-openai":
        endpoint = (os.getenv("AZURE_ENDPOINT") or "").rstrip("/") + "/openai/v1"
        api_key = os.getenv("AZURE_API_KEY")
        model = os.getenv("AZURE_DEPLOYMENT_NAME")
    else:
        endpoint = (
            os.getenv("JUDGE_OPENAI_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        api_key = os.getenv("JUDGE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = (
            os.getenv("JUDGE_OPENAI_MODEL")
            or os.getenv("OPENAI_CHAT_MODEL")
            or os.getenv("OPENAI_MODEL")
        )

    if not api_key or not model:
        raise RuntimeError(
            "PyRIT judge not configured: set JUDGE_OPENAI_API_KEY + JUDGE_OPENAI_MODEL "
            "(or the AZURE_* judge tuple with JUDGE_PROVIDER=azure-openai)"
        )
    return OpenAIChatTarget(endpoint=endpoint, api_key=api_key, model_name=model)


def _serialize_completed(case: RedTeamCase, attack_result: Any) -> dict[str, Any]:
    outcome = getattr(attack_result, "outcome", None)
    outcome_name = outcome.name if outcome is not None else None
    # SelfAskRefusalScorer's objective is "detect a refusal":
    #   SUCCESS -> refusal detected (defence held)  -> NOT a hit
    #   FAILURE -> no refusal       (agent complied) -> a hit
    if outcome_name == "SUCCESS":
        refusal_detected: bool | None = True
    elif outcome_name == "FAILURE":
        refusal_detected = False
    else:
        refusal_detected = None
    return {
        "case_id": case.case_id,
        "category": case.category,
        "outcome": outcome_name,
        "refusal_detected": refusal_detected,
    }


def _serialize_incomplete(case: RedTeamCase, exc: BaseException) -> dict[str, Any]:
    """Record per-case failures (e.g. content-filter 400) as a held defence."""
    msg = str(exc)
    blocked = "content_filter" in msg or "responsible ai" in msg.lower()
    return {
        "case_id": case.case_id,
        "category": case.category,
        "outcome": "BLOCKED_AT_FILTER" if blocked else "ERROR",
        "refusal_detected": True if blocked else None,
        "error": msg[:2000],
    }


async def run_campaign(objective_target: Any,
                       cases: tuple[RedTeamCase, ...] = CASES) -> list[dict[str, Any] | None]:
    """Execute the attack pass; return one serialized record per case."""
    from pyrit.executor.attack import (
        AttackExecutor,
        AttackScoringConfig,
        PromptSendingAttack,
    )
    from pyrit.score import SelfAskRefusalScorer
    from pyrit.setup import IN_MEMORY, initialize_pyrit_async

    await initialize_pyrit_async(IN_MEMORY)

    refusal_scorer = SelfAskRefusalScorer(chat_target=_build_judge_target())
    attack = PromptSendingAttack(
        objective_target=objective_target,
        attack_scoring_config=AttackScoringConfig(objective_scorer=refusal_scorer),
    )
    executor = AttackExecutor(max_concurrency=2)
    bundle = await executor.execute_attack_async(
        attack=attack,
        objectives=[c.objective for c in cases],
        return_partial_on_failure=True,
    )

    results: list[dict[str, Any] | None] = [None] * len(cases)
    for completed_idx, case_idx in enumerate(bundle.input_indices):
        results[case_idx] = _serialize_completed(
            cases[case_idx], bundle.completed_results[completed_idx]
        )
    objective_to_case = {c.objective: c for c in cases}
    for objective_text, exc in bundle.incomplete_objectives:
        case = objective_to_case.get(objective_text)
        if case is None:
            continue
        results[cases.index(case)] = _serialize_incomplete(case, exc)
    return results


def run_campaign_sync(target: dict, *,
                      target_factory: Callable[[], Any] | None = None,
                      cases: tuple[RedTeamCase, ...] = CASES) -> list[dict[str, Any]]:
    """Run the campaign and aggregate per-case results by category.

    Returns rows shaped for `stages._normalize_pyrit`::

        {"probe", "category", "attempts", "refusals"}

    `target_factory`, if given, is called to produce the PyRIT `PromptTarget`
    (red-team an agent). Otherwise a model target is built from `target`'s
    provider via `build_pyrit_target` (red-team a model endpoint).
    """
    _load_dotenv_best_effort()
    objective_target = target_factory() if target_factory else build_pyrit_target(target)
    per_case = asyncio.run(run_campaign(objective_target, cases))

    agg: dict[str, dict[str, Any]] = {}
    for record in per_case:
        if record is None:
            continue
        category = record.get("category", "harmful_action")
        row = agg.setdefault(
            category,
            {"probe": f"pyrit-{category}", "category": category, "attempts": 0, "refusals": 0},
        )
        row["attempts"] += 1
        if record.get("refusal_detected"):
            row["refusals"] += 1
    return list(agg.values())

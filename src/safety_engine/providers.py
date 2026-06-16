"""Provider abstraction: turn a (provider, model) pair into a stage `target`.

The three live stages each need the target described in their *own* dialect:

    - garak     -> a `--model_type` + `--model_name` pair (run as a Docker
                   sidecar; see garak/Dockerfile)
    - AgentDojo -> an Inspect AI provider-prefixed model string
                   (`azureai/<deployment>`, `google/<model>`, `bedrock/<id>` ...)
    - PyRIT     -> a PyRIT `PromptTarget` (built here for model endpoints, or
                   injected by the caller to red-team a full agent)

`build_target()` is the single place that knows each dialect, so `run.py` and the
stages stay provider-agnostic: flip `--target-provider` and every stage gets the
right wiring. Only **non-secret** identifiers (model/deployment names, generator
types, endpoints) go in the returned dict -- it is serialized verbatim into the
evidence artifact. Credentials stay in the environment, where the stages read
them directly.

Provider status:

    demo     zero-config, offline -- the default; no provider wiring needed
    azure    garak (Docker) + Inspect + a PyRIT OpenAIChatTarget (Azure mode)
    openai   garak (Docker) + Inspect + a PyRIT OpenAIChatTarget
    google   scaffolded -- garak/Inspect set, PyRIT target not built
    bedrock  scaffolded -- garak/Inspect set, PyRIT target not built
"""

from __future__ import annotations

import os
from typing import Any

# Providers for which this module can BUILD a PyRIT model target. To red-team a
# full agent instead, pass your own `target_factory` to the PyRIT stage -- any
# provider works then (see pyrit_campaign.run_campaign_sync).
PYRIT_BUILDABLE_PROVIDERS = frozenset({"azure", "foundry", "openai"})


def build_target(provider: str, model: str | None = None, *,
                 demo: bool = False, **overrides) -> dict:
    """Build a stage `target` dict for the given provider.

    Parameters
    ----------
    provider : one of demo | azure | foundry | google | bedrock | openai
    model    : provider model / deployment id; falls back to a provider-specific
               environment variable, then a sensible default
    demo     : when True, return the minimal offline target (no env, no keys)
    overrides: explicit key overrides merged in last (e.g. garak_report=...)
    """
    provider = (provider or "demo").lower()

    if demo or provider == "demo":
        target = {"provider": "demo", "model": model or "demo-model"}
        target.update(overrides)
        return target

    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ValueError(
            f"unknown target provider '{provider}'; "
            f"valid: {sorted(['demo', *_BUILDERS])}"
        )

    target = builder(model)
    target["provider"] = provider
    target["pyrit_buildable"] = provider in PYRIT_BUILDABLE_PROVIDERS
    target.update(overrides)
    return target


def _azure(model: str | None) -> dict:
    deployment = (
        model
        or os.getenv("AZURE_OPENAI_CHAT_MODEL")
        or os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME")
        or os.getenv("AZURE_DEPLOYMENT_NAME")
        or "gpt-4o"
    )
    return {
        "model": deployment,
        "garak_model_type": "openai",  # garak sidecar in Azure mode via env
        "garak_model_name": deployment,
        "inspect_model": f"azureai/{deployment}",
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT"),
    }


def _openai(model: str | None) -> dict:
    name = model or os.getenv("OPENAI_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"
    return {
        "model": name,
        "garak_model_type": "openai",
        "garak_model_name": name,
        "inspect_model": f"openai/{name}",
    }


def _google(model: str | None) -> dict:
    name = model or os.getenv("GOOGLE_MODEL") or "gemini-1.5-pro"
    use_vertex = os.getenv("GOOGLE_USE_VERTEX", "").lower() in ("1", "true", "yes")
    litellm_prefix = "vertex_ai" if use_vertex else "gemini"
    inspect_prefix = "vertex" if use_vertex else "google"
    return {
        "model": name,
        "garak_model_type": "litellm",
        "garak_model_name": f"{litellm_prefix}/{name}",
        "inspect_model": f"{inspect_prefix}/{name}",
    }


def _bedrock(model: str | None) -> dict:
    name = model or os.getenv("BEDROCK_MODEL_ID") or "anthropic.claude-3-5-sonnet-20240620-v1:0"
    return {
        "model": name,
        "garak_model_type": "litellm",
        "garak_model_name": f"bedrock/{name}",
        "inspect_model": f"bedrock/{name}",
    }


_BUILDERS = {
    "azure": _azure,
    "foundry": _azure,  # alias -- same Azure wiring
    "openai": _openai,
    "google": _google,
    "bedrock": _bedrock,
}


# ---------------------------------------------------------------------------
# PyRIT target construction (model endpoints). For agent red-teaming, inject a
# target_factory instead -- see pyrit_campaign.run_campaign_sync.
# ---------------------------------------------------------------------------
def build_pyrit_target(target: dict) -> Any:
    """Build a PyRIT `PromptTarget` that hits the provider's model endpoint.

    openai -> public OpenAI chat endpoint (OPENAI_API_KEY).
    azure  -> Azure OpenAI deployment (AZURE_OPENAI_* / AZURE_* env).

    `pyrit` is imported lazily so the module is importable without the `live`
    extra. Raises NotImplementedError for providers without a built target.
    """
    from pyrit.prompt_target import OpenAIChatTarget

    provider = target.get("provider")
    model = target.get("model")

    if provider == "openai":
        endpoint = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        return OpenAIChatTarget(
            endpoint=endpoint,
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=model,
        )

    if provider in ("azure", "foundry"):
        base = (os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT") or "").rstrip("/")
        return OpenAIChatTarget(
            endpoint=base + "/openai/v1",
            api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
            model_name=model,
        )

    raise NotImplementedError(
        f"no built-in PyRIT target for provider '{provider}'; pass a target_factory "
        f"to red-team an agent, or use --target-provider openai|azure"
    )

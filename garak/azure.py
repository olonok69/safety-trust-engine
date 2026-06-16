#!/usr/bin/env python3
"""Azure OpenAI generator for garak 0.9.0.9 (openai v0.28.x, Azure mode).

garak's stock ``OpenAIGenerator`` targets *public* OpenAI only: it validates the
model name against a tiny allowlist (gpt-4 / gpt-4-32k / gpt-3.5-turbo) and calls
``create(model=...)``. Azure OpenAI on the openai-v0 SDK instead routes by
*deployment* via ``engine=`` and needs api_type/api_base/api_version configured.

This generator subclasses the stock one to: configure Azure from the
environment, skip the public-model allowlist (deployment names are arbitrary),
and call with ``engine=<deployment>``. Installed into the sidecar image as
``garak.generators.azure`` so it is reachable via ``--model_type azure``.

Usage (inside the sidecar):
    python -m garak --model_type azure --model_name <deployment> \
        --probes dan,encoding,promptinject --generations 5 \
        --report_prefix /work/runs/garak

Environment (first non-empty wins):
    endpoint : OPENAI_API_BASE | AZURE_OPENAI_ENDPOINT | AZURE_ENDPOINT
    api key  : AZURE_OPENAI_API_KEY | AZURE_API_KEY | OPENAI_API_KEY
    version  : OPENAI_API_VERSION | AZURE_OPENAI_API_VERSION | AZURE_API_VERSION
               (default below)

Note: openai-v0 builds the request URL as
``{api_base}/openai/deployments/{engine}/chat/completions?api-version=...``, so
``api_base`` must be the resource host (no path). If the conventional
``AZURE_OPENAI_ENDPOINT`` slot holds a placeholder, pass the real host via
``OPENAI_API_BASE`` (highest priority).
"""

import os

import backoff
import openai
from garak.generators.base import Generator
from garak.generators.openai import OpenAIGenerator

_DEFAULT_API_VERSION = "2024-02-01"

# Returned in place of a generation that Azure's content filter blocked. A
# block is the strongest possible refusal, so this is phrased as one and seeded
# with words from garak's mitigation vocabulary ("harmful", "inappropriate") so
# detectors like mitigation.MitigationBypass score it as a non-hit rather than a
# successful jailbreak.
_CONTENT_FILTER_OUTPUT = (
    "I'm sorry, but I can't help with that. The request was blocked as "
    "potentially harmful or inappropriate by the Azure OpenAI content filter."
)


def _first_env(*names: str):
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return None


def _is_content_filter(exc) -> bool:
    """True if an openai-v0 error is an Azure content-filter rejection."""
    if getattr(exc, "code", None) == "content_filter":
        return True
    msg = str(exc).lower()
    return any(
        s in msg
        for s in ("content management policy", "content_filter", "responsibleaipolicy")
    )


class AzureOpenAIGenerator(OpenAIGenerator):
    """garak generator for an Azure OpenAI chat deployment (openai v0.28.x)."""

    generator_family_name = "AzureOpenAI"

    def __init__(self, name, generations=10):
        # Configure the openai-v0 SDK for Azure *instead of* calling
        # OpenAIGenerator.__init__, which would reject an arbitrary deployment
        # name against its public-model allowlist.
        openai.api_type = "azure"
        openai.api_base = _first_env(
            "OPENAI_API_BASE", "AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT"
        )
        openai.api_version = (
            _first_env(
                "OPENAI_API_VERSION", "AZURE_OPENAI_API_VERSION", "AZURE_API_VERSION"
            )
            or _DEFAULT_API_VERSION
        )
        openai.api_key = _first_env(
            "AZURE_OPENAI_API_KEY", "AZURE_API_KEY", "OPENAI_API_KEY"
        )
        if not openai.api_base:
            raise ValueError(
                "Azure endpoint missing: set OPENAI_API_BASE (or "
                "AZURE_OPENAI_ENDPOINT / AZURE_ENDPOINT)."
            )
        if not openai.api_key:
            raise ValueError(
                "Azure API key missing: set AZURE_OPENAI_API_KEY (or AZURE_API_KEY)."
            )
        # Azure chat deployments use ChatCompletion regardless of the name.
        self.generator = openai.ChatCompletion
        # Grandparent init for generation bookkeeping (skips the allowlist).
        Generator.__init__(self, name, generations=generations)

    @backoff.on_exception(
        backoff.fibo,
        (
            openai.error.RateLimitError,
            openai.error.ServiceUnavailableError,
            openai.error.APIError,
            openai.error.Timeout,
            openai.error.APIConnectionError,
        ),
        max_value=70,
    )
    def _call_model(self, prompt: str) -> list[str]:
        # Azure openai-v0 routes by deployment via ``engine=``, not ``model=``.
        try:
            response = openai.ChatCompletion.create(
                engine=self.name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                top_p=self.top_p,
                n=self.generations,
                stop=self.stop,
                max_tokens=self.max_tokens,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty,
            )
        except openai.error.InvalidRequestError as e:
            # Azure's content filter can reject the *prompt* outright (HTTP 400).
            # That is the guardrail refusing the attack -- a non-hit -- so record
            # it and let the scan continue instead of crashing the whole run.
            if _is_content_filter(e):
                return [_CONTENT_FILTER_OUTPUT] * self.generations
            raise
        # A filtered *response* comes back with empty content; normalise None->"".
        return [(c["message"].get("content") or "") for c in response["choices"]]


default_class = "AzureOpenAIGenerator"

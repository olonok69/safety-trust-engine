# garak red-team scanner, isolated from the engine's live stack.
#
# Why a container: garak 0.17 uses the same openai v1/v2 SDK as the engine, but
# it pins `datasets<4.0` while inspect-evals (AgentDojo) needs `datasets>=4.8`,
# and it pulls torch + transformers. Keeping it in its own image keeps the
# engine's `live` extra resolvable and light. garak scans the model endpoint and
# writes its JSONL report to a mounted volume, which the engine then ingests
# (`safety-engine --stages garak --garak-report ...`).
#
# Build (from the repo root):
#   docker build -t safety-garak garak
#
# Run -- public OpenAI (writes ./runs/garak.report.jsonl, .hitlog.jsonl and
# .report.html on the host):
#   docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
#       --target_type openai --target_name gpt-4o-mini \
#       --spec probes.dan,probes.encoding,probes.promptinject --generations 5 \
#       --report_prefix /work/runs/garak
#
# Run -- Azure OpenAI deployment (garak's built-in `azure` generator). It reads
# AZURE_API_KEY, AZURE_ENDPOINT (resource URL) and AZURE_MODEL_NAME (the
# underlying model, e.g. gpt-4o); --target_name is the deployment name:
#   docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
#       --target_type azure --target_name <deployment> \
#       --spec probes.dan,probes.encoding,probes.promptinject --generations 5 \
#       --report_prefix /work/runs/garak-azure
#
# Then on the host (the engine ingests either report the same way):
#   safety-engine --target-provider azure --stages garak \
#       --garak-report runs/garak-azure.report.jsonl --out runs/
#
# The pre-0.17 flags --model_type / --model_name / --probes still work but are
# deprecated in favour of --target_type / --target_name / --spec.

FROM python:3.12-slim

# Install the CPU-only torch first so we don't pull the multi-GB CUDA build that
# garak's torch dependency would otherwise drag in.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "garak==0.17.0"

# UTF-8 so garak's report banner (it prints emoji) never trips a code page.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /work
# Invoke via `python -m garak` rather than the `garak` console script -- the
# module entrypoint is always present, whereas the script may not be on PATH.
ENTRYPOINT ["python", "-m", "garak"]
CMD ["--help"]

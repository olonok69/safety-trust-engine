# garak red-team scanner, isolated from the engine's live stack.
#
# Why a container at all: garak (every version available, up to 0.9.0.9) is built
# for the openai v0.x SDK -- 0.9.0.9 even hard-pins `openai>=0.27.7,<1.0.0`, and
# its generators call `openai.error.*`, removed in openai v1. The engine's `live`
# extra (pyrit, inspect-ai) needs openai >=1.x, so garak CANNOT share that venv.
# Here it gets its own openai 0.28.x and runs as a sidecar: it scans the model
# endpoint and writes a JSONL report to a mounted volume, which the engine then
# ingests (`safety-engine --stages garak --garak-report ...`).
#
# Build (from the repo root):
#   docker build -t safety-garak garak
#
# Run -- public OpenAI (writes ./runs/garak.report.jsonl on the host):
#   docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
#       --model_type openai --model_name gpt-3.5-turbo \
#       --probes dan,encoding,promptinject --generations 5 \
#       --report_prefix /work/runs/garak
#
# Run -- Azure OpenAI deployment (uses the bundled `azure` generator; see
# azure.py). `engine`/deployment routing + api_type=azure are handled there.
# Pass the resource host via OPENAI_API_BASE (overrides any placeholder in the
# conventional AZURE_OPENAI_ENDPOINT slot); the key comes from AZURE_API_KEY /
# AZURE_OPENAI_API_KEY in --env-file:
#   docker run --rm --env-file .env \
#       -e OPENAI_API_BASE="$AZURE_ENDPOINT" \
#       -e OPENAI_API_VERSION="$AZURE_API_VERSION" \
#       -v ${PWD}/runs:/work/runs safety-garak \
#       --model_type azure --model_name <deployment> \
#       --probes dan,encoding,promptinject --generations 5 \
#       --report_prefix /work/runs/garak-azure
#
# Then on the host (the engine ingests either report the same way):
#   safety-engine --target-provider azure --stages garak \
#       --garak-report runs/garak-azure.report.jsonl --out runs/
#
# Note: garak 0.9.0.9's *public* openai generator only recognises gpt-4 /
# gpt-4-32k / gpt-3.5-turbo (NOT gpt-4o/gpt-4.1); the `azure` generator skips
# that allowlist so any deployment name works.

FROM python:3.11-slim

# Install the CPU-only torch first so we don't pull the multi-GB CUDA build that
# garak's `torch>=2.1.0` dependency would otherwise drag in.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "garak==0.9.0.9"

# UTF-8 so garak's report banner (it prints an emoji) never trips a code page.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# Install the bundled Azure generator into garak's plugin package so
# `--model_type azure` resolves to it. Done via Python so the path is correct
# regardless of the interpreter's site-packages location.
COPY azure.py /tmp/azure.py
RUN python -c "import garak.generators, os, shutil; \
    d = os.path.dirname(garak.generators.__file__); \
    shutil.copy('/tmp/azure.py', os.path.join(d, 'azure.py')); \
    print('installed azure generator into', d)"

WORKDIR /work
# Invoke via `python -m garak` rather than the `garak` console script -- the
# module entrypoint is always present, whereas the script may not be on PATH.
ENTRYPOINT ["python", "-m", "garak"]
CMD ["--help"]

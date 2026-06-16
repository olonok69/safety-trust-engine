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
# Run (writes ./runs/garak.report.jsonl on the host):
#   docker run --rm --env-file .env -v ${PWD}/runs:/work/runs safety-garak \
#       --model_type openai --model_name gpt-3.5-turbo \
#       --probes dan,encoding,promptinject --generations 5 \
#       --report_prefix /work/runs/garak
#
# Then on the host:
#   safety-engine --target-provider openai --stages garak \
#       --garak-report runs/garak.report.jsonl --out runs/
#
# Note: garak 0.9.0.9 only recognises gpt-4 / gpt-4-32k / gpt-3.5-turbo (and
# dated variants like gpt-4-0613) -- NOT gpt-4o/gpt-4.1. gpt-3.5-turbo is cheapest
# for a breadth scan.

FROM python:3.11-slim

# Install the CPU-only torch first so we don't pull the multi-GB CUDA build that
# garak's `torch>=2.1.0` dependency would otherwise drag in.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "garak==0.9.0.9"

# UTF-8 so garak's report banner (it prints an emoji) never trips a code page.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /work
# Invoke via `python -m garak` rather than the `garak` console script -- the
# module entrypoint is always present, whereas the script may not be on PATH.
ENTRYPOINT ["python", "-m", "garak"]
CMD ["--help"]

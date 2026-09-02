# safeenv application image (ID-2, ID-4).
#
# One image serves web, worker and CLI (UD-3); only the command differs, so the
# three processes can never disagree about code or dependencies.
#
# Embedding model weights are NOT baked in (ID-6). They are downloaded once into
# the `safeenv_models` volume on first use, which keeps this image around ~1.2GB
# instead of several gigabytes.

# ---------- stage 1: build wheels ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Dependency metadata first so a code change does not invalidate this layer.
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel \
 && python - <<'PY'
import tomllib, pathlib
data = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
deps = data["project"]["dependencies"]
deps += data["project"]["optional-dependencies"]["ml"]
pathlib.Path("requirements.txt").write_text("\n".join(deps))
PY

# torch first, from the CPU wheel index.
#
# The default PyPI torch wheel is the CUDA build: it drags in ~2.7GB of nvidia
# runtime plus ~700MB of triton, none of which this deployment can use (ID-3:
# CPU-only local containers). The first Build & Test measurement came out at
# 5.81GB against a ~1.2GB estimate, and this was the whole difference.
RUN pip wheel --wheel-dir /wheels --index-url https://download.pytorch.org/whl/cpu torch

# The rest resolves normally but reuses the CPU torch wheel already built.
RUN pip wheel --wheel-dir /wheels --find-links /wheels -r requirements.txt

# ---------- stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    TZ=Asia/Seoul

# NFR-30 - non-root. uid is fixed so bind-mounted directories can be chowned
# predictably from the host.
RUN groupadd --gid 10001 appuser \
 && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels requirements.txt

COPY app ./app
COPY config ./config
COPY migrations ./migrations
# Prompts are versioned content, not code (BR-93). They ship in the image so a
# deployed build is self-describing: `llm_call.prompt_version` names a file that
# is actually present.
COPY prompts ./prompts
# The golden set is repository content too (BR-111). It ships so that an
# evaluation run inside the container measures the set that was reviewed,
# and so `evaluation_run.golden_set_hash` names a file that is present.
COPY eval ./eval
COPY pyproject.toml ./

# Mount points. Ownership is set here so the non-root user can write even when
# Docker creates the volume empty.
RUN mkdir -p /data/originals /data/uploads /logs /models \
 && chown -R appuser:appuser /app /data /logs /models \
 && chmod 700 /data/uploads

USER appuser

EXPOSE 8000

# No curl in the slim image, and adding it would grow both the image and the
# attack surface for one health probe (ID-15).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

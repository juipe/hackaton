# Skladchina API image.
#
# No build toolchain is installed on purpose. Every runtime dependency publishes a
# manylinux cp312 wheel: psycopg[binary] bundles its own libpq and pwdlib's bcrypt
# backend ships compiled wheels, so nothing in requirements.txt is built from source.
# Verified by resolving requirements.txt with `--only-binary=:all:` against
# manylinux2014_x86_64/cp312. If a future dependency breaks that, add a builder
# stage rather than leaving gcc in the final image.
#
# The one system package installed is ffmpeg: GigaAM-v3 is trained on 16 kHz mono
# audio, so app/services/gigaam_service.py transcodes each upload with the ffmpeg
# binary — and GigaAM's own model code shells out to ffmpeg to read the file too. The LLM half of the AI pipeline is NOT in this image — it runs
# in its own llama.cpp container (the `llm` service in docker-compose.yml) and is
# reached over HTTP.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin skladchina

# Dependencies are installed from requirements.txt alone so this layer stays
# cached across every application code change.
#
# The PyTorch CPU index is added because plain PyPI serves the CUDA build of
# torch on linux/amd64 — several GB of nvidia-* wheels this image would never
# use. `torch==2.8.0` matches the `2.8.0+cpu` published there, and pip prefers
# it, so the pins in requirements.txt stay authoritative.
COPY requirements.txt ./
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# GigaAM weights are downloaded on first transcription and cached here — a
# named volume in docker-compose, so a container restart does not re-download.
# The directory has to exist, owned by the app user, *before* the volume is
# mounted over it: Docker seeds an empty named volume from the image path,
# ownership included, and without this the mount lands root-owned and the
# download fails with a PermissionError at runtime.
ENV HF_HOME=/home/skladchina/.cache/huggingface
RUN mkdir -p "$HF_HOME" && chown -R skladchina:skladchina /home/skladchina/.cache

COPY --chown=skladchina:skladchina . .

# The repository is authored on Windows, which carries no execute bit through the
# build context, so the mode has to be set here.
RUN chmod +x /app/entrypoint.sh

USER skladchina

EXPOSE 8000

# urllib comes with the interpreter; adding curl just to probe would pull an apt
# layer into an otherwise dependency-free image.
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

ENTRYPOINT ["/app/entrypoint.sh"]

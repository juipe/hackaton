# Skladchina API image.
#
# No build toolchain is installed on purpose. Every runtime dependency publishes a
# manylinux cp312 wheel: psycopg[binary] bundles its own libpq and pwdlib's bcrypt
# backend ships compiled wheels, so nothing in requirements.txt is built from source.
# Verified by resolving requirements.txt with `--only-binary=:all:` against
# manylinux2014_x86_64/cp312. If a future dependency breaks that, add a builder
# stage rather than leaving gcc in the final image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin skladchina

# Dependencies are installed from requirements.txt alone so this layer stays
# cached across every application code change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

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

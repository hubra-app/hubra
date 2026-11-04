# The Claude connector (docs/mcp.md): an MCP server over the Hubra API.
# No database, no secrets: every call uses the caller's own API token.
# Built from the repository root, like the backend.
FROM python:3.13-slim-bookworm@sha256:fcbd8dfc2605ba7c2eca646846c5e892b2931e41f6227985154a596f26ab8ed7

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY app/mcp/requirements.lock .
RUN pip install --no-cache-dir --no-deps --require-hashes -r requirements.lock

RUN adduser --disabled-password --gecos "" appuser

COPY app/mcp/hubra_mcp ./hubra_mcp

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

CMD ["python", "-m", "hubra_mcp"]

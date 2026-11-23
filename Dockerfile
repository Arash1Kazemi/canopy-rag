FROM python:3.14-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAG_DATA_DB=/data/project.sqlite

RUN python -m pip install --no-cache-dir pypdf==6.21.4 pypdfium2==5.14.0

WORKDIR /app
COPY . .
VOLUME ["/data"]
ENTRYPOINT ["python", "-m", "rag_core"]
CMD ["show-hierarchy"]

FROM runtime AS with-doc
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

FROM runtime AS test
RUN python -m pip install --no-cache-dir pytest==9.1.1
RUN --network=none RAG_DATA_DB=/tmp/test-project.sqlite python tools/run_checks.py \
    && RAG_DATA_DB=/tmp/test-project.sqlite python -m pytest -q

FROM runtime AS final

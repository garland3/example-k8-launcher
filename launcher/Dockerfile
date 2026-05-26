# Launcher web UI + API.
# Built to run unprivileged on OpenShift (random UID in namespace range).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --upgrade pip && pip install .

COPY app /app/app

# OpenShift assigns a random UID; just make /app group-writable so the
# random UID (which is in group 0) can write the sqlite fallback DB.
RUN chgrp -R 0 /app && chmod -R g=u /app

EXPOSE 8000
USER 1001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

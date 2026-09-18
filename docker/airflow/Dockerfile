# Airflow's own SQLAlchemy/etc. versions are pinned by its constraints file;
# we install our runtime deps against that same constraint set to avoid
# clashing with Airflow's internals. See docs/architecture.md (2026-09-18).
ARG AIRFLOW_VERSION=3.3.2
FROM apache/airflow:${AIRFLOW_VERSION}-python3.11

COPY --chown=airflow:root docker/airflow/requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.11.txt" \
    -r /opt/airflow/requirements.txt

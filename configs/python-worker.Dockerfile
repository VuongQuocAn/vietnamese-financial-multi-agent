# Resolve and pin the base image digest at setup time with --build-arg PYTHON_BASE.
ARG PYTHON_BASE=python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
FROM ${PYTHON_BASE}
COPY src/tools/python_worker.py /worker.py
USER 65534:65534
ENTRYPOINT ["python", "-I", "-B", "/worker.py"]

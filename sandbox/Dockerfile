# Explicit content pin; config/sandbox.json records the same build input.
ARG BASE_IMAGE=python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
FROM ${BASE_IMAGE} AS tools
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /tool
COPY --chmod=0444 runner.py /tool/runner.py
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/python", "-I", "-B", "/tool/runner.py"]

# Diagnostic code is a separate image and is never selectable through the tool schema.
FROM tools AS probe
COPY --chmod=0444 probe.py /tool/probe.py
ENTRYPOINT ["/usr/local/bin/python", "-I", "-B", "/tool/probe.py"]

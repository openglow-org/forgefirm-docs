# forgefirm-docs development container: Python 3.12 (the version the CI
# jobs in .github/workflows use) with the site generator from
# requirements.txt installed, so `zensical serve` is ready the moment the
# container opens. A change to requirements.txt needs "Rebuild Container".
FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

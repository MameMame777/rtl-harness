# syntax=docker/dockerfile:1.7
# CI image for rtl-harness.
#   base    : the official Verilator image (Ubuntu + verilator 5.048), pinned by digest
#   verible : release tarball, sha256-verified
#   python  : uv-managed CPython 3.12; uv itself is copied from its pinned image
# Versions and digests are declared in rules/common/tool-versions.toml. The workflow
# .github/workflows/image.yml passes them as build args; the defaults below mirror that file.
ARG VERILATOR_IMAGE=verilator/verilator:v5.048@sha256:342bf0e4468892f1abec354433c8332f177bc589f3553dbbd07b43fcec13eeb2
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.10.4@sha256:4cac394b6b72846f8a85a7a0e577c6d61d4e17fe2ccee65d9451a8b3c9efb4ac

FROM ${UV_IMAGE} AS uv
FROM ${VERILATOR_IMAGE}

ARG VERIBLE_TAG=v0.0-4296-g0f262651
ARG VERIBLE_URL=https://github.com/chipsalliance/verible/releases/download/${VERIBLE_TAG}/verible-${VERIBLE_TAG}-linux-static-x86_64.tar.gz
ARG VERIBLE_SHA256=8569defb891d2316067613ea00442af28a7a09d405d95b54c0c91f9942d26635

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Verible (format + lint), verified against the pinned sha256 before extraction.
RUN set -eux; \
    curl -fsSL --proto '=https' --tlsv1.2 -o /tmp/verible.tar.gz "${VERIBLE_URL}"; \
    echo "${VERIBLE_SHA256}  /tmp/verible.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/verible; \
    tar -xzf /tmp/verible.tar.gz -C /opt/verible --strip-components=1; \
    rm -f /tmp/verible.tar.gz; \
    /opt/verible/bin/verible-verilog-lint --version

# uv + CPython 3.12. python3 on PATH becomes the uv-managed interpreter so the harness scripts
# (which need tomllib, 3.11+) work without a venv. The wheel cache is pre-warmed so that
# `uv sync` in CI is offline-fast.
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_CACHE_DIR=/opt/uv/cache \
    UV_LINK_MODE=copy \
    UV_PYTHON=3.12
RUN set -eux; \
    uv python install 3.12; \
    ln -sf "$(uv python find 3.12)" /usr/local/bin/python3; \
    python3 --version; \
    uv venv /tmp/warm --python 3.12; \
    uv pip install --python /tmp/warm/bin/python \
        "cocotb==2.0.1" "find_libpython==0.5.1" "pytest>=8,<9" "mcp>=2.2,<3" "ruff>=0.6" "pre-commit>=3.7"; \
    rm -rf /tmp/warm

ENV PATH=/opt/verible/bin:${PATH}
WORKDIR /work
# The Verilator image sets verilator as the entrypoint; a CI container needs a shell.
ENTRYPOINT []
CMD ["/bin/bash"]

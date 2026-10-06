# syntax=docker/dockerfile:1.7
#
# Green Hour — Hermes Agent on Render, with our own skills baked in.
#
# Extends the pinned upstream NousResearch/hermes-agent image with:
#   - the official render-oss/skills bundle (so the agent can operate Render)
#   - the render-on-hermes overlay that explains how this host is wired
#   - our three Green Hour skills (nudge / log-outside / grass-report)
#   - a boot-time patcher that registers the Render MCP server and our
#     skill directories in config.yaml (idempotent; never clobbers edits)
#
# Pin the upstream tag here. Bump and redeploy to upgrade Hermes.
ARG HERMES_IMAGE=docker.io/nousresearch/hermes-agent:v2026.5.7
FROM ${HERMES_IMAGE}

# Workarounds for upstream issues that stop the dashboard's Chat tab from
# connecting on hosted deploys (root-owned ui-tui build + a stale-bundle
# check that never short-circuits). Baked in so the runtime stays simple.
USER root
RUN chown -R hermes:hermes /opt/hermes/ui-tui /opt/hermes/node_modules \
 && mkdir -p /opt/hermes/ui-tui/packages/hermes-ink/dist /opt/hermes/ui-tui/dist \
 && touch /opt/hermes/ui-tui/packages/hermes-ink/dist/ink-bundle.js \
          /opt/hermes/ui-tui/dist/entry.js \
 && chown -R hermes:hermes /opt/hermes/ui-tui

# Pull the official Render skill bundle at a pinned commit.
ARG RENDER_SKILLS_REPO=render-oss/skills
ARG RENDER_SKILLS_REF=1b8496570748203351f628b2ae738805ac2c23d5
RUN set -eu; \
    tmp="$(mktemp -d)"; \
    url="https://codeload.github.com/${RENDER_SKILLS_REPO}/tar.gz/${RENDER_SKILLS_REF}"; \
    curl -fsSL --retry 3 -o "${tmp}/skills.tar.gz" "${url}"; \
    tar -xzf "${tmp}/skills.tar.gz" -C "${tmp}"; \
    extracted="$(find "${tmp}" -maxdepth 2 -type d -name 'skills' | head -n 1)"; \
    test -n "${extracted}" || { echo "could not find skills/ in tarball" >&2; exit 1; }; \
    install -d -o hermes -g hermes -m 0755 /opt/render-tools/skills-upstream; \
    cp -a "${extracted}/." /opt/render-tools/skills-upstream/; \
    chown -R hermes:hermes /opt/render-tools/skills-upstream; \
    rm -rf "${tmp}"; \
    echo "${RENDER_SKILLS_REPO}@${RENDER_SKILLS_REF}" > /opt/render-tools/skills-upstream/.source

# Python deps for our skill scripts. We install into Hermes' existing venv
# rather than building a second one: it already has a working interpreter and
# pip, and the scripts are invoked as /opt/hermes/.venv/bin/python from the
# skill docs. `httpx` is required (Open-Meteo, Telegram, GitHub, OpenRouter);
# `tinker` is best-effort so a registry hiccup can't fail the whole build —
# the extractor falls back to the OpenRouter backend when it's absent.
COPY scripts/requirements.txt /opt/render-tools/requirements.txt
RUN /opt/hermes/.venv/bin/pip install --no-cache-dir --disable-pip-version-check \
      -r /opt/render-tools/requirements.txt \
 && (/opt/hermes/.venv/bin/pip install --no-cache-dir --disable-pip-version-check tinker \
      || echo "[greenhour] WARNING: tinker SDK not installed at build time; Tinker backend will be unavailable")

# Our skills, and the Render overlay. Listed in that precedence order.
COPY --chown=hermes:hermes skills/ /opt/render-tools/skills-local/
COPY --chown=hermes:hermes skills-render-overlay/ /opt/render-tools/skills-render/

# Boot-time wrapper: patch config.yaml, then hand off to the upstream
# entrypoint chain (tini -> docker/entrypoint.sh -> gosu drop -> gateway).
COPY --chown=root:root scripts/bootstrap.sh /opt/render-tools/bootstrap.sh
COPY --chown=root:root scripts/patch-config.py /opt/render-tools/patch-config.py
RUN chmod 0755 /opt/render-tools/bootstrap.sh /opt/render-tools/patch-config.py

# Pre-create the data dir so chown works cleanly on first boot. The mounted
# disk replaces this empty dir at runtime.
RUN install -d -o hermes -g hermes -m 0755 /opt/data

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/render-tools/bootstrap.sh"]
CMD ["gateway", "run"]

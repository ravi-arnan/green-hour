#!/bin/sh
# Green Hour entrypoint wrapper.
#
# Runs as root (PID-1 child of tini). On every boot it:
#   1. Ensures /opt/data exists and is owned by hermes:hermes.
#   2. Runs the config patcher as the hermes user. The patcher is
#      idempotent: it only INSERTs entries it owns; it never overwrites
#      user edits made from the dashboard.
#   3. Exec's the upstream entrypoint chain with the original args
#      (default CMD is `gateway run`).
#
# The upstream entrypoint also chowns /opt/data and drops to the hermes
# user via gosu for the gateway process. Our chown is redundant in the
# happy path but harmless, and it lets the patcher run on a fresh disk.

set -eu

DATA_DIR="${HERMES_HOME:-/opt/data}"
PATCHER="/opt/render-tools/patch-config.py"

mkdir -p "${DATA_DIR}"
if ! chown -R hermes:hermes "${DATA_DIR}" 2>/dev/null; then
  echo "[greenhour] warning: could not chown ${DATA_DIR}; continuing" >&2
fi

# The journal and its state live under the persistent disk.
if [ -n "${GREENHOUR_HOME:-}" ]; then
  mkdir -p "${GREENHOUR_HOME}"
  chown -R hermes:hermes "${GREENHOUR_HOME}" 2>/dev/null || true
fi

if [ -x "${PATCHER}" ]; then
  if ! gosu hermes "${PATCHER}" "${DATA_DIR}/config.yaml"; then
    echo "[greenhour] warning: config patch failed; continuing with unmodified config" >&2
  fi
else
  echo "[greenhour] warning: ${PATCHER} not found or not executable; skipping" >&2
fi

exec /opt/hermes/docker/entrypoint.sh "$@"

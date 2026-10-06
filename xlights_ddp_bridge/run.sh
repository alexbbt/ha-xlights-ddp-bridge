#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# Supervisor entrypoint: load options and exec the Python bridge.
set -euo pipefail

OPTIONS="/data/options.json"
if ! bashio::fs.file_exists "${OPTIONS}"; then
  bashio::exit.nok "Missing ${OPTIONS}"
fi

HZ="$(bashio::jq "${OPTIONS}" '.hz')"
DDP_PORT="$(bashio::jq "${OPTIONS}" '.ddp_port')"
DDP_BIND="$(bashio::jq "${OPTIONS}" '.ddp_bind')"
LIGHTS_JSON="$(bashio::jq "${OPTIONS}" '[.lights[].entity_id]')"
COUNT="$(bashio::jq "${OPTIONS}" '.lights | length')"

if [[ -z "${COUNT}" || "${COUNT}" -lt 1 ]]; then
  bashio::exit.nok "Configure at least one light entity_id under options.lights"
fi

if [[ -z "${SUPERVISOR_TOKEN:-}" ]]; then
  bashio::exit.nok "SUPERVISOR_TOKEN is missing; cannot reach Home Assistant API"
fi

export HZ DDP_PORT DDP_BIND LIGHTS_JSON
export HA_URL="http://supervisor/core/api"
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export INGRESS_PORT="${INGRESS_PORT:-8099}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="/opt/xlights_ddp_bridge"

bashio::log.info "Starting xLights DDP bridge (hz=${HZ}, port=${DDP_PORT}, lights=${COUNT}, ingress=${INGRESS_PORT})"

cd /opt/xlights_ddp_bridge
exec python3 -m bridge

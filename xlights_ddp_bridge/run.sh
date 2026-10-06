#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

OPTIONS="/data/options.json"
if ! bashio::fs.file_exists "${OPTIONS}"; then
  bashio::exit.nok "Missing ${OPTIONS}"
fi

HZ="$(bashio::jq "${OPTIONS}" '.hz')"
DDP_PORT="$(bashio::jq "${OPTIONS}" '.ddp_port')"
DDP_BIND="$(bashio::jq "${OPTIONS}" '.ddp_bind')"
LIGHTS_JSON="$(bashio::jq "${OPTIONS}" '[.lights[].entity_id]')"

export HZ DDP_PORT DDP_BIND LIGHTS_JSON
export HA_URL="http://supervisor/core/api"
export HA_TOKEN="${SUPERVISOR_TOKEN:?SUPERVISOR_TOKEN is required}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="/opt/xlights_ddp_bridge"

COUNT="$(bashio::jq "${OPTIONS}" '.lights | length')"
bashio::log.info "Starting xLights DDP bridge (hz=${HZ}, port=${DDP_PORT}, lights=${COUNT})"

cd /opt/xlights_ddp_bridge
exec python3 -m bridge

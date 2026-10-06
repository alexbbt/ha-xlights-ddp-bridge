ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

WORKDIR /opt/xlights_ddp_bridge

# config.yaml is required at runtime so the Web UI can report / cache-bust by version.
# (Supervisor reads it from the repo; the container did not previously include it.)
COPY config.yaml /opt/xlights_ddp_bridge/config.yaml
COPY bridge /opt/xlights_ddp_bridge/bridge
COPY run.sh /run.sh

RUN chmod a+x /run.sh

ARG BUILD_VERSION=0.2.10
ENV ADDON_VERSION=${BUILD_VERSION}

LABEL \
  io.hass.name="xLights DDP Entity Bridge" \
  io.hass.description="DDP from xLights/FPP to Home Assistant light entities" \
  io.hass.type="addon" \
  io.hass.version="0.2.10" \
  io.hass.arch="aarch64|amd64"

CMD ["/run.sh"]

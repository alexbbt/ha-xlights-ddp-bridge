ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

WORKDIR /opt/xlights_ddp_bridge

COPY bridge /opt/xlights_ddp_bridge/bridge
COPY run.sh /run.sh

RUN chmod a+x /run.sh

LABEL \
  io.hass.name="xLights DDP Entity Bridge" \
  io.hass.description="DDP from xLights/FPP to Home Assistant light entities" \
  io.hass.type="addon" \
  io.hass.version="0.2.4" \
  io.hass.arch="aarch64|amd64"

CMD ["/run.sh"]

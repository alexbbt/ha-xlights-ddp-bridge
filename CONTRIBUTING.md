# Contributing

Thanks for improving the xLights DDP Entity Bridge. Small, focused changes are easiest to review.

## Development setup

You need Python 3.11+ (3.12/3.13 fine). No Home Assistant install is required for unit tests.

```bash
cd xlights_ddp_bridge
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Optional local bridge (talks to a real HA instance):

```bash
export HA_URL=http://HOMEASSISTANT_IP:8123
export HA_TOKEN=YOUR_LONG_LIVED_TOKEN
export LIGHTS_JSON='["light.example_pixel_1"]'
PYTHONPATH=. python3 -m bridge
```

Send a one-shot DDP packet:

```bash
PYTHONPATH=. python3 -m tests.smoke_ddp --host 127.0.0.1
```

## Releases

Merges/pushes to `main` that pass CI trigger `.github/workflows/release.yml`, which bumps `xlights_ddp_bridge/config.yaml` (and the Dockerfile label), writes `CHANGELOG.md`, tags `vX.Y.Z`, and creates a GitHub Release.

- Default: patch bump
- `[minor]` or `feat:` in the commit message → minor
- `[major]` or `BREAKING CHANGE` → major
- `[skip release]` → no release (used by the bot’s own bump commits)

Changelog notes are built from commits since the previous `v*` tag, grouped into **Features** (`feat:` / `[minor]`), **Fixes** (`fix:`), **Documentation** (`docs:`), and **Changes** (everything else). Prefer conventional commit prefixes so release notes stay readable.

## Pull requests

1. Keep behavior the same unless the PR is intentionally changing it
2. Prefer docs/CI/tests alongside code changes
3. Do not commit tokens, `.ha_token`, or personal host IPs as required defaults
4. Run unit tests before opening a PR

## Scope notes

- This repo is a Supervisor add-on + a small Python bridge
- Prefer high-level DDP handling and HA service calls over protocol expansions unless discussed in an issue
- Add-on packaging files live under `xlights_ddp_bridge/` (`config.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`)

## Reporting bugs

Use a [bug report](https://github.com/alexbbt/ha-xlights-ddp-bridge/issues/new/choose) and include add-on version, `hz`/`ddp_port`, light count, and relevant logs (redact tokens).

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

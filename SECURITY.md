# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Email **alexander@bell-towne.com** with:

- A short description of the issue
- Steps to reproduce (if known)
- Impact assessment (e.g. token exposure, unauthenticated control of lights)

You should receive an acknowledgement within a few days. After a fix is available (or we agree on disclosure), we can credit you if you want.

## Scope notes

- The add-on listens for unauthenticated DDP on a configured UDP port (by design, matching xLights/FPP). Restrict that port to trusted show networks.
- Long-lived Home Assistant tokens used for local development must never be committed. Prefer Supervisor API access when running as an add-on.

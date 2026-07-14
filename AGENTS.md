# AutoGematria Agent Guide

## Start here

- Read `docs/production.md` before any Docker, deployment, data-path, or host work.
- The checkout at `/home/ubuntu/gematria` is source code, not the live process.
- Production is an experimental but user-facing service on this machine. A commit or push does
  not build, deploy, restart, or otherwise change it.

## Production safety

- Inspect first. Do not rebuild or retag `autogematria:latest`, edit the deployment under
  `/home/ubuntu/server-setup-v2`, run Compose, or restart containers without explicit production
  authorization.
- Never use `webdeploy down gematria` for an upgrade. It removes the deployment directory and
  also changes Cloudflare DNS, tunnel ingress, and Access state.
- Do not print secrets from `.env` files or `/etc/cloudflared`. Do not inspect or copy job payloads,
  report results, or raw run logs unless the user explicitly requests that data.
- Preserve unrelated changes in both Git worktrees. The server-setup checkout may already be
  dirty for other experiments.
- Before an authorized release, create an immutable rollback image tag, back up SQLite state,
  validate the external corpus, and use the single-replica Compose layout in
  `docs/production.md`.

## Development checks

```bash
source .venv/bin/activate
ruff check .
pytest -q
ag-data-check --allow-legacy
```

The checked-in database is currently a valid legacy-schema corpus; a newly prepared release
corpus should pass `ag-data-check` without `--allow-legacy`.

When production topology or release steps change, update `docs/production.md` in the same commit.

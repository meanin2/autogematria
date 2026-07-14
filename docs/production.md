# Production Operations

This document records the production topology observed on **2026-07-14 UTC**. The service is
experimental, but it is live and user-facing. Re-check the machine before acting because this is
a status snapshot, not a substitute for runtime inspection.

## The most important facts

- There is no CI/CD path from GitHub to this host.
- `git commit` and `git push` do not change the running application.
- The live application runs from a locally built Docker image, not from a bind-mounted checkout.
- The current production Compose file is incompatible with the image built from current `main`.
- Do not deploy by rebuilding the mutable `autogematria:latest` tag in place.
- Do not use `webdeploy down gematria` for an upgrade; it tears down DNS and tunnel state as well
  as the containers.

No live container, live image tag, deployment file, database, service, DNS record, or tunnel was
changed while producing this document. Disposable candidate-image checks were kept off-route.

## Request path

```text
Browser / API client
        |
        v
Cloudflare DNS + named tunnel
        |
        v
cloudflared.service (server-setup-v2, enabled on the host)
        |
        v
127.0.0.1:18080
        |
        v
experiments-caddy (caddy-docker-proxy)
        |
        v
Docker network: proxy
        |
        v
app-gematria-app-{1..4}:8080
```

The public URL is <https://gematria.jewishaiart.com>. A cache-busted public request to `/health`
returned HTTP 200 through Cloudflare and Caddy during the observation. Cloudflare Access is off.

Relevant host locations:

| Purpose | Location |
| --- | --- |
| Application source | `/home/ubuntu/gematria` |
| Edge/deployment checkout | `/home/ubuntu/server-setup-v2` |
| Gematria Compose state | `/home/ubuntu/server-setup-v2/deployments/gematria` |
| Shared writable app state | `/home/ubuntu/server-setup-v2/deployments/gematria/var` |
| Caddy listener | `127.0.0.1:18080` |
| Cloudflared credential file | `/etc/cloudflared/server-setup-v2.token` (never print or commit) |

`server-setup-v2/scripts/deploy.sh` is a generic provisioning/teardown tool. It has no app-update
command. Its `app` action regenerates deployment files and touches Cloudflare state, so an existing
Gematria release should be updated with an explicitly reviewed Compose change, not by rerunning
`webdeploy app`.

## Observed running release

| Item | Observed value |
| --- | --- |
| Compose project | `app-gematria` |
| Containers | `app-gematria-app-1` through `app-gematria-app-4` |
| Image tag | `autogematria:latest` |
| Image ID | `sha256:579cb2212d448608c1f6b47301fe7ae920dce7b9e79703963d41f92548792eb7` |
| Image created | 2026-04-15 19:25 UTC |
| Image size | 592,712,254 bytes |
| Source match | Key API/job files exactly match Git commit `a55b025` |
| Container start | 2026-07-12 20:28 UTC |
| Restart policy | `unless-stopped` |
| Per-container limit | 2 GiB |
| Runtime user | root (the old image has no `USER`) |
| Docker health check | none |
| `/health` | HTTP 200, process-only liveness |
| `/ready` | HTTP 404 in the old release |
| API authentication | none (`AUTOGEMATRIA_API_TOKEN` is unset) |

One idle resource snapshot showed 143-198 MiB per replica, about 665 MiB total. The application
ports are not published on the host; Caddy reaches port 8080 over the `proxy` Docker network.

The Git checkout was at `56dda09` when observed. Its image candidate
`autogematria:codex-final` existed locally but was not running. Pushing those commits did not deploy
them.

## Corpus and writable state

The old image embeds `/app/data`:

- `/app/data/autogematria.db` is 194,379,776 bytes.
- Its SHA-256 is `9263a62383f3bceac5d06892e9fa6dc48a3100630a865dc398f05833918a89a8`.
- That hash exactly matched `/home/ubuntu/gematria/data/autogematria.db` when observed.
- The embedded image also contains the 39 corpus JSON files and an old `run_log.jsonl`.

All four replicas mount this one host directory read-write:

```text
/home/ubuntu/server-setup-v2/deployments/gematria/var -> /app/var
```

The live April code intentionally uses SQLite WAL plus `BEGIN IMMEDIATE` to claim queued jobs
atomically across four worker threads. Completed and failed jobs are deleted after one hour.
However, it has no abandoned-job recovery.

At observation time, `jobs.db` contained exactly one row: a `full_report` job stuck in `running`
since 2026-04-15 14:11 UTC. Its worker hostname belongs to an old container, not any current
replica. The query payload and result were deliberately not inspected. Current `main` migrates the
table with an `attempts` column and would requeue this old job on first startup, so an operator must
decide whether to retry or mark it failed after taking a backup.

The old run logger writes input text into `/app/data/run_log.jsonl`. Because `/app/data` is an image
layer in production, each replica has a separate, ephemeral log that disappears with its container.
Treat both that log and `jobs.db` as potentially containing user-submitted names; never dump them
into tickets, commits, chat, or agent memory.

## Why current `main` cannot use the existing Compose file

The existing deployment sets:

```text
AUTOGEMATRIA_DATA_DIR=/app/data
AUTOGEMATRIA_VAR_DIR=/app/var
replicas=4
only /app/var is mounted
```

The new image instead:

- excludes `data/` from the build context;
- expects the corpus at `/data` and state at `/var/lib/autogematria`;
- runs as the non-root `autogematria` user;
- declares `/data` and `/var/lib/autogematria` as volumes;
- calls `/ready` from its Docker health check; and
- intentionally supports one API replica because startup recovery assumes any existing running
  job belonged to the one previous worker.

If the existing Compose file merely points `IMAGE` at the new build, `/app/data` will be absent.
The API will fail startup validation, `/ready` will fail, and the container will restart. Leaving
four replicas would also make the new startup-recovery contract unsafe during restarts.

## Proposed production Compose shape

Keep the existing Caddy labels, network, restart policy, and memory limit, but change the
application-specific portion to this shape:

```yaml
services:
  app:
    image: ${IMAGE}
    restart: unless-stopped
    environment:
      AUTOGEMATRIA_DATA_DIR: /data
      AUTOGEMATRIA_VAR_DIR: /var/lib/autogematria
    volumes:
      - /home/ubuntu/server-setup-v2/deployments/gematria/data:/data:ro
      - /home/ubuntu/server-setup-v2/deployments/gematria/var:/var/lib/autogematria
    deploy:
      replicas: 1
      resources:
        limits:
          memory: 2G
```

Do not apply this fragment blindly: merge it into the existing file so its `proxy` network and
Caddy/Homepage labels remain intact.

The dedicated deployment data directory is preferable to mounting the Git checkout into
production. Seed its corpus JSON from the checkout, then run `ag-prepare-data --skip-download`
with `AUTOGEMATRIA_DATA_DIR` pointed at that directory. A release corpus should pass
`ag-data-check` without `--allow-legacy`. The checked-in database is valid for runtime use but has
legacy SQLite `user_version=0`, so strict release validation correctly rejects it until rebuilt.

## Manual release runbook

This is a runbook, not evidence that a deployment happened. Every state-changing step requires
explicit production approval and a quiet window.

1. **Record current state.** Capture `git rev-parse HEAD`, `docker ps`, the current image ID,
   `docker compose ... config`, `/health`, `/ready`, and aggregate job counts. Never capture job
   payloads or raw environment values.
2. **Create rollback assets.** Tag the exact running image ID with an immutable rollback tag. Save
   copies of the current `compose.yml` and deployment `.env`. Back up `jobs.db` with SQLite's online
   backup API so the WAL is represented consistently.
3. **Build immutably.** Build a commit-specific tag such as `autogematria:56dda09`. Do not replace
   `autogematria:latest` until the candidate has passed smoke tests.
4. **Prepare external data.** Populate
   `/home/ubuntu/server-setup-v2/deployments/gematria/data`, run the atomic preparation command,
   run strict `ag-data-check`, and make the directory readable by the image user. Determine the
   image UID/GID rather than guessing it; make the state directory writable only by that identity.
5. **Resolve the abandoned job.** After the backup, explicitly choose whether the April job should
   be retried by the new worker or marked failed. Do not inspect its payload to make this decision.
6. **Smoke-test off-route.** Start the commit-specific image against the prepared data and a fresh
   temporary state directory. Verify `/health`, `/ready`, the UI, and a bounded sample report. Stop
   and remove only that temporary container afterward.
7. **Review the production diff.** Change the two mount paths and reduce replicas to one while
   preserving every existing Caddy label and the external `proxy` network. Set `IMAGE` to the
   immutable candidate tag. Validate with `docker compose config`.
8. **Deploy manually.** From the Gematria deployment directory, use the same project name:

   ```bash
   docker compose --env-file .env -f compose.yml -p app-gematria up -d --force-recreate
   ```

9. **Verify before declaring success.** Require one healthy container, Docker health `healthy`,
   local Caddy `/ready` HTTP 200 using the Gematria Host header, public `/ready` HTTP 200, a working
   UI, a completed bounded report, and stable resource usage/logs.
10. **Preserve rollback until the release has soaked.** Do not remove the old image tag or backups
    immediately.

## Rollback

Restore the saved Compose file and deployment `.env`, point `IMAGE` at the immutable April rollback
tag, and run the same Compose `up -d --force-recreate` command. Then verify local and public
`/health`. The April image has no `/ready`, so HTTP 404 there is expected after rollback.

Do not run `webdeploy down gematria`: it removes the deployment directory and invokes Cloudflare
DNS/tunnel/Access teardown.

## Safe inspection commands

These commands are read-only when used as shown:

```bash
docker ps --filter name=app-gematria
docker inspect app-gematria-app-1 \
  --format 'image={{.Image}} started={{.State.StartedAt}} status={{.State.Status}}'
docker logs --tail 50 app-gematria-app-1
docker stats --no-stream app-gematria-app-1

cd /home/ubuntu/server-setup-v2/deployments/gematria
docker compose --env-file .env -f compose.yml -p app-gematria ps
docker compose --env-file .env -f compose.yml -p app-gematria config

curl -H 'Host: gematria.jewishaiart.com' http://127.0.0.1:18080/health
curl https://gematria.jewishaiart.com/health
```

Redact variables containing `TOKEN`, `KEY`, `SECRET`, or `PASSWORD` before sharing container
metadata. Do not read `/home/ubuntu/server-setup-v2/.env` or the cloudflared token into terminal
output. Query only schema and aggregate status counts from `jobs.db` unless the user explicitly
authorizes access to submitted content.

## Other host context

- The active OpenClaw workspace is `/home/ubuntu/clawd`.
- Global AutoMem runs on port 8901 and the private instance on 8902; both are Docker services.
- Neither AutoMem instance had a useful Gematria-specific deployment record before this audit.
- `/home/ubuntu/clawd/MEMORY.md` was already over 11 KiB, so detailed project operations belong in
  this repository document rather than in always-loaded global memory.
- The `server-setup-v2` Git worktree already had unrelated changes when observed. Preserve them.

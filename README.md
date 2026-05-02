# SEU DOMjudge Public Deployment Snapshot

This repository stores a public, sanitized snapshot of the SEU DOMjudge
deployment configuration.

Production URL:

```text
https://domjudge.seucpc.com/
```

The live service is currently deployed with Docker on `Server-SEUCPC`. The
public entrypoint is nginx, which terminates TLS and proxies to the DOMjudge
domserver container on localhost port `12345`. The current DOMjudge version is
`9.0.0`.

## What Is Included

- Sanitized nginx virtual host configuration.
- Example Docker Compose and environment templates.
- Deployment notes that describe paths, containers, ports, and DNS.
- Rollboard helper code, nginx snippets, and systemd templates for the
  protected XCPCIO resolver page.
- Maintenance instructions for future agents.

## What Is Not Included

This public repository intentionally excludes live data and secrets:

- MariaDB data directories and SQL dumps.
- DOMjudge user, team, contest, submission, or judging data.
- Admin passwords, judgehost passwords, database passwords, API tokens, and
  generated `*.secret` files.
- TLS private keys, ACME account data, and DNS provider credentials.
- Runtime logs, caches, sessions, and judging work directories.

Use the files here as a reproducible reference for the deployment shape, not as
a complete copy of the live server.

## Current Service Shape

```text
Client
  -> https://domjudge.seucpc.com/
  -> nginx :443
  -> http://127.0.0.1:12345/
  -> Docker container dj-domserver
  -> Docker network dj-net
  -> Docker container dj-mariadb
```

Judgehost:

```text
dj-judgehost-0 -> http://dj-domserver/api/v4
```

Rollboard:

```text
Admin browser
  -> https://domjudge.seucpc.com/rollboard/admin/
  -> nginx Basic Auth
  -> http://127.0.0.1:18090/api/
  -> rollboard-admin.service
  -> DOMjudge API http://127.0.0.1:12345/api/v4
  -> generated XCPCIO data under /mnt/domjudge/rollboard/www/data/
```

## Safe Restore Outline

1. Provision a Linux host with Docker, nginx, and certbot.
2. Create fresh secrets locally; do not reuse values from this repository.
3. Start MariaDB, domserver, and judgehost using the templates under `deploy/`.
4. Configure nginx using `nginx/domjudge.seucpc.com.conf`.
5. Issue a new certificate for `domjudge.seucpc.com` using DNS-01 validation.

Live database backups, if ever needed, must be transferred through a private
channel and must not be committed to this public repository.

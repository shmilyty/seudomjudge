# DOMjudge Maintenance Instructions

This workspace is used to maintain the SEU DOMjudge deployment.

## Public Backup Repository

All future website changes that should be preserved must be synchronized to:

```text
https://github.com/shmilyty/seudomjudge.git
```

Treat that repository as public. Only commit sanitized configuration, patches,
documentation, scripts, and source changes that are safe to disclose.

## Sensitive Data Rules

Never commit, push, paste, or archive secrets or live private data. This includes:

- DOMjudge user/team/submission databases or database dumps.
- Passwords, initial admin passwords, judgehost passwords, API tokens, cookies, or sessions.
- Files under live `secrets` directories.
- MariaDB data directories.
- TLS private keys, certificates with private material, ACME account data, or DNS provider credentials.
- `.env`, `.secret`, `.pem`, `.key`, `.crt`, `.csr`, `.p12`, `.pfx`, `.my.cnf`, and similar credential files.
- Logs that may contain tokens, passwords, IP addresses, submissions, or user data.
- Contest submissions, private problem data, hidden tests, and judging artifacts unless explicitly sanitized.

If a file might contain private data, do not add it. Create a sanitized example file instead.

## Live Deployment Boundaries

The live server may contain deployment data under paths such as:

```text
/mnt/domjudge/domjudge-live/
/etc/nginx/sites-available/domjudge.seucpc.com
/etc/letsencrypt/
```

Do not mirror the live deployment directory wholesale. In particular, never copy these into the
public backup repository:

```text
/mnt/domjudge/domjudge-live/mariadb/
/mnt/domjudge/domjudge-live/secrets/
/mnt/domjudge/domjudge-live/domserver/etc/*.secret
/etc/letsencrypt/
```

For nginx or deployment configuration, commit a sanitized copy or a patch that preserves hostnames
and routing but removes credential paths, tokens, and private values when necessary.

## Backup Workflow

When making a website change:

1. Identify the minimal files or patches that represent the change.
2. Copy only sanitized, non-sensitive artifacts into the public backup working tree.
3. Review the diff before staging:

```bash
git status --short
git diff
```

4. Scan staged content for likely secrets before committing:

```bash
git diff --cached
git diff --cached --name-only
```

5. If any staged file contains live data or credentials, unstage it and replace it with a sanitized example.
6. Commit with a clear message describing the website change.
7. Push to `https://github.com/shmilyty/seudomjudge.git`.

## Quick Secret Scan

Before pushing, run a conservative text search from the repository root:

```bash
rg -n --hidden --glob '!.git' --glob '!node_modules' --glob '!vendor' \
  'password|passwd|secret|token|api[_-]?key|private[_-]?key|BEGIN .*PRIVATE KEY|MYSQL_ROOT_PASSWORD|JUDGEDAEMON_PASSWORD|initial_admin_password'
```

Investigate every hit. Some documentation hits may be intentional, but real values must never be
published.

## Commit Rule

If you are not certain a file is safe for a public repository, do not commit it. Ask for review or
commit a redacted template instead.

# DOMjudge 9.0.0 Upgrade Notes

Upgrade date: 2026-05-02

## Summary

The live deployment was upgraded from DOMjudge 7.3.0 to DOMjudge 9.0.0 using the
official DOMjudge container images:

```text
domjudge/domserver:9.0.0
domjudge/judgehost:9.0.0
```

## Safety Steps

- A private SQL dump was created under `/mnt/domjudge/backups/` on the live host.
- The previous 7.3.0 domserver tree was kept under `/mnt/domjudge/domjudge-live/`
  for rollback.
- The public repository only records sanitized source, template, and deployment
  metadata changes. It does not include SQL dumps, secrets, logs, TLS material,
  or private contest data.

## Live Adjustments

- The 9.0.0 DOMserver tree was extracted from the container image to the
  non-root deployment partition.
- Existing DOMjudge secret files were copied into the new tree on the live host.
- The scoreboard enhancement was reapplied to the 9.0.0 Twig templates.
- Judgehost writable directories were adjusted for the 9.0.0 container user.

## Verification

- Public scoreboard returns HTTP 200 over HTTPS.
- Rendered HTML reports `DOMjudge version 9.0.0`.
- `dj-domserver` runs `domjudge/domserver:9.0.0`.
- `dj-judgehost-0` runs `domjudge/judgehost:9.0.0` and connects to
  `http://dj-domserver/api/v4`.
- Twig syntax checks pass for the modified scoreboard templates.

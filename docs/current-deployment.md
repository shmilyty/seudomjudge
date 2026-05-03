# Current Deployment Notes

Snapshot date: 2026-05-03

DOMjudge version: `9.0.0`

## Public Entry

```text
https://domjudge.seucpc.com/
```

DNS:

```text
domjudge.seucpc.com CNAME gate.m5d431.cn
gate.m5d431.cn A 10.210.55.111
```

nginx listens on ports `80` and `443`.

- Port `80` redirects to HTTPS.
- Port `443` terminates TLS and proxies to `http://127.0.0.1:12345`.

## Live Server Paths

The live deployment stores persistent data outside the root filesystem:

```text
/mnt/domjudge/domjudge-live/
```

Important live directories:

```text
/mnt/domjudge/domjudge-live/domserver/
/mnt/domjudge/domjudge-live/judgehost/
/mnt/domjudge/domjudge-live/mariadb/     # private, excluded
/mnt/domjudge/domjudge-live/secrets/     # private, excluded
```

Do not copy `mariadb/`, `secrets/`, `*.secret`, or `.env.local` files into this
repository.

The previous DOMjudge 7.3.0 domserver tree was kept on the live host for
rollback after the 2026-05-02 upgrade.

## Containers

```text
dj-mariadb
dj-domserver
dj-judgehost-0
dj-judgehost-1
dj-judgehost-2
dj-judgehost-3
```

Current DOMjudge images:

```text
domjudge/domserver:9.0.0
domjudge/judgehost:9.0.0
```

Docker network:

```text
dj-net
```

The domserver publishes:

```text
127.0.0.1:12345 -> container port 80
```

The deployment runs four enabled judgehosts. This keeps judging parallelism
well below the server's 16 hardware threads while removing the original
single-judgehost bottleneck.

## Printing

DOMjudge's team and jury printing links are enabled through the `print_command`
configuration value. The live command calls:

```text
/opt/domjudge/domserver/bin/seu-print-spool [file] [original] [language] [username] [teamname] [teamid] [location] 2>&1
```

The script stores print requests under:

```text
/mnt/domjudge/domjudge-live/domserver/var/print-spool/pending/
```

Each request contains `metadata.txt`, `source`, and `print.txt`. This is a safe
server-side print queue; it does not embed any printer credentials. To send jobs
to paper automatically, connect the queue to a chosen host CUPS printer.

## Certificates

TLS certificates are issued by Let's Encrypt using DNS-01 validation. The live
private key and ACME state are stored under `/etc/letsencrypt/` and must never
be committed.

For a new host, issue fresh certificates rather than copying the live ones.

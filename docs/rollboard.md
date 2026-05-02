# Rollboard Deployment

The rollboard feature deploys XCPCIO Board as a static page under:

```text
https://domjudge.seucpc.com/rollboard/
```

The admin helper page is:

```text
https://domjudge.seucpc.com/rollboard/admin/
```

DOMjudge admins can open that helper from the jury navbar. The helper lists
DOMjudge contests, generates XCPCIO `config.json`, `team.json`, and `run.json`
files for the selected contest, then opens the XCPCIO resolver view.

## Live Layout

```text
/mnt/domjudge/rollboard/
  rollboard/             # sanitized Python package and admin HTML
  www/                   # XCPCIO static dist and generated JSON data
  www/data/<contest-id>/ # generated config.json, team.json, run.json
  secrets/               # private htpasswd and local environment files
```

The `secrets/` directory is intentionally excluded from the public repository.
It contains the Basic Auth password file and local environment file. The
environment file points at DOMjudge's local API and a password file already
present on the live host; it must not contain a pasted password value.

## Data Flow

1. The admin page calls the localhost-only rollboard admin service through
   `/rollboard/api/`.
2. The service runs `rollboard/tools/rollboard_build.py`.
3. The builder reads DOMjudge CLICS API data for the selected contest.
4. The builder writes XCPCIO data files under `/rollboard/data/<contest-id>/`.
5. The admin page opens:

```text
/rollboard/?component=resolver&data-source=/rollboard/data/<contest-id>
```

## Safety

- `/rollboard/`, `/rollboard/admin/`, `/rollboard/data/`, and `/rollboard/api/`
  are protected by nginx Basic Auth.
- The admin API binds to `127.0.0.1` only.
- Live contest data generated under `www/data/` is not committed.
- API credentials, htpasswd files, passwords, and generated data are not
  committed.

## Manual Commands

Generate data for a contest directly on the server:

```bash
cd /mnt/domjudge/rollboard
/usr/bin/python3 -m rollboard.tools.rollboard_build --contest-id demo
```

Restart the admin service:

```bash
sudo systemctl restart rollboard-admin.service
```

Check the service:

```bash
systemctl status rollboard-admin.service --no-pager
curl http://127.0.0.1:18090/api/health
```

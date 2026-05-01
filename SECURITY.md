# Security Policy

This repository is public. Do not commit live secrets or private contest data.

Never publish:

- Database files or dumps.
- Passwords, API tokens, cookies, sessions, or generated DOMjudge secret files.
- TLS private keys, DNS credentials, ACME account files, or cloud provider keys.
- Hidden tests, private statements, submissions, judging logs, or user data.

Before pushing changes, inspect the staged diff and search for likely secret
markers:

```bash
git diff --cached
rg -n --hidden --glob '!.git' \
  'password|passwd|secret|token|api[_-]?key|private[_-]?key|BEGIN .*PRIVATE KEY|MYSQL_ROOT_PASSWORD|JUDGEDAEMON_PASSWORD|initial_admin_password'
```

If a file may contain private data, do not commit it. Commit a redacted template
instead.

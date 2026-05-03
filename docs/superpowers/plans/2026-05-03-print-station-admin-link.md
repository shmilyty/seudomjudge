# Print Station Admin Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Print Station discoverable from the DOMjudge admin page and show onsite printing cautions on the Print Station page.

**Architecture:** Add a safe external link to the DOMjudge jury/admin dashboard template and add an operator notes panel to the existing static Print Station page. Keep the changes in the public backup repository as sanitized source files only.

**Tech Stack:** DOMjudge Twig templates, vanilla HTML/CSS/JavaScript, Python `unittest`, nginx-served static assets.

---

### Task 1: Static Page Safety Test

**Files:**
- Modify: `rollboard/tests/test_print_station.py`
- Modify: `rollboard/www/print-station/index.html`

- [ ] **Step 1: Write failing tests**

```python
def test_print_station_page_contains_operator_notes(self):
    html = (Path(__file__).parents[1] / "www" / "print-station" / "index.html").read_text(encoding="utf-8")
    self.assertIn("比赛时只在一台现场笔记本打开本页面", html)
    self.assertIn("暂停期间选手打印请求仍会排队", html)
    self.assertIn("完成表示已交给本机打印系统", html)
```

- [ ] **Step 2: Verify test fails**

Run:

```bash
python -m unittest rollboard.tests.test_print_station -v
```

Expected: FAIL because the notes are not present yet.

- [ ] **Step 3: Add operator notes panel**

Add a compact notice panel near the top of `rollboard/www/print-station/index.html`
with the exact safety notes from the test.

- [ ] **Step 4: Verify test passes**

Run:

```bash
python -m unittest rollboard.tests.test_print_station -v
```

Expected: PASS.

### Task 2: DOMjudge Admin Entry

**Files:**
- Modify live: `/mnt/domjudge/domjudge-live/domserver/webapp/templates/jury/index.html.twig`
- Copy sanitized public backup: `webapp/templates/jury/index.html.twig`

- [ ] **Step 1: Inspect the live DOMjudge jury dashboard**

Run:

```bash
ssh miao 'sed -n "1,220p" /mnt/domjudge/domjudge-live/domserver/webapp/templates/jury/index.html.twig'
```

- [ ] **Step 2: Add a Print Station entry**

Add a small admin dashboard link to `/print-station/` near the existing contest
operation links, using DOMjudge's existing button/list style.

- [ ] **Step 3: Clear DOMjudge cache and verify**

Run:

```bash
ssh miao 'docker exec dj-domserver bash -lc "cd /opt/domjudge/domserver && bin/console cache:clear --env=prod --no-debug"'
curl -k -I https://domjudge.seucpc.com/print-station/
```

Expected: Print Station stays protected and the DOMjudge cache clear succeeds.

### Task 3: Public Backup

**Files:**
- Modify: public backup repository under `/mnt/domjudge/seudomjudge-public`

- [ ] **Step 1: Sync sanitized files**

Copy the modified static page, test, plan, and DOMjudge template into the public
backup repository. Do not copy live queue files, credentials, logs, or generated
contest data.

- [ ] **Step 2: Run tests and secret scan**

```bash
cd /mnt/domjudge/seudomjudge-public
python3 -m unittest rollboard.tests.test_print_station -v
git diff --cached --check
git diff --cached -U0 | grep -n -E '^\\+.*(password|passwd|secret|token|api[_-]?key|private[_-]?key|BEGIN .*PRIVATE KEY|MYSQL_ROOT_PASSWORD|JUDGEDAEMON_PASSWORD|initial_admin_password)' || true
```

- [ ] **Step 3: Commit and push**

```bash
git commit -m "Expose print station in admin UI"
git push
```

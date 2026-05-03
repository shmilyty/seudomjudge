# Print Station Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a protected Print Station page that lets an onsite admin laptop automatically process DOMjudge print jobs while supporting pause, retry, and recovery.

**Architecture:** Extend the existing rollboard admin service with a small print queue module and JSON API. Serve a static `/print-station/` frontend through nginx Basic Auth, with queue files kept only on the live server.

**Tech Stack:** Python `http.server`, filesystem-backed queue directories, vanilla HTML/CSS/JavaScript, nginx reverse proxy, Python `unittest`.

---

### Task 1: Queue State Model

**Files:**
- Create: `rollboard/service/print_station.py`
- Test: `rollboard/tests/test_print_station.py`

- [ ] **Step 1: Write failing tests**

```python
def test_claim_moves_oldest_pending_job_to_printing(self):
    write_job(self.spool / "pending" / "job-1", "older")
    write_job(self.spool / "pending" / "job-2", "newer")

    store = PrintQueueStore(self.spool)
    job = store.claim_next("station-a")

    self.assertEqual(job["id"], "job-1")
    self.assertFalse((self.spool / "pending" / "job-1").exists())
    self.assertTrue((self.spool / "printing" / "job-1").exists())

def test_pause_blocks_claiming_but_keeps_pending_jobs(self):
    write_job(self.spool / "pending" / "job-1", "queued")

    store = PrintQueueStore(self.spool)
    store.set_paused(True)

    self.assertIsNone(store.claim_next("station-a"))
    self.assertTrue((self.spool / "pending" / "job-1").exists())
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m unittest rollboard.tests.test_print_station -v
```

Expected: FAIL because `rollboard.service.print_station` does not exist.

- [ ] **Step 3: Implement minimal queue store**

Create `PrintQueueStore` with directory initialization, pause control, job listing,
claim, done, fail, and requeue methods. Use `Path.rename()` for atomic same-filesystem
state transitions and strict job ID validation.

- [ ] **Step 4: Verify tests pass**

Run:

```bash
python -m unittest rollboard.tests.test_print_station -v
```

Expected: PASS.

### Task 2: HTTP API

**Files:**
- Modify: `rollboard/service/rollboard_admin_server.py`
- Test: `rollboard/tests/test_rollboard_admin_server.py`

- [ ] **Step 1: Write failing API tests**

Add tests that instantiate `Settings(print_spool_root=tmp_path)`, then call the
new store-backed helpers through the handler-facing functions:

```python
def test_print_status_reports_pause_and_counts(self):
    settings = rollboard_admin_server.Settings(print_spool_root=self.spool)
    write_job(self.spool / "pending" / "job-1", "queued")

    status = rollboard_admin_server.print_status(settings)

    self.assertFalse(status["paused"])
    self.assertEqual(status["counts"]["pending"], 1)

def test_print_claim_respects_station_lock(self):
    settings = rollboard_admin_server.Settings(print_spool_root=self.spool)
    write_job(self.spool / "pending" / "job-1", "queued")

    claimed = rollboard_admin_server.print_claim(settings, "station-a")

    self.assertEqual(claimed["job"]["id"], "job-1")
```

- [ ] **Step 2: Verify API tests fail**

Run:

```bash
python -m unittest rollboard.tests.test_rollboard_admin_server -v
```

Expected: FAIL because the print helper functions do not exist.

- [ ] **Step 3: Add API routes**

Add routes below, normalized for both `/print-station/api/...` and
`/rollboard/api/print-station/...` if needed:

```text
GET  /print-station/api/status
GET  /print-station/api/jobs
POST /print-station/api/pause
POST /print-station/api/resume
POST /print-station/api/jobs/claim
GET  /print-station/api/jobs/{id}/print
POST /print-station/api/jobs/{id}/done
POST /print-station/api/jobs/{id}/fail
POST /print-station/api/jobs/{id}/requeue
```

- [ ] **Step 4: Verify API tests pass**

Run:

```bash
python -m unittest rollboard.tests.test_rollboard_admin_server -v
```

Expected: PASS.

### Task 3: Browser UI

**Files:**
- Create: `rollboard/www/print-station/index.html`
- Modify: `rollboard/nginx/rollboard.locations.conf`

- [ ] **Step 1: Create the static UI**

Build a dense operator console with:

- Auto/manual mode toggle.
- Pause/resume button.
- Current job panel.
- Queue counts.
- Pending, printing, failed, and recent done sections.
- Reprint/requeue/mark done/mark failed controls.

- [ ] **Step 2: Wire auto print loop**

The browser loop should:

```text
poll status -> stop if paused -> claim next -> open printable content ->
window.print() -> mark done after afterprint or timeout -> continue
```

- [ ] **Step 3: Add nginx route**

Expose `/print-station/` with the same Basic Auth file as rollboard. Proxy
`/print-station/api/` to the rollboard admin service.

### Task 4: Deployment And Verification

**Files:**
- Modify live files under `/mnt/domjudge/rollboard`
- Modify nginx site include using sanitized public config
- Modify docs if operator instructions need clarification

- [ ] **Step 1: Run unit tests locally**

```bash
python -m unittest rollboard.tests.test_print_station rollboard.tests.test_rollboard_admin_server -v
```

- [ ] **Step 2: Sync sanitized code to server**

Copy only source, tests, static UI, nginx snippets, and docs. Do not copy live
queue content, credentials, or generated contest data.

- [ ] **Step 3: Restart services**

```bash
sudo systemctl restart rollboard-admin
sudo nginx -t
sudo systemctl reload nginx
```

- [ ] **Step 4: Verify live API**

```bash
curl -fsS http://127.0.0.1:18090/print-station/api/status
curl -I https://domjudge.seucpc.com/print-station/
```

- [ ] **Step 5: Commit and push public backup**

Run the secret scan, commit with a clear message, and push to
`https://github.com/shmilyty/seudomjudge.git`.

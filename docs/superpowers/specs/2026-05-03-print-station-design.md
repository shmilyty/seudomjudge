# Print Station Design

Date: 2026-05-03

## Purpose

The contest printer is attached to an onsite admin laptop, not to the
DOMjudge host. DOMjudge should still accept team print requests, but the final
print action must be performed by a protected browser page running on that
laptop.

The goal is to make normal printing mostly automatic while keeping an operator
able to pause the flow during paper jams, ink replacement, printer offline
events, or other onsite issues.

## Scope

This design covers a protected Print Station page and queue API for existing
DOMjudge print jobs.

In scope:

- Queue team print jobs on the server.
- Let an authenticated onsite laptop claim and print jobs.
- Support automatic printing with a kiosk browser setup.
- Support pause, resume, retry, mark done, and mark failed.
- Avoid duplicate printing when more than one browser tab or laptop is open.
- Recover jobs that were claimed but never completed.

Out of scope:

- Installing printer drivers on the DOMjudge host.
- Full integration with the DOMjudge Symfony admin session.
- Silent printing from an ordinary browser without kiosk or OS setup.
- Publishing live print jobs, submissions, secrets, or queue data.

## Recommended Approach

Use an independent Print Station page protected by HTTP Basic Auth. It can be
served by the existing rollboard admin service and nginx protected location, or
by a sibling service with the same deployment style.

The onsite admin laptop opens the Print Station URL before the contest starts.
In normal operation, the page polls the queue, claims the next pending job,
dispatches it to the laptop's default printer with `window.print()`, marks the
job as done after the browser reports the print dialog finished, and then moves
to the next job.

For near-unattended operation, the laptop should start Chrome or Edge with a
dedicated shortcut using kiosk printing. Without kiosk printing, the same page
can still process the queue, but the operating system may ask for manual print
confirmation for each job.

## Queue Layout

The live queue remains outside the public repository:

```text
/mnt/domjudge/domjudge-live/domserver/var/print-spool/
  pending/
  printing/
  done/
  failed/
  control/
```

Each job is a directory containing sanitized metadata plus the printable
content:

```text
<job-id>/
  metadata.txt
  source
  print.txt
  state.json
```

The spool writer should create each job atomically. A safe implementation is to
write into a temporary directory and then rename it into `pending`, or to write
a `.ready` marker only after all files have been flushed.

The public backup repository must contain only scripts, docs, tests, and
sanitized examples. It must never contain live queue directories or submitted
source files.

## API

The Print Station service exposes authenticated endpoints:

- `GET /print-station/`
  serves the browser UI.
- `GET /print-station/api/status`
  returns paused state, active station, queue counts, and recent errors.
- `POST /print-station/api/pause`
  pauses automatic claiming of new jobs.
- `POST /print-station/api/resume`
  resumes automatic claiming.
- `GET /print-station/api/jobs`
  lists pending, printing, failed, and recent done jobs.
- `POST /print-station/api/jobs/{id}/claim`
  moves one pending job to printing and assigns it to the current station.
- `GET /print-station/api/jobs/{id}/print`
  returns a printable HTML or plain-text view.
- `POST /print-station/api/jobs/{id}/done`
  moves a claimed job to done.
- `POST /print-station/api/jobs/{id}/fail`
  moves a claimed job to failed with an operator-visible reason.
- `POST /print-station/api/jobs/{id}/requeue`
  moves a failed, stale, or recent done job back to pending.

All job IDs must be validated with a strict allowlist such as
`[A-Za-z0-9_.-]+`, and resolved paths must remain inside the spool root.

## Browser Workflow

The Print Station page has two modes:

- Auto mode: claim and print the next job whenever printing is not paused.
- Manual mode: show the queue and let the operator print or requeue jobs.

Normal auto flow:

1. Poll status and queue.
2. Stop if server-side pause is enabled.
3. Claim the oldest pending job.
4. Render the printable view in a print frame or child window.
5. Call `window.print()`.
6. After `afterprint` or a conservative timeout, mark the job as done.
7. Wait a short configurable delay, then continue.

Because browsers cannot reliably know whether paper physically came out, `done`
means "handed to the laptop print subsystem". The UI must keep a recent done
list with a reprint action so the operator can recover from paper jams or
missing pages.

## Pause And Incident Handling

Pause is a server-side control so it survives browser refreshes.

When paused:

- New DOMjudge print requests still enter `pending`.
- No new job is claimed by the Print Station.
- The operator can still inspect, reprint, mark failed, or mark done manually.

The UI should provide:

- A prominent pause/resume control.
- Queue counts for pending, printing, failed, and done.
- A visible current-job panel.
- Reprint for recent done jobs.
- Requeue for failed or stale printing jobs.
- A warning if another active station appears to be handling the queue.

## Locking And Recovery

Each Print Station browser creates a `station_id` and sends a heartbeat while
open. A job claimed for printing records:

- `station_id`
- claim time
- last heartbeat time
- attempt count

Only the station that claimed a job can mark it done by default. An operator can
manually take over stale jobs.

If a job remains in printing for longer than a configured stale timeout, the UI
marks it as stale. The system should not silently reprint stale jobs immediately,
because the original laptop may still have opened a print dialog. The safer
default is to show a prominent recovery action and let the operator requeue or
mark done.

## Security

The Print Station is protected by Basic Auth at nginx or an equivalent service
boundary. It does not need DOMjudge admin session integration for the first
version.

Security requirements:

- No unauthenticated queue access.
- No path traversal through job IDs.
- No arbitrary file reads from API endpoints.
- No public backup of live queue content.
- No credentials, cookies, sessions, TLS private material, or live submissions
  in commits.
- POST endpoints should require same-origin requests and reject unsupported
  methods.

## Testing

Automated tests:

- Job ID validation rejects traversal and special paths.
- Pending jobs can be claimed once.
- Pause prevents auto claim.
- Done, failed, and requeue transitions move job directories correctly.
- Stale printing jobs are detected without silent reprint.
- Multiple station IDs cannot mark each other's active jobs done accidentally.

Manual deployment tests:

- Submit a print job from a team page.
- Confirm it appears in Print Station.
- Confirm pause blocks auto printing while queueing continues.
- Confirm resume prints queued jobs.
- Confirm recent done jobs can be reprinted.
- Confirm failed jobs can be requeued.
- Confirm kiosk browser prints to the onsite laptop default printer.

## Deployment Notes

Recommended public URL:

```text
https://domjudge.seucpc.com/print-station/
```

Recommended onsite setup:

- Set the intended printer as the laptop's default printer.
- Start Chrome or Edge from a dedicated shortcut with kiosk printing enabled.
- Open the Print Station before the contest starts.
- Keep one active Print Station window during the contest.
- Use pause before fixing paper, ink, toner, or printer connection issues.

The exact kiosk command should be documented after implementation and tested on
the operating system used by the onsite laptop.

# Print Station

The onsite contest printer is attached to an admin laptop, not to the DOMjudge
host. DOMjudge queues team print requests on the server, and the laptop prints
them through a protected browser page:

```text
https://domjudge.seucpc.com/print-station/
```

The page uses the same Basic Auth protection style as rollboard. It does not
expose live submissions or queue contents in this public repository.

## Normal Contest Flow

1. Set the intended printer as the laptop's default printer.
2. Open the Print Station page on exactly one onsite laptop.
3. Keep automatic mode enabled.
4. Use Pause before fixing paper, ink, toner, or printer connection issues.
5. Resume after the printer is ready.

Team print requests continue entering the pending queue while printing is
paused.

## Kiosk Printing

For the lowest operator workload, start Chrome or Edge with kiosk printing
enabled and open the Print Station URL. Browser vendors may still require
initial printer setup at the operating system level.

Example command shape:

```text
chrome --kiosk-printing https://domjudge.seucpc.com/print-station/
```

Use the actual Chrome or Edge executable path for the onsite laptop.

## Recovery

The Print Station keeps queue states under the live spool root:

```text
/mnt/domjudge/domjudge-live/domserver/var/print-spool/
```

Operators can:

- Pause automatic printing.
- Reprint a recent done job.
- Requeue failed jobs.
- Mark an active job done or failed.
- Manually process the next pending job.

Only one active Print Station should be used. If a second Print Station opens,
it sees a warning and will not automatically claim jobs while the first station
is active.

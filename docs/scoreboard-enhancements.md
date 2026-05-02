# Scoreboard Enhancements

This deployment adds a small front-end enhancement on top of DOMjudge's built-in AJAX scoreboard refresh.

## Behavior

- Public and team scoreboards retune the native AJAX refresh interval to 15 seconds when refresh is enabled.
- Existing first solves on page load are treated as the baseline and do not trigger alerts.
- Newly appearing `score_first` cells trigger an in-page "First Blood" toast.
- Alerts are suppressed once the rendered scoreboard state says updates are frozen, stopped, preliminary, or final.
- Rows whose solved count or penalty changes are briefly highlighted after an AJAX refresh.

## Files

```text
webapp/public/js/seu-scoreboard-enhance.js
webapp/templates/public/scoreboard.html.twig
webapp/templates/team/scoreboard.html.twig
webapp/templates/partials/scoreboard.html.twig
tests/seu-scoreboard-enhance.test.js
```

The script is intentionally self-contained and does not store secrets or contest data outside each browser's local storage.

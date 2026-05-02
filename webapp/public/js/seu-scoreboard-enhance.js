(function (root, factory) {
    var api = factory(root);
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    } else {
        root.SeuScoreboardEnhance = api;
    }
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
    'use strict';

    var DEFAULT_STORAGE_KEY = 'seu-scoreboard-first-solves';
    var STORAGE_VERSION = 1;
    var TOAST_LIFETIME_MS = 30000;
    var previousRows = null;
    var initialized = false;
    var state = null;
    var notificationPromptBound = false;

    function normalizeText(value) {
        return String(value || '').replace(/\s+/g, ' ').trim();
    }

    function entryKey(entry) {
        return normalizeText(entry.problem) + '\u0000' + normalizeText(entry.team);
    }

    function toKeySet(entries) {
        var keys = {};
        for (var i = 0; i < entries.length; i++) {
            keys[entryKey(entries[i])] = true;
        }
        return keys;
    }

    function diffFirstSolves(previous, current, alertsClosed) {
        if (alertsClosed) {
            return [];
        }

        var previousKeys = toKeySet(previous || []);
        var newlySolved = [];
        for (var i = 0; i < current.length; i++) {
            if (!previousKeys[entryKey(current[i])]) {
                newlySolved.push(current[i]);
            }
        }
        return newlySolved;
    }

    function createMemoryState(initialEntries) {
        var entries = Array.isArray(initialEntries) ? initialEntries.slice() : null;
        return {
            load: function () {
                return entries ? entries.slice() : null;
            },
            save: function (nextEntries) {
                entries = nextEntries.slice();
            },
        };
    }

    function createStorageState(storage, key) {
        var storageKey = key || DEFAULT_STORAGE_KEY;
        return {
            load: function () {
                if (!storage) {
                    return null;
                }
                try {
                    var parsed = JSON.parse(storage.getItem(storageKey) || 'null');
                    if (!parsed || parsed.version !== STORAGE_VERSION || !Array.isArray(parsed.entries)) {
                        return null;
                    }
                    return parsed.entries;
                } catch (error) {
                    return null;
                }
            },
            save: function (nextEntries) {
                if (!storage) {
                    return;
                }
                try {
                    storage.setItem(storageKey, JSON.stringify({
                        version: STORAGE_VERSION,
                        entries: nextEntries,
                    }));
                } catch (error) {
                    // Storage can be disabled by browser policy; in-page alerts still work for this refresh.
                }
            },
        };
    }

    function processSnapshot(snapshotState, currentEntries, alertsClosed) {
        var previousEntries = snapshotState.load();
        var alerts = previousEntries === null ? [] : diffFirstSolves(previousEntries, currentEntries, alertsClosed);
        snapshotState.save(currentEntries);
        return {
            alerts: alerts,
            firstObservation: previousEntries === null,
        };
    }

    function getProblemLabels(rootNode) {
        var labels = [];
        var headers = rootNode.querySelectorAll('.scoreboard thead th[title^="problem "]');
        for (var i = 0; i < headers.length; i++) {
            var anchor = headers[i].querySelector('a');
            labels.push(normalizeText(anchor ? anchor.firstChild && anchor.firstChild.nodeValue : headers[i].textContent));
        }
        return labels;
    }

    function getTeamName(row) {
        var teamCell = row.querySelector('.scoretn');
        if (!teamCell) {
            return '';
        }
        return normalizeText(teamCell.getAttribute('title') || teamCell.textContent);
    }

    function extractFirstSolves(rootNode) {
        if (!rootNode || !rootNode.querySelectorAll) {
            return [];
        }

        var labels = getProblemLabels(rootNode);
        var result = [];
        var rows = rootNode.querySelectorAll('.scoreboard tbody tr[id^="team:"]');
        for (var rowIndex = 0; rowIndex < rows.length; rowIndex++) {
            var row = rows[rowIndex];
            var cells = row.querySelectorAll('td.score_cell');
            for (var problemIndex = 0; problemIndex < cells.length; problemIndex++) {
                if (cells[problemIndex].querySelector('.score_first')) {
                    result.push({
                        problem: labels[problemIndex] || String(problemIndex + 1),
                        team: getTeamName(row),
                    });
                }
            }
        }

        return result;
    }

    function isAlertsClosed(rootNode) {
        if (!rootNode || !rootNode.querySelector) {
            return false;
        }

        var marker = rootNode.querySelector('[data-seu-scoreboard-state]');
        if (marker && marker.getAttribute('data-alerts-closed') === '1') {
            return true;
        }

        var alert = rootNode.querySelector('.alert.alert-warning');
        var text = normalizeText(alert ? alert.textContent : '');
        return /scoreboard was frozen|contest over|final standings|preliminary results/i.test(text);
    }

    function snapshotRows(rootNode) {
        var rows = {};
        if (!rootNode || !rootNode.querySelectorAll) {
            return rows;
        }

        var tableRows = rootNode.querySelectorAll('.scoreboard tbody tr[id^="team:"]');
        for (var i = 0; i < tableRows.length; i++) {
            var row = tableRows[i];
            var rowId = row.getAttribute('id');
            var solved = row.querySelector('.scorenc');
            var total = row.querySelector('.scorett');
            if (rowId) {
                rows[rowId] = normalizeText(solved ? solved.textContent : '') + '|' +
                    normalizeText(total ? total.textContent : '');
            }
        }
        return rows;
    }

    function highlightChangedRows(rootNode, before, after) {
        if (!before || !rootNode || !rootNode.querySelectorAll) {
            return;
        }

        var rows = rootNode.querySelectorAll('.scoreboard tbody tr[id^="team:"]');
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var rowId = row.getAttribute('id');
            if (rowId && before[rowId] && after[rowId] && before[rowId] !== after[rowId]) {
                row.classList.add('seu-scoreboard-row-changed');
            }
        }
    }

    function ensureStyles(documentNode) {
        if (!documentNode || documentNode.getElementById('seu-scoreboard-enhance-style')) {
            return;
        }

        var style = documentNode.createElement('style');
        style.id = 'seu-scoreboard-enhance-style';
        style.textContent = '' +
            '@keyframes seuScoreboardPulse{0%{box-shadow:inset 0 0 0 9999px rgba(255,210,77,.34)}100%{box-shadow:inset 0 0 0 9999px rgba(255,210,77,0)}}' +
            '.seu-scoreboard-row-changed{animation:seuScoreboardPulse 1.8s ease-out}' +
            '.seu-firstblood-stack{position:fixed;right:1rem;bottom:1rem;z-index:1080;display:flex;flex-direction:column;gap:.5rem;max-width:min(24rem,calc(100vw - 2rem))}' +
            '.seu-firstblood-toast{position:relative;background:#101820;color:#fff;border-left:4px solid #ffbf3c;border-radius:.25rem;box-shadow:0 .5rem 1.2rem rgba(0,0,0,.24);padding:.75rem 2.1rem .75rem .9rem;font-size:.95rem;line-height:1.35;opacity:0;transform:translateY(.75rem);transition:opacity .18s ease,transform .18s ease}' +
            '.seu-firstblood-toast.is-visible{opacity:1;transform:translateY(0)}' +
            '.seu-firstblood-title{font-weight:700;margin-bottom:.15rem}' +
            '.seu-firstblood-body{color:#f8f9fa}' +
            '.seu-firstblood-close{position:absolute;top:.35rem;right:.45rem;border:0;background:transparent;color:#fff;font-size:1.1rem;line-height:1;cursor:pointer;opacity:.72}' +
            '.seu-firstblood-close:hover,.seu-firstblood-close:focus{opacity:1}';
        documentNode.head.appendChild(style);
    }

    function getToastStack(documentNode) {
        var stack = documentNode.querySelector('.seu-firstblood-stack');
        if (stack) {
            return stack;
        }

        stack = documentNode.createElement('div');
        stack.className = 'seu-firstblood-stack';
        stack.setAttribute('aria-live', 'polite');
        stack.setAttribute('aria-atomic', 'false');
        documentNode.body.appendChild(stack);
        return stack;
    }

    function showToast(entry) {
        var documentNode = root.document;
        if (!documentNode) {
            return;
        }

        ensureStyles(documentNode);
        var toast = documentNode.createElement('div');
        toast.className = 'seu-firstblood-toast';
        toast.innerHTML = '<div class="seu-firstblood-title">First Blood</div>' +
            '<div class="seu-firstblood-body">' + escapeHtml(entry.team) +
            ' solved problem ' + escapeHtml(entry.problem) + ' first.</div>' +
            '<button type="button" class="seu-firstblood-close" aria-label="Close first blood alert">&times;</button>';
        getToastStack(documentNode).appendChild(toast);

        var closeButton = toast.querySelector('.seu-firstblood-close');
        if (closeButton) {
            closeButton.addEventListener('click', function () {
                dismissToast(toast);
            });
        }

        root.setTimeout(function () {
            toast.classList.add('is-visible');
        }, 20);
        scheduleToastDismiss(toast, documentNode);

        maybeBrowserNotification(entry);
    }

    function dismissToast(toast) {
        if (!toast || !toast.parentNode) {
            return;
        }

        toast.classList.remove('is-visible');
        root.setTimeout(function () {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 220);
    }

    function getToastAutoDismissDelay(documentNode) {
        if (documentNode && documentNode.hidden) {
            return null;
        }
        return TOAST_LIFETIME_MS;
    }

    function scheduleToastDismiss(toast, documentNode) {
        var delay = getToastAutoDismissDelay(documentNode);
        if (delay !== null) {
            root.setTimeout(function () {
                dismissToast(toast);
            }, delay);
            return;
        }

        var onVisible = function () {
            if (documentNode.hidden) {
                return;
            }
            documentNode.removeEventListener('visibilitychange', onVisible);
            root.setTimeout(function () {
                dismissToast(toast);
            }, TOAST_LIFETIME_MS);
        };
        documentNode.addEventListener('visibilitychange', onVisible);
    }

    function escapeHtml(value) {
        return normalizeText(value).replace(/[&<>"']/g, function (character) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            }[character];
        });
    }

    function maybeBrowserNotification(entry) {
        if (!root.Notification || root.Notification.permission !== 'granted') {
            return;
        }

        try {
            var notification = new root.Notification('First Blood', {
                body: normalizeText(entry.team) + ' solved problem ' + normalizeText(entry.problem) + ' first.',
                tag: 'firstblood-' + entryKey(entry),
            });
            root.setTimeout(function () {
                notification.close();
            }, TOAST_LIFETIME_MS);
        } catch (error) {
            // Browser notifications are optional; the in-page toast is the reliable path.
        }
    }

    function requestNotificationPermissionOnInteraction(documentNode) {
        if (!documentNode || !root.Notification || notificationPromptBound) {
            return;
        }
        if (root.Notification.permission !== 'default') {
            return;
        }

        var requestPermission = function () {
            documentNode.removeEventListener('click', requestPermission);
            documentNode.removeEventListener('keydown', requestPermission);
            try {
                root.Notification.requestPermission();
            } catch (error) {
                // Some browsers require a different permission flow; in-page toasts remain available.
            }
        };

        documentNode.addEventListener('click', requestPermission);
        documentNode.addEventListener('keydown', requestPermission);
        notificationPromptBound = true;
    }

    function afterRefresh() {
        var documentNode = root.document;
        if (!documentNode || !state) {
            return;
        }

        ensureStyles(documentNode);
        var alertsClosed = isAlertsClosed(documentNode);
        var currentFirstSolves = extractFirstSolves(documentNode);
        var currentRows = snapshotRows(documentNode);
        var result = processSnapshot(state, currentFirstSolves, alertsClosed);

        highlightChangedRows(documentNode, previousRows, currentRows);
        previousRows = currentRows;

        for (var i = 0; i < result.alerts.length; i++) {
            showToast(result.alerts[i]);
        }
    }

    function retuneRefresh(config) {
        if (!config || !config.refreshUrl || !config.refreshAfter) {
            return;
        }
        if (root.seuScoreboardRefreshTuned || root.refreshEnabled !== true) {
            return;
        }
        if (typeof root.disableRefresh !== 'function' || typeof root.enableRefresh !== 'function') {
            return;
        }

        root.disableRefresh(true);
        root.enableRefresh(config.refreshUrl, config.refreshAfter, true);
        root.seuScoreboardRefreshTuned = true;
    }

    function init(config) {
        if (initialized) {
            return;
        }
        initialized = true;
        config = config || {};
        state = createStorageState(root.localStorage, config.storageKey || DEFAULT_STORAGE_KEY);
        requestNotificationPermissionOnInteraction(root.document);
        retuneRefresh(config);
        afterRefresh();
    }

    return {
        init: init,
        afterRefresh: afterRefresh,
        createMemoryState: createMemoryState,
        diffFirstSolves: diffFirstSolves,
        processSnapshot: processSnapshot,
        isAlertsClosed: isAlertsClosed,
        getToastAutoDismissDelay: getToastAutoDismissDelay,
        extractFirstSolves: extractFirstSolves,
        snapshotRows: snapshotRows,
    };
});

const assert = require('node:assert/strict');
const test = require('node:test');

const enhance = require('../webapp/public/js/seu-scoreboard-enhance.js');

test('diffFirstSolves returns only newly appearing first solves', () => {
  const previous = [
    { problem: 'A', team: 'Alpha' },
  ];
  const current = [
    { problem: 'A', team: 'Alpha' },
    { problem: 'B', team: 'Beta' },
  ];

  assert.deepEqual(enhance.diffFirstSolves(previous, current, false), [
    { problem: 'B', team: 'Beta' },
  ]);
});

test('diffFirstSolves suppresses alerts once scoreboard alerts are closed', () => {
  const current = [
    { problem: 'C', team: 'Gamma' },
  ];

  assert.deepEqual(enhance.diffFirstSolves([], current, true), []);
});

test('processSnapshot treats the first observation as baseline', () => {
  const state = enhance.createMemoryState();

  const firstPass = enhance.processSnapshot(state, [
    { problem: 'A', team: 'Alpha' },
  ], false);
  const secondPass = enhance.processSnapshot(state, [
    { problem: 'A', team: 'Alpha' },
    { problem: 'D', team: 'Delta' },
  ], false);

  assert.deepEqual(firstPass.alerts, []);
  assert.deepEqual(secondPass.alerts, [
    { problem: 'D', team: 'Delta' },
  ]);
});

test('isAlertsClosed recognizes the rendered DOMjudge state marker', () => {
  const marker = {
    getAttribute(name) {
      return name === 'data-alerts-closed' ? '1' : null;
    },
  };
  const root = {
    querySelector(selector) {
      return selector === '[data-seu-scoreboard-state]' ? marker : null;
    },
  };

  assert.equal(enhance.isAlertsClosed(root), true);
});

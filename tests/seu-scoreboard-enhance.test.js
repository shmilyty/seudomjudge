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

test('diffFirstSolves de-duplicates first solves rendered in desktop and mobile scoreboards', () => {
  const current = [
    { problem: 'A', team: 'Alpha' },
    { problem: 'A', team: 'Alpha' },
    { problem: 'B', team: 'Beta' },
  ];

  assert.deepEqual(enhance.diffFirstSolves([], current, false), [
    { problem: 'A', team: 'Alpha' },
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

test('toast auto-dismiss is delayed while the page is hidden', () => {
  assert.equal(enhance.getToastAutoDismissDelay({ hidden: true }), null);
  assert.equal(enhance.getToastAutoDismissDelay({ hidden: false }), 30000);
});

test('showToast creates an in-page alert and a browser notification when permission is granted', () => {
  const originalDocument = global.document;
  const originalNotification = global.Notification;
  const originalSetTimeout = global.setTimeout;
  const fakeDocument = createFakeDocument();
  const notifications = [];

  function FakeNotification(title, options) {
    notifications.push({ title, options });
    this.close = () => {};
  }
  FakeNotification.permission = 'granted';

  global.document = fakeDocument;
  global.Notification = FakeNotification;
  global.setTimeout = () => 1;

  try {
    enhance.showToast({ problem: 'A', team: 'Alpha' });

    const stack = fakeDocument.querySelector('.seu-firstblood-stack');
    assert.ok(stack, 'toast stack should be created');
    assert.equal(stack.children.length, 1);
    assert.match(stack.children[0].innerHTML, /Alpha solved problem A first\./);
    assert.deepEqual(notifications, [
      {
        title: 'First Blood',
        options: {
          body: 'Alpha solved problem A first.',
          tag: 'firstblood-A\u0000Alpha',
        },
      },
    ]);
  } finally {
    global.document = originalDocument;
    global.Notification = originalNotification;
    global.setTimeout = originalSetTimeout;
  }
});

function createFakeDocument() {
  const elementsById = new Map();
  const body = createFakeElement('body');
  const head = createFakeElement('head');

  head.appendChild = (child) => {
    child.parentNode = head;
    head.children.push(child);
    if (child.id) {
      elementsById.set(child.id, child);
    }
  };

  return {
    hidden: false,
    body,
    head,
    createElement: createFakeElement,
    getElementById(id) {
      return elementsById.get(id) || null;
    },
    querySelector(selector) {
      if (selector === '.seu-firstblood-stack') {
        return body.children.find((child) => child.className === 'seu-firstblood-stack') || null;
      }
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
}

function createFakeElement(tagName) {
  const element = {
    tagName: tagName.toUpperCase(),
    id: '',
    className: '',
    textContent: '',
    innerHTML: '',
    children: [],
    parentNode: null,
    attributes: {},
    classList: {
      add(className) {
        this.owner.className = mergeClassName(this.owner.className, className);
      },
      remove(className) {
        this.owner.className = this.owner.className
          .split(/\s+/)
          .filter((value) => value && value !== className)
          .join(' ');
      },
    },
    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name] || null;
    },
    querySelector(selector) {
      if (selector === '.seu-firstblood-close') {
        return { addEventListener() {} };
      }
      return null;
    },
    addEventListener() {},
  };

  element.classList.owner = element;
  return element;
}

function mergeClassName(existing, next) {
  const values = new Set(existing.split(/\s+/).filter(Boolean));
  values.add(next);
  return Array.from(values).join(' ');
}

// Runs before every test file. Two jobs: remove the listeners the page scripts add to
// document and window after each test (the scripts are loaded again for every test), and
// restore the globals the tests replace.
import { afterEach, vi } from "vitest";

const added = [];
for (const target of [document, window]) {
  const add = target.addEventListener.bind(target);
  target.addEventListener = (type, listener, options) => {
    added.push([target, type, listener, options]);
    add(type, listener, options);
  };
}

afterEach(() => {
  for (const [target, type, listener, options] of added.splice(0)) {
    target.removeEventListener(type, listener, options);
  }
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
  document.body.innerHTML = "";
  delete window.UniSpaceI18n;
  delete window.UniSpaceApi;
  delete window.UniSpaceModules;
  delete window.UniSpaceGrid;
  delete window.UniSpaceUI;
  delete window.UniSpaceAuth;
});

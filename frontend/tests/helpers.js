// Shared test helpers: the real page markup, the real i18n dictionaries, and a fetch stub.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { vi } from "vitest";

export const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// Puts the <body> of a page file into the document, as the browser does.
export function mountPage(relativePath) {
  const html = readFileSync(resolve(FRONTEND, relativePath), "utf8");
  document.body.innerHTML = new DOMParser().parseFromString(
    html,
    "text/html",
  ).body.innerHTML;
}

// Loads the i18n runtime and both dictionaries, in the order the pages load them.
export async function loadI18n(language = "en") {
  localStorage.setItem("unispace-lang", language);
  await import("../i18n/i18n.js");
  await import("../i18n/ro.js");
  await import("../i18n/en.js");
}

// Loads one browser script as the page would (a fresh copy for each test).
export async function loadScript(relativePath) {
  await import(resolve(FRONTEND, relativePath));
}

export const flush = () => new Promise((done) => setImmediate(done));

export function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  };
}

// A fetch stub: each route is a path (query ignored) mapped to a function of the full URL.
export function stubFetch(routes) {
  const fetch = vi.fn((url) => {
    const path = new URL(url, "http://localhost").pathname;
    const route = routes[path];
    if (!route) return Promise.resolve(response({ detail: "not found" }, 404));
    return Promise.resolve(route(url));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

// A promise that the test settles by hand, to control the order of responses.
export function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

// The query string of a request, as an object.
export function queryOf(url) {
  return Object.fromEntries(
    new URL(url, "http://localhost").searchParams.entries(),
  );
}

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  flush,
  loadI18n,
  loadScript,
  mountPage,
  response,
} from "../helpers.js";

// Admin: the Users tab (C-008, D-025). The list loads when the tab opens; the invite card and
// the pending invitations are shown above it.
const USERS = [
  {
    id: "u1",
    email: "ana@ulbsibiu.ro",
    name: "Ana Pop",
    role: "STUDENT",
    faculty_name: "Facultatea de Drept",
    study_formation_name: "332CA",
    created_at: "2026-11-20T10:00:00Z",
  },
  {
    id: "u2",
    email: "root@ulbsibiu.ro",
    name: "Root",
    role: "ADMIN",
    faculty_name: null,
    study_formation_name: null,
    created_at: "2026-11-19T10:00:00Z",
  },
];

const INVITES = [
  {
    id: "i1",
    email: "reps@club.ro",
    role: "STUDENT_ORG",
    token: "T1",
    invite_url: "/login?invite=T1",
    expires_at: "2026-11-27T10:00:00Z",
    created_at: "2026-11-25T10:00:00Z",
  },
];

const usersPage = (items, total = items.length, offset = 0) =>
  response({ items, total, limit: 15, offset });

// Answers by "METHOD /path". A route is a function of the parsed URL and the request options.
function apiStub(overrides = {}) {
  const routes = {
    "GET /api/admin/bookings/pending": () => response([]),
    "GET /api/admin/bookings": () =>
      response({ items: [], total: 0, limit: 15, offset: 0 }),
    "GET /api/faculties": () => response([]),
    "GET /api/admin/classrooms": () => response([]),
    "GET /api/admin/users": () => usersPage(USERS),
    "GET /api/admin/invitations": () => response(INVITES),
    ...overrides,
  };
  const fetch = vi.fn((url, options = {}) => {
    const parsed = new URL(url, "http://localhost");
    const route = routes[`${options.method || "GET"} ${parsed.pathname}`];
    const answer = route
      ? route(parsed, options)
      : response({ detail: "not found" }, 404);
    return Promise.resolve(answer);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

const requestsTo = (fetch, method, path) =>
  fetch.mock.calls.filter(
    ([url, options]) =>
      (options?.method || "GET") === method &&
      new URL(url, "http://localhost").pathname === path,
  );

const $ = (id) => document.getElementById(id);

async function setup({ language = "en", routes = {} } = {}) {
  mountPage("pages/admin/index.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  const fetch = apiStub(routes);
  await loadScript("components/toast.js");
  const toast = vi.spyOn(window.UniSpaceUI, "toast");
  await loadScript("js/api.js");
  await loadScript("js/bookings.js");
  await loadScript("js/pages/admin-history.js");
  await loadScript("js/pages/admin-rooms.js");
  await loadScript("js/pages/admin-users.js");
  await flush();
  const clipboard = { writeText: vi.fn(() => Promise.resolve()) };
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: clipboard,
  });
  return { fetch, toast, clipboard };
}

// Opens the Users tab and waits for both lists to draw.
async function openUsersTab(ctx) {
  $("tab-users").click();
  await flush();
  return ctx;
}

const rows = (id) => Array.from($(id).querySelectorAll("tr"));

describe("admin-users.js: the Users tab", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("opens with its users and pending invitations, and hides the other tabs", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    expect($("panel-users").hidden).toBe(false);
    expect($("panel-rooms").hidden).toBe(true);
    expect($("panel-pending").hidden).toBe(true);
    expect(rows("usr-body")).toHaveLength(2);
    expect(rows("inv-body")).toHaveLength(1);
    expect($("usr-range").textContent).toBe("1–2 of 2");
  });

  it("shows the admin as a badge and the other roles as a dropdown without Admin", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    const [student, admin] = rows("usr-body");
    expect(admin.querySelector("select")).toBeNull();
    expect(admin.querySelector(".pill").textContent).toBe("Admin");

    const select = student.querySelector("select");
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "STUDENT",
      "PROFESSOR",
      "STUDENT_ORG",
    ]);
    expect(select.value).toBe("STUDENT");
  });

  it("names the faculty and study group, or says Not set", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    const [student, admin] = rows("usr-body");
    expect(student.textContent).toContain("Facultatea de Drept · 332CA");
    expect(admin.textContent).toContain("Not set");
  });

  it("saves a changed role, and confirms it", async () => {
    const ctx = await setup({
      routes: {
        "PATCH /api/admin/users/u1/role": (_url, options) =>
          response({ id: "u1", role: JSON.parse(options.body).role }),
      },
    });
    await openUsersTab(ctx);

    const select = rows("usr-body")[0].querySelector("select");
    select.value = "PROFESSOR";
    select.dispatchEvent(new Event("change"));
    await flush();

    const [patch] = requestsTo(ctx.fetch, "PATCH", "/api/admin/users/u1/role");
    expect(JSON.parse(patch[1].body)).toEqual({ role: "PROFESSOR" });
    expect(ctx.toast).toHaveBeenLastCalledWith("Role saved.");
  });

  it("puts the old role back and says so when a change is refused", async () => {
    const ctx = await setup({
      routes: {
        "PATCH /api/admin/users/u1/role": () =>
          response({ detail: "refused" }, 422),
      },
    });
    await openUsersTab(ctx);

    const select = rows("usr-body")[0].querySelector("select");
    select.value = "STUDENT_ORG";
    select.dispatchEvent(new Event("change"));
    await flush();

    expect(select.value).toBe("STUDENT");
    expect(ctx.toast).toHaveBeenLastCalledWith(
      "The role could not be saved. Try again.",
    );
  });

  it("filters by role, and starts again from the first page", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    $("usr-role").value = "PROFESSOR";
    $("usr-role").dispatchEvent(new Event("change"));
    await flush();

    const last = requestsTo(ctx.fetch, "GET", "/api/admin/users").at(-1);
    const query = new URL(last[0], "http://localhost").searchParams;
    expect(query.get("role")).toBe("PROFESSOR");
    expect(query.get("offset")).toBe("0");
  });

  it("searches by email after a short pause, not on every key", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const ctx = await setup();
    await openUsersTab(ctx);
    const before = requestsTo(ctx.fetch, "GET", "/api/admin/users").length;

    const search = $("usr-search");
    search.value = "i";
    search.dispatchEvent(new Event("input"));
    search.value = "ion";
    search.dispatchEvent(new Event("input"));
    expect(requestsTo(ctx.fetch, "GET", "/api/admin/users")).toHaveLength(
      before,
    );

    vi.advanceTimersByTime(300);
    await flush();

    const calls = requestsTo(ctx.fetch, "GET", "/api/admin/users");
    expect(calls).toHaveLength(before + 1);
    const query = new URL(calls.at(-1)[0], "http://localhost").searchParams;
    expect(query.get("search")).toBe("ion");
  });

  it("pages through the users, fifteen to a page", async () => {
    const many = Array.from({ length: 15 }, (_, n) => ({
      ...USERS[0],
      id: `m${n}`,
      email: `m${n}@ulbsibiu.ro`,
    }));
    const ctx = await setup({
      routes: {
        "GET /api/admin/users": (url) => {
          const offset = Number(url.searchParams.get("offset"));
          return offset === 0
            ? usersPage(many, 20, 0)
            : usersPage(USERS, 20, 15);
        },
      },
    });
    await openUsersTab(ctx);

    expect($("usr-prev").disabled).toBe(true);
    expect($("usr-next").disabled).toBe(false);
    expect($("usr-range").textContent).toBe("1–15 of 20");

    $("usr-next").click();
    await flush();
    const offsets = requestsTo(ctx.fetch, "GET", "/api/admin/users").map(
      ([url]) => new URL(url, "http://localhost").searchParams.get("offset"),
    );
    expect(offsets).toContain("15");
    expect($("usr-prev").disabled).toBe(false);
    expect($("usr-next").disabled).toBe(true);
    expect($("usr-range").textContent).toBe("16–17 of 20");

    $("usr-prev").click();
    await flush();
    expect($("usr-prev").disabled).toBe(true);
    expect($("usr-range").textContent).toBe("1–15 of 20");
  });

  it("shows an empty state when no user matches", async () => {
    const ctx = await setup({
      routes: { "GET /api/admin/users": () => usersPage([]) },
    });
    await openUsersTab(ctx);

    expect($("usr-empty").hidden).toBe(false);
    expect($("usr-pager").hidden).toBe(true);
  });

  it("shows a load error when the users cannot be loaded", async () => {
    const ctx = await setup({
      routes: { "GET /api/admin/users": () => response({}, 500) },
    });
    await openUsersTab(ctx);

    expect($("usr-status").textContent).toBe(
      "Could not load the users. Try again.",
    );
    expect($("usr-status").className).toBe("notice notice--error");
  });

  it("invites an email, shows the link to copy, and lists the new invitation", async () => {
    const created = {
      id: "i2",
      email: "reps@club.ro",
      role: "STUDENT_ORG",
      token: "T9",
      invite_url: "/login?invite=T9",
      expires_at: "2026-11-27T10:00:00Z",
      created_at: "2026-11-25T11:00:00Z",
    };
    const ctx = await setup({
      routes: {
        "POST /api/admin/invitations": () => response(created, 201),
      },
    });
    await openUsersTab(ctx);

    $("inv-email").value = "Reps@Club.ro";
    $("inv-role").value = "STUDENT_ORG";
    $("inv-form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush();

    const [post] = requestsTo(ctx.fetch, "POST", "/api/admin/invitations");
    expect(JSON.parse(post[1].body)).toEqual({
      email: "Reps@Club.ro",
      role: "STUDENT_ORG",
    });
    expect($("inv-status").textContent).toBe(
      "Invitation created for reps@club.ro.",
    );
    expect($("inv-copy-wrap").hidden).toBe(false);
    expect($("inv-email").value).toBe("");
    expect(
      requestsTo(ctx.fetch, "GET", "/api/admin/invitations").length,
    ).toBeGreaterThan(1);
  });

  it("copies the invite link with the site address", async () => {
    const created = {
      id: "i2",
      email: "reps@club.ro",
      role: "STUDENT_ORG",
      token: "T9",
      invite_url: "/login?invite=T9",
      expires_at: "2026-11-27T10:00:00Z",
      created_at: "2026-11-25T11:00:00Z",
    };
    const ctx = await setup({
      routes: { "POST /api/admin/invitations": () => response(created, 201) },
    });
    await openUsersTab(ctx);
    $("inv-email").value = "reps@club.ro";
    $("inv-form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush();

    $("inv-copy").click();
    await flush();

    expect(ctx.clipboard.writeText).toHaveBeenCalledWith(
      `${window.location.origin}/login?invite=T9`,
    );
    expect(ctx.toast).toHaveBeenLastCalledWith("Link copied.");
  });

  it("says who already has an account, with their email and role", async () => {
    const ctx = await setup({
      routes: {
        "POST /api/admin/invitations": () =>
          response(
            {
              detail: "User already exists",
              existing_user: { email: "ion@ulbsibiu.ro", role: "PROFESSOR" },
            },
            409,
          ),
      },
    });
    await openUsersTab(ctx);
    $("inv-email").value = "ion@ulbsibiu.ro";
    $("inv-form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush();

    expect($("inv-status").textContent).toBe(
      "ion@ulbsibiu.ro is already a registered user (Role: Teacher).",
    );
    expect($("inv-status").className).toBe("notice notice--error");
    expect($("inv-copy-wrap").hidden).toBe(true);
  });

  it("says an invitation is already waiting when the 409 names no account", async () => {
    const ctx = await setup({
      routes: {
        "POST /api/admin/invitations": () =>
          response(
            { detail: "An invitation for this email is already pending." },
            409,
          ),
      },
    });
    await openUsersTab(ctx);
    $("inv-email").value = "reps@club.ro";
    $("inv-form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush();

    expect($("inv-status").textContent).toBe(
      "An invitation for this email is already waiting.",
    );
  });

  it("says the invitation could not be sent for any other failure", async () => {
    const ctx = await setup({
      routes: { "POST /api/admin/invitations": () => response({}, 500) },
    });
    await openUsersTab(ctx);
    $("inv-email").value = "reps@club.ro";
    $("inv-form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush();

    expect($("inv-status").textContent).toBe(
      "The invitation could not be sent. Try again.",
    );
  });

  it("reports a link that could not be copied", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);
    ctx.clipboard.writeText.mockImplementationOnce(() =>
      Promise.reject(new Error("denied")),
    );

    rows("inv-body")[0].querySelectorAll("button")[0].click();
    await flush();

    expect(ctx.toast).toHaveBeenLastCalledWith(
      "The link could not be copied. Try again.",
    );
  });

  it("copies the link of a pending invitation from the list", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    rows("inv-body")[0].querySelectorAll("button")[0].click();
    await flush();

    expect(ctx.clipboard.writeText).toHaveBeenCalledWith(
      `${window.location.origin}/login?invite=T1`,
    );
  });

  it("revokes a pending invitation and refreshes the list", async () => {
    const ctx = await setup({
      routes: { "DELETE /api/admin/invitations/i1": () => response(null, 204) },
    });
    await openUsersTab(ctx);

    rows("inv-body")[0].querySelectorAll("button")[1].click();
    await flush();

    expect(
      requestsTo(ctx.fetch, "DELETE", "/api/admin/invitations/i1"),
    ).toHaveLength(1);
    expect(ctx.toast).toHaveBeenCalledWith("Invitation revoked.");
    expect(
      requestsTo(ctx.fetch, "GET", "/api/admin/invitations").length,
    ).toBeGreaterThan(1);
  });

  it("reports a revoke that is refused", async () => {
    const ctx = await setup({
      routes: {
        "DELETE /api/admin/invitations/i1": () =>
          response({ detail: "no" }, 409),
      },
    });
    await openUsersTab(ctx);

    rows("inv-body")[0].querySelectorAll("button")[1].click();
    await flush();

    expect(ctx.toast).toHaveBeenLastCalledWith(
      "The invitation could not be revoked. Try again.",
    );
  });

  it("says when no invitation is waiting", async () => {
    const ctx = await setup({
      routes: { "GET /api/admin/invitations": () => response([]) },
    });
    await openUsersTab(ctx);

    expect(rows("inv-body")).toHaveLength(0);
    expect($("inv-empty").hidden).toBe(false);
  });

  it("shows a load error when the invitations cannot be loaded", async () => {
    const ctx = await setup({
      routes: { "GET /api/admin/invitations": () => response({}, 500) },
    });
    await openUsersTab(ctx);

    expect($("inv-list-status").textContent).toBe(
      "Could not load the invitations. Try again.",
    );
  });

  it("draws the same rows again when the language changes", async () => {
    const ctx = await setup();
    await openUsersTab(ctx);

    document.dispatchEvent(new Event("unispace:langchange"));
    await flush();

    expect(rows("usr-body")).toHaveLength(2);
    expect(rows("inv-body")).toHaveLength(1);
  });
});

describe("admin-users.js: Romanian", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("writes the labels and the expiry date in Romanian", async () => {
    const ctx = await setup({ language: "ro" });
    $("tab-users").click();
    await flush();

    const [invitation] = rows("inv-body");
    expect(invitation.textContent).toContain("Organizație studențească");
    expect(invitation.querySelector("td:nth-child(3)").textContent).toMatch(
      /2026/,
    );
    expect(ctx.fetch).toHaveBeenCalled();
  });
});

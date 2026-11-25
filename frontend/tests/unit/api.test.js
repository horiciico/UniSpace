import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadScript, queryOf, response, stubFetch } from "../helpers.js";

describe("api.js: fetch wrappers for /api/*", () => {
  let api;

  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/api.js");
    api = window.UniSpaceApi;
  });

  it("calls the same-origin /api path and resolves with the JSON body", async () => {
    const fetch = stubFetch({
      "/api/faculties": () =>
        response([{ id: "f1", code: "dre", name: "Drept" }]),
    });
    await expect(api.faculties()).resolves.toEqual([
      { id: "f1", code: "dre", name: "Drept" },
    ]);
    expect(fetch).toHaveBeenCalledWith("/api/faculties", {
      headers: { Accept: "application/json" },
    });
  });

  it("builds each lookup with its query parameter", async () => {
    const fetch = stubFetch({
      "/api/groups": () => response([]),
      "/api/professors": () => response([]),
      "/api/classrooms": () => response([]),
    });
    await api.groups("f1");
    await api.professors("f1");
    await api.classrooms("campus");
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({ faculty_id: "f1" });
    expect(queryOf(fetch.mock.calls[1][0])).toEqual({ faculty_id: "f1" });
    expect(queryOf(fetch.mock.calls[2][0])).toEqual({ faculty_id: "campus" });
  });

  it("sends the free-room and schedule parameters through the query", async () => {
    const fetch = stubFetch({
      "/api/classrooms/free": () => response([]),
      "/api/schedule": () => response({ items: [] }),
    });
    await api.freeClassrooms({
      faculty_id: "f1",
      start_time: "14:40",
      end_time: "16:10",
      has_projector: true,
    });
    await api.schedule({ room_id: "r1", date: "2026-11-23" });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({
      faculty_id: "f1",
      start_time: "14:40",
      end_time: "16:10",
      has_projector: "true",
    });
    expect(queryOf(fetch.mock.calls[1][0])).toEqual({
      room_id: "r1",
      date: "2026-11-23",
    });
  });

  it("leaves out parameters that are null, undefined, empty or false", async () => {
    const fetch = stubFetch({ "/api/classrooms/free": () => response([]) });
    await api.freeClassrooms({
      faculty_id: null,
      min_capacity: undefined,
      date: "",
      only_verified: false,
      start_time: "10:00",
    });
    expect(fetch.mock.calls[0][0]).toBe(
      "/api/classrooms/free?start_time=10%3A00",
    );
  });

  it("omits the query string when there are no parameters", async () => {
    const fetch = stubFetch({ "/api/faculties": () => response([]) });
    await api.faculties();
    expect(fetch.mock.calls[0][0]).toBe("/api/faculties");
  });

  it("lists the rooms for the admin and sends a PATCH with the changed fields", async () => {
    const fetch = stubFetch({
      "/api/admin/classrooms": () => response([]),
      "/api/admin/classrooms/r1": () => response({ id: "r1" }),
    });
    await api.adminClassrooms("campus");
    await api.patchAdminClassroom("r1", {
      is_bookable: false,
      board_type: null,
    });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({ faculty_id: "campus" });
    expect(fetch.mock.calls[1][0]).toBe("/api/admin/classrooms/r1");
    expect(fetch.mock.calls[1][1].method).toBe("PATCH");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      is_bookable: false,
      board_type: null,
    });
  });

  it("encodes parameter values", async () => {
    const fetch = stubFetch({ "/api/schedule": () => response({}) });
    await api.schedule({ professor: "Ana Pop & Ion" });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({
      professor: "Ana Pop & Ion",
    });
  });

  it("rejects with an Error that carries the HTTP status", async () => {
    stubFetch({ "/api/schedule": () => response({ detail: "boom" }, 500) });
    const error = await api.schedule({ room_id: "r1" }).catch((e) => e);
    expect(error).toBeInstanceOf(Error);
    expect(error.status).toBe(500);
    expect(error.message).toBe("HTTP 500");
  });

  it("sends a signed-out visitor to /login and still rejects", async () => {
    stubFetch({
      "/api/faculties": () => response({ detail: "signed out" }, 401),
    });
    const assign = vi.fn();
    const location = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...location, assign },
    });
    try {
      const error = await api.faculties().catch((e) => e);
      expect(assign).toHaveBeenCalledWith("/login");
      expect(error.status).toBe(401);
    } finally {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: location,
      });
    }
  });

  it("saves the student's faculty and study formation with a PUT and resolves with the user", async () => {
    const fetch = stubFetch({
      "/api/me/study-profile": () =>
        response({ id: "u1", needs_onboarding: false }),
    });
    await expect(api.saveStudyProfile("f1", "g1")).resolves.toEqual({
      id: "u1",
      needs_onboarding: false,
    });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/me/study-profile");
    expect(options.method).toBe("PUT");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({
      faculty_id: "f1",
      study_formation_id: "g1",
    });
  });

  it("rejects a refused save with the HTTP status", async () => {
    stubFetch({
      "/api/me/study-profile": () =>
        response({ detail: "not in the faculty" }, 422),
    });
    const error = await api.saveStudyProfile("f1", "g9").catch((e) => e);
    expect(error.status).toBe(422);
  });

  it("lists my bookings, creates one with a JSON body, and cancels one with DELETE", async () => {
    const fetch = stubFetch({
      "/api/bookings/my": () => response([{ id: "b1" }]),
      "/api/bookings": () => response({ id: "b2", status: "pending" }, 201),
      "/api/bookings/b1": () => response({ id: "b1", status: "cancelled" }),
    });
    await expect(api.myBookings()).resolves.toEqual([{ id: "b1" }]);
    const body = {
      classroom_id: "r1",
      specific_date: "2026-12-14",
      start_time: "08:00",
      end_time: "09:30",
      title: "Club",
    };
    await expect(api.createBooking(body)).resolves.toEqual({
      id: "b2",
      status: "pending",
    });
    await expect(api.cancelBooking("b1")).resolves.toEqual({
      id: "b1",
      status: "cancelled",
    });

    expect(fetch.mock.calls[0][1]).toEqual({
      headers: { Accept: "application/json" },
    });
    expect(fetch.mock.calls[1][1]).toEqual({
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    expect(fetch.mock.calls[2][1]).toEqual({
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
  });
});

describe("api.js: the admin Users tab (C-008)", () => {
  let api;

  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/api.js");
    api = window.UniSpaceApi;
  });

  it("lists users with their filters and paging, leaving out empty ones", async () => {
    const fetch = stubFetch({
      "/api/admin/users": () => response({ items: [], total: 0 }),
    });
    await api.adminUsers({ role: "", search: "ion", limit: 15, offset: 30 });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({
      search: "ion",
      limit: "15",
      offset: "30",
    });
  });

  it("changes a role with a PATCH carrying only the role", async () => {
    const fetch = stubFetch({
      "/api/admin/users/u1/role": () =>
        response({ id: "u1", role: "PROFESSOR" }),
    });
    await expect(api.changeUserRole("u1", "PROFESSOR")).resolves.toEqual({
      id: "u1",
      role: "PROFESSOR",
    });
    expect(fetch.mock.calls[0][1].method).toBe("PATCH");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      role: "PROFESSOR",
    });
  });

  it("lists, creates and revokes invitations", async () => {
    const fetch = vi.fn((url, options) =>
      Promise.resolve(
        options && options.method === "POST"
          ? response({ id: "i1", invite_url: "/login?invite=t" }, 201)
          : response([{ id: "i1" }]),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    await expect(api.adminInvitations()).resolves.toEqual([{ id: "i1" }]);
    await expect(
      api.createInvitation({ email: "a@b.ro", role: "STUDENT_ORG" }),
    ).resolves.toEqual({ id: "i1", invite_url: "/login?invite=t" });
    expect(fetch.mock.calls[1][1].method).toBe("POST");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      email: "a@b.ro",
      role: "STUDENT_ORG",
    });
  });

  it("resolves a revoke with nothing, since the backend answers 204 with no body", async () => {
    stubFetch({});
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 204,
          json: () => Promise.reject(new SyntaxError("no body")),
        }),
      ),
    );
    await expect(api.revokeInvitation("i 1")).resolves.toBeNull();
  });

  it("gives a refused request its JSON body, for the 409 message", async () => {
    stubFetch({
      "/api/admin/invitations": () =>
        response(
          {
            detail: "User already exists",
            existing_user: { email: "ion@ulbsibiu.ro", role: "PROFESSOR" },
          },
          409,
        ),
    });
    const error = await api
      .createInvitation({ email: "ion@ulbsibiu.ro", role: "STUDENT" })
      .catch((e) => e);
    expect(error.status).toBe(409);
    expect(error.body.existing_user).toEqual({
      email: "ion@ulbsibiu.ro",
      role: "PROFESSOR",
    });
  });

  it("still refuses with the status when the refused body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.reject(new SyntaxError("html")),
        }),
      ),
    );
    const error = await api.adminUsers({}).catch((e) => e);
    expect(error.status).toBe(500);
    expect(error.body).toBeNull();
  });
});

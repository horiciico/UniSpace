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
    const fetch = stubFetch({ "/api/faculties": () => response([{ id: "f1", code: "dre", name: "Drept" }]) });
    await expect(api.faculties()).resolves.toEqual([{ id: "f1", code: "dre", name: "Drept" }]);
    expect(fetch).toHaveBeenCalledWith("/api/faculties", { headers: { Accept: "application/json" } });
  });

  it("builds each lookup with its query parameter", async () => {
    const fetch = stubFetch({
      "/api/groups": () => response([]),
      "/api/professors": () => response([]),
      "/api/classrooms": () => response([])
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
      "/api/schedule": () => response({ items: [] })
    });
    await api.freeClassrooms({ faculty_id: "f1", start_time: "14:40", end_time: "16:10", has_projector: true });
    await api.schedule({ room_id: "r1", date: "2026-11-23" });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({
      faculty_id: "f1", start_time: "14:40", end_time: "16:10", has_projector: "true"
    });
    expect(queryOf(fetch.mock.calls[1][0])).toEqual({ room_id: "r1", date: "2026-11-23" });
  });

  it("leaves out parameters that are null, undefined, empty or false", async () => {
    const fetch = stubFetch({ "/api/classrooms/free": () => response([]) });
    await api.freeClassrooms({ faculty_id: null, min_capacity: undefined, date: "", only_verified: false, start_time: "10:00" });
    expect(fetch.mock.calls[0][0]).toBe("/api/classrooms/free?start_time=10%3A00");
  });

  it("omits the query string when there are no parameters", async () => {
    const fetch = stubFetch({ "/api/faculties": () => response([]) });
    await api.faculties();
    expect(fetch.mock.calls[0][0]).toBe("/api/faculties");
  });

  it("encodes parameter values", async () => {
    const fetch = stubFetch({ "/api/schedule": () => response({}) });
    await api.schedule({ professor: "Ana Pop & Ion" });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({ professor: "Ana Pop & Ion" });
  });

  it("rejects with an Error that carries the HTTP status", async () => {
    stubFetch({ "/api/schedule": () => response({ detail: "boom" }, 500) });
    const error = await api.schedule({ room_id: "r1" }).catch((e) => e);
    expect(error).toBeInstanceOf(Error);
    expect(error.status).toBe(500);
    expect(error.message).toBe("HTTP 500");
  });

  it("sends a signed-out visitor to /login and still rejects", async () => {
    stubFetch({ "/api/faculties": () => response({ detail: "signed out" }, 401) });
    const assign = vi.fn();
    const location = window.location;
    Object.defineProperty(window, "location", { configurable: true, value: { ...location, assign } });
    try {
      const error = await api.faculties().catch((e) => e);
      expect(assign).toHaveBeenCalledWith("/login");
      expect(error.status).toBe(401);
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: location });
    }
  });

  it("saves the student's faculty and study formation with a PUT and resolves with the user", async () => {
    const fetch = stubFetch({ "/api/me/study-profile": () => response({ id: "u1", needs_onboarding: false }) });
    await expect(api.saveStudyProfile("f1", "g1")).resolves.toEqual({ id: "u1", needs_onboarding: false });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/me/study-profile");
    expect(options.method).toBe("PUT");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ faculty_id: "f1", study_formation_id: "g1" });
  });

  it("rejects a refused save with the HTTP status", async () => {
    stubFetch({ "/api/me/study-profile": () => response({ detail: "not in the faculty" }, 422) });
    const error = await api.saveStudyProfile("f1", "g9").catch((e) => e);
    expect(error.status).toBe(422);
  });

  it("lists my bookings, creates one with a JSON body, and cancels one with DELETE", async () => {
    const fetch = stubFetch({
      "/api/bookings/my": () => response([{ id: "b1" }]),
      "/api/bookings": () => response({ id: "b2", status: "pending" }, 201),
      "/api/bookings/b1": () => response({ id: "b1", status: "cancelled" })
    });
    await expect(api.myBookings()).resolves.toEqual([{ id: "b1" }]);
    const body = { classroom_id: "r1", specific_date: "2026-12-14", start_time: "08:00", end_time: "09:30", title: "Club" };
    await expect(api.createBooking(body)).resolves.toEqual({ id: "b2", status: "pending" });
    await expect(api.cancelBooking("b1")).resolves.toEqual({ id: "b1", status: "cancelled" });

    expect(fetch.mock.calls[0][1]).toEqual({ headers: { Accept: "application/json" } });
    expect(fetch.mock.calls[1][1]).toEqual({
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    expect(fetch.mock.calls[2][1]).toEqual({ method: "DELETE", headers: { Accept: "application/json" } });
  });
});

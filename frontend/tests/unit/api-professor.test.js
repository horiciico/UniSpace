import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadScript, queryOf, response, stubFetch } from "../helpers.js";

// The professor's wrappers in js/api.js (C-009).
describe("api.js: the professor's own timetable, availability and move", () => {
  let api;

  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/api.js");
    api = window.UniSpaceApi;
  });

  it("asks for the week of the timetable", async () => {
    const fetch = stubFetch({
      "/api/professors/me/timetable": () =>
        response({ linked: true, activities: [] }),
    });

    await expect(api.professorTimetable("2026-11-23")).resolves.toEqual({
      linked: true,
      activities: [],
    });
    expect(queryOf(fetch.mock.calls[0][0])).toEqual({
      week_start: "2026-11-23",
    });
  });

  it("lists the movable activities", async () => {
    const fetch = stubFetch({
      "/api/professors/me/movable-activities": () =>
        response({ linked: false, activities: [] }),
    });

    await expect(api.movableActivities()).resolves.toEqual({
      linked: false,
      activities: [],
    });
    expect(fetch.mock.calls[0][0]).toBe(
      "/api/professors/me/movable-activities",
    );
  });

  it("repeats group_ids for each group and leaves out an empty exclusion", async () => {
    const fetch = stubFetch({
      "/api/professors/me/availability": () => response({ modules: [] }),
    });

    await api.professorAvailability("2026-11-24", ["g1", "g2"], null);

    const url = fetch.mock.calls[0][0];
    expect(url).toBe(
      "/api/professors/me/availability?date=2026-11-24&group_ids=g1&group_ids=g2",
    );
    expect(fetch.mock.calls[0][1]).toEqual({
      headers: { Accept: "application/json" },
    });
  });

  it("sends the excluded activity and no groups when there are none", async () => {
    const fetch = stubFetch({
      "/api/professors/me/availability": () => response({ modules: [] }),
    });

    await api.professorAvailability("2026-11-24", undefined, "a1");

    expect(fetch.mock.calls[0][0]).toBe(
      "/api/professors/me/availability?date=2026-11-24&exclude_activity_id=a1",
    );
  });

  it("posts the move to the activity's own path, with the body as JSON", async () => {
    const body = {
      original_date: "2026-11-23",
      new_date: "2026-11-24",
      start_time: "09:40",
      end_time: "11:10",
      new_classroom_id: "r1",
    };
    const fetch = stubFetch({
      "/api/professors/me/activities/a%201/move": () =>
        response({ id: "n1", date: "2026-11-24" }),
    });

    await expect(api.moveActivity("a 1", body)).resolves.toEqual({
      id: "n1",
      date: "2026-11-24",
    });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/professors/me/activities/a%201/move");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual(body);
  });

  it("rejects a refused move with its status and the body the backend sent", async () => {
    stubFetch({
      "/api/professors/me/activities/a1/move": () =>
        response({ detail: "The room is taken." }, 409),
    });

    const error = await api
      .moveActivity("a1", { original_date: "x" })
      .catch((failure) => failure);

    expect(error.status).toBe(409);
    expect(error.body).toEqual({ detail: "The room is taken." });
  });
});

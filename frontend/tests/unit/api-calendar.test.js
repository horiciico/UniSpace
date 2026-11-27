import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadScript, response, stubFetch } from "../helpers.js";

describe("api.js: the academic calendar (C-010)", () => {
  let api;

  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/api.js");
    api = window.UniSpaceApi;
  });

  const body = {
    name: "Sesiune",
    type: "EXAM_SESSION",
    start_date: "2027-01-11",
    end_date: "2027-02-07",
  };

  it("reads the periods for everyone and for the admin", async () => {
    const fetch = stubFetch({
      "/api/academic-periods": () => response([{ id: "p1" }]),
      "/api/admin/academic-periods": () => response([{ id: "p2" }]),
    });

    await expect(api.academicPeriods()).resolves.toEqual([{ id: "p1" }]);
    await expect(api.adminAcademicPeriods()).resolves.toEqual([{ id: "p2" }]);
    expect(fetch.mock.calls[0][0]).toBe("/api/academic-periods");
    expect(fetch.mock.calls[1][0]).toBe("/api/admin/academic-periods");
  });

  it("creates, updates and deletes a period", async () => {
    const fetch = stubFetch({
      "/api/admin/academic-periods": () => response({ id: "p1" }, 201),
      "/api/admin/academic-periods/p%2F1": () => response(null, 204),
    });

    await api.createAcademicPeriod(body);
    await api.updateAcademicPeriod("p/1", body);
    await expect(api.deleteAcademicPeriod("p/1")).resolves.toBeNull();

    expect(fetch.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(body);
    expect(fetch.mock.calls[1][0]).toBe("/api/admin/academic-periods/p%2F1");
    expect(fetch.mock.calls[1][1].method).toBe("PUT");
    expect(fetch.mock.calls[2][1].method).toBe("DELETE");
  });
});

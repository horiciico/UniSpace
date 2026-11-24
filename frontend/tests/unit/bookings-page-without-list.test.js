import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// A page without its request list does nothing: the script stops at once and calls no API.
describe("bookings page: a page without its request list", () => {
  beforeEach(() => vi.resetModules());
  afterEach(() => {
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("stops without calling the API", async () => {
    mountPage("pages/shared/bookings.html");
    document.getElementById("bk-list").remove();
    await loadI18n("en");
    await loadScript("js/modules.js");
    await loadScript("js/api.js");
    await loadScript("js/bookings.js");
    const fetch = stubFetch({ "/api/faculties": () => response([]) });
    await loadScript("js/auth.js");
    await loadScript("js/pages/bookings.js");
    await flush();

    expect(fetch.mock.calls.map((c) => c[0])).not.toContain("/api/faculties");
    expect(document.getElementById("bk-form")).not.toBeNull();
  });
});

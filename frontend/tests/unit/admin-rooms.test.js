import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// Admin: the Rooms tab (admin attributes of a room, C-007). Lazy: the rooms load when the tab opens.
const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const ROOMS = [
  { id: "r1", name: "B110", faculty_id: "f1", capacity: 30, is_bookable: true, has_projector: true,
    board_type: "smartboard", access_notes: "Cheia la portar", equipment_notes: "24 PC-uri" },
  { id: "r2", name: "L2", faculty_id: null, capacity: null, is_bookable: false, has_projector: null,
    board_type: null, access_notes: null, equipment_notes: null },
  { id: "r3", name: "S7", faculty_id: "f1", capacity: 50, is_bookable: true, has_projector: false,
    board_type: "whiteboard", access_notes: null, equipment_notes: null }
];

async function setup({ rooms = ROOMS, routes = {} } = {}) {
  mountPage("pages/admin/index.html");
  await loadI18n("en");
  window.UniSpaceI18n.setLanguage("en");
  window.UniSpaceI18n.apply(document.body);
  const fetch = stubFetch({
    "/api/admin/bookings/pending": () => response([]),
    "/api/admin/bookings": () => response({ items: [], total: 0, limit: 15, offset: 0 }),
    "/api/faculties": () => response(FACULTIES),
    "/api/admin/classrooms": () => response(rooms),
    ...routes
  });
  await loadScript("js/api.js");
  await loadScript("js/bookings.js");
  await loadScript("js/pages/admin-history.js");
  await loadScript("js/pages/admin-rooms.js");
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const tab = (name) => document.querySelector(`[role="tab"][data-tab="${name}"]`);
const rows = () => [...document.querySelectorAll("#rooms-body > tr")];
const cellsOf = (row) => [...row.querySelectorAll("td")].map((cell) => cell.textContent);
const roomCalls = (fetch) => fetch.mock.calls.filter(([url]) => new URL(url, "http://x").pathname === "/api/admin/classrooms");
const patchCalls = (fetch) => fetch.mock.calls.filter(([, options]) => options && options.method === "PATCH");
const openRooms = async () => {
  tab("rooms").click();
  await flush();
};
const editButton = (name) => document.querySelector(`[aria-label="Edit room ${name}"]`);

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  document.body.innerHTML = "";
  document.querySelectorAll("script").forEach((node) => node.remove());
});

describe("admin Rooms tab", () => {
  it("loads the rooms only when the tab is opened, and shows the rooms panel on its own", async () => {
    const { fetch } = await setup();
    expect(roomCalls(fetch)).toHaveLength(0);
    await openRooms();
    expect(roomCalls(fetch)).toHaveLength(1);
    expect($("panel-rooms").hidden).toBe(false);
    expect($("panel-history").hidden).toBe(true);
    expect($("panel-pending").hidden).toBe(true);
    expect(rows()).toHaveLength(3);
  });

  it("switching to another tab hides the rooms panel", async () => {
    await setup();
    await openRooms();
    tab("history").click();
    await flush();
    expect($("panel-rooms").hidden).toBe(true);
    expect($("panel-history").hidden).toBe(false);
  });

  it("shows each room's attributes, and says when a value is unspecified", async () => {
    await setup();
    await openRooms();
    expect(cellsOf(rows()[0]).slice(0, 7)).toEqual(
      ["B110", "Facultatea de Drept", "30", "Yes", "Yes", "Smartboard", "Cheia la portar"]
    );
    expect(cellsOf(rows()[1]).slice(0, 7)).toEqual(
      ["L2", "Campus", "Unknown capacity", "No", "Unspecified", "Unspecified", "Unspecified"]
    );
    expect(cellsOf(rows()[2]).slice(0, 7)).toEqual(
      ["S7", "Facultatea de Drept", "50", "Yes", "No", "Whiteboard", "Unspecified"]
    );
  });

  it("reloads the rooms for the chosen faculty, campus, or all faculties", async () => {
    const { fetch } = await setup();
    await openRooms();
    const faculty = $("rooms-faculty");
    faculty.value = "f1";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    expect(new URL(roomCalls(fetch).at(-1)[0], "http://x").searchParams.get("faculty_id")).toBe("f1");
    faculty.value = "campus";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    expect(new URL(roomCalls(fetch).at(-1)[0], "http://x").searchParams.get("faculty_id")).toBe("campus");
    faculty.value = "";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    expect(new URL(roomCalls(fetch).at(-1)[0], "http://x").searchParams.has("faculty_id")).toBe(false);
  });

  it("searches by room name, ignoring case, and says when nothing matches", async () => {
    await setup();
    await openRooms();
    const search = $("rooms-search");
    search.value = "s7";
    search.dispatchEvent(new Event("input"));
    expect(rows().map((row) => cellsOf(row)[0])).toEqual(["S7"]);
    expect($("rooms-empty").hidden).toBe(true);
    search.value = "zzz";
    search.dispatchEvent(new Event("input"));
    expect(rows()).toHaveLength(0);
    expect($("rooms-empty").hidden).toBe(false);
    search.value = "";
    search.dispatchEvent(new Event("input"));
    expect(rows()).toHaveLength(3);
    expect($("rooms-empty").hidden).toBe(true);
  });

  it("opens the editor with the room's current values", async () => {
    await setup();
    await openRooms();
    editButton("B110").click();
    expect($("rooms-edit").hidden).toBe(false);
    expect($("rooms-edit-title").textContent).toBe("Edit room B110");
    expect($("rooms-bookable").checked).toBe(true);
    expect($("rooms-projector").value).toBe("yes");
    expect($("rooms-board").value).toBe("smartboard");
    expect($("rooms-access").value).toBe("Cheia la portar");
    expect($("rooms-equipment").value).toBe("24 PC-uri");

    editButton("L2").click();
    expect($("rooms-projector").value).toBe("");
    expect($("rooms-board").value).toBe("");
    expect($("rooms-access").value).toBe("");
    expect($("rooms-bookable").checked).toBe(false);

    editButton("S7").click();
    expect($("rooms-projector").value).toBe("no");
    expect($("rooms-board").value).toBe("whiteboard");
  });

  it("scrolls to the edit section when clicking edit", async () => {
    await setup();
    await openRooms();
    const scrollIntoView = vi.fn();
    $("rooms-edit").scrollIntoView = scrollIntoView;
    editButton("B110").click();
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
  });

  it("an older answer does not replace a newer one", async () => {
    const pending = [];
    await setup({
      routes: {
        "/api/admin/classrooms": () => new Promise((resolve) => pending.push(resolve))
      }
    });
    tab("rooms").click();
    await flush();
    const faculty = $("rooms-faculty");
    faculty.value = "f1";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    pending[1](response([ROOMS[0]]));
    await flush();
    pending[0](response(ROOMS));
    await flush();
    expect(rows().map((row) => cellsOf(row)[0])).toEqual(["B110"]);
  });

  it("saves the form, sends null for unspecified values, and shows the new values", async () => {
    const saved = { ...ROOMS[1], is_bookable: true, has_projector: false, board_type: "blackboard",
      access_notes: "Portar", equipment_notes: "" };
    const { fetch } = await setup({ routes: { "/api/admin/classrooms/r2": () => response(saved) } });
    await openRooms();
    editButton("L2").click();
    $("rooms-bookable").checked = true;
    $("rooms-projector").value = "no";
    $("rooms-board").value = "blackboard";
    $("rooms-access").value = "Portar";
    $("rooms-equipment").value = "";
    $("rooms-save").click();
    await flush();

    const [url, options] = patchCalls(fetch)[0];
    expect(url).toBe("/api/admin/classrooms/r2");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({
      is_bookable: true, has_projector: false, board_type: "blackboard", access_notes: "Portar", equipment_notes: ""
    });
    expect($("rooms-status").textContent).toBe("Room saved.");
    expect($("rooms-edit").hidden).toBe(true);
    expect(cellsOf(rows()[1]).slice(0, 7)).toEqual(
      ["L2", "Campus", "Unknown capacity", "Yes", "No", "Blackboard", "Portar"]
    );
  });

  it("sends null when the projector and the board are set back to unspecified", async () => {
    const { fetch } = await setup({ routes: { "/api/admin/classrooms/r1": () => response({ ...ROOMS[0], has_projector: null, board_type: null }) } });
    await openRooms();
    editButton("B110").click();
    $("rooms-projector").value = "";
    $("rooms-board").value = "";
    $("rooms-save").click();
    await flush();
    expect(JSON.parse(patchCalls(fetch)[0][1].body)).toMatchObject({ has_projector: null, board_type: null });
  });

  it("explains a rejected save and keeps the editor open", async () => {
    await setup({ routes: { "/api/admin/classrooms/r1": () => response({ detail: "bad" }, 422) } });
    await openRooms();
    editButton("B110").click();
    $("rooms-save").click();
    await flush();
    expect($("rooms-status").textContent).toBe(
      "Check the values: notes are up to 255 characters for access and 500 for equipment."
    );
    expect($("rooms-edit").hidden).toBe(false);
  });

  it("says that the save failed for any other error", async () => {
    await setup({ routes: { "/api/admin/classrooms/r1": () => response({}, 500) } });
    await openRooms();
    editButton("B110").click();
    $("rooms-save").click();
    await flush();
    expect($("rooms-status").textContent).toBe("Could not save the room. Try again.");
    expect($("rooms-status").className).toBe("notice notice--error");
  });

  it("cancel closes the editor without a request", async () => {
    const { fetch } = await setup();
    await openRooms();
    editButton("B110").click();
    $("rooms-cancel").click();
    expect($("rooms-edit").hidden).toBe(true);
    expect(patchCalls(fetch)).toHaveLength(0);
  });

  it("says when the rooms cannot be loaded", async () => {
    await setup({ routes: { "/api/admin/classrooms": () => response({}, 500) } });
    await openRooms();
    expect($("rooms-status").textContent).toBe("Could not load the rooms. Try again.");
    expect(rows()).toHaveLength(0);
  });

  it("says when the faculties cannot be loaded", async () => {
    await setup({ routes: { "/api/faculties": () => response({}, 500) } });
    await openRooms();
    expect($("rooms-status").textContent).toBe("Could not load the rooms. Try again.");
  });

  it("rebuilds its labels when the language changes, with or without an open editor", async () => {
    await setup();
    await openRooms();
    window.UniSpaceI18n.setLanguage("ro");
    window.UniSpaceI18n.apply(document.body);
    document.dispatchEvent(new Event("unispace:langchange"));
    await flush();
    expect(cellsOf(rows()[0]).slice(3, 6)).toEqual(["Da", "Da", "Tablă interactivă"]);
    expect($("rooms-edit").hidden).toBe(true);

    rows()[0].querySelector("button").click();
    expect($("rooms-edit-title").textContent).toBe("Editează sala B110");
    window.UniSpaceI18n.setLanguage("en");
    window.UniSpaceI18n.apply(document.body);
    document.dispatchEvent(new Event("unispace:langchange"));
    await flush();
    expect($("rooms-edit-title").textContent).toBe("Edit room B110");
    expect($("rooms-edit").hidden).toBe(false);
  });
});

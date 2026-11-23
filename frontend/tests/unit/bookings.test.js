import { beforeEach, describe, expect, it } from "vitest";
import { loadScript } from "../helpers.js";

const FACULTY = "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b";
const ROOM = "7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f";

describe("bookings.js: the Bookings page link and status labels", () => {
  let bookings;

  beforeEach(async () => {
    await loadScript("js/bookings.js");
    bookings = window.UniSpaceBookings;
  });

  it("builds the link with only the values that are set", () => {
    expect(bookings.link({ faculty_id: FACULTY, room: ROOM, date: "2026-12-14", start: "08:00", end: "09:30" }))
      .toBe(`/bookings/?faculty_id=${FACULTY}&room=${ROOM}&date=2026-12-14&start=08%3A00&end=09%3A30`);
    expect(bookings.link({})).toBe("/bookings/");
    expect(bookings.link({ room: ROOM, date: "" })).toBe(`/bookings/?room=${ROOM}`);
  });

  it("reads the link back, keeping the campus value", () => {
    const search = `?faculty_id=campus&room=${ROOM}&date=2026-12-14&start=08:00&end=09:30`;
    expect(bookings.readPrefill(search)).toEqual({
      faculty_id: "campus", room: ROOM, date: "2026-12-14", start: "08:00", end: "09:30"
    });
  });

  it("reads a faculty id and drops values that are not in the right shape", () => {
    const search = `?faculty_id=${FACULTY}&room=not-a-uuid&date=14.12.2026&start=8:00&end=25:00`;
    expect(bookings.readPrefill(search)).toEqual({
      faculty_id: FACULTY, room: "", date: "", start: "", end: ""
    });
  });

  it("reads nothing from an empty query", () => {
    expect(bookings.readPrefill("")).toEqual({ faculty_id: "", room: "", date: "", start: "", end: "" });
  });

  it("maps each status to its label key and pill", () => {
    expect(bookings.statusInfo("pending")).toEqual({ key: "bookings.statusPending", pill: "pill--pending" });
    expect(bookings.statusInfo("approved")).toEqual({ key: "status.approved", pill: "pill--approved" });
    expect(bookings.statusInfo("rejected")).toEqual({ key: "bookings.statusRejected", pill: "pill--rejected" });
    expect(bookings.statusInfo("cancelled")).toEqual({ key: "status.cancelled", pill: "pill" });
    expect(bookings.statusInfo("weird")).toEqual({ key: null, pill: "pill" });
  });

  it("allows cancelling a pending booking only", () => {
    expect(bookings.canCancel({ status: "pending" })).toBe(true);
    expect(bookings.canCancel({ status: "approved" })).toBe(false);
    expect(bookings.canCancel({ status: "cancelled" })).toBe(false);
  });
});

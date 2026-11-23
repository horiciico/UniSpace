/*
 * Room booking helpers that do not touch the page: the link that opens the Bookings page with
 * a room, a date and a window filled in, the reading of that link, and the status labels.
 * The URL is the contract between the timetable, Free Now and the Bookings page:
 *   /bookings/?faculty_id=UUID|campus&room=UUID&date=YYYY-MM-DD&start=HH:MM&end=HH:MM
 * Every value is optional. A value that is not in the right shape is dropped when read.
 */
(function () {
  "use strict";

  var DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
  var TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
  var UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  // Status word (the backend's value) -> the i18n key of its label and the pill class.
  var STATUSES = {
    pending: { key: "bookings.statusPending", pill: "pill--pending" },
    approved: { key: "status.approved", pill: "pill--approved" },
    rejected: { key: "bookings.statusRejected", pill: "pill--rejected" },
    cancelled: { key: "status.cancelled", pill: "pill" }
  };

  // Builds the Bookings page link. Empty values are left out.
  function bookingLink(values) {
    var params = new URLSearchParams();
    if (values.faculty_id) params.set("faculty_id", values.faculty_id);
    if (values.room) params.set("room", values.room);
    if (values.date) params.set("date", values.date);
    if (values.start) params.set("start", values.start);
    if (values.end) params.set("end", values.end);
    var query = params.toString();
    return "/bookings/" + (query ? "?" + query : "");
  }

  // Reads the link's parameters. Anything not in the right shape comes back as "".
  function readPrefill(search) {
    var params = new URLSearchParams(search);
    function pick(name, pattern) {
      var value = params.get(name) || "";
      return pattern.test(value) ? value : "";
    }
    var faculty = params.get("faculty_id") || "";
    return {
      faculty_id: faculty === "campus" ? "campus" : pick("faculty_id", UUID_PATTERN),
      room: pick("room", UUID_PATTERN),
      date: pick("date", DATE_PATTERN),
      start: pick("start", TIME_PATTERN),
      end: pick("end", TIME_PATTERN)
    };
  }

  // The label key and pill class of a booking status. An unknown status has no label.
  function statusInfo(status) {
    return STATUSES[status] || { key: null, pill: "pill" };
  }

  // Only a pending booking can be cancelled by its owner (C-005).
  function canCancel(booking) {
    return booking.status === "pending";
  }

  window.UniSpaceBookings = {
    link: bookingLink,
    readPrefill: readPrefill,
    statusInfo: statusInfo,
    canCancel: canCancel
  };
})();

/*
 * Fetch wrappers for the backend API (/api/...). Same origin: nginx proxies /api/ to the
 * backend. Each call resolves with the parsed JSON, or rejects with an Error whose
 * `status` is the HTTP status. Parameters that are null, empty or false are left out
 * (true is sent as "true").
 */
(() => {
  function query(params) {
    var parts = [];
    Object.keys(params || {}).forEach((key) => {
      var value = params[key];
      if (
        value === null ||
        value === undefined ||
        value === "" ||
        value === false
      )
        return;
      var text = value === true ? "true" : String(value);
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(text));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  // One request to /api. A 401 sends the visitor to sign in again; any other failure rejects.
  function call(path, options) {
    return fetch("/api" + path, options).then((response) => {
      if (response.status === 401) {
        // Signed out (the session ended): send the visitor to sign in again.
        window.location.assign("/login");
      }
      if (!response.ok) {
        const error = /** @type {Error & { status?: number }} */ (
          new Error("HTTP " + response.status)
        );
        error.status = response.status;
        throw error;
      }
      return response.json();
    });
  }

  function get(path, params) {
    return call(path + query(params), {
      headers: { Accept: "application/json" },
    });
  }

  // A request with a JSON body (PUT, POST) or without one (DELETE).
  function send(method, path, body) {
    var options = { method: method, headers: { Accept: "application/json" } };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    return call(path, options);
  }

  window.UniSpaceApi = {
    faculties: () => get("/faculties"),
    groups: (facultyId) => get("/groups", { faculty_id: facultyId }),
    professors: (facultyId) => get("/professors", { faculty_id: facultyId }),
    classrooms: (facultyId) => get("/classrooms", { faculty_id: facultyId }),
    freeClassrooms: (params) => get("/classrooms/free", params),
    schedule: (params) => get("/schedule", params),
    // The student's faculty and study formation (D-022). Resolves with the user.
    saveStudyProfile: (facultyId, formationId) =>
      send("PUT", "/me/study-profile", {
        faculty_id: facultyId,
        study_formation_id: formationId,
      }),
    // Room bookings (C-005). Your own bookings, upcoming first.
    myBookings: () => get("/bookings/my"),
    // A booking request: { classroom_id, specific_date, start_time, end_time, title }. Resolves with the booking.
    createBooking: (body) => send("POST", "/bookings", body),
    // Cancels your own pending booking. Resolves with the booking, now cancelled.
    // Admin review of booking requests (C-006). Only an administrator gets an answer.
    pendingBookings: () => get("/admin/bookings/pending"),
    // Booking history (admin, C-006): one page of bookings. params: limit, offset, faculty_id, classroom_id, status.
    adminBookings: (params) => get("/admin/bookings", params),
    // Cancels a future approved booking (any user's): it becomes rejected. body: { message? }.
    // Resolves with the booking.
    adminCancelBooking: (id, body) =>
      send(
        "POST",
        "/admin/bookings/" + encodeURIComponent(id) + "/cancel",
        body,
      ),
    // Rooms for the admin Rooms tab (C-007). params: faculty_id (UUID or "campus"). Resolves with the rooms.
    adminClassrooms: (facultyId) =>
      get("/admin/classrooms", { faculty_id: facultyId }),
    // Changes only the fields sent: { is_bookable?, has_projector?, board_type?, access_notes?, equipment_notes? }.
    // A null clears a field. Resolves with the room.
    patchAdminClassroom: (id, body) =>
      send("PATCH", "/admin/classrooms/" + encodeURIComponent(id), body),
    // Decides a request: { decision: "approve" | "reject", message? }. Resolves with the booking.
    decideBooking: (id, body) =>
      send(
        "POST",
        "/admin/bookings/" + encodeURIComponent(id) + "/decision",
        body,
      ),
    cancelBooking: (id) =>
      send("DELETE", "/bookings/" + encodeURIComponent(id)),
  };
})();

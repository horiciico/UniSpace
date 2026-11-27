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

  // One request to /api. A 401 sends the visitor to sign in again; any other failure rejects
  // with the HTTP status and, when the answer is JSON, its body (`error.body`, for example
  // the 409 that names an existing user). A 204 answer resolves with null.
  function call(path, options) {
    return fetch("/api" + path, options).then((response) => {
      if (response.status === 401) {
        // Signed out (the session ended): send the visitor to sign in again.
        window.location.assign("/login");
      }
      if (response.status === 204) return null;
      if (!response.ok) {
        return response
          .json()
          .catch(() => null)
          .then((body) => {
            const error =
              /** @type {Error & { status?: number, body?: any }} */ (
                new Error("HTTP " + response.status)
              );
            error.status = response.status;
            error.body = body;
            throw error;
          });
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
    // The signed-in professor's own week (C-009). Resolves with { linked, professor_id, week_start, week_end, activities }.
    professorTimetable: (weekStart) =>
      get("/professors/me/timetable", { week_start: weekStart }),
    // The activities the professor may move: { linked, activities } (C-009).
    movableActivities: () => get("/professors/me/movable-activities"),
    // The modules of a day for the professor and the groups (repeated group_ids, C-009).
    professorAvailability: (day, groupIds, excludeActivityId) =>
      call(
        "/professors/me/availability" +
          query({ date: day, exclude_activity_id: excludeActivityId }) +
          (groupIds || [])
            .map((id) => "&group_ids=" + encodeURIComponent(id))
            .join(""),
        { headers: { Accept: "application/json" } },
      ),
    // Schedule Exam (C-011). The professor's subjects: { linked, subjects: [{ name, groups }] }.
    professorSubjects: () => get("/professors/me/subjects"),
    // Whether a day's start-end suits the groups: exam_session, available, conflict_reason, rooms.
    professorInterval: (day, start, end, groupIds) =>
      call(
        "/professors/me/availability/interval" +
          query({ date: day, start_time: start, end_time: end }) +
          groupIds.map((id) => "&group_ids=" + encodeURIComponent(id)).join(""),
        { headers: { Accept: "application/json" } },
      ),
    // body: { subject_name, group_ids, exam_date, start_time, end_time, classroom_id }.
    scheduleExam: (body) => send("POST", "/professors/me/exams", body),
    // Moves one occurrence (C-009): { original_date, new_date, start_time, end_time, new_classroom_id }.
    moveActivity: (id, body) =>
      send(
        "POST",
        "/professors/me/activities/" + encodeURIComponent(id) + "/move",
        body,
      ),
    // The student's faculty and study formation (D-022). Resolves with the user.
    saveStudyProfile: (facultyId, formationId) =>
      send("PUT", "/me/study-profile", {
        faculty_id: facultyId,
        study_formation_id: formationId,
      }),
    // The academic calendar (C-010): every period, by start date: [{ id, name, type, start_date, end_date }].
    academicPeriods: () => get("/academic-periods"),
    // The same list for the admin, and its create, update and delete (C-010). body: { name, type, start_date, end_date }.
    adminAcademicPeriods: () => get("/admin/academic-periods"),
    createAcademicPeriod: (body) =>
      send("POST", "/admin/academic-periods", body),
    updateAcademicPeriod: (id, body) =>
      send("PUT", "/admin/academic-periods/" + encodeURIComponent(id), body),
    deleteAcademicPeriod: (id) =>
      send("DELETE", "/admin/academic-periods/" + encodeURIComponent(id)),
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
    // Users for the admin Users tab (C-008). params: role, search, limit, offset. Resolves with {items, total, limit, offset}.
    adminUsers: (params) => get("/admin/users", params),
    // Sets a non-admin role. Resolves with the user.
    changeUserRole: (id, role) =>
      send("PATCH", "/admin/users/" + encodeURIComponent(id) + "/role", {
        role: role,
      }),
    // Pending invitations, newest first. Each carries its invite_url.
    adminInvitations: () => get("/admin/invitations"),
    // Invites an email with a role: { email, role }. Resolves with the invitation (201).
    createInvitation: (body) => send("POST", "/admin/invitations", body),
    // Revokes a pending invitation. Resolves with null (204).
    revokeInvitation: (id) =>
      send("DELETE", "/admin/invitations/" + encodeURIComponent(id)),
  };
})();

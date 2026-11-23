/*
 * Fetch wrappers for the backend API (/api/...). Same origin: nginx proxies /api/ to the
 * backend. Each call resolves with the parsed JSON, or rejects with an Error whose
 * `status` is the HTTP status. Parameters that are null, empty or false are left out
 * (true is sent as "true").
 */
(function () {
  "use strict";

  function query(params) {
    var parts = [];
    Object.keys(params || {}).forEach(function (key) {
      var value = params[key];
      if (value === null || value === undefined || value === "" || value === false) return;
      var text = value === true ? "true" : String(value);
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(text));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  // One request to /api. A 401 sends the visitor to sign in again; any other failure rejects.
  function call(path, options) {
    return fetch("/api" + path, options)
      .then(function (response) {
        if (response.status === 401) {
          // Signed out (the session ended): send the visitor to sign in again.
          window.location.assign("/login");
        }
        if (!response.ok) {
          var error = new Error("HTTP " + response.status);
          error.status = response.status;
          throw error;
        }
        return response.json();
      });
  }

  function get(path, params) {
    return call(path + query(params), { headers: { Accept: "application/json" } });
  }

  function put(path, body) {
    return call(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body)
    });
  }

  window.UniSpaceApi = {
    faculties: function () {
      return get("/faculties");
    },
    groups: function (facultyId) {
      return get("/groups", { faculty_id: facultyId });
    },
    professors: function (facultyId) {
      return get("/professors", { faculty_id: facultyId });
    },
    classrooms: function (facultyId) {
      return get("/classrooms", { faculty_id: facultyId });
    },
    freeClassrooms: function (params) {
      return get("/classrooms/free", params);
    },
    schedule: function (params) {
      return get("/schedule", params);
    },
    // The student's faculty and study formation (D-022). Resolves with the user.
    saveStudyProfile: function (facultyId, formationId) {
      return put("/me/study-profile", { faculty_id: facultyId, study_formation_id: formationId });
    }
  };
})();

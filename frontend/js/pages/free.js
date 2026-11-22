/*
 * Liber acum (free rooms) page. "Free now" asks the backend for the current time; "custom
 * interval" sends the chosen date and times. Each room card links to its timetable
 * (/timetable?mode=room&faculty_id=...&id=...). The backend decides who is free; this script
 * only sends the filters and draws the cards.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var modeButtons = document.querySelectorAll("[data-free-mode]");
  var customFields = document.getElementById("free-custom");
  var dateInput = document.getElementById("free-date");
  var startInput = document.getElementById("free-start");
  var endInput = document.getElementById("free-end");
  var facultySelect = document.getElementById("free-faculty");
  var capacityInput = document.getElementById("free-capacity");
  var projectorInput = document.getElementById("free-projector");
  var verifiedInput = document.getElementById("free-verified");
  var statusLine = document.getElementById("free-status");
  var list = document.getElementById("free-list");
  if (!list) return;

  var mode = "now";
  var requestNumber = 0;

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function todayIso() {
    var now = new Date();
    return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
  }

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  function setStatus(text, isError) {
    statusLine.textContent = text || "";
    statusLine.className = isError && text ? "notice notice--error" : "muted";
  }

  function filters() {
    var custom = mode === "custom";
    return {
      faculty_id: facultySelect.value || null,
      date: custom && dateInput.value ? dateInput.value : null,
      start_time: custom && startInput.value ? startInput.value : null,
      end_time: custom && endInput.value ? endInput.value : null,
      min_capacity: capacityInput.value ? capacityInput.value : null,
      has_projector: projectorInput.checked ? true : null,
      only_verified: verifiedInput.checked ? true : null
    };
  }

  function roomHref(room, date) {
    var params = new URLSearchParams({
      mode: "room",
      faculty_id: room.faculty_id || "campus",
      id: room.id
    });
    if (date) params.set("date", date);
    return "/timetable?" + params.toString();
  }

  function card(room, date) {
    var item = document.createElement("li");
    var link = document.createElement("a");
    link.className = "room-card";
    link.href = roomHref(room, date);
    link.setAttribute("aria-label", t("free.openRoom", { name: room.name }));

    var name = document.createElement("h2");
    name.className = "room-card__name";
    name.textContent = room.name;
    link.appendChild(name);

    var faculty = document.createElement("p");
    faculty.className = "room-card__faculty";
    faculty.textContent = room.faculty_name || t("common.campus");
    link.appendChild(faculty);

    var badges = document.createElement("p");
    badges.className = "room-card__badges";
    var availability = document.createElement("span");
    availability.className = "pill pill--info";
    availability.textContent = room.free_until
      ? t("free.freeUntil", { time: room.free_until })
      : t("free.freeRestOfDay");
    badges.appendChild(availability);
    var verified = document.createElement("span");
    verified.className = "pill " + (room.is_field_verified ? "pill--confirmed" : "pill--pending");
    verified.textContent = room.is_field_verified ? t("free.verified") : t("free.estimate");
    badges.appendChild(verified);
    link.appendChild(badges);

    var details = document.createElement("p");
    details.className = "room-card__details";
    details.textContent = room.capacity !== null && room.capacity !== undefined
      ? t("free.seats", { n: room.capacity })
      : t("free.seatsUnknown");
    link.appendChild(details);

    var equipment = [];
    if (room.has_projector) equipment.push(t("free.projectorTag"));
    if (room.has_outlets) equipment.push(t("free.outletsTag"));
    if (equipment.length) {
      var tags = document.createElement("p");
      tags.className = "room-card__tags";
      equipment.forEach(function (label) {
        var tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = label;
        tags.appendChild(tag);
      });
      link.appendChild(tags);
    }

    item.appendChild(link);
    return item;
  }

  function draw(rooms, date) {
    list.textContent = "";
    rooms.forEach(function (room) {
      list.appendChild(card(room, date));
    });
  }

  function load() {
    var values = filters();
    if (mode === "custom" && values.start_time && values.end_time && values.end_time <= values.start_time) {
      setStatus(t("free.badRange"), true);
      draw([], null);
      return;
    }
    var current = ++requestNumber;
    setStatus(t("free.loading"));
    api.freeClassrooms(values).then(function (rooms) {
      if (current !== requestNumber) return;
      draw(rooms, values.date);
      setStatus(rooms.length ? t("free.count", { n: rooms.length }) : t("free.empty"));
    }).catch(function () {
      if (current !== requestNumber) return;
      draw([], null);
      setStatus(t("free.error"), true);
    });
  }

  function setMode(next) {
    mode = next;
    modeButtons.forEach(function (button) {
      var selected = button.getAttribute("data-free-mode") === next;
      button.setAttribute("aria-selected", String(selected));
    });
    customFields.hidden = next !== "custom";
    load();
  }

  function loadFaculties() {
    var chosen = facultySelect.value;
    api.faculties().then(function (faculties) {
      var all = document.createElement("option");
      all.value = "";
      all.textContent = t("free.allFaculties");
      facultySelect.textContent = "";
      facultySelect.appendChild(all);
      var campus = document.createElement("option");
      campus.value = "campus";
      campus.textContent = t("common.campus");
      facultySelect.appendChild(campus);
      faculties.forEach(function (faculty) {
        var option = document.createElement("option");
        option.value = faculty.id;
        option.textContent = faculty.name;
        facultySelect.appendChild(option);
      });
      facultySelect.value = chosen;
    }).catch(function () {
      setStatus(t("free.error"), true);
    });
  }

  modeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      setMode(button.getAttribute("data-free-mode"));
    });
  });
  [facultySelect, dateInput, startInput, endInput, capacityInput, projectorInput, verifiedInput]
    .forEach(function (control) {
      control.addEventListener("change", load);
    });

  dateInput.value = todayIso();
  loadFaculties();
  setMode("now");

  // The cards and the status line are built by the script: ask again in the new language.
  document.addEventListener("unispace:langchange", function () {
    loadFaculties();
    load();
  });
})();

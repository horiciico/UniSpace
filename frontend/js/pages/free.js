/*
 * Liber acum (free rooms) page. "Free now" sends the exact local time of every visit (on load,
 * on switching to the tab, and when the page is shown again). "Custom interval" picks whole
 * modules. The backend decides who is free; this script sends the filters and draws the cards.
 * Each card links to the room's timetable (/timetable?mode=room&faculty_id=...&id=...).
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var modules = window.UniSpaceModules;

  var modeButtons = document.querySelectorAll("[data-free-mode]");
  var customFields = document.getElementById("free-custom");
  var dateInput = document.getElementById("free-date");
  var fromSelect = document.getElementById("free-from");
  var toSelect = document.getElementById("free-to");
  var facultySelect = document.getElementById("free-faculty");
  var capacityInput = document.getElementById("free-capacity");
  var projectorInput = document.getElementById("free-projector");
  var verifiedInput = document.getElementById("free-verified");
  var statusLine = document.getElementById("free-status");
  var list = document.getElementById("free-list");
  if (!list) return;

  var mode = "now";
  var requestNumber = 0;
  var shownModule = -1; // the module index the list was loaded for (free now)

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function todayIso(now) {
    return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
  }

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  function setStatus(text, isError) {
    statusLine.textContent = text || "";
    statusLine.className = isError && text ? "notice notice--error" : "muted";
  }

  // The index of the module that contains the moment, or the next one during a break.
  function moduleIndexAt(minutes) {
    for (var index = 0; index < modules.list.length; index++) {
      if (minutes < modules.list[index].endMin) return index;
    }
    return -1;
  }

  // Fills the two module pickers. Each option reads "1 · 08:00–09:30".
  function fillModules(selectedFrom, selectedTo) {
    [fromSelect, toSelect].forEach(function (select) {
      select.textContent = "";
      modules.list.forEach(function (module, index) {
        var option = document.createElement("option");
        option.value = String(index);
        option.textContent = module.number + " · " + module.start + "–" + module.end;
        select.appendChild(option);
      });
    });
    fromSelect.value = String(selectedFrom);
    toSelect.value = String(selectedTo);
  }

  // The request for the current mode. Free now: the exact local date and time, no end.
  function now() {
    var moment = new Date();
    var minutes = moment.getHours() * 60 + moment.getMinutes();
    return { date: todayIso(moment), minutes: minutes, time: pad(moment.getHours()) + ":" + pad(moment.getMinutes()) };
  }

  function filters() {
    var values = {
      faculty_id: facultySelect.value || null,
      min_capacity: capacityInput.value ? capacityInput.value : null,
      has_projector: projectorInput.checked ? true : null,
      only_verified: verifiedInput.checked ? true : null
    };
    if (mode === "custom") {
      var from = modules.list[Number(fromSelect.value)];
      var to = modules.list[Number(toSelect.value)];
      values.date = dateInput.value || todayIso(new Date());
      values.start_time = from.start;
      values.end_time = to.end;
    } else {
      // Free now: the rooms free for the whole current module (the next one during a break).
      var moment = now();
      var current = modules.list[moduleIndexAt(moment.minutes)];
      values.date = moment.date;
      values.start_time = current.start;
      values.end_time = current.end;
    }
    return values;
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
    availability.textContent = t("free.freeUntil", { time: room.free_until });
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
    var current = ++requestNumber;
    // No rooms until a faculty is chosen: the page asks for one instead of listing every room.
    if (!facultySelect.value) {
      draw([], null);
      setStatus(t("free.pickFaculty"));
      return;
    }
    if (mode === "now") {
      var index = moduleIndexAt(now().minutes);
      shownModule = index;
      // After the last module no room can be booked: say so, and do not ask.
      if (index < 0) {
        draw([], null);
        setStatus(t("free.afterLast"), true);
        return;
      }
    }
    if (mode === "custom" && Number(toSelect.value) < Number(fromSelect.value)) {
      draw([], null);
      setStatus(t("free.badRange"), true);
      return;
    }
    var values = filters();
    setStatus(t("free.loading"));
    api.freeClassrooms(values).then(function (rooms) {
      if (current !== requestNumber) return;
      draw(rooms, values.date);
      var count = rooms.length ? t("free.count", { n: rooms.length }) : t("free.empty");
      if (mode === "now") {
        var module = modules.list[shownModule];
        setStatus(count + " · " + t("free.inModule", { start: module.start, end: module.end }));
      } else {
        setStatus(count);
      }
    }).catch(function (error) {
      if (current !== requestNumber) return;
      draw([], null);
      setStatus(t(error.status === 400 ? "free.badRange" : "free.error"), true);
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
      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = t("free.chooseFaculty");
      facultySelect.textContent = "";
      facultySelect.appendChild(placeholder);
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
      if (!chosen) setStatus(t("free.pickFaculty"));
    }).catch(function () {
      setStatus(t("free.error"), true);
    });
  }

  modeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      setMode(button.getAttribute("data-free-mode"));
    });
  });
  [facultySelect, dateInput, fromSelect, toSelect, capacityInput, projectorInput, verifiedInput]
    .forEach(function (control) {
      control.addEventListener("change", load);
    });

  // Every visit gets the exact local time: when the page is shown again (back button,
  // returning to the tab), the free-now list is asked again.
  window.addEventListener("pageshow", function () {
    if (mode === "now") load();
  });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && mode === "now") load();
  });

  var moment = now();
  var index = moduleIndexAt(moment.minutes);
  // A module changes while the page is open: the free-now list follows it.
  window.setInterval(function () {
    if (mode === "now" && moduleIndexAt(now().minutes) !== shownModule) load();
  }, 30000);
  dateInput.value = moment.date;
  fillModules(index < 0 ? 0 : index, index < 0 ? 0 : index);
  loadFaculties();
  setMode("now");
  facultySelect.focus();

  // The cards, the status and the module labels are built by the script: build them again.
  document.addEventListener("unispace:langchange", function () {
    fillModules(Number(fromSelect.value), Number(toSelect.value));
    loadFaculties();
    load();
  });
})();

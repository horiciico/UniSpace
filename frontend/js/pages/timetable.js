/*
 * Timetable placeholder: draws a sample week and switches the view label.
 * The real timetable will come from the backend (group, teacher or room view).
 * Weekday names, the kind labels and the view labels are UI text (i18n); the course
 * titles and room codes are sample data and are shown as they are.
 */
(function () {
  "use strict";

  var grid = document.getElementById("tt-grid");
  if (!grid) return;

  var t = window.UniSpaceI18n.t;
  var FIRST_HOUR = 8;
  var LAST_HOUR = 20;
  var DAY_KEYS = ["day.mon", "day.tue", "day.wed", "day.thu", "day.fri"];
  var KIND_KEYS = { course: "kind.lecture", seminar: "kind.seminar", lab: "kind.lab" };

  // day: 0 = Monday. start/end: hours. type: course | seminar | lab
  var SAMPLE = [
    { day: 0, start: 8, end: 10, type: "course", title: "Analysis I", room: "A101" },
    { day: 0, start: 12, end: 14, type: "seminar", title: "Databases", room: "B204" },
    { day: 1, start: 10, end: 12, type: "lab", title: "Operating systems", room: "L3" },
    { day: 1, start: 14, end: 16, type: "course", title: "Linear algebra", room: "A101" },
    { day: 2, start: 9, end: 11, type: "seminar", title: "Web programming", room: "B110" },
    { day: 2, start: 16, end: 18, type: "lab", title: "Databases lab", room: "L1" },
    { day: 3, start: 8, end: 10, type: "course", title: "Probability", room: "C02" },
    { day: 3, start: 13, end: 15, type: "seminar", title: "Analysis I", room: "B204" },
    { day: 4, start: 10, end: 12, type: "course", title: "Software design", room: "A101" },
    { day: 4, start: 15, end: 17, type: "lab", title: "Web programming lab", room: "L2" }
  ];

  var VIEWS = {
    group: { key: "timetable.viewGroup", vars: { name: "CS-2A" } },
    teacher: { key: "timetable.viewTeacher", vars: { name: "Prof. Sample" } },
    room: { key: "timetable.viewRoom", vars: { name: "A101" } }
  };

  var activeView = "group";

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function pad(hour) {
    return String(hour).padStart(2, "0") + ":00";
  }

  function draw() {
    grid.textContent = "";

    grid.appendChild(el("div", "tt-head", t("timetable.time")));
    DAY_KEYS.forEach(function (key, index) {
      var head = el("div", "tt-head", t(key));
      head.style.gridColumn = String(index + 2);
      head.style.gridRow = "1";
      grid.appendChild(head);
    });

    for (var hour = FIRST_HOUR; hour < LAST_HOUR; hour++) {
      var row = hour - FIRST_HOUR + 2;
      var label = el("div", "tt-time", pad(hour));
      label.style.gridColumn = "1";
      label.style.gridRow = String(row);
      grid.appendChild(label);
      for (var day = 0; day < DAY_KEYS.length; day++) {
        var cell = el("div", "tt-cell");
        cell.style.gridColumn = String(day + 2);
        cell.style.gridRow = String(row);
        grid.appendChild(cell);
      }
    }

    SAMPLE.forEach(function (item) {
      var block = el("div", "tt-block tt-block--" + item.type);
      block.style.gridColumn = String(item.day + 2);
      block.style.gridRow = (item.start - FIRST_HOUR + 2) + " / " + (item.end - FIRST_HOUR + 2);
      block.appendChild(el("strong", null, item.title));
      block.appendChild(el("span", null, t(KIND_KEYS[item.type]) + " · " + item.room));
      grid.appendChild(block);
    });
  }

  function showViewLabel() {
    var label = document.getElementById("tt-view-label");
    var view = VIEWS[activeView];
    if (label) label.textContent = t(view.key, view.vars);
  }

  function bindTabs() {
    var tabs = document.querySelectorAll("[role='tab'][data-view]");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (other) {
          other.setAttribute("aria-selected", String(other === tab));
        });
        activeView = tab.dataset.view;
        showViewLabel();
      });
    });
  }

  draw();
  showViewLabel();
  bindTabs();
  document.addEventListener("unispace:langchange", function () {
    draw();
    showViewLabel();
  });
})();

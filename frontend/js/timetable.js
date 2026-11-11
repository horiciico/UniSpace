/*
 * Timetable placeholder: draws a sample week and switches the view label.
 * The real timetable will come from the backend (group, teacher or room view).
 */
(function () {
  "use strict";

  var grid = document.getElementById("tt-grid");
  if (!grid) return;

  var FIRST_HOUR = 8;
  var LAST_HOUR = 20;
  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];

  // day: 0 = Monday. start/end: hours. type: course | seminar | lab
  var SAMPLE = [
    { day: 0, start: 8, end: 10, type: "course", title: "Analysis I", who: "Lecture", room: "A101" },
    { day: 0, start: 12, end: 14, type: "seminar", title: "Databases", who: "Seminar", room: "B204" },
    { day: 1, start: 10, end: 12, type: "lab", title: "Operating systems", who: "Lab", room: "L3" },
    { day: 1, start: 14, end: 16, type: "course", title: "Linear algebra", who: "Lecture", room: "A101" },
    { day: 2, start: 9, end: 11, type: "seminar", title: "Web programming", who: "Seminar", room: "B110" },
    { day: 2, start: 16, end: 18, type: "lab", title: "Databases lab", who: "Lab", room: "L1" },
    { day: 3, start: 8, end: 10, type: "course", title: "Probability", who: "Lecture", room: "C02" },
    { day: 3, start: 13, end: 15, type: "seminar", title: "Analysis I", who: "Seminar", room: "B204" },
    { day: 4, start: 10, end: 12, type: "course", title: "Software design", who: "Lecture", room: "A101" },
    { day: 4, start: 15, end: 17, type: "lab", title: "Web programming lab", who: "Lab", room: "L2" }
  ];

  var VIEWS = {
    group: "Group CS-2A (sample)",
    teacher: "Teacher: Prof. Sample (sample)",
    room: "Room A101 (sample)"
  };

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

    grid.appendChild(el("div", "tt-head", "Time"));
    DAYS.forEach(function (name, index) {
      var head = el("div", "tt-head", name);
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
      for (var day = 0; day < DAYS.length; day++) {
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
      block.appendChild(el("span", null, item.who + " · " + item.room));
      grid.appendChild(block);
    });
  }

  function bindTabs() {
    var tabs = document.querySelectorAll("[role='tab'][data-view]");
    var label = document.getElementById("tt-view-label");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (other) {
          other.setAttribute("aria-selected", String(other === tab));
        });
        if (label) label.textContent = VIEWS[tab.dataset.view];
      });
    });
  }

  draw();
  bindTabs();
})();

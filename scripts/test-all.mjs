#!/usr/bin/env node
/*
 * Runs every test suite (or a single suite) and writes one report: output/test-report.md.
 *
 *   node scripts/test-all.mjs [backend | etl | frontend]
 *
 * Suites (each runs in Docker, as AGENTS.md asks):
 *   backend   pytest in the backend container (backend/tests)
 *   etl       pytest for the ETL pipelines (etl/), with etl/ and data/ mounted
 *   frontend  Vitest in jsdom, with the 100% coverage gate (frontend/tests)
 *
 * Before each suite, a count of its tests is taken, so the progress bar has a total.
 * In a terminal the bars update live, in colour. Otherwise (a log file, CI) one plain line
 * per suite is printed. NO_COLOR turns colours off; TEST_ALL_LIVE=1 forces the live display.
 *
 * Exit code: 0 when every suite passes, 1 otherwise.
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT_DIR = join(ROOT, "output");
const REPORT = join(OUTPUT_DIR, "test-report.md");
const FAILURE_LINES = 40;
const BAR_WIDTH = 28;
const REFRESH_MS = 120;

// TEST_ALL_LIVE=1 forces the live display (for checking it where there is no terminal).
const TTY = Boolean(process.stdout.isTTY) || process.env.TEST_ALL_LIVE === "1";
const COLOUR = TTY && !process.env.NO_COLOR;
const paint = (code) => (text) => (COLOUR ? `\x1b[${code}m${text}\x1b[0m` : text);
const style = {
  green: paint("32"), red: paint("31"), yellow: paint("33"),
  dim: paint("2"), bold: paint("1"), cyan: paint("36"),
};
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g;
const strip = (text) => text.replace(ANSI, "");
const asMount = (path) => path.replace(/\\/g, "/");
const ETL_MOUNTS = [
  "-v", `${asMount(join(ROOT, "etl"))}:/app/etl`,
  "-v", `${asMount(join(ROOT, "data"))}:/app/data`,
];
const FRONTEND_INSTALL = "npm install --no-audit --no-fund >/dev/null 2>&1";

const SUITES = [
  {
    name: "backend",
    label: "Backend",
    detail: "pytest, 75 tests in the backend container",
    count: ["compose", "run", "--rm", "backend", "pytest", "--collect-only", "-q"],
    run: ["compose", "run", "--rm", "-e", "PYTHONUNBUFFERED=1", "backend", "pytest", "-q"],
    parse: parsePytestLine,
    summary: parsePytest,
  },
  {
    name: "etl",
    label: "ETL",
    detail: "pytest, schedule importer tests",
    count: ["compose", "run", "--rm", ...ETL_MOUNTS, "backend", "pytest", "--collect-only", "-q", "etl"],
    run: ["compose", "run", "--rm", "-e", "PYTHONUNBUFFERED=1", ...ETL_MOUNTS, "backend", "pytest", "-q", "etl"],
    parse: parsePytestLine,
    summary: parsePytest,
  },
  {
    name: "frontend",
    label: "Frontend",
    detail: "Vitest in jsdom, coverage gate 100%",
    count: ["compose", "--profile", "test", "run", "--rm", "frontend-test", "sh", "-c",
      `${FRONTEND_INSTALL} && npx vitest list --json`],
    run: ["compose", "--profile", "test", "run", "--rm", "frontend-test", "sh", "-c",
      `${FRONTEND_INSTALL} && npx vitest run --coverage --reporter=verbose`],
    parse: parseVitestLine,
    summary: parseVitest,
  },
];

// ---- Reading the output ---------------------------------------------------------------

// pytest -q prints one character per test ("..F.s"), with a percentage at the end of a line.
function parsePytestLine(line) {
  const text = strip(line);
  if (!/^[.FEsxX]+(\s+\[\s*\d+%\])?\s*$/.test(text)) return [];
  return [...text.replace(/\s*\[.*$/, "")].map((ch) => (ch === "F" || ch === "E" ? "fail" : "pass"));
}

// Vitest --reporter=verbose prints "✓ name" or "× name" for each test.
function parseVitestLine(line) {
  const match = /^\s*(✓|×)\s/.exec(strip(line));
  return match ? [match[1] === "✓" ? "pass" : "fail"] : [];
}

// Counts the tests of a suite from its own collect command (pytest --collect-only, vitest list).
function countFrom(suite, output) {
  if (suite.name === "frontend") {
    const start = output.search(/^\[/m);
    if (start < 0) return null;
    try { return JSON.parse(output.slice(start)).length; } catch { return null; }
  }
  const match = /(\d+) tests? collected/.exec(output);
  return match ? Number(match[1]) : null;
}

// The final numbers, from the summary line of the runner.
function parsePytest(output) {
  const line = [...output.matchAll(/^.*\b(\d+ (?:passed|failed|error|errors)[^\n]*)$/gm)].at(-1);
  if (!line) return { passed: 0, failed: 0, text: "no result line found" };
  const passed = Number((/(\d+) passed/.exec(line[1]) || [0, 0])[1]);
  const failed = Number((/(\d+) (?:failed|error)/.exec(line[1]) || [0, 0])[1]);
  return { passed, failed, text: line[1].trim() };
}

// Vitest prints "Tests  207 passed (207)" and, below 100% coverage, "ERROR: Coverage ...".
function parseVitest(output) {
  const plain = strip(output);
  const line = /Tests\s+(?:(\d+) failed \| )?(\d+) passed/.exec(plain);
  if (!line) return { passed: 0, failed: 0, text: "no result line found" };
  const failed = Number(line[1] || 0);
  const passed = Number(line[2]);
  const coverage = /ERROR: Coverage for (\w+) \(([\d.]+%)\) does not meet/.exec(plain);
  const text = `${passed} passed${failed ? `, ${failed} failed` : ""}` +
    (coverage ? `; coverage gate failed for ${coverage[1]} (${coverage[2]})` : "");
  return { passed, failed: failed + (coverage ? 1 : 0), text };
}

// ---- Running a command and collecting its output --------------------------------------

function capture(args) {
  return new Promise((done) => {
    const child = spawn("docker", args, { cwd: ROOT, shell: false });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.stderr.on("data", (chunk) => { output += chunk; });
    child.on("close", (code) => done({ code, output }));
    child.on("error", (error) => done({ code: -1, output: error.message }));
  });
}

// ---- Live display ---------------------------------------------------------------------

const requestedSuite = process.argv[2];
const activeSuites = requestedSuite
  ? SUITES.filter((suite) => suite.name.toLowerCase() === requestedSuite.toLowerCase())
  : SUITES;

if (requestedSuite && activeSuites.length === 0) {
  console.error(`Unknown suite "${requestedSuite}". Expected one of: ${SUITES.map((s) => s.name).join(", ")}`);
  process.exit(1);
}

const rows = activeSuites.map((suite) => ({
  ...suite, status: "waiting", total: 0, done: 0, failed: 0, started: 0, seconds: 0, text: "", output: "",
}));

function bar(row) {
  const ratio = row.total ? Math.min(1, row.done / row.total) : 0;
  const filled = Math.round(ratio * BAR_WIDTH);
  const colour = row.failed ? style.red : style.green;
  return colour("█".repeat(filled)) + style.dim("░".repeat(BAR_WIDTH - filled));
}

// The status word is padded before it is coloured, so the columns line up in the terminal.
function statusLabel(row) {
  const word = { pass: "PASS", fail: "FAIL", running: "RUNNING" }[row.status] || "waiting";
  const colour = { pass: style.green, fail: style.red, running: style.yellow }[row.status] || style.dim;
  return colour(word.padEnd(10));
}

function rowLine(row) {
  const elapsed = row.status === "running" ? (Date.now() - row.started) / 1000 : row.seconds;
  const count = `${row.done}/${row.total || "?"}`.padStart(9);
  const failed = row.failed ? style.red(`${row.failed} failed`.padEnd(12)) : style.dim("0 failed".padEnd(12));
  return `  ${style.bold(row.label.padEnd(10))} ${bar(row)} ${count}  ${failed} ` +
    `${statusLabel(row)} ${elapsed ? `${elapsed.toFixed(1)}s` : ""}`;
}

let drawnLines = 0;
function draw() {
  const lines = [style.bold("Test run"), ...rows.map(rowLine), ""];
  if (drawnLines) process.stdout.write(`\x1b[${drawnLines}A`);
  for (const line of lines) process.stdout.write(`\x1b[2K${line}\n`);
  drawnLines = lines.length;
}

// ---- One suite ------------------------------------------------------------------------

async function runSuite(row) {
  const counted = await capture(row.count);
  row.total = countFrom(row, counted.output) ?? 0;

  row.status = "running";
  row.started = Date.now();
  let buffer = "";
  const child = spawn("docker", row.run, { cwd: ROOT, shell: false });
  const onChunk = (chunk) => {
    buffer += chunk;
    let cut;
    while ((cut = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 1);
      for (const outcome of row.parse(line)) {
        row.done += 1;
        if (outcome === "fail") row.failed += 1;
      }
      row.output += `${line}\n`;
    }
    if (TTY) draw();
  };
  child.stdout.on("data", onChunk);
  child.stderr.on("data", onChunk);

  await new Promise((done) => {
    child.on("close", (code) => {
      row.seconds = (Date.now() - row.started) / 1000;
      const result = row.summary(row.output);
      row.text = result.text;
      row.failed = Math.max(row.failed, result.failed);
      row.done = Math.max(row.done, result.passed + result.failed);
      row.ok = code === 0 && result.failed === 0;
      row.status = row.ok ? "pass" : "fail";
      if (!TTY) {
        console.log(`${row.ok ? "PASS" : "FAIL"}  ${row.label}: ${row.text} (${row.seconds.toFixed(1)}s)`);
      }
      done();
    });
    child.on("error", (error) => {
      row.status = "fail";
      row.ok = false;
      row.failed = Math.max(row.failed, 1);
      row.text = `docker did not start (${error.message})`;
      row.output += row.text;
      done();
    });
  });
}

// ---- Report ----------------------------------------------------------------------------

function tail(output) {
  return output.split("\n").filter((line) => line.trim()).slice(-FAILURE_LINES).join("\n");
}

function buildReport(allRows) {
  const total = allRows.reduce((sum, r) => sum + (r.summary(r.output).passed || 0), 0);
  const allOk = allRows.every((r) => r.ok);
  const lines = [
    "# Test report",
    "",
    `Generated ${new Date().toISOString()}`,
    "",
    `**${allOk ? "All suites passed" : "Some suites failed"}.** ${total} tests passed in total.`,
    "",
    "| Suite | Result | Time | Status |",
    "| --- | --- | --- | --- |",
    ...allRows.map((r) => `| ${r.label} | ${r.text} | ${r.seconds.toFixed(1)}s | ${r.ok ? "pass" : "**fail**"} |`),
    "",
  ];
  for (const r of allRows.filter((x) => !x.ok)) {
    lines.push(`## ${r.label}`, "", "Last lines of the output:", "", "```", tail(r.output), "```", "");
  }
  return lines.join("\n");
}

// ---- Main ------------------------------------------------------------------------------

async function main() {
  if (TTY) process.stdout.write("\x1b[?25l"); // hide the cursor while the bars move
  const restore = () => { if (TTY) process.stdout.write("\x1b[?25h"); };
  process.on("SIGINT", () => { restore(); process.exit(130); });

  if (!TTY) {
    console.log(`Running ${requestedSuite ? requestedSuite + " test suite" : "all test suites"} in Docker.`);
  }
  const ticker = TTY ? setInterval(draw, REFRESH_MS) : null;
  if (TTY) draw();

  for (const row of rows) {
    await runSuite(row);
    if (TTY) draw();
  }
  if (ticker) clearInterval(ticker);
  restore();

  mkdirSync(OUTPUT_DIR, { recursive: true });
  writeFileSync(REPORT, buildReport(rows));
  const allOk = rows.every((r) => r.ok);
  const totalPassed = rows.reduce((sum, r) => sum + (r.summary(r.output).passed || 0), 0);
  const headline = allOk
    ? style.green(style.bold(`All suites passed: ${totalPassed} tests.`))
    : style.red(style.bold("Some suites failed. See the report."));
  console.log(`\n${headline}`);
  console.log(style.dim(`Report: ${REPORT}`));
  process.exit(allOk ? 0 : 1);
}

main();

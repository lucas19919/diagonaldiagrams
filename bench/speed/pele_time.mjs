// Time Pele's render() on one Mermaid file, for scripts/bench_speed.py.
//
//   node pele_time.mjs PELE_ENTRY FILE.mmd RUNS          -> JSON {median, min, max, runs} in ms
//   node pele_time.mjs PELE_ENTRY FILE.mmd --once OUT.svg -> renders once and writes the SVG
//
// PELE_ENTRY is the package's dist/pele.js, passed as a path so nothing is imported from the
// folder this script is run in.
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [entry, file, arg, out] = process.argv.slice(2);
const { render } = await import(pathToFileURL(entry).href);
const text = readFileSync(file, "utf8");

if (arg === "--once") {
  writeFileSync(out, render(text).svg);
} else {
  const runs = Number(arg);
  for (let i = 0; i < 50; i++) render(text); // warm the JIT
  const times = [];
  for (let i = 0; i < runs; i++) {
    const t0 = process.hrtime.bigint();
    render(text);
    times.push(Number(process.hrtime.bigint() - t0) / 1e6);
  }
  times.sort((a, b) => a - b);
  const mid = times.length >> 1;
  const median = times.length % 2 ? times[mid] : (times[mid - 1] + times[mid]) / 2;
  const r = (x) => Math.round(x * 1000) / 1000;
  console.log(JSON.stringify({ median: r(median), min: r(times[0]), max: r(times[times.length - 1]), runs }));
}

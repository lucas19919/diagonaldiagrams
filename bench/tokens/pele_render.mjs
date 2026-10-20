// The command the token benchmark's Pele agents run (through bin\pele.cmd, which bench_prompts.py writes).
//
//   node pele_render.mjs PELE_ENTRY BROWSER IN.mmd OUT.svg   -> Pele's SVG
//   node pele_render.mjs PELE_ENTRY BROWSER IN.mmd OUT.png   -> the same SVG, screenshotted by headless Edge or Chrome
//
// Pele ships a library, not a command line, so this is the smallest one: render(text) and write the
// result. The PNG option gives Pele agents a way to look, as mmdc's own PNG output gives Mermaid agents.
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [entry, browser, input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error("usage: pele IN.mmd OUT.svg|OUT.png");
  process.exit(2);
}
const { render } = await import(pathToFileURL(entry).href);
let svg;
try {
  svg = render(readFileSync(input, "utf8")).svg;
} catch (e) {
  console.error(`pele: ${e.message}`);
  process.exit(1);
}
if (!output.toLowerCase().endsWith(".png")) {
  writeFileSync(output, svg);
  console.log(`wrote ${output}`);
} else {
  const m = svg.match(/viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"/);
  const [w, h] = m ? [Math.ceil(+m[1]), Math.ceil(+m[2])] : [1200, 900];
  const dir = mkdtempSync(join(tmpdir(), "pele-png-"));
  try {
    const page = join(dir, "figure.html");
    writeFileSync(page, `<!doctype html><style>html,body{margin:0;background:#fff}</style>${svg}`);
    execFileSync(browser, ["--headless", "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${join(dir, "profile")}`,
      `--window-size=${w},${h}`, `--screenshot=${resolve(output)}`, pathToFileURL(page).href], { stdio: "ignore" });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  console.log(`wrote ${output} (${w}x${h})`);
}

// The engine in a browser's Python, run in Node: unpack the wheel into Pyodide and draw one flowchart.
//
//   npm install --no-save pyodide@0.27.2      (the version CI pins)
//   python -m pip wheel . --no-deps -w dist
//   node tests/pyodide_smoke.mjs dist/diagonaldiagrams-*.whl
//
// Exit 0 when the verdict says ok.
import { loadPyodide } from "pyodide";
import { readFileSync } from "node:fs";

const wheel = process.argv[2];
if (!wheel) {
  console.error("usage: node tests/pyodide_smoke.mjs WHEEL");
  process.exit(2);
}
function said(e) {  // an error's message, short: Pyodide's own stack is one minified line of 64 KB
  return (e && e.message ? e.message : String(e)).slice(0, 4000);
}
let py;
try {
  py = await loadPyodide();
  py.unpackArchive(new Uint8Array(readFileSync(wheel)), "wheel");  // a plain typed array: Pyodide refuses Node's Buffer
} catch (e) {
  console.error("loading Pyodide or the wheel failed:\n" + said(e));
  process.exit(1);
}
py.FS.mkdirTree("/out");
py.FS.writeFile("/in.json", JSON.stringify({
  title: "Pyodide smoke",
  nodes: [{ id: "a", name: "Start", shape: "oval" }, { id: "b", name: "Valid?", shape: "diamond" },
          { id: "c", name: "Ship it" }, { id: "d", name: "Fix it" }, { id: "e", name: "Done", shape: "oval" }],
  edges: [{ from: "a", to: "b" }, { from: "b", to: "c", label: "yes" }, { from: "b", to: "d", label: "no" },
          { from: "c", to: "e" }, { from: "d", to: "b" }],
}));
let out;
try {
  out = py.runPython(`
import contextlib, io, sys
from diagonaldiagrams.cli import cli
buf = io.StringIO()
sys.argv = ["diagonaldiagrams", "flow", "/in.json", "-o", "/out/fig.svg"]
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        cli()
except SystemExit:
    pass
buf.getvalue()
`);
} catch (e) {  // a Python error: its traceback, not Pyodide's minified stack
  console.error("Python raised:\n" + said(e));
  process.exit(1);
}
let verdict = {};
try {
  verdict = JSON.parse(out.trim().split("\n").pop());
} catch (e) {
  console.error("no JSON verdict:\n" + out);
  process.exit(1);
}
if (!verdict.ok || !py.FS.analyzePath("/out/fig.svg").exists) {
  console.error(out);
  process.exit(1);
}
console.log(`pyodide render ok: ${verdict.items} items; ${verdict.layout.join("; ")}`);

// The browser playground's path, in Node: unpack the wheel into Pyodide and draw one flowchart.
//
//   npm install --no-save pyodide@0.27.2      (the version docs/index.html loads)
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
const py = await loadPyodide();
py.unpackArchive(readFileSync(wheel), "wheel");
py.FS.mkdirTree("/out");
py.FS.writeFile("/in.json", JSON.stringify({
  title: "Pyodide smoke",
  nodes: [{ id: "a", name: "Start", shape: "oval" }, { id: "b", name: "Valid?", shape: "diamond" },
          { id: "c", name: "Ship it" }, { id: "d", name: "Fix it" }, { id: "e", name: "Done", shape: "oval" }],
  edges: [{ from: "a", to: "b" }, { from: "b", to: "c", label: "yes" }, { from: "b", to: "d", label: "no" },
          { from: "c", to: "e" }, { from: "d", to: "b" }],
}));
const out = py.runPython(`
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

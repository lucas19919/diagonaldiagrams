// Render Mermaid files with Pele in one Node process: node pele_render.mjs PELE_ENTRY IN.mmd OUT.svg [IN OUT ...]
// Pele's render() at its defaults, as the token benchmark's agents ran it (no host CSS, so its fallback colors).
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [entry, ...files] = process.argv.slice(2);
const { render } = await import(pathToFileURL(entry).href);
let failed = 0;
for (let i = 0; i + 1 < files.length; i += 2) {
  try {
    writeFileSync(files[i + 1], render(readFileSync(files[i], "utf8")).svg);
  } catch (e) {
    failed++;
    console.error(`${files[i]}: ${e.message}`);
  }
}
process.exit(failed ? 1 : 0);

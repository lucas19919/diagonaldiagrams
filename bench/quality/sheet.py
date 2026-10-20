"""Write sheet.html, the human spot-check sheet: python bench/quality/sheet.py

One card per pair: both figures as the slide shows them (the column images are linked), how often
dd won each question in each placement, and every judge's reasons, unblinded."""
import csv, html, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {"dd": "diagonaldiagrams 0.8.0", "pele": "Pele 1.6.0", "mermaid": "Mermaid CLI 12"}
FAMILY = {"A": "Agent figures (each agent wrote its own source)", "L": "One Mermaid source, drawn by each tool",
          "N": "Our reference figure from its native spec, against the Mermaid translation"}

CSS = """
:root{--paper:#fbfbfa;--ink:#1f2330;--muted:#5b6478;--rule:#e3e5ea;--card:#fff;--good:#1d7a4a;--bad:#b3261e}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#16181d;--ink:#eceef2;--muted:#a3aab8;--rule:#2c3038;--card:#1f2228;--good:#5cc18a;--bad:#f2867d}}
:root[data-theme="dark"]{--paper:#16181d;--ink:#eceef2;--muted:#a3aab8;--rule:#2c3038;--card:#1f2228;--good:#5cc18a;--bad:#f2867d}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,'Segoe UI',sans-serif}
main{max-width:1880px;margin:0 auto;padding:28px 16px 80px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 8px}
p{max-width:80ch}.muted{color:var(--muted)}
.pair{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:14px;margin:18px 0}
.head{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:10px}.tally{font-size:13px;color:var(--muted)}
.tally b{color:var(--good)}.tally b.lost{color:var(--bad)}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:14px}.imgs figure{margin:0}
.imgs figcaption{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.imgs img{width:100%;height:auto;border:1px solid var(--rule);border-radius:6px;background:#fff}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted);font-size:13px}details li{font-size:13px}
@media (max-width:820px){.imgs{grid-template-columns:1fr}}
"""


def main():
    with open(os.path.join(HERE, "judgments", "key.json"), encoding="utf-8") as f:
        pairs = json.load(f)["pairs"]
    rows = list(csv.DictReader(open(os.path.join(HERE, "judgments", "all.csv"), encoding="utf-8")))
    by = defaultdict(list)
    for r in rows:
        by[r["pair"]].append(r)
    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Quality spot check</title>"
           f"<style>{CSS}</style></head><body><main><h1>Quality benchmark: spot check</h1>"
           "<p class='muted'>Every judged pair, unblinded. dd is diagonaldiagrams 0.8.0. The tallies count dd's wins out of "
           "four judgments per question and placement (Sonnet and Opus, both orders). Images show the slide placement; "
           "the column images are linked under each figure. See README.md for the method.</p>"]
    for fam in ("A", "L", "N"):
        out.append(f"<h2>{html.escape(FAMILY[fam])}</h2>")
        for pid, p in pairs.items():
            if p["family"] != fam or pid not in by:
                continue
            rs = by[pid]
            bits = []
            for ctx in ("slide", "column"):
                for q, qn in (("clearer", "clearer"), ("looks", "looks")):
                    sub = [r for r in rs if r["context"] == ctx and r["question"] == q]
                    won = sum(r["dd_won"] == "True" for r in sub)
                    cls = "" if won * 2 >= len(sub) else " class='lost'"
                    bits.append(f"{ctx} {qn} <b{cls}>{won}/{len(sub)}</b>")
            other = p["tools"][1]
            out.append(f"<div class='pair'><div class='head'><h3>{html.escape(pid)}</h3>"
                       f"<span class='tally'>dd wins: {' · '.join(bits)}</span></div><div class='imgs'>")
            for fig, tool in zip(p["figs"], p["tools"]):
                out.append(f"<figure><figcaption>{html.escape(NAMES[tool])} · <a href='png/column/{fig}.png'>column</a> · "
                           f"<a href='svg/{fig}.svg'>svg</a></figcaption><img loading='lazy' src='png/slide/{fig}.png' "
                           f"alt='{html.escape(fig)}'></figure>")
            out.append("</div><details><summary>Judges' reasons</summary><ul>")
            for r in sorted(rs, key=lambda r: (r["context"], r["question"], r["model"])):
                verdict = "dd" if r["dd_won"] == "True" else other
                out.append(f"<li><b>{r['context']}, {r['question']}, {r['model']}: {verdict}</b> ({html.escape(r['margin'])}). "
                           f"{html.escape(r['why'])} <span class='muted'>dd's weakness: {html.escape(r['weak_dd'])}; "
                           f"{other}'s: {html.escape(r['weak_other'])}</span></li>")
            out.append("</ul></details></div>")
    out.append("</main></body></html>")
    with open(os.path.join(HERE, "sheet.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("wrote sheet.html")


if __name__ == "__main__":
    main()

"""Count the tokens an agent spent on a task, leaving out the harness.

Reads Claude Code subagent transcripts (*.jsonl beside *.meta.json) and counts only the task's own
content: what the agent wrote (tool inputs and text) and what came back (tool results and images).
The system prompt, tool definitions, and reminders the harness adds are the same for any task, so
they are not counted. Neither is the run's final report to its caller.

Time is the span from the run's first transcript entry to its last.

Text is counted at 4 characters per token. An image is counted at Claude's rate: scaled to fit
1568 px and 1.15 megapixels, then width x height / 750. Thinking is redacted in transcripts and is
not counted for either method.

    py -3 scripts/bench_tokens.py TRANSCRIPT_DIR [--match Bench] [--csv OUT.csv] [--summary OUT.csv]

--summary reads run names of the form "Bench TOOL STEPS rN" (bench/tokens/README.md) and writes the
mean per tool and size, with the lowest and highest run, in docs/data/bench_tools.csv's columns. It
also prints each tool's totals over all its runs.
"""
import argparse
import base64
import csv
import datetime
import glob
import json
import math
import os
import statistics
import struct
import sys

SKIP_TOOLS = {"SubagentHandback"}
LABELS = {"mermaid": "Mermaid CLI", "pele": "Pele"}


def image_tokens(b64):
    head = base64.b64decode(b64[:64] + "=" * (-len(b64[:64]) % 4))
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return 1600  # not a PNG: count a full-size image
    w, h = struct.unpack(">II", head[16:24])
    s = min(1.0, 1568 / max(w, h), math.sqrt(1_150_000 / (w * h)))
    return int(w * s * h * s / 750)


def count(path):
    calls, wrote, read, docs, images, shots = set(), 0, 0, 0, 0, 0
    doc_ids, stamps = set(), []
    last, said, acted = None, {}, set()  # the last message; text written per message; messages that used a tool
    for line in open(path, encoding="utf-8"):
        o = json.loads(line)
        if o.get("timestamp"):
            stamps.append(datetime.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")))
        if o.get("type") == "assistant":
            m = o["message"]
            calls.add(m["id"])
            last = m["id"]
            for c in m.get("content", []):
                if c.get("type") == "text":
                    wrote += len(c["text"])
                    said[m["id"]] = said.get(m["id"], 0) + len(c["text"])
                elif c.get("type") == "tool_use" and c["name"] not in SKIP_TOOLS:
                    acted.add(m["id"])
                    wrote += len(json.dumps(c.get("input", {}), ensure_ascii=False))
                    if str(c.get("input", {}).get("file_path", "")).lower().endswith(".md"):
                        doc_ids.add(c["id"])  # a doc the agent read before working
        elif o.get("type") == "user" and isinstance(o["message"]["content"], list):
            for x in o["message"]["content"]:
                if x.get("type") != "tool_result":
                    continue
                body = x.get("content")
                parts = [{"type": "text", "text": body}] if isinstance(body, str) else (body or [])
                for p in parts:
                    if p.get("type") == "text":
                        if x.get("tool_use_id") in doc_ids:
                            docs += len(p["text"])
                        else:
                            read += len(p["text"])
                    elif p.get("type") == "image":
                        images += image_tokens(p["source"]["data"])
                        shots += 1
    if last is not None and last not in acted:  # the final report, sent as plain text rather than a handback tool
        wrote -= said.get(last, 0)
    toks = {"wrote": round(wrote / 4), "docs": round(docs / 4), "read": round(read / 4), "images": images}
    seconds = round((max(stamps) - min(stamps)).total_seconds()) if stamps else 0
    return len(calls), shots, seconds, toks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--match", default="Bench")
    ap.add_argument("--csv")
    ap.add_argument("--summary", help="write per tool and size means here (docs/data/bench_tools.csv's columns)")
    a = ap.parse_args()
    rows = []
    for meta in sorted(glob.glob(os.path.join(a.dir, "*.meta.json"))):
        name = json.load(open(meta, encoding="utf-8")).get("description", "")
        if a.match not in name:
            continue
        calls, shots, seconds, t = count(meta[: -len(".meta.json")] + ".jsonl")
        rows.append({"run": name, "calls": calls, "screenshots": shots, "seconds": seconds, **t,
                     "total": sum(t.values())})
    w = csv.DictWriter(open(a.csv, "w", newline="", encoding="utf-8") if a.csv else sys.stdout,
                       fieldnames=["run", "calls", "screenshots", "seconds", "wrote", "docs", "read", "images", "total"])
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: r["run"]))
    if a.summary:
        summary(rows, a.summary)


def summary(rows, path):
    groups = {}
    for r in rows:
        _, tool, steps, _ = r["run"].split()
        groups.setdefault((LABELS.get(tool, tool), int(steps)), []).append(r)
    out, totals = [], {}
    for (tool, steps), runs in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0] != "diagonaldiagrams", kv[0][0])):
        tokens = [r["total"] for r in runs]
        out.append({"steps": steps, "tool": tool, "tokens": round(statistics.mean(tokens)), "low": min(tokens),
                    "high": max(tokens), "calls": statistics.mean(r["calls"] for r in runs),
                    "screenshots": statistics.mean(r["screenshots"] for r in runs),
                    "seconds": round(statistics.mean(r["seconds"] for r in runs))})
        t = totals.setdefault(tool, {"runs": 0, "tokens": 0, "calls": 0, "screenshots": 0, "seconds": 0})
        t["runs"] += len(runs)
        for k in ("calls", "screenshots", "seconds"):
            t[k] += sum(r[k] for r in runs)
        t["tokens"] += sum(tokens)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({k: (f"{v:g}" if isinstance(v, float) else v) for k, v in r.items()} for r in out)
    print("\n| | Runs | Tokens | Calls | Screenshots | Time |\n| --- | --- | --- | --- | --- | --- |", file=sys.stderr)
    for tool, t in totals.items():
        print(f"| {tool} | {t['runs']} | {t['tokens'] / 1000:.1f}k | {t['calls']} | {t['screenshots']} | "
              f"{round(t['seconds'] / 60)} min |", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Count the tokens an agent spent on a task, leaving out the harness.

Reads Claude Code subagent transcripts (*.jsonl beside *.meta.json) and counts only the task's own
content: what the agent wrote (tool inputs and text) and what came back (tool results and images).
The system prompt, tool definitions, and reminders the harness adds are the same for any task, so
they are not counted. Neither is the run's final report to its caller.

Text is counted at 4 characters per token. An image is counted at Claude's rate: scaled to fit
1568 px and 1.15 megapixels, then width x height / 750. Thinking is redacted in transcripts and is
not counted for either method.

    py -3 scripts/bench_tokens.py TRANSCRIPT_DIR [--match Bench] [--csv OUT.csv]
"""
import argparse
import base64
import csv
import glob
import json
import math
import os
import struct
import sys

SKIP_TOOLS = {"SubagentHandback"}


def image_tokens(b64):
    head = base64.b64decode(b64[:64] + "=" * (-len(b64[:64]) % 4))
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return 1600  # not a PNG: count a full-size image
    w, h = struct.unpack(">II", head[16:24])
    s = min(1.0, 1568 / max(w, h), math.sqrt(1_150_000 / (w * h)))
    return int(w * s * h * s / 750)


def count(path):
    calls, wrote, read, docs, images, shots = set(), 0, 0, 0, 0, 0
    doc_ids = set()
    for line in open(path, encoding="utf-8"):
        o = json.loads(line)
        if o.get("type") == "assistant":
            m = o["message"]
            calls.add(m["id"])
            for c in m.get("content", []):
                if c.get("type") == "text":
                    wrote += len(c["text"])
                elif c.get("type") == "tool_use" and c["name"] not in SKIP_TOOLS:
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
    toks = {"wrote": round(wrote / 4), "docs": round(docs / 4), "read": round(read / 4), "images": images}
    return len(calls), shots, toks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--match", default="Bench")
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = []
    for meta in sorted(glob.glob(os.path.join(a.dir, "*.meta.json"))):
        name = json.load(open(meta, encoding="utf-8")).get("description", "")
        if a.match not in name:
            continue
        calls, shots, t = count(meta[: -len(".meta.json")] + ".jsonl")
        rows.append({"run": name, "calls": calls, "screenshots": shots, **t, "total": sum(t.values())})
    w = csv.DictWriter(open(a.csv, "w", newline="", encoding="utf-8") if a.csv else sys.stdout,
                       fieldnames=["run", "calls", "screenshots", "wrote", "docs", "read", "images", "total"])
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: r["run"]))


if __name__ == "__main__":
    main()

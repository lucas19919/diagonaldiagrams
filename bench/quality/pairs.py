"""Build the blind judging batches: python bench/quality/pairs.py JUDGE_DIR

Pairs (62):
  A  the agents' figures: dd against Pele and against Mermaid, run 1 with run 1 and run 2 with run 2 (16)
  L  one Mermaid source drawn by each tool: dd-Pele and dd-Mermaid (17 sources, 34)
  N  our reference figures from their native specs against Pele's and Mermaid's drawing of the
     Mermaid translation (6 references, 12)

Each pair is judged in two placements (slide, column), in both orders, by two judge models. A batch
holds one model, one placement and one order of about 21 pairs on slides or 11 in the column (its tall figures come in several tiles), so no
judge sees a pair twice.
The images go to JUDGE_DIR/<batch>/ under blind names (pNN-A.png, pNN-B-2of5.png); which figure is
which is written only to bench/quality/judgments/key.json, outside the judges' folders."""
import json, os, random, shutil, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TILE_H, OVERLAP = 1100, 60
MODELS = ("sonnet", "opus")
CONTEXTS = ("slide", "column")
PER_BATCH = {"slide": 21, "column": 11}


def pairs():
    out = []
    for s in ("05", "11", "20", "40"):
        for r in ("r1", "r2"):
            for other in ("pele", "mermaid"):
                out.append({"id": f"A-{s}-{r}-dd~{other}", "family": "A", "size": s, "tools": ["dd", other],
                            "figs": [f"A-{s}-{r}-dd", f"A-{s}-{r}-{other}"]})
    srcs = sorted(f[:-4] for f in os.listdir(os.path.join(HERE, "sources")) if f.endswith(".mmd"))
    for src in srcs:
        size = src.split("-")[1]  # bench-20-a -> 20, ref-arch-... -> arch, ex-er-shop -> er
        for a, b in (("dd", "pele"), ("dd", "mermaid")):
            out.append({"id": f"L-{src}-{a}~{b}", "family": "L", "size": size, "source": src, "tools": [a, b],
                        "figs": [f"L-{src}-{a}", f"L-{src}-{b}"]})
    for src in srcs:
        if src.startswith("ref-"):
            for other in ("pele", "mermaid"):
                out.append({"id": f"N-{src}-dd~{other}", "family": "N", "size": src.split("-")[1], "source": src,
                            "tools": ["dd", other], "figs": [f"N-{src}-dd", f"L-{src}-{other}"]})
    return out


def tiles(png):
    im = Image.open(png)
    w, h = im.size
    if h <= TILE_H + OVERLAP:
        return [im]
    n = -(-(h - OVERLAP) // (TILE_H - OVERLAP))
    step = (h - TILE_H) / (n - 1)
    return [im.crop((0, round(i * step), w, round(i * step) + TILE_H)) for i in range(n)]


def main():
    judge_dir = sys.argv[1]
    rng = random.Random(20261019)
    ps = pairs()
    key = {"pairs": {p["id"]: p for p in ps}, "batches": {}}
    if os.path.isdir(judge_dir):
        shutil.rmtree(judge_dir)
    n_batch = 0
    for model in MODELS:
        for ctx in CONTEXTS:
            for order in (0, 1):
                # order 0 shows a random side first; order 1 shows the same pairs swapped
                todo = ps[:]
                rng.shuffle(todo)
                k = -(-len(todo) // PER_BATCH[ctx])
                for chunk in (todo[i::k] for i in range(k)):
                    n_batch += 1
                    bid = f"b{n_batch:02d}"
                    folder = os.path.join(judge_dir, bid)
                    os.makedirs(folder)
                    items = []
                    for j, p in enumerate(chunk, 1):
                        first = (hash_side(p["id"], model, ctx) + order) % 2  # which of figs is shown as A
                        a, b = p["figs"][first], p["figs"][1 - first]
                        files = {}
                        for side, fig in (("A", a), ("B", b)):
                            ts = tiles(os.path.join(HERE, "png", ctx, fig + ".png")) if ctx == "column" else \
                                [Image.open(os.path.join(HERE, "png", ctx, fig + ".png"))]
                            names = []
                            for t, im in enumerate(ts, 1):
                                name = f"p{j:02d}-{side}.png" if len(ts) == 1 else f"p{j:02d}-{side}-{t}of{len(ts)}.png"
                                im.save(os.path.join(folder, name))
                                names.append(name)
                            files[side] = names
                        items.append({"n": j, "pair": p["id"], "A": a, "B": b, "files": files})
                    key["batches"][bid] = {"model": model, "context": ctx, "order": order, "items": items}
    os.makedirs(os.path.join(HERE, "judgments"), exist_ok=True)
    with open(os.path.join(HERE, "judgments", "key.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, indent=1)
    tokens = {}
    for bid, b in key["batches"].items():
        px = sum(Image.open(os.path.join(judge_dir, bid, n)).size[0] * Image.open(os.path.join(judge_dir, bid, n)).size[1]
                 for it in b["items"] for side in "AB" for n in it["files"][side])
        tokens[bid] = round(px / 750 / 1000)
    print(f"{len(ps)} pairs, {n_batch} batches; image k-tokens per batch:", tokens)


def hash_side(pid, model, ctx):
    import hashlib
    return hashlib.sha256(f"{pid}|{model}|{ctx}".encode()).digest()[0] % 2


if __name__ == "__main__":
    main()

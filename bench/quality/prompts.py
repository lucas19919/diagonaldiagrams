import json, os, sys
Q = r"D:\Repos\diagonaldiagrams\.claude\worktrees\sweet-wing-9aaa06\bench\quality"
J = r"C:\Users\lucas\AppData\Local\Temp\claude\D--Repos-diagonaldiagrams--claude-worktrees-sweet-wing-9aaa06\1750134b-7f1e-45d8-8a21-683024afa1e9\scratchpad\judge"
PLACE = {
 "slide": "Each image is a whole 16:9 presentation slide (1600 x 900 pixels) with the figure fitted onto it, as an audience sees it on a screen or projector. Nobody can zoom or scroll: what is legible on the slide is what the audience can read.",
 "column": "Each figure sits in a narrow document or notes column, 700 pixels wide (as in a notes app or a README), drawn at 1.5x for a sharp screen. The reader scrolls down the page but does not zoom: a figure wider than the column is shrunk to fit it. A tall figure comes as several images that continue each other from top to bottom, with a small overlap: `p03-A-1of5.png` is the top and `p03-A-5of5.png` the bottom. Read all of them as one figure.",
}
key = json.load(open(os.path.join(Q, "judgments", "key.json")))
tpl = open(os.path.join(Q, "judge_prompt.md"), encoding="utf-8").read()
for bid in sys.argv[1:]:
    b = key["batches"][bid]
    print(f"=== {bid} {b['model']} {b['context']}")
    files = "\n".join(f"- p{it['n']:02d}: A = " + ", ".join(it["files"]["A"]) + "; B = " + ", ".join(it["files"]["B"])
                      for it in b["items"])
    print(tpl.format(folder=os.path.join(J, bid), n=len(b["items"]), placement=PLACE[b["context"]], files=files))

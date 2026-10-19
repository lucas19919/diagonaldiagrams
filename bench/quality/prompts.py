r"""Write each judge batch's instructions: python bench/quality/prompts.py JUDGE_DIR [--run RUN]

Fills judge_prompt.md for every batch in judgments/key.json and writes JUDGE_DIR/bNN/instructions.md. Each judge
was then started as a fresh subagent (Sonnet or Opus, as the batch says) with only: "Read the file
JUDGE_DIR\bNN\instructions.md and follow it exactly. It is your whole task; open nothing outside that folder."
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLACE = {
    "slide": "Each image is a whole 16:9 presentation slide (1600 x 900 pixels) with the figure fitted onto it, as an "
             "audience sees it on a screen or projector. Nobody can zoom or scroll: what is legible on the slide is what "
             "the audience can read.",
    "column": "Each figure sits in a narrow document or notes column, 700 pixels wide (as in a notes app or a README), "
              "drawn at 1.5x for a sharp screen. The reader scrolls down the page but does not zoom: a figure wider than "
              "the column is shrunk to fit it. A tall figure comes as several images that continue each other from top "
              "to bottom, with a small overlap: `p03-A-1of5.png` is the top and `p03-A-5of5.png` the bottom. Read all of "
              "them as one figure.",
}


def main():
    judge_dir = os.path.abspath(sys.argv[1])
    root = os.path.join(HERE, "runs", sys.argv[3]) if sys.argv[2:3] == ["--run"] else HERE  # a rerun: pairs.py --run
    with open(os.path.join(root, "judgments", "key.json"), encoding="utf-8") as f:
        key = json.load(f)
    with open(os.path.join(HERE, "judge_prompt.md"), encoding="utf-8") as f:
        tpl = f.read()
    for bid, b in key["batches"].items():
        files = "\n".join(f"- p{it['n']:02d}: A = " + ", ".join(it["files"]["A"]) + "; B = " + ", ".join(it["files"]["B"])
                          for it in b["items"])
        folder = os.path.join(judge_dir, bid)
        with open(os.path.join(folder, "instructions.md"), "w", encoding="utf-8") as f:
            f.write(tpl.format(folder=folder, n=len(b["items"]), placement=PLACE[b["context"]], files=files))
    print(f"wrote instructions for {len(key['batches'])} batches")


if __name__ == "__main__":
    main()

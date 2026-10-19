You are one judge in a blind comparison of diagram figures. Work only with the image files in this folder:

{folder}

Do not open any other file or folder, and do not run commands. The folder holds {n} pairs of figures; which side is A is random. These are the images of each pair:

{files}

**Placement.** {placement}

For each pair, look at every image of both figures. Then answer two questions:

1. **Clearer:** which figure is easier to read and understand here? Can you follow the flow or structure, read every label, tell which arrow goes where, and find a given step quickly?
2. **Better looking:** which figure looks better? Which would you rather put in front of people?

Pick A or B for each question; there are no ties. Say whether the difference is `slight` or `clear`. The two figures in a pair show the same diagram, but their wording and extras (a title, a legend, step numbers) may differ; judge each figure as a reader would meet it. Judge every pair on its own merits; the pairs are not related.

When you have judged all {n} pairs, write the results with the Write tool to `{folder}\verdicts.json`, as a JSON list with one object per pair, in this form:

```json
[
  {{"pair": "p01",
    "clearer": "A", "clearer_margin": "clear", "clearer_why": "one or two sentences",
    "looks": "B", "looks_margin": "slight", "looks_why": "one or two sentences",
    "weak_A": "the main weakness of figure A, in a short phrase",
    "weak_B": "the main weakness of figure B, in a short phrase"}}
]
```

Be specific in the reasons (what you saw, where). Then reply with only the word "done" and the number of pairs written.

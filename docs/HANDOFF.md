# Handoff: where the redesign stands (2026-10-19)

This brief is for whoever continues the work in docs/PLAN.md. docs/DESIGN.md says what the engine should be, PLAN.md says in what order to build it, and the "As built" notes in DESIGN record where the build differs. Read those three. This file adds what they don't: the current state, what's open, how to check your work, and the habits that kept output stable.

## State of the repository

- **Branches.** Each phase is a branch stacked on the one before: `master` (= origin/master, 0.5.0) → `p0-baseline` → `p1-package` → `p1b-bugs` → `p2-core` → `p3-style` → `p4-layout`.
  - Three slices sit on `p4-layout`, ahead of P5, each stacked on the one before: `slice-edit-animate` (edit a diagram in its page, apply the patch, animate the change), `slice-stories` (views of one figure in one page) and `slice-edit-hardening` (keyboard editing, moves along the layout's layers, messages, regeneration). `b29-fuzz` (the B29 fixes, also on `p4-layout`) is merged into `slice-stories`.
  - `slice-integration`, on `slice-edit-hardening`, holds everything built through 2026-10-18. It merges three stacks built in side sessions, each on its own `claude/...` branch:
    - the default look for flow, arch, seq and schema (B25, DESIGN 8.5), the straight trunk in long flows, and default text judged by the audit (`data-legibility`);
    - pins in flow and arch (DESIGN 4.6), and the router fixes pins exposed (B30);
    - motion from meaning: a story view's `trace` and `flow`, filmed as a GIF or MP4 (DESIGN 21.2.1).
  - `slice-slim`, on `slice-integration`, is current. The owner found the human editing of little use in a tool for agents, and asked what was overcomplicated. With their go-ahead, it cuts four things, one commit each, with the docs:

    | Cut | Package lines | Why |
    | --- | --- | --- |
    | Pins in flow and arch: `not-drawn` again (DESIGN 4.6) | −286 | two layouts per figure, still failing some pin fuzz; `place`, `rank` and `order` do it in one |
    | The v1 engine (`legacy.py`, `--layout-engine v1`); schema `x`/`y` draw with v2 as columns (DESIGN 7.3) | −746 | v2 passes every gate; the flag never shipped |
    | The page's Edit mode; the change animation stays (DESIGN 21.4) | −407 | about 400 lines of untested page script for people; agents write patches |
    | `gif.py` and `_cdp.py`; `--svg` writes an animated SVG, and `--gif` and `--video` go through ffmpeg (DESIGN 21.2.1) | −651 | ffmpeg codes GIFs better; the SVG needs nothing |

    Package code went from 22,913 lines (21,948 Python, 965 JavaScript) to 20,823 (20,264 and 559), and tests from 5,257 to 4,891. Every gate passed at d37c304: unit 242, style 7, smoke 264 with `DD_ENTRY` unset and `module`, 115 goldens byte-identical and deterministic, scene round trip 29/29 (69/69 with `--fuzz 40`), fuzz 0 failed at seeds 5000 and 20000 (200, `--strict`) and 0 of 1,000 at seeds 0, 20000 and 40000.
  - `fit-placement`, on `slice-slim`, says where a figure will be read: `--fit slide|page|column`, a Mermaid front matter line `fit: column`, or a spec's `size.fit` (DESIGN 7.3). It is the top fix from the blind quality benchmark (`bench-quality-0.8`, bench/quality/README.md), where 116 of the 160 judgments dd lost were in a 700 px column. `slide` stays the default, so no golden changed. In a `column`, a long flow stays one strip, a layer too wide for 640 px is dealt into stacked columns (`layout/rows.py`), and a wide schema stacks its tables. `tests/fuzz/run.py --fit column` fuzzes that path; it is not a CI gate. The column judging was rerun on `bench-quality-fit` (bench/quality/runs/fit-column). Gates: unit 254, style 7, smoke 267 with `DD_ENTRY` unset and `module`, 115 goldens byte-identical and deterministic, scene round trip 29/29, fuzz 0 failed at seeds 5000 and 20000 (200, `--strict`).
  - `fit-arch-whole`, on `fit-placement`, deals a too-wide layer into rows only where that takes less of the column than keeping the layers whole and shrinking the figure (`layered.room`: height with title and legend, times width in column widths). The column judging found the dealt arch figures three screens tall with arrows wrapping round their columns: the grouped checkout figures lost all 8 of their judgments. Now both checkout figures keep their layers (956 x 886 and 880 x 876, against 638 x 1716 and 651 x 1700), the agent platforms deal one group (822 x 970 and 679 x 1314, against 797 x 1264 and 579 x 1782), an 8-service fan-out still deals, and every flow, schema and sequence figure in the benchmark draws byte-identical. The arch column pairs were judged again on `bench-quality-fit-arch` (bench/quality/runs/fit-column-arch, 32 judgments): clearer, dd's native arch went from 50% and 50% to 88% and 88% against Pele and Mermaid, and the same-source arch from 0% and 0% to 0% and 38%. The Mermaid agent platform still loses on its bundle of parallel edges out of Agent. Gates: unit 256, style 7, smoke 267 with `DD_ENTRY` unset and `module`, 115 goldens byte-identical and deterministic, scene round trip 29/29, fuzz 0 failed at seeds 5000 and 20000 (200, `--strict`), and the same with `--fit column`.
  - The six phase branches are on GitHub since 2026-10-17, as a backup. `slice-integration` is on GitHub too, as PR #1 against `master` (CI green, not merged). `slice-slim`, the other slices, the `claude/...` branches and `b29-fuzz` are local only. Nothing is merged into `master`: anyone who installs from the README still gets 0.5.0.
  - CI runs on pushes to `master` and on PRs, so the phase branches have not run in CI yet.
- **Version.** 0.8.0 in `diagonaldiagrams/__init__.py`, `.claude-plugin/plugin.json` and `server.json` (they must match). Nothing past 0.5.0 has been released.
- **Rules from the owner:**
  - No push, PR, merge, release or publish without their go-ahead, given for that action.
  - Downloads need permission too: font files for bundled metrics, and npm for the Pyodide check.

## Phases

| Phase | Status | Where |
| --- | --- | --- |
| P0 Baseline and safety net | done | goldens (115 figures), fuzz harness, `scripts/metrics.py`, `bench/metrics/baseline.md` |
| P1 Package split | done | `graph.py` is a shim over the `diagonaldiagrams` package; `bench/metrics/p1.md` |
| P1b Known bugs B1–B9 | done | |
| P2 Core seams | done | scene model, display list, audit as registered checks, patches (`apply`), receipts v2, sanitizer, registries, a11y; `bench/metrics/p2.md` |
| P3 Style system and text | done (0.7.0) | cascade, token themes, presets, decorations, encodings, text layout, font files, project config and brand policy; `bench/metrics/p3.md` |
| P4 Layout and routing kernels | built (0.8.0); fuzz 0 of 1,000 on seeds 0, 20000, 40000 (B29) | PLAN P4 status |
| P5–P13 | not started | PLAN.md, one section each |

## P4 as it stands

- **Layout.** flow, arch and schema draw with the layered kernel (`layout/`) once, with no repair loop. Schema runs it left to right with each relation pinned to its column rows (`from_at`, `to_at`). seq draws from `layout/sequence.py`. The v1 engine (`legacy.py`, `--layout-engine v1`) was removed on `slice-slim`; schema tables placed with `x` and `y` draw with v2, as a column and a place in it (DESIGN 7.3).
- **Deleted on 2026-10-17:** eight kernels and the container protocol (`layout/base.py`) that no renderer called. DESIGN 7.3 says why and when each comes back. Don't restore them without a caller.
- **Labels** keep the case the spec gives (B26). Group titles and the figure label stay small caps.
- **Fuzz.** CI gates seeds 5000 and 20000 (200 scenes each, `--strict`). A nightly workflow fuzzes 1,000 new seeds and uploads the failures. B29 fixed what seeds 0 and 40000 found (about 0.5% of scenes); those sets and seed 20000 now fail 0 of 1,000. New seeds may still find more: add each as a `FuzzRegressions` test in `tests/unit/test_layout.py`.
- **Open in P4:** P4.9–P4.12, constraints beyond rank, lane and order, and LR, BT and RL for flow and arch. P4.1 (nested groups and the container protocol) moves to P5.

## What's next

The owner asked for animation and better editing ahead of P5. Three slices were built (PLAN's P10 and P9 statuses, DESIGN 21.2 and 21.4 as-built), and `slice-slim` then cut the parts an agent doesn't use:
- **Edit loop:** an agent writes a patch (`place`, `order`, `text`, `style`, ...); `apply` writes it into the spec; drawing again at the same path keeps the other boxes near their places, reports `changed`, and animates the old drawing into the new one. `diff` compares any two drawings. A kept patch applied again after the spec is regenerated keeps every edit or reports it (`tests/unit/test_regeneration.py`).
- **Pins:** removed on `slice-slim` (2026-10-19). A pin on a flow or arch node is `not-drawn` again; `place`, `rank` and `order` say where a box goes (DESIGN 4.6). The router fixes pins exposed (B30) stay.
- **Stories:** `story STORY.json -o OUT.html` presents one figure as views (focus, dim, hide, highlight, reveal) in one page that animates between them.
- **Motion:** a view's `motion` block traces a path or sets dots flowing along arrows; the page plays it, `story ... --svg` writes it as an animated SVG, and `--gif` or `--video` film it through ffmpeg (DESIGN 21.2.1).
- **The default look** (DESIGN 8.5): labels beside their arrows, boxes that fit their text, balanced arch, a straight trunk in long flows, default text that passes contrast and size checks. Blind pairwise judging: 103 of 104 for the new look.

Next is the owner's call: bring the chart kinds up to the new look (P6, P8), a dark product theme and isometric 3D (P7), widen stories, or go back to P5.

## Decisions that wait on the owner

- **Downloads:** font files for bundled metrics (Inter, Selawik, Roboto, Liberation Sans) and npm for the Pyodide check.
- **Merging, pushing, releasing:** all theirs.
- The defaults table in PLAN ("Decisions needed") applies wherever nobody has decided.

## How to check a change

```
python -m unittest discover tests/unit
python -m unittest discover tests/style
python tests_smoke.py
python scripts/golden.py                      # byte-compare 115 figures; prints what changed
python scripts/golden.py --update --only NAME ...   # only after reviewing the change
python scripts/scene_roundtrip.py
python tests/fuzz/run.py --n 200 --seed 5000 --strict      # what CI gates (also --seed 20000)
python tests/fuzz/run.py --n 200 --seed 5000 --fit column  # the narrow-column path (--fit), not gated
python tests/fuzz/run.py --n 1000 --seed 40000 --keep DIR  # new seeds find what the gate misses
python tests/fuzz/run.py --one KIND SEED NODES             # one scene, from a --keep JSON
python scripts/metrics.py --save NAME --compare bench/metrics/p3.json
```

**Reviewing golden changes.**
- Rasterize old and new and look at them side by side: `diagonaldiagrams.export._raster_svg(svg_text, png_path, "png", width)` uses headless Edge.
- Also compare each golden's `exit` against the previous commit. A figure that drops from passing to failing the audit is easy to miss by eye; it happened once here.
- When a change should touch only text (letter case, wording), check it mechanically: compare each old and new file case-folded, and the exits, rather than looking at 30 pictures.

**Fuzz failures.** Before calling one a regression, render the same spec on the commit before yours, from a `git archive` export, not by swapping one file into this tree.

**Timing.**
- This machine's speed swings up to 2×. Never compare against a number recorded on another day.
- Measure the reference tree and the new one interleaved, in the same session. Export the reference with `git archive` or a worktree.
- Measure compiled and uncompiled separately. `PYTHONDONTWRITEBYTECODE=1` is set here, so every import compiles from source. To time with bytecode, unset it *and* set `PYTHONPYCACHEPREFIX=<temp dir>`, then warm once: the prefix alone does nothing while writing is off. On 2026-10-17 a flow render took about 1 s uncached and 0.25–0.3 s cached through the CLI. A warm in-process call (the MCP path) took about 20 ms.

## Habits and gotchas

- **Line endings.** git `autocrlf=true`, and files mix CRLF and LF. When editing from a script, read with `newline=""`, keep the file's own line ending, and write it back the same way.
- **Edit scripts.** bash heredocs mangle `\\n` and sometimes quotes. Write an edit script to a file and run it, or use an editor tool. An edit script should assert each old string occurs exactly once before replacing, and write nothing unless every replacement matched.
- **Commits.** `git commit --amend` and a bare `git commit` take everything staged, including a `git rm` meant for a later commit. Stage per commit, or commit with explicit paths.
- **Printing non-Latin text** needs `PYTHONIOENCODING=utf-8`.
- **Default output is a contract.** Until a change deliberately alters it, goldens stay byte-identical. When output changes, review every changed figure and update only the reviewed ones.
- **Performance.** Keep the import path small and lazy; DESIGN 16 has the budgets. Don't use `dataclasses` on the render path (25–40 ms per import here); the code uses slotted classes.
- **Writing.** Docs, docstrings and commit messages are plain prose: short sentences, concrete, no jargon. Commit subjects are imperative and name the PLAN task, for example "(P4.3)".
- **Claims.** Write a status from what was run, on what seeds, at which commit. The 2026-10-14 P4 status claimed every exit criterion and kernels that nothing called, and had to be corrected.

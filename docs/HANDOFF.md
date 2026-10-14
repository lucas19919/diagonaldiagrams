# Handoff: where the redesign stands (2026-10-14)

This brief is for whoever continues the work in docs/PLAN.md. docs/DESIGN.md says what the engine should be, PLAN.md says in what order to build it, and the "As built" notes in DESIGN record where the build differs. Read those three. This file adds what they don't: the current state, what's half done, how to check your work, and the habits that kept output stable.

## State of the repository

- **Branches.** Each phase is a branch stacked on the one before. None is merged into `master`, and none is pushed:
  - `master` (= origin/master) → `p0-baseline` → `p1-package` → `p1b-bugs` → `p2-core` → `p3-style` → `p4-layout` (current, 49 commits ahead of master).
  - Each branch ends with a commit that closes its phase, except `p4-layout`, which is mid-phase.
- **Version.** `diagonaldiagrams/__init__.py` says 0.7.0, and so do `.claude-plugin/plugin.json` and `server.json` (they must match). P4 closes at 0.8.0.
- **Working tree.** Clean at commit `f068f01`.
- **Nothing has left the machine.** The owner's rules are:
  - No push, PR, release or publish without their explicit go-ahead.
  - Downloads need permission too: font files for bundled metrics, and npm for the Pyodide check.

## Phases

| Phase | Status | Where |
| --- | --- | --- |
| P0 Baseline and safety net | done | goldens (115 figures), fuzz harness, `scripts/metrics.py`, `bench/metrics/baseline.md` |
| P1 Package split | done | `graph.py` is a shim over the `diagonaldiagrams` package; `bench/metrics/p1.md` |
| P1b Known bugs B1–B9 | done | |
| P2 Core seams | done | scene model, display list, audit as registered checks, patches (`apply`), receipts v2, sanitizer, registries, a11y; `bench/metrics/p2.md` |
| P3 Style system and text | done (0.7.0) | cascade, token themes, presets, decorations, encodings, text layout, font files, project config and brand policy; `bench/metrics/p3.md` |
| P4 Layout and routing kernels | in progress | see below |
| P5–P13 | not started | PLAN.md, one section each |

## P4: what is built

flow and arch now draw from a layered layout kernel in one pass. There is no repair loop.

**Modules (`diagonaldiagrams/layout/`):**
- `rank.py`: v1's cycle breaking, then the longest path compacted by the network simplex (up to 400 nodes per connected part).
- `order.py`: layers sorted as a tree, so group members stay contiguous. Port items carry back edges; sweeps, transposition and port-side trials keep the best ordering.
- `bk.py`: Brandes–Köpf coordinates, with group borders forced into one block, so every frame is a rectangle.
- `channels.py`: a track per sideways run in each gap, with doglegs for runs that trade columns.
- `layered.py`: the pipeline, ports and routes.
- `wrap.py`: folds layouts of 12+ layers into columns near the target aspect (4:3, or `size.aspect`).

**Renderers.** `diagrams.py` has the new `render_flow` and `render_arch` (shared `_layered`). The v1 code moved verbatim to `legacy.py`, reachable with `--layout-engine v1`, which still matches the v1 bytes; the receipt records it, and export honors it. `render_schema` still calls the v1 code in `legacy.py`. `render_seq` is unchanged.

**Back-edge styles.** flow climbs beside its nodes (`back: "side"`). arch rises from the top port of the lower box to the bottom of the upper one (`back: "ports"`).

**Audit change.** Arrows that meet end to start through a junction dot count as one path, not a shared line (`audit/checks.py`, `shared_runs`).

**Measured:**
- **Fuzz:** 0 of 1,000 scenes fail the audit, and 0 of 1,000 more on seeds from 5000 (P3 had 149 of 200 failing).
- **Big flows:** gen-flow-40 renders in about 77 ms, against 3.8 s at P3, with no redraws; wrapped, it is 2372 × 1528, aspect 1.55. gen-flow-20 takes about 29 ms (1272 × 892).
- **Goldens:** 24 figures changed. Each was compared side by side with v1, and the five that got worse along the way were fixed. No golden's exit code got worse.
- **Tests:** unit (161), style demos (7), smoke (256) and goldens (115) pass; `scripts/scene_roundtrip.py` gives 29/29.

`tests/unit/test_layout.py` tests the kernel by invariants rather than pixels:
- simplex optimality and crossing counts;
- no box overlaps, orthogonal routes ending on their boxes;
- frames hold only their members;
- back-edge styles, directions and wrapping.

## P4: what is left

1. **Speed at 200 nodes.** A generated 200-node flow takes 3.4 s against the exit target of 1 s; a 200-node arch takes 0.7 s. Profile it first. Ordering is the likely cost: `_sort_layer`'s per-call dict building, and port trials (`_flip_ports` skips arrows that cross nothing, which took gen-flow-40 from about 115 to 77 ms). P4.11's budgets go further: 1,000 and 10,000 nodes, laying out per group and then composing.
2. **P4.1:** the container protocol (`layout/base.py`, measure bottom-up and place top-down) and groups with their own `layout`. Nothing yet: groups are clusters inside the layered kernel.
3. **P4.4:** labels as a module. Placement is still `_draw._place_label` (shared with v1, so don't change its behavior), seeded by `diagrams._longest`, which avoids frame borders.
4. **P4.5:** the other kernels. stack, grid, tree, radial, force, manual, sequence (with activations and fragments), table (schema rows as ports), timeaxis. Schema and seq then move onto them; B6 and schema's swap loop stay in `legacy.py` until then.
5. **P4.7:** grow `tests/fuzz/gen.py` to nested groups, lanes, constraints, every shape, long labels, self-loops and 5–200 nodes, then get back to zero. Turn on `run.py --strict` in CI with a fixed seed set.
6. **Smaller items:**
   - P4.8: export `--layout` presets (`size.aspect` already drives wrap);
   - P4.9: incremental layout from the receipt;
   - P4.10: page model;
   - P4.12: verdict `metrics`, `--preview png`, `--candidates N`.
   - Constraints (DESIGN 4.6) beyond rank, lane and order are not read yet: same-rank, above, align, pin, together.
   - LR, BT and RL work in the kernel (unit-tested) but no renderer offers them yet.
7. **Close-out:**
   - Rerun `scripts/metrics.py --save p4 --compare bench/metrics/p3.json`. The exit wants corpus crossings and wire at or under baseline, so check that.
   - Update the scoreboard and the bug table: B18–B23 are fixed in the new path but still listed as targets.
   - Run `scripts/build_site.py` and review the gallery.
   - Bump to 0.8.0 in all three places.
   - Write the PLAN P4 status. A partial one is already there.

## Decisions that wait on the owner

- **B25** (P8): the default themes miss WCAG AA (editorial `soft` 3.5:1, accent text 2.9:1, 7–8 px tags). Fixing it moves every default figure. Until then, the contrast and min-size checks judge only stylesheet-set values.
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
python tests/fuzz/run.py --n 1000 [--seed 5000] [--keep DIR]
python scripts/metrics.py --save NAME --compare bench/metrics/p3.json
```

**Reviewing golden changes.**
- Rasterize old and new and look at them side by side: `diagonaldiagrams.export._raster_svg(svg_text, png_path, "png", width)` uses headless Edge.
- Also compare each golden's `exit` against the previous commit. A figure that drops from passing to failing the audit is easy to miss by eye; it happened once here.

**Timing.**
- This machine's speed swings up to 2×. Never compare against a number recorded on another day.
- Measure the reference tree and the new one interleaved, in the same session. Export the reference with `git archive` or a worktree.
- Measure compiled and uncompiled separately: `PYTHONDONTWRITEBYTECODE=1` is set here, so every import compiles from source. Use `PYTHONPYCACHEPREFIX=<temp dir>` to time with bytecode without littering the repo.

## Habits and gotchas

- **Line endings.** git `autocrlf=true`, and files mix CRLF and LF. When editing from a script, read with `newline=""`, keep the file's own line ending, and write it back the same way.
- **Edit scripts.** bash heredocs mangle `\\n` and sometimes quotes. Write an edit script to a file and run it, or use an editor tool. An edit script should assert each old string occurs exactly once before replacing.
- **Printing non-Latin text** needs `PYTHONIOENCODING=utf-8`.
- **Default output is a contract.** Until a phase deliberately changes it, goldens stay byte-identical. When a phase changes output, review every changed figure and update only the reviewed ones.
- **Performance.** Keep the import path small and lazy; DESIGN 16 has the budgets. Don't use `dataclasses` on the render path (25–40 ms per import here); the code uses slotted classes.
- **Writing.** Docs, docstrings and commit messages are plain prose: short sentences, concrete, no jargon. Commit subjects are imperative and name the PLAN task, for example "(P4.3)".
- **Session-only tools.** The previous session's helper scripts lived in its scratchpad and are gone: an interleaved timer, a CLI timer, a side-by-side golden review sheet, a "which arrow crosses this box" finder, and a debug viewer for raw layouts. Recreate them if needed. Each was under 60 lines.

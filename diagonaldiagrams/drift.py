"""monitor and sync: notice when code and its diagrams drift apart, and fix it."""
import json, os, sys
from .errors import SpecError
from ._proc import _self_cmd
from ._lazy import lazy

_merge_specs = lazy("diagonaldiagrams.extract", "_merge_specs")
_spec_diff = lazy("diagonaldiagrams.extract", "_spec_diff")


def do_sync(args):
    """Auto-fix bot (plan Mode 3): monitor -> extract -> validate -> doc ->
    audit, optionally commit. Default touches only the working tree; --commit
    creates a local commit of the files sync wrote, and nothing else (never
    pushes). Exit 1 if anything is left undone."""
    import re as _re
    import subprocess as _sp
    path = args.path or "."
    me, me_env = _self_cmd()
    mon = me + ["monitor", "--path", path, "--base", args.base or "HEAD"]
    if args.map:
        mon += ["--map", args.map]
    r = _sp.run(mon, capture_output=True, text=True, env=me_env)
    try:
        rep = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SpecError(f"sync: monitor produced no report:\n{r.stdout}\n{r.stderr}")
    synced, failed = [], []
    for item in rep.get("stale_domains", []):
        spec = item.get("diagram_spec", "")
        argv = item.get("remediation_argv") or []
        m = _re.match(r"(?:py graph\.py|diagonaldiagrams) extract (\w+) (\S+) -o (\S+)", item.get("remediation_cmd", ""))
        if len(argv) == 5 and argv[0] == "extract" and argv[3] == "-o":
            kind, src = argv[1], argv[2]
        elif m:
            kind, src, _ = m.groups()
        else:
            kind = src = None
        if not spec or not kind:
            failed.append({"spec": spec or item.get("domain", "?"),
                           "reason": "heuristic-only finding: add a --map mapping for machine remediation"})
            continue
        p1 = _sp.run(me + ["extract", kind, os.path.join(path, src),
                           "-o", os.path.join(path, spec)], capture_output=True, text=True, env=me_env)
        if p1.returncode:
            failed.append({"spec": spec, "reason": (p1.stderr.strip() or "extract failed")[-200:]})
            continue
        p2 = _sp.run(me + ["validate", os.path.join(path, spec)],
                     capture_output=True, text=True, env=me_env)
        if p2.returncode:
            failed.append({"spec": spec, "reason": "extracted spec fails validate"})
            continue
        ok_all, audited = True, []
        for d in (args.docs or []):
            dp = d if os.path.isabs(d) else os.path.join(path, d)
            p3 = _sp.run(me + ["doc", dp], capture_output=True, text=True, env=me_env)
            if p3.returncode:
                failed.append({"spec": spec, "reason": f"doc failed on {d}"})
                ok_all = False
                break
            for line in p3.stdout.splitlines():
                mm = _re.search(r"\[compiled\] \w+ -> (.+)", line)
                if mm:
                    pa = _sp.run(me + ["audit", mm.group(1).strip()],
                                 capture_output=True, text=True, env=me_env)
                    audited.append(mm.group(1).strip())
                    if pa.returncode:
                        failed.append({"spec": spec, "reason": f"audit failed: {mm.group(1).strip()}"})
                        ok_all = False
                        break
            if not ok_all:
                break
        if ok_all:
            synced.append({"spec": spec, "diff": item.get("diff_summary", ""), "audited": audited})
    committed = False
    if args.commit and synced and not failed:
        # only what sync wrote: the specs it extracted, the docs it compiled and their figures. Other
        # work in the tree, staged or not, stays out of the commit.
        wrote = [os.path.join(path, s["spec"]) for s in synced] + [f for s in synced for f in s["audited"]]
        wrote += [d if os.path.isabs(d) else os.path.join(path, d) for d in (args.docs or [])]
        wrote = sorted({os.path.abspath(f) for f in wrote if os.path.exists(f)})
        c2 = _sp.run(["git", "-C", path, "add", "--", *wrote], capture_output=True, text=True)
        staged = _sp.run(["git", "-C", path, "diff", "--cached", "--quiet", "--", *wrote], capture_output=True, text=True)
        if wrote and c2.returncode == 0 and staged.returncode == 1:
            names = ", ".join(s["spec"] for s in synced)
            c3 = _sp.run(["git", "-C", path, "-c", "user.email=graph-bot", "-c", "user.name=graph-sync",
                          "commit", "-m", f"chore(docs): synchronize architecture diagrams ({names})", "--", *wrote],
                         capture_output=True, text=True)
            committed = c3.returncode == 0
    out = {"ok": not failed, "synced": synced, "failed": failed, "committed": committed}
    print(json.dumps(out, indent=2))
    return 0 if not failed else 1


def do_monitor(args):
    import subprocess
    path = args.path or "."
    base = args.base or "HEAD"
    changed_files = []
    try:
        if base == "HEAD":
            # local mode: uncommitted working-tree state (tracked mods + untracked)
            r = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=path, capture_output=True, text=True)
            if r.returncode == 0:
                changed_files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
            r2 = subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True)
            if r2.returncode == 0:
                changed_files += [line[3:].strip().strip('"') for line in r2.stdout.splitlines()
                                  if line.startswith("??") and line[3:].strip()]
        else:
            # CI mode: working tree against a base ref (branch compare)
            r = subprocess.run(["git", "diff", "--name-only", base], cwd=path, capture_output=True, text=True)
            if r.returncode == 0:
                changed_files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
            else:
                r2 = subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True)
                if r2.returncode == 0:
                    changed_files = [line[3:].strip() for line in r2.stdout.splitlines() if line[3:].strip()]
    except Exception:
        pass
    changed_files = sorted(set(changed_files))
    schema_triggers = [f for f in changed_files if any(k in f.lower() for k in ("migration", "schema", "model", "entity", ".sql", ".prisma"))]
    api_triggers = [f for f in changed_files if any(k in f.lower() for k in ("route", "controller", "endpoint", "api"))]
    diagram_files = [f for f in changed_files if f.endswith((".graph.json", ".svg"))]
    stale = []
    covered = set()
    if getattr(args, "map", None) and os.path.exists(args.map):
        try:
            import fnmatch as _fn
            _maps = json.load(open(args.map, encoding="utf-8")).get("mappings", [])
            for _mp in _maps:
                _pat = _mp.get("code", "")
                covered.update(f for f in changed_files
                               if _fn.fnmatch(f, _pat) or _fn.fnmatch(f.replace("\\", "/"), _pat)
                               or _fn.fnmatch(os.path.basename(f), _pat))
        except (json.JSONDecodeError, OSError):
            pass
    schema_triggers = [f for f in schema_triggers if f not in covered]
    api_triggers = [f for f in api_triggers if f not in covered]
    if schema_triggers and not any("schema" in d.lower() for d in diagram_files):
        stale.append({"domain": "database", "changed_files": schema_triggers, "remediation": "diagonaldiagrams extract schema <model_file> -o docs/schema.graph.json"})
    if api_triggers and not any("route" in d.lower() or "arch" in d.lower() for d in diagram_files):
        stale.append({"domain": "architecture_api", "changed_files": api_triggers, "remediation": "diagonaldiagrams extract routes <route_file> -o docs/arch.graph.json"})
    if getattr(args, "map", None):
        # mapping-driven semantic check: extract code, diff against the spec.
        # No semantic difference => no drift (kills heuristic false positives).
        import fnmatch
        me, me_env = _self_cmd()
        try:
            with open(args.map, encoding="utf-8") as f:
                mappings = json.load(f).get("mappings", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise SpecError(f"bad --map file: {e}")
        for mp in mappings:
            pat, spec_rel = mp.get("code", ""), mp.get("spec", "")
            kind = mp.get("kind", "schema")
            domain = mp.get("domain", kind)
            hits = [f for f in changed_files
                    if fnmatch.fnmatch(f, pat) or fnmatch.fnmatch(f.replace("\\", "/"), pat)
                    or fnmatch.fnmatch(os.path.basename(f), pat)]
            if not hits or spec_rel in changed_files or any(s.get("diagram_spec") == spec_rel for s in stale):
                continue
            specs = []
            for h in hits:
                src = os.path.join(path, h)
                if not os.path.exists(src):
                    continue
                r = subprocess.run(me + ["extract", kind, src],
                                   capture_output=True, text=True, env=me_env)
                try:
                    specs.append(json.loads(r.stdout))
                except json.JSONDecodeError:
                    pass
            remedy = f"diagonaldiagrams extract {kind} {hits[0]} -o {spec_rel}"
            fix = {"remediation_cmd": remedy, "remediation_argv": ["extract", kind, hits[0], "-o", spec_rel]}
            if not specs:
                stale.append({"domain": domain, "changed_files": hits, "diagram_spec": spec_rel,
                              "diff_summary": "extractor produced no spec (unverifiable)", **fix})
                continue
            spec_path = os.path.join(path, spec_rel)
            if not os.path.exists(spec_path):
                stale.append({"domain": domain, "changed_files": hits, "diagram_spec": spec_rel,
                              "diff_summary": "diagram spec missing", **fix})
                continue
            with open(spec_path, encoding="utf-8") as f:
                diff = _spec_diff(json.load(f), _merge_specs(specs, kind), kind)
            if diff:
                stale.append({"domain": domain, "changed_files": hits, "diagram_spec": spec_rel,
                              "diff_summary": diff, **fix})
    drift_detected = bool(stale)
    report = {
        "ok": not drift_detected,
        "drift": drift_detected,
        "changed_files_count": len(changed_files),
        "stale_domains": stale,
        "remediation_hint": "Run suggested extraction commands or update corresponding .graph.json specs before committing."
    }
    print(json.dumps(report, indent=2))
    if args.ci and drift_detected:
        return 1

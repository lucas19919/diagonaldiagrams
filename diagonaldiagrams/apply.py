"""apply SPEC PATCH: write a patch into a spec (DESIGN 21.3, D12).

The patch's operations land in the spec as fields, constraints and style rules, so the next render,
and the next generation of the spec, keep them. A v2 scene is written back as a scene; a v1 spec
stays a v1 spec (scene-only fields keep their scene names there, which today's renderers ignore).
"""
import json
import os
import sys


def _read(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def do_apply(a):
    """Prints the JSON verdict and returns the exit code: 0 when every operation applied, 1 when
    some conflicted (the rest are still written) or nothing could be read."""
    from .inputs.v1 import detect, from_v1, to_v1
    from .mermaid import load_spec
    from .scene import check
    from .scene.patch import apply, compact
    from .validate import _json_where

    def fail(stage, errors):
        print(json.dumps({"ok": False, "stage": stage, "errors": errors,
                          "next": "fix the spec or the patch and run the same command again; nothing was written"}))
        return 1

    dest = a.o or a.spec
    if not dest.lower().endswith(".json"):
        return fail("read", [{"msg": f"apply writes JSON, and {os.path.basename(dest)} is not a .json file",
                              "fix": "pass -o OUT.json"}])
    try:
        spec = load_spec(a.spec) if a.spec.lower().endswith((".mmd", ".mermaid", ".yaml", ".yml")) else _read(a.spec)
    except (OSError, ValueError) as e:
        return fail("read", [{"msg": f"the spec can't be read: {_json_where(e)}", "fix": "check the path and the JSON"}])
    try:
        ops = _read(a.patch)
    except (OSError, ValueError) as e:
        return fail("read", [{"msg": f"the patch can't be read: {_json_where(e)}",
                              "fix": 'a patch is JSON: [{"op": "text", "id": "api", "name": "API gateway"}]'}])
    scene_in = isinstance(spec, dict) and spec.get("version") == 2
    if scene_in:
        raw = spec
    else:
        if not isinstance(spec, dict):
            return fail("validate", [{"msg": "the spec is not a JSON object", "fix": "pass a flow, arch, seq or schema spec"}])
        spec = {k: v for k, v in spec.items() if k not in ("_warnings", "_errors")}  # a Mermaid parse's notes
        raw = from_v1(spec, a.type or detect(spec))
    scene, errors, _ = check(raw)
    if errors:
        return fail("validate", errors)
    patched, applied, conflicts = apply(scene, ops)
    if scene_in:
        result, warnings = compact(patched.to_dict()), []
    else:
        _, result, warnings = to_v1(patched)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    out = {"ok": not conflicts, "applied": applied, "conflicts": conflicts, "warnings": warnings, "spec": dest}
    if conflicts:
        out["next"] = (f"{applied} operation(s) were written to the spec; the conflicts were skipped. "
                       "Read each one, then fix the patch or drop the operation")
    else:
        out["next"] = "render the spec again to see the change"
    print(json.dumps(out))
    return 0 if not conflicts else 1


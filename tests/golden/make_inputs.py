#!/usr/bin/env python3
"""Write the golden corpus inputs and tests/golden/corpus.json.

    py -3 tests/golden/make_inputs.py

Run once to create the corpus; the inputs and corpus.json are committed, so later changes to
tests_smoke.py or this script do not move the baseline by themselves. Rerun only to grow the
corpus on purpose, then review the new entries with `scripts/golden.py --update --only ...`.

Sources:
- every renderable file in examples/, with the flags the tests and the site use;
- the site's gallery and benchmark figures (scripts/build_site.py);
- one chart per `chart <kind>` (the fixtures in tests_smoke.py's charts());
- generated flowcharts at 5, 11, 20 and 40 steps, the sizes in the README benchmark;
- known bad cases: invalid specs and figures the audit rejects, so verdict errors are pinned too.
"""
import ast
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
INPUTS = os.path.join(HERE, "inputs")


def rel(*parts):
    return "/".join(parts)


def smoke_fixtures():
    """csv_body and json_body from tests_smoke.py's charts(), read without running the tests."""
    tree = ast.parse(open(os.path.join(REPO, "tests_smoke.py"), encoding="utf-8").read())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("csv_body", "json_body"):
                found[node.targets[0].id] = ast.literal_eval(node.value)
    return found["csv_body"], found["json_body"]


STEPS = ["Validate the request", "Load the customer account", "Score the fraud risk", "Reserve the stock",
         "Charge the card", "Write the ledger entry", "Notify the warehouse", "Print the shipping label",
         "Send the receipt", "Update the order status"]


def flow_spec(n):
    """A process of n steps: start, steps, a decision every fourth step, end. Some decisions loop
    back, the rest skip ahead, so the drawing needs back edges and long edges."""
    nodes = [{"id": "s0", "name": "Request received", "shape": "oval"}]
    for i in range(1, n - 1):
        if i % 4 == 3:
            nodes.append({"id": f"s{i}", "name": f"Check {i // 4 + 1} passed?", "shape": "diamond"})
        else:
            nodes.append({"id": f"s{i}", "name": f"{STEPS[i % len(STEPS)]} ({i})"})
    nodes.append({"id": f"s{n - 1}", "name": "Done", "shape": "oval"})
    edges = []
    for i in range(n - 1):
        e = {"from": f"s{i}", "to": f"s{i + 1}"}
        if nodes[i].get("shape") == "diamond":
            e["label"] = "yes"
            back = i % 8 == 3
            target = i - 2 if back else min(i + 3, n - 1)
            edges.append({"from": f"s{i}", "to": f"s{target}", "label": "no"})
        edges.append(e)
    return {"title": f"A {n}-step process", "sub": "Generated for the golden corpus.",
            "nodes": nodes, "edges": edges, "budget": False}


# Figures the audit currently rejects or draws badly; pinned so the fixes show up as diffs.
CASES = {
    "swim-review": {"title": "Code review handoff",
                    "lanes": [{"id": "dev", "name": "Developer"}, {"id": "rev", "name": "Reviewer"},
                              {"id": "ci", "name": "CI system"}],
                    "nodes": [{"id": "a", "name": "Open pull request", "lane": "dev"},
                              {"id": "b", "name": "Run tests and lint", "lane": "ci"},
                              {"id": "c", "name": "Review the diff carefully", "lane": "rev"},
                              {"id": "d", "name": "Address comments", "lane": "dev"},
                              {"id": "e", "name": "Approve", "lane": "rev"},
                              {"id": "f", "name": "Merge and deploy", "lane": "ci"}],
                    "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "d"},
                              {"from": "d", "to": "c"}, {"from": "c", "to": "e"}, {"from": "e", "to": "f"}]},
    "state-order": {"title": "Order lifecycle",
                    "nodes": [{"id": "new", "name": "New"}, {"id": "paid", "name": "Payment authorized"},
                              {"id": "pick", "name": "Picking in warehouse"}, {"id": "ship", "name": "Shipped"},
                              {"id": "del", "name": "Delivered"}, {"id": "ret", "name": "Returned to sender"}],
                    "edges": [{"from": "new", "to": "paid", "label": "pay"},
                              {"from": "paid", "to": "pick", "label": "reserve stock"},
                              {"from": "pick", "to": "ship", "label": "hand to carrier"},
                              {"from": "ship", "to": "del", "label": "scan"},
                              {"from": "ship", "to": "ret", "label": "refused"},
                              {"from": "ret", "to": "pick", "label": "restock"},
                              {"from": "paid", "to": "new", "label": "declined"}]},
}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    corpus = []

    def add(name, argv, tags):
        corpus.append({"name": name, "argv": argv, "tags": tags})

    ex = lambda f: rel("examples", f)
    # examples/: diagrams
    for name, kind, f in [
        ("flow-decision", "flow", "flow_decision.json"), ("flow-cross", "flow", "flow_cross.json"),
        ("flow-canary", "flow", "show_canary.json"),
        ("arch", "arch", "arch.json"), ("arch-agent-platform", "arch", "agent_platform.json"),
        ("arch-checkout", "arch", "checkout_platform.json"), ("arch-checkout-groups", "arch", "checkout_groups.json"),
        ("arch-grammar", "arch", "grammar_arch.json"), ("arch-palantir-stack", "arch", "palantir_stack.json"),
        ("arch-retrieval", "arch", "show_retrieval.json"),
        ("seq-checkout", "seq", "seq_checkout.json"), ("seq-grammar", "seq", "grammar_act.json"),
        ("seq-toolloop", "seq", "show_toolloop.json"),
        ("schema-ecommerce", "schema", "schema_ecommerce.json"), ("schema-store", "schema", "show_store.json"),
        ("mmd-how-it-works", "mermaid", "how_it_works.mmd"), ("mmd-checkout-sequence", "mermaid", "checkout_sequence.mmd"),
        ("mmd-shop-er", "mermaid", "shop_er.mmd"), ("mmd-icons", "mermaid", "icons.mmd"),
    ]:
        add(name, [kind, ex(f)], ["example"])
    add("flow-decision-auto", ["flow", ex("flow_decision.json"), "--auto"], ["example", "flag"])
    add("flow-decision-ink", ["flow", ex("flow_decision.json"), "--theme", "ink"], ["example", "theme"])
    add("flow-decision-sharp", ["flow", ex("flow_decision.json"), "--corners", "sharp"], ["example", "flag"])
    add("arch-print", ["arch", ex("arch.json"), "--theme", "print"], ["example", "theme"])
    add("iso-platform", ["iso", ex("iso_platform.json")], ["example", "iso"])
    add("iso-platform-ink", ["iso", ex("iso_platform.json"), "--theme", "ink"], ["example", "theme", "iso"])
    add("iso-ai-stack", ["iso", ex("showcase/ai_stack.json")], ["example", "iso"])
    add("iso-three-tier", ["iso", ex("iso_three_tier.json")], ["example", "iso"])
    # examples/: data
    add("bar-latency", ["bar", ex("bar_latency.csv"), "--cat", "service", "--val", "p99_latency_ms"], ["example"])
    add("bar-latency-styled", ["bar", ex("bar_latency.csv"), "--cat", "service", "--val", "p99_latency_ms",
                               "--no-grid", "--no-markers", "--highlight", "Payment Pipeline",
                               "--title", "Latency", "--subtitle", "p99"], ["example", "flag"])
    add("bar-latency-h", ["bar", ex("bar_latency.csv"), "--cat", "service", "--val", "p99_latency_ms",
                          "--orientation", "h", "--sort", "desc", "--unit", "ms"], ["example", "flag"])
    add("line-throughput", ["line", ex("line_throughput.csv"), "--x", "timestamp", "--y", "rps", "--group", "service"],
        ["example"])
    add("scatter", ["scatter", ex("scatter.csv"), "--x", "dose", "--y", "expr"], ["example"])
    add("scatter-groups", ["scatter", ex("scatter_groups.csv"), "--x", "dose", "--y", "expr", "--yerr", "expr_err",
                           "--group", "tissue", "--facet", "cohort", "--title", "Dose response",
                           "--subtitle", "Expression rises with dose in every tissue."], ["example", "flag"])
    add("scatter-latency", ["scatter", ex("show_latency.csv"), "--x", "context_k", "--y", "p99_ms", "--yerr", "p99_sd",
                            "--group", "machine"], ["example"])
    add("geo-cities", ["geo", ex("geo_cities.csv"), "--lat", "lat", "--lon", "lon", "--label", "city",
                       "--val", "people_m", "--title", "Cities"], ["example"])
    add("geo-ports", ["geo", ex("show_ports.csv"), "--lat", "lat", "--lon", "lon", "--label", "port",
                      "--val", "calls_k"], ["example"])
    add("chart-math-example", ["chart", "math", ex("math.json")], ["example", "chart"])

    # the site (scripts/build_site.py)
    add("site-signups", ["line", ex("signups.csv"), "--x", "month", "--y", "signups", "--group", "product",
                         "--title", "Atlas more than doubled while Beacon declined",
                         "--subtitle", "Monthly signups per product, January to June 2026",
                         "--xlabel", "Month", "--ylabel", "Signups per month"], ["site"])
    add("site-bench-tools", ["line", "docs/data/bench_tools.csv", "--x", "steps", "--y", "tokens", "--group", "tool",
                             "--highlight", "diagonaldiagrams", "--title", "Tokens per flowchart",
                             "--xlabel", "Steps in the flowchart", "--ylabel", "Tokens used (average of 2 runs)"],
        ["site"])

    # one figure per chart kind
    csv_body, json_body = smoke_fixtures()
    for kind, body in csv_body.items():
        write(os.path.join(INPUTS, "charts", kind + ".csv"), body)
        add(f"chart-{kind}", ["chart", kind, rel("tests", "golden", "inputs", "charts", kind + ".csv"), "--title", kind],
            ["chart"])
    for kind, spec in json_body.items():
        write(os.path.join(INPUTS, "charts", kind + ".json"), json.dumps(spec, indent=1) + "\n")
        add(f"chart-{kind}", ["chart", kind, rel("tests", "golden", "inputs", "charts", kind + ".json"), "--title", kind],
            ["chart"])
    for kind, f in [("container", "arch.json"), ("component", "arch.json"), ("process", "seq_checkout.json"),
                    ("flowsheet", "flow_decision.json"), ("decision", "flow_decision.json"), ("point", "geo_cities.csv")]:
        add(f"alias-{kind}", ["chart", kind, ex(f)], ["chart", "alias"])

    # generated flows, the README benchmark sizes
    for n in (5, 11, 20, 40):
        path = rel("tests", "golden", "inputs", "flows", f"flow-{n:02d}.json")
        write(os.path.join(REPO, path), json.dumps(flow_spec(n), indent=1) + "\n")
        add(f"gen-flow-{n:02d}", ["flow", path], ["generated", "flow"])

    # known bad
    for name, spec in CASES.items():
        kind = "swim" if "lanes" in spec else "state"
        path = rel("tests", "golden", "inputs", "cases", name + ".json")
        write(os.path.join(REPO, path), json.dumps(spec, indent=1) + "\n")
        add(f"case-{name}", ["chart", kind, path], ["case"])
    add("case-bad-flow", ["flow", ex("bad.json")], ["case", "invalid"])
    add("case-bad-seq", ["seq", ex("bad_seq.json")], ["case", "invalid"])

    names = [c["name"] for c in corpus]
    assert len(names) == len(set(names)), "duplicate corpus names"
    write(os.path.join(HERE, "corpus.json"), json.dumps(corpus, indent=1) + "\n")
    print(f"wrote {len(corpus)} corpus entries")


if __name__ == "__main__":
    main()

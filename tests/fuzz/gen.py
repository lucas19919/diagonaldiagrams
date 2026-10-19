"""Seeded random v1 specs for the fuzz harness.

Every spec is valid: unique ids, arrows between real nodes, at most 2 focal nodes, at most 3
exits per decision, each node in at most one group. Validation warnings are allowed; validation
errors would be a generator bug, and run.py counts them separately.

5-200 nodes, nested groups, lanes, constraints, every shape, long labels, back edges, self-loops.
The same (kind, seed, n) always gives the same spec.
"""
import random

ICONS = ["bolt", "bot", "chart", "cloud", "database", "file", "gear", "globe", "key", "lock", "mail",
         "mobile", "queue", "server", "shield", "user", "web"]

SHORT = ["Start", "Done", "Retry", "Log", "Wait", "Fail", "Ship", "Pay", "Auth", "Queue"]
MEDIUM = ["Validate the request", "Load the account", "Score the risk", "Reserve stock", "Charge the card",
          "Write the ledger", "Notify the warehouse", "Print the label", "Send the receipt", "Update status",
          "Check inventory", "Ask for approval", "Resize the image", "Parse the upload", "Refresh the token"]
LONG = ["Reconcile the settlement batch with the bank statement",
        "Escalate to the on-call engineer and open an incident",
        "Recompute every affected customer's loyalty balance",
        "Migrate the remaining tenants to the new storage cluster"]
QUESTIONS = ["Valid?", "Approved?", "In stock?", "Fraud risk high?", "Retry limit reached?",
             "Customer verified by the identity provider?", "Payment captured?"]
SERVICES = ["API gateway", "Auth", "Orders", "Payments", "Inventory", "Search", "Catalog", "Notifications",
            "Ledger", "Fraud scoring", "Recommendation engine", "Image resizer", "Billing", "Shipping",
            "User profile service", "Session store", "Event bus", "Analytics warehouse", "Feature flags", "Web app"]
TECH = ["Go", "Python", "Node", "Postgres", "Redis", "Kafka", "S3", "Envoy", "Java", "Rust", "gRPC", "Elastic"]
VERBS = ["calls", "reads", "writes", "publishes", "streams", "verifies", "caches", "queries", "notifies"]


def _name(rng, i, long_p=0.15):
    r = rng.random()
    if r < long_p:
        base = rng.choice(LONG)
    elif r < 0.3:
        base = rng.choice(SHORT)
    else:
        base = rng.choice(MEDIUM)
    return f"{base} {i}"


def _groups(rng, n, max_groups=4):
    """Runs of node indices, optionally nested with a parent."""
    groups, used = [], set()
    num_g = rng.randint(1, max_groups)
    parent_cand = None
    for g in range(num_g):
        size = rng.randint(2, min(5, max(2, n // 3)))
        start = rng.randrange(0, max(1, n - size))
        span = set(range(start, start + size))
        if span & used:
            continue
        used |= span
        parent = None
        if parent_cand is not None and rng.random() < 0.3:
            parent = parent_cand
        gid = f"g{g}"
        groups.append((gid, sorted(span), parent))
        if parent is None:
            parent_cand = gid
    return groups


def flow(rng: random.Random, n: int) -> dict:
    nodes = []
    for i in range(n):
        if i == 0 or i == n - 1:
            nodes.append({"id": f"n{i}", "name": "Start" if i == 0 else "End", "shape": "oval"})
            continue
        r = rng.random()
        if r < 0.2:
            nodes.append({"id": f"n{i}", "name": f"{rng.choice(QUESTIONS)} ({i})", "shape": "diamond"})
        elif r < 0.23:
            nodes.append({"id": f"n{i}", "name": "", "shape": "dot"})
        else:
            node = {"id": f"n{i}", "name": _name(rng, i)}
            if rng.random() < 0.15:
                node["sub"] = rng.choice(TECH)
            if rng.random() < 0.1:
                node["icon"] = rng.choice(ICONS)
            nodes.append(node)
    out = {i: 0 for i in range(n)}
    seen, edges = set(), []

    def can_leave(i):
        return nodes[i].get("shape") != "diamond" or out[i] < 3

    def add(a, b, **kw):
        if (a, b) in seen or not can_leave(a):
            return False
        seen.add((a, b))
        out[a] += 1
        e = {"from": f"n{a}", "to": f"n{b}"}
        if nodes[a].get("shape") == "diamond":
            e["label"] = ["yes", "no", "maybe"][out[a] - 1]
        elif rng.random() < 0.15:
            e["label"] = f"{rng.choice(VERBS)}: {rng.choice(MEDIUM)}" if rng.random() < 0.2 else rng.choice(VERBS)
        if rng.random() < 0.1:
            e["async"] = True
        e.update(kw)
        edges.append(e)
        return True

    for i in range(1, n):  # every node is reachable from an earlier one
        choices = [p for p in range(max(0, i - 3), i) if can_leave(p)] or [p for p in range(i) if can_leave(p)]
        if choices:
            add(rng.choice(choices), i)
    for _ in range(n // 5):  # forward skips
        a = rng.randrange(0, n - 2)
        add(a, rng.randrange(a + 2, n))
    for _ in range(max(1, n // 10)):  # loops back up
        a = rng.randrange(2, n)
        add(a, rng.randrange(0, a - 1))
    for _ in range(max(1, n // 20)):  # self-loops
        if rng.random() < 0.3:
            a = rng.randrange(1, max(2, n - 1))
            if nodes[a].get("shape") != "diamond":
                add(a, a, label="retry" if rng.random() < 0.5 else "")
    for i in rng.sample(range(n), k=min(2, n)) if rng.random() < 0.5 else []:
        nodes[i]["focal"] = True
    spec = {"title": f"Fuzz flow {n}", "sub": "Generated by tests/fuzz/gen.py.",
            "nodes": nodes, "edges": edges, "budget": False}
    if rng.random() < 0.35:
        spec["groups"] = [
            dict({"id": gid, "name": f"Stage {k + 1}", "nodes": [f"n{i}" for i in members]},
                 **({"parent": parent} if parent else {}))
            for k, (gid, members, parent) in enumerate(_groups(rng, n))
        ]
    if rng.random() < 0.2:
        for i in rng.sample(range(n), k=max(1, n // 5)):
            nodes[i]["lane"] = rng.randint(-2, 2)
    return spec


def arch(rng: random.Random, n: int) -> dict:
    width = rng.randint(2, 5)
    nodes = []
    for i in range(n):
        node = {"id": f"s{i}", "name": f"{rng.choice(SERVICES)} {i}",
                "layer": i // width + (1 if rng.random() < 0.1 else 0)}
        if rng.random() < 0.6:
            node["sub"] = rng.choice(TECH)
        if rng.random() < 0.3:
            node["icon"] = rng.choice(ICONS)
        elif rng.random() < 0.1:
            node["tag"] = rng.choice(["EDGE", "CORE", "DATA"])
        nodes.append(node)
    layer = {i: nodes[i]["layer"] for i in range(n)}
    seen, edges = set(), []

    def add(a, b):
        if (a, b) in seen:
            return
        seen.add((a, b))
        e = {"from": f"s{a}", "to": f"s{b}"}
        if rng.random() < 0.4:
            e["label"] = f"{rng.choice(VERBS)}: {rng.choice(MEDIUM)}" if rng.random() < 0.2 else rng.choice(VERBS)
        if rng.random() < 0.3:
            e["proto"] = rng.choice(["https", "http", "grpc", "amqp"])
        if rng.random() < 0.15:
            e["async"] = True
        edges.append(e)

    for i in range(n):  # each node below the top row hangs off one in the row above
        above = [j for j in range(n) if layer[j] == layer[i] - 1]
        if above:
            for j in rng.sample(above, k=min(len(above), rng.randint(1, 2))):
                add(j, i)
    for _ in range(n // 4):  # same-row, skipping and upward arrows
        a, b = rng.randrange(n), rng.randrange(n)
        add(a, b)
    for _ in range(max(1, n // 20)):  # self-loops
        if rng.random() < 0.3:
            a = rng.randrange(n)
            add(a, a)
    for i in rng.sample(range(n), k=min(2, n)) if rng.random() < 0.5 else []:
        nodes[i]["focal"] = True
    spec = {"title": f"Fuzz architecture {n}", "sub": "Generated by tests/fuzz/gen.py.",
            "nodes": nodes, "edges": edges, "budget": False}
    if rng.random() < 0.4:
        spec["groups"] = [
            dict({"id": gid, "name": f"Zone {k + 1}", "nodes": [f"s{i}" for i in members]},
                 **({"parent": parent} if parent else {}))
            for k, (gid, members, parent) in enumerate(_groups(rng, n))
        ]
    if rng.random() < 0.2:
        for i in rng.sample(range(n), k=max(1, n // 5)):
            nodes[i]["lane"] = rng.randint(-2, 2)
    return spec


KINDS = {"flow": flow, "arch": arch}


def make(kind: str, seed: int, n: int) -> dict:
    return KINDS[kind](random.Random(f"{kind}:{seed}:{n}"), n)

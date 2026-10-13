"""Tracks in the gap between two layers (DESIGN 8.2, channel nudging): every sideways run of an arrow
gets a height of its own, so two arrows never share a line (B21: gaps, not port heights, decide).

A run is a horizontal segment with its attachments: where its arrow comes in or leaves, each from the
top of the gap or the bottom. Two runs that overlap sideways need different tracks. A run that leaves
downward at x must sit below a run that comes down at the same x, or they would share that vertical
line. Among the orders those rules allow, the one with fewer crossings is preferred: a run sits above
another when that crosses fewer of their vertical legs.
"""

NEAR = 12.0  # attachments closer than this share a line for the audit's eye


class Run:
    __slots__ = ("key", "ends", "lo", "hi", "track", "above")

    def __init__(self, key, ends):
        """key: who owns the run (one arrow, or a trunk of several). ends: [(x, "top" | "bottom" |
        "mid")]: "mid" is a dogleg's jog to another run of the same arrow, which `above` names."""
        self.key, self.ends = key, ends
        xs = [x for x, _ in ends]
        self.lo, self.hi = min(xs), max(xs)
        self.track = 0
        self.above = []  # runs this one must sit above (the low half of its dogleg)


def _cost_above(a, b):
    """Crossings when run a sits above run b: a's horizontal crosses b's legs that come from the top
    inside a's span (they reach down past a), and b's horizontal crosses a's legs that go to the
    bottom inside b's span."""
    n = sum(1 for x, d in b.ends if d == "top" and a.lo + 0.5 < x < a.hi - 0.5)
    n += sum(1 for x, d in a.ends if d == "bottom" and b.lo + 0.5 < x < b.hi - 0.5)
    return n


def trading(a, b):
    """True when runs a and b trade columns: a comes down where b leaves downward and b comes down
    where a leaves. No pair of tracks can keep them apart; one needs a dogleg."""
    def meets(p, q):
        return any(dp == "top" and dq == "bottom" and abs(xp - xq) < NEAR for xp, dp in p.ends for xq, dq in q.ends)
    return meets(a, b) and meets(b, a)


def assign(runs, margin=14.0):
    """Gives each run a track (0 at the top of the gap). Returns the number of tracks."""
    if not runs:
        return 0
    n = len(runs)
    must = {i: set() for i in range(n)}  # i -> runs that must sit above i
    for i, a in enumerate(runs):
        for j, b in enumerate(runs):
            if i == j:
                continue
            # a comes down at x where b leaves downward: a above b
            if any(da == "top" and db == "bottom" and abs(xa - xb) < NEAR for xa, da in a.ends for xb, db in b.ends):
                if i not in must[j] or j not in must[i]:
                    must[j].add(i)
    index = {id(r): k for k, r in enumerate(runs)}
    for i, a in enumerate(runs):
        for b in a.above:
            if id(b) in index:
                must[index[id(b)]].add(i)
    for j in range(n):  # a cycle (two runs trading places at one x) can't be met: drop one direction
        for i in list(must[j]):
            if j in must[i] and i > j:
                must[j].discard(i)
    overlap = {i: set() for i in range(n)}
    for i, a in enumerate(runs):
        for j, b in enumerate(runs):
            if i < j and a.lo - margin < b.hi and b.lo - margin < a.hi:
                overlap[i].add(j)
                overlap[j].add(i)
    # soft preference: wins counts how many overlapping runs a run should sit above
    wins = {}
    for i, a in enumerate(runs):
        w = 0
        for j in overlap[i]:
            ca, cb = _cost_above(a, runs[j]), _cost_above(runs[j], a)
            if ca < cb:
                w += 1
            elif ca > cb:
                w -= 1
        wins[i] = w
    # topological order of the hard rules, most wins first, then left to right
    indeg = {i: len(must[i]) for i in range(n)}
    below = {i: [] for i in range(n)}
    for j in range(n):
        for i in must[j]:
            below[i].append(j)
    ready = sorted((i for i in range(n) if indeg[i] == 0), key=lambda i: (-wins[i], runs[i].lo, i))
    order = []
    while ready:
        i = ready.pop(0)
        order.append(i)
        for j in below[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                ready.append(j)
        ready.sort(key=lambda i: (-wins[i], runs[i].lo, i))
    order += [i for i in range(n) if i not in set(order)]
    placed = {}
    for i in order:
        t = 0
        for j, tj in placed.items():
            if j in overlap[i] or j in must[i]:
                t = max(t, tj + 1)
        placed[i] = t
        runs[i].track = t
    return max(placed.values()) + 1

"""Layers for a layered layout (DESIGN 7.2): which arrows go back up, then which layer each node sits in.

back_edges() breaks cycles the way v1 did, so a loop's start stays on top: a depth-first walk from the
nodes nothing points at (else the first node), in the spec's order, marks each arrow that returns to
a node still on the walk. Those arrows are drawn going back up.

ranks() gives every node a layer. Ranks the spec pins are kept. Otherwise the longest-path layering is
compacted with the network simplex method (Gansner et al. 1993, as dagre does it), which minimizes the
total length of the arrows: a node with one arrow into a deep layer moves down beside it instead of
waiting at the top. Each connected part is ranked on its own, and big graphs skip the simplex.
"""

SIMPLEX_LIMIT = 400  # nodes in one connected part: above this, the longest path alone (the simplex is O(n^2))


def back_edges(ids, edges):
    """Indices of the edges (from, to) that close a cycle, found by a depth-first walk in spec order."""
    succ = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for k, (a, b) in enumerate(edges):
        if a in succ and b in succ and a != b:
            succ[a].append((b, k))
            indeg[b] += 1
    back, state = set(), {}
    for root in [i for i in ids if indeg[i] == 0] + list(ids):
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(succ[root]))]
        while stack:
            v, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[v] = 2
                stack.pop()
                continue
            w, k = nxt
            if state.get(w) == 1:
                back.add(k)
            elif w not in state:
                state[w] = 1
                stack.append((w, iter(succ[w])))
    return back


def longest_path(ids, edges):
    """Ranks with every arrow pointing down at least its minlen: sources at 0, each node below its
    deepest predecessor. edges: [(u, v, minlen, weight)], acyclic."""
    preds = {i: [] for i in ids}
    for u, v, mn, _ in edges:
        preds[v].append((u, mn))
    rank = {}
    for nid in ids:  # explicit stack: no deep recursion on long chains
        stack = [nid]
        while stack:
            v = stack[-1]
            if v in rank:
                stack.pop()
                continue
            todo = [u for u, _ in preds[v] if u not in rank]
            if todo:
                stack.extend(todo)
            else:
                rank[v] = max((rank[u] + mn for u, mn in preds[v]), default=0)
                stack.pop()
    return rank


def _components(ids, edges):
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u, v, _, _ in edges:
        parent[find(u)] = find(v)
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def network_simplex(ids, edges, max_iter=None):
    """Ranks minimizing the sum of weight * length over the arrows, each at least minlen long. ids are
    one connected part; edges [(u, v, minlen, weight)] are acyclic, without self-loops."""
    merged = {}
    for u, v, mn, w in edges:  # parallel arrows count once, with their weights summed
        if (u, v) in merged:
            m = merged[(u, v)]
            merged[(u, v)] = (max(m[0], mn), m[1] + w)
        else:
            merged[(u, v)] = (mn, w)
    E = [(u, v, mn, w) for (u, v), (mn, w) in merged.items()]
    parts = _components(ids, E)
    if len(parts) > 1:  # each connected part on its own
        out = {}
        for part in parts:
            pset = set(part)
            out.update(network_simplex(part, [e for e in E if e[0] in pset], max_iter))
        return out
    rank = longest_path(ids, E)
    if len(ids) < 2 or not E:
        return rank
    inc = {i: [] for i in ids}  # node -> [edge index]
    for k, (u, v, _, _) in enumerate(E):
        inc[u].append(k)
        inc[v].append(k)

    def slack(k):
        u, v, mn, _ = E[k]
        return rank[v] - rank[u] - mn

    # A feasible tight spanning tree: grow it along tight edges; when it stalls, shift the tree's
    # ranks by the smallest slack of an edge leaving it, which makes that edge tight.
    in_tree = {ids[0]}
    tree = set()  # edge indices
    while True:
        stack = list(in_tree)
        while stack:
            x = stack.pop()
            for k in inc[x]:
                u, v, _, _ = E[k]
                y = v if u == x else u
                if y not in in_tree and slack(k) == 0:
                    in_tree.add(y)
                    tree.add(k)
                    stack.append(y)
        if len(in_tree) == len(ids):
            break
        best = None
        for k, (u, v, _, _) in enumerate(E):
            if (u in in_tree) != (v in in_tree):
                s = slack(k)
                if best is None or s < best[0]:
                    best = (s, k)
        s, k = best
        delta = s if E[k][0] in in_tree else -s  # tail in the tree: move the tree down to meet the head
        for x in in_tree:
            rank[x] += delta

    adj = {i: [] for i in ids}  # tree adjacency: node -> [(other, edge index)]
    root = ids[0]

    def rebuild():
        for i in ids:
            adj[i] = []
        for k in tree:
            u, v, _, _ = E[k]
            adj[u].append((v, k))
            adj[v].append((u, k))

    low, lim, par = {}, {}, {}  # par: node -> (parent, edge index to it)

    def low_lim():
        """Post-order numbers (lim) and the lowest number in each subtree (low)."""
        par.clear()
        par[root] = (None, None)
        n = 0
        stack = [(root, iter(adj[root]))]
        low[root] = 1
        while stack:
            x, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                n += 1
                lim[x] = n
                low[x] = min(low.get(x, n), n)
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    low[p] = min(low.get(p, n), low[x])
                continue
            y, k = nxt
            if y == par[x][0] and k == par[x][1]:
                continue
            par[y] = (x, k)
            low[y] = n + 1
            stack.append((y, iter(adj[y])))

    cut = {}

    def cut_values():
        order = sorted(ids, key=lambda i: lim[i])  # children before parents
        for child in order:
            p, k = par[child]
            if p is None:
                continue
            u, v, _, w = E[k]
            child_is_tail = u == child
            cv = w
            for k2 in inc[child]:
                if k2 == k:
                    continue
                a, b, _, w2 = E[k2]
                is_out = a == child
                other = b if is_out else a
                points_to_head = is_out == child_is_tail
                cv += w2 if points_to_head else -w2
                if k2 in tree:
                    cv += -cut[k2] if points_to_head else cut[k2]
            cut[k] = cv

    def update_ranks():
        stack = [root]
        seen = {root}
        while stack:
            x = stack.pop()
            for y, k in adj[x]:
                if y in seen:
                    continue
                seen.add(y)
                u, v, mn, _ = E[k]
                rank[y] = rank[x] + mn if u == x else rank[x] - mn
                stack.append(y)

    rebuild()
    low_lim()
    cut_values()
    limit = max_iter if max_iter is not None else 4 * len(ids) + 200
    for _ in range(limit):
        leave = next((k for k in sorted(tree) if cut[k] < 0), None)
        if leave is None:
            break
        u, v, _, _ = E[leave]
        # u is the tail; the side holding the root decides which way the entering edge must point
        tail = u
        flip = False
        if lim[u] > lim[v]:
            tail = v
            flip = True
        lo, li = low[tail], lim[tail]

        def below(x):
            return lo <= lim[x] <= li
        enter = None
        for k, (a, b, _, _) in enumerate(E):
            if flip == below(a) and flip != below(b):
                s = slack(k)
                if enter is None or s < enter[0]:
                    enter = (s, k)
        if enter is None:
            break
        tree.discard(leave)
        tree.add(enter[1])
        rebuild()
        low_lim()
        cut_values()
        update_ranks()
    lo = min(rank.values())
    return {i: r - lo for i, r in rank.items()}


def ranks(ids, edges, fixed=None, simplex=True):
    """{node: layer} for nodes ids and arrows edges [(u, v, minlen, weight)], pointing down after
    back edges were reversed. fixed pins some nodes' layers: when every node is pinned the pins are
    used as given (made dense, keeping their order); when some are, the others take the longest path
    below their predecessors."""
    fixed = {k: v for k, v in (fixed or {}).items() if k in set(ids)}
    edges = [e for e in edges if e[0] != e[1]]
    if fixed and len(fixed) == len(ids):
        dense = {r: k for k, r in enumerate(sorted(set(fixed.values())))}
        return {i: dense[fixed[i]] for i in ids}
    if fixed:
        preds = {i: [] for i in ids}
        for u, v, mn, _ in edges:
            preds[v].append((u, mn))
        rank = {}
        for nid in ids:
            stack = [nid]
            while stack:
                v = stack[-1]
                if v in rank:
                    stack.pop()
                    continue
                if v in fixed:
                    rank[v] = fixed[v]
                    stack.pop()
                    continue
                todo = [u for u, _ in preds[v] if u not in rank]
                if todo:
                    stack.extend(todo)
                else:
                    rank[v] = max((rank[u] + mn for u, mn in preds[v]), default=min(fixed.values()))
                    stack.pop()
        dense = {r: k for k, r in enumerate(sorted(set(rank.values())))}
        return {i: dense[rank[i]] for i in ids}
    out = {}
    for comp in _components(ids, edges):
        cset = set(comp)
        ce = [e for e in edges if e[0] in cset]
        if simplex and len(comp) <= SIMPLEX_LIMIT:
            r = network_simplex(comp, ce)
        else:
            r = longest_path(comp, ce)
        out.update(r)
    return {i: out[i] for i in ids}

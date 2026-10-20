"""The sequence layout: actors side by side, each with a lifeline, and messages down a
time axis, one step per message.

    res = layout(actors, messages, options)

actors: [{"id", "w", "h"}], drawn at one height, the tallest; messages: [{"id", "from", "to",
"label_w"?}], label_w being the width of the label's pill. Neighboring lifelines stand far enough
apart for the widest label between two actors. Sizes keep the type they come in with, so ints stay
ints and the figure's numbers print as they did. A layout never paints.
"""

DEFAULTS = {
    "margin": 70,     # between the canvas edge and the outermost actor box
    "pitch": 180,     # least distance between two lifelines
    "label_pad": 36,  # beside the widest label, within one pitch
    "min_label": 48,  # the narrowest label the pitch makes room for
    "top": 90,        # the actor boxes' top
    "box_h": 52,      # least height of an actor box
    "gap": 34,        # between the boxes and the first message, which its label needs
    "step": 52,       # between two messages
    "bottom": 80,     # below the last message
}


class Result:
    __slots__ = ("x", "top", "box_w", "box_h", "y", "size")

    def __init__(self):
        self.x = {}         # actor id -> its lifeline's x
        self.top = 0.0      # the actor boxes' top
        self.box_w = 0.0
        self.box_h = 0.0
        self.y = []         # message index -> its y
        self.size = (0.0, 0.0)


def layout(actors, messages, options=None):
    o = dict(DEFAULTS, **(options or {}))
    res = Result()
    widest = max([o["min_label"]] + [m.get("label_w") or 0 for m in messages if m.get("from") != m.get("to")])
    pitch = max(o["pitch"], widest + o["label_pad"])
    res.box_w = max([0] + [a.get("w") or 0 for a in actors]) or 140
    res.box_h = max([o["box_h"]] + [a.get("h") or 0 for a in actors])
    res.top = o["top"]
    half = res.box_w // 2 if res.box_w % 2 == 0 else res.box_w / 2
    for i, a in enumerate(actors):
        res.x[a["id"]] = o["margin"] + half + i * pitch
    first = res.top + res.box_h + o["gap"]
    res.y = [first + i * o["step"] for i in range(len(messages))]
    w = 2 * o["margin"] + max(0, len(actors) - 1) * pitch + res.box_w
    res.size = (w, first + len(messages) * o["step"] + o["bottom"])
    return res

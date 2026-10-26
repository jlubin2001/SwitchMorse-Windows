# SwitchMorse Windows - hints.py
# The hints line under the dots and dashes: while a code is being entered,
#   = d     what it would do if you stopped now
#   -:x .:b what one or two more symbols would do (shortest first)
# e.g. after -..  ->  "= d   -:x  .:b  .-:Insert"
import mapload


def _short(label, n=10):
    for prefix in ("Mouse ", "Group ", "secret "):
        if label.startswith(prefix):
            label = label[len(prefix):]
    if label.startswith("Double ") and label.endswith(" click"):
        label = "2×" + label[7:-6]                      # Double left click -> 2xleft
    elif label.endswith(" click"):
        label = "click " + label[:-6].lower()               # Right click -> click right
    return label if len(label) <= n else label[:n - 1] + "…"


def hint(codes, group, buffer, limit=4):
    """The hints text for `buffer` (dots and dashes) in `group`; "" when empty."""
    n = len(buffer)
    if not n or n > 8:
        return ""
    p = int(buffer.replace(".", "0").replace("-", "1"), 2)
    parts = []
    now = codes.get((0, n, p)) or codes.get((group, n, p))
    parts.append("= " + _short(now.label) if now else "= ?")
    more = []
    for extra in (1, 2):                                   # one or two more symbols
        m = n + extra
        if m > 8:
            break
        for tail in range(1 << extra):
            q = (p << extra) | tail
            a = codes.get((0, m, q)) or codes.get((group, m, q))
            if a:
                more.append("%s:%s" % (mapload.code_str(m, q)[n:], _short(a.label)))
    if more:
        parts.append("  ".join(more[:limit]) + ("  …" if len(more) > limit else ""))
    return "   ".join(parts)

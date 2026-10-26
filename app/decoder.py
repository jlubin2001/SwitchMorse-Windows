# SwitchMorse Windows - decoder.py
# Switch presses -> Morse codes. Pure logic with no Windows or serial, so it can
# be tested with made-up times. Same rules as the SwitchMorse firmware:
#   - each release of the dot switch adds a dot, the dash switch a dash
#   - no switch held for ACCEPT_DELAY after the last release = the code is done
#   - a press held LONG_PRESS or more = next group (and drops the code so far)
#   - a switch that lets go for less than `bounce` seconds and closes again is
#     ONE press (a sip-and-puff switch can open for 2-10 ms in the middle of
#     one sip or puff, which would type .-.- as .--.-; but two real puffs can
#     be only 17-28 ms apart, so keep `bounce` small)

DOT, DASH = "dot", "dash"


class Decoder:
    def __init__(self, accept_delay=0.5, long_press=1.0, long_press_cycles=True, bounce=0.015):
        self.accept_delay = accept_delay
        self.long_press = long_press
        self.long_press_cycles = long_press_cycles
        self.bounce = bounce
        self.last_up = {DOT: None, DASH: None}      # (time, press start, what it did)
        self.down_at = {DOT: None, DASH: None}
        self.consumed = set()       # presses that only stopped a repeat
        self.hinted = False
        self.pattern = 0            # dots (0) and dashes (1) so far, oldest first
        self.count = 0
        self.last_release = 0.0

    @property
    def buffer(self):
        return "".join("-" if (self.pattern >> (self.count - 1 - i)) & 1 else "."
                       for i in range(self.count))

    @property
    def holding(self):
        return any(t is not None for t in self.down_at.values())

    def clear(self):
        self.pattern = 0
        self.count = 0

    def consume(self, switch):
        """The press now held on `switch` only stopped a repeat: its release
        adds nothing (as in AeroMorse)."""
        if self.down_at[switch] is not None:
            self.consumed.add(switch)

    def feed(self, switch, pressed, t):
        """A press or release. Returns a list of events:
        ("symbol", buffer)  a dot or dash was added
        ("cycle",)          a long press ended: go to the next group"""
        out = []
        if pressed:
            if self.down_at[switch] is None:
                up = self.last_up[switch]
                self.last_up[switch] = None
                if up is not None and t - up[0] < self.bounce:
                    # It only let go for a moment: carry on with the same press.
                    self.down_at[switch] = up[1]
                    if up[2] == "symbol" and self.count:   # take back the symbol it added
                        self.pattern >>= 1
                        self.count -= 1
                        out.append(("symbol", self.buffer))
                    elif up[2] == "consumed":
                        self.consumed.add(switch)
                    elif up[2] == "cycle":          # the group already changed
                        self.consumed.add(switch)
                    return out
                self.down_at[switch] = t
                self.hinted = False
            return out
        start = self.down_at[switch]
        if start is None:
            return out                  # the "it's up" state sent on connect
        self.down_at[switch] = None
        self.last_release = t
        if switch in self.consumed:
            self.consumed.discard(switch)
            self.last_up[switch] = (t, start, "consumed")
            return out
        if self.long_press_cycles and t - start >= self.long_press:
            self.clear()
            out.append(("cycle",))
            self.last_up[switch] = (t, start, "cycle")
        else:
            self.pattern = (self.pattern << 1) | (1 if switch == DASH else 0)
            self.count += 1
            out.append(("symbol", self.buffer))
            self.last_up[switch] = (t, start, "symbol")
        return out

    def tick(self, t):
        """Call often (every ~10 ms). Returns events:
        ("code", count, pattern)  the code is finished - look it up
        ("long",)                 a press has been held long enough to change group"""
        out = []
        if self.holding:
            if (self.long_press_cycles and not self.hinted and
                    any(s is not None and t - s >= self.long_press and sw not in self.consumed
                        for sw, s in self.down_at.items())):
                self.hinted = True
                out.append(("long",))
        elif self.count and t - self.last_release >= self.accept_delay:
            out.append(("code", self.count, self.pattern))
            self.clear()
        return out

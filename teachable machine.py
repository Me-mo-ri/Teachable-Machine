"""TM 연결!!!!!!!!!
가위(if) VAR OP NUM [바위(and) VAR OP NUM ...] good/bad
"""

import operator

threshold = 3.0

IF = "scissors"
AND = "rock"
VAR_A, VAR_B = "heart", "belowV"
GT, LT = ">", "<"
ON, OFF = "good", "bad"
NUMS = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
VALID = {"START":{IF}, "VAR":{VAR_A, VAR_B}, "OP":{GT, LT}, "NUM":set(NUMS), "NEXT":{AND, ON, OFF}}


class Rule:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state, self.conds, self.cur = "START", [], {}

    def valid(self):
        return VALID[self.state]

    def feed(self, tok):
        if tok not in self.valid():
            return None
        if self.state == "START":
            self.state = "VAR"
        elif self.state == "VAR":
            self.cur = {"var": tok}; self.state = "OP"
        elif self.state == "OP":
            self.cur["op"] = tok; self.state = "NUM"
        elif self.state == "NUM":
            self.cur["num"] = NUMS[tok] * 100
            self.conds.append(self.cur); self.state = "NEXT"
        elif self.state == "NEXT":
            if tok == AND:
                self.state = "VAR"
            else:
                rule = {"conds": self.conds, "out": "led=on" if tok == ON else "led=off"}
                self.reset()
                return rule
        return None


class Holdtime:
    def __init__(self, builder, hold=threshold, min_prob=0.8, min_mass=0.3):
        self.b, self.hold, self.min_prob, self.min_mass = builder, hold, min_prob, min_mass
        self.cur, self.t0, self.armed = None, 0.0, True

    def update(self, probs, t):
        valid = self.b.valid()
        cand = {k: v for k, v in probs.items() if k in valid}
        mass = sum(cand.values())
        label = None
        if mass >= self.min_mass:
            best = max(cand, key=cand.get)
            if cand[best] / mass >= self.min_prob:
                label = best
        if label is None:
            self.cur, self.armed = None, True
            return None
        if not self.armed:
            return None
        if label != self.cur:
            self.cur, self.t0 = label, t
            return None
        if t - self.t0 >= self.hold - 1e-9:
            self.cur, self.armed = None, False
            return label
        return None


def parse_init(s):
    a, b = [float(x) for x in s.split(",")]
    return {VAR_A: a, VAR_B: b}


def evaluate(rule, vals):
    ops = {GT: operator.gt, LT: operator.lt}
    ok = all(ops[c["op"]](vals[c["var"]], c["num"]) for c in rule["conds"])
    return rule["out"] if ok else None


def describe(rule):
    name = {VAR_A: "A", VAR_B: "B"}
    cond = " and ".join(f'{name[c["var"]]} {c["op"]} {c["num"]}' for c in rule["conds"])
    return f'if {cond}: print("{rule["out"]}")'


if __name__ == "__main__":
    FPS = 10

    def simulate(seq):
        b = Rule(); h = Holdtime(b)
        rule, idx, log = None, 0, []
        for label, dur in seq:
            for _ in range(int(dur * FPS)):
                t = idx / FPS; idx += 1
                probs = {"background": 0.95} if label is None else {label: 0.9, "background": 0.1}
                tok = h.update(probs, t)
                if tok:
                    log.append(f"{t:5.1f}s  {tok:5} (state 전: 처리됨)")
                    rule = b.feed(tok) or rule
        return rule, log, idx / FPS

    b = Rule(); h = Holdtime(b)
    for t in (IF, VAR_A, GT):
        b.feed(t)
    got = None
    for i in range(35):
        got = h.update({"scissors": 0.5, "2": 0.4, "background": 0.1}, i / FPS) or got
    print(f"\n[혼동 테스트] NUM 상태에서 가위 0.5 / 2 0.4 -> 토큰: {got}")
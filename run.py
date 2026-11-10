import argparse
import operator
import os
import sys
import time


HOLD_SEC = 2.0

IF = "1"
VAR_A, VAR_B = "okay", "ILY"
AND = "rock"
GT, LT = ">", "<"
ON, OFF = "good", "bad"
NUMS = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}

VALID = {
    "START": {IF},
    "VAR":   {VAR_A, VAR_B},
    "OP":    {GT, LT},
    "NUM":   set(NUMS),
    "NEXT":  {AND, ON, OFF},
}

MEANING = {IF: "if", VAR_A: "A", VAR_B: "B", AND: "and", GT: ">", LT: "<",
           ON: "then led=on", OFF: "then led=off"}

HINT = {
    "START": f"다음: {IF}(if) 로 규칙 시작",
    "VAR":   f"다음: 변수  {VAR_A}(A) / {VAR_B}(B)",
    "OP":    f"다음: 비교  {GT} / {LT}",
    "NUM":   "다음: 숫자 1~5 (x100)",
    "NEXT":  f"다음: {AND}(and) 로 조건 추가, 또는 {ON}(led=on) / {OFF}(led=off) 로 끝내기",
}

REQUIRED = [IF, VAR_A, VAR_B, AND, GT, LT, ON, OFF, *NUMS]

class RuleBuilder:
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


class HoldTracker:
    def __init__(self, builder, hold=HOLD_SEC, min_prob=0.8, min_mass=0.3):
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


class Controller:
    def __init__(self, init_str, hold=HOLD_SEC, progress=True):
        self.vals = parse_init(init_str)
        self.b = RuleBuilder()
        self.h = HoldTracker(self.b, hold)
        self.hold, self.progress = hold, progress
        self.led = "led=off"
        self.words, self._bar = [], False
        print(f"initSet: A={self.vals[VAR_A]:g}, B={self.vals[VAR_B]:g}   LED 초기 상태: {self.led}")
        print(HINT["START"])

    def reset(self):
        self._clear()
        self.b.reset()
        self.h.cur, self.h.armed = None, True
        self.words = []
        print("[리셋] 입력 중이던 규칙을 지웠습니다")
        print(HINT["START"])

    def step(self, probs, t):
        tok = self.h.update(probs, t)
        if tok is None:
            self._show_progress(t)
            return
        self._clear()
        word = str(NUMS[tok] * 100) if self.b.state == "NUM" else MEANING[tok]
        self.words.append(word)
        rule = self.b.feed(tok)
        print(f"[인식] {tok:<5} -> {word}")
        if rule is None:
            print(f"       규칙: {' '.join(self.words)}")
            print(f"       {HINT[self.b.state]}")
        else:
            self._finish(rule)

    def _finish(self, rule):
        print(f"[완성] {describe(rule)}")
        out = evaluate(rule, self.vals)
        if out is None:
            print(f"[실행] 조건 불만족 -> LED 유지 ({self.led})")
        else:
            self.led = out
            print(f"[실행] 조건 만족   -> {out}")
        print()
        self.words = []
        print(HINT["START"])

    def _show_progress(self, t):
        if not self.progress:
            return
        if self.h.cur is None:
            self._clear()
            return
        held = max(0.0, min(t - self.h.t0, self.hold))
        n = int(held / self.hold * 10)
        sys.stdout.write(f"\r  인식 중: {self.h.cur:<5} [{'#' * n}{'.' * (10 - n)}] "
                         f"{held:.1f}/{self.hold:.1f}s   ")
        sys.stdout.flush()
        self._bar = True

    def _clear(self):
        if self._bar:
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            self._bar = False

def load_labels(path):
    names = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            head, _, tail = line.partition(" ")
            names.append(tail if head.isdigit() and tail else line)
    return names


def predict(model, names, frame_bgr):
    import cv2
    import numpy as np
    img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
    img = np.asarray(img, dtype=np.float32).reshape(1, 224, 224, 3)
    img = img / 127.5 - 1
    p = model.predict(img, verbose=0)[0]
    return dict(zip(names, map(float, p)))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(here, "keras_model.h5"))
    ap.add_argument("--labels", default=os.path.join(here, "labels.txt"))
    ap.add_argument("--init", default="350, 120", help='센서 대신 쓸 값 "A, B"')
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--flip", action="store_true",
                    help="좌우반전. TM에서 샘플 수집할 때 반전을 켰다면 같이 켜세요(> 와 < 가 뒤바뀜 방지)")
    ap.add_argument("--no-window", action="store_true", help="미리보기 창 없이 터미널만 사용")
    args = ap.parse_args()

    try:
        parse_init(args.init)
    except ValueError:
        sys.exit('--init 은 "350, 120" 처럼 숫자 2개를 쉼표로 구분해 주세요')
    for p in (args.model, args.labels):
        if not os.path.isfile(p):
            sys.exit(f"파일을 찾을 수 없습니다: {p}")

    print("TensorFlow/Keras 불러오는 중... (처음엔 10~30초 걸릴 수 있습니다)", flush=True)
    import cv2
    from keras.models import load_model
    print("모델 로딩 중...", flush=True)
    model = load_model(args.model, compile=False)
    names = load_labels(args.labels)
    missing = [r for r in REQUIRED if r not in names]
    print(f"클래스: {names}")
    if missing:
        print(f"[경고] labels.txt 에 없는 제스처: {missing}  (run.py 상단 라벨명과 맞춰 주세요)")

    print("카메라 여는 중...", flush=True)
    cam = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW) if sys.platform == "win32" \
        else cv2.VideoCapture(args.camera)
    if not cam.isOpened():
        cam = cv2.VideoCapture(args.camera)
    if not cam.isOpened():
        sys.exit("카메라를 열 수 없습니다 (--camera 1 처럼 번호를 바꿔 보세요)")
    print("카메라 연결됨. 'gesture' 창이 안 보이면 작업표시줄을 확인하세요. (q 종료 / r 리셋)", flush=True)

    ctrl = Controller(args.init)
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                break
            if args.flip:
                frame = cv2.flip(frame, 1)
            ctrl.step(predict(model, names, frame), time.time())
            if not args.no_window:
                cv2.imshow("gesture", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("r"):
                    ctrl.reset()
    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
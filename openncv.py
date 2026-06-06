import cv2
import mediapipe as mp
import numpy as np
import threading
import subprocess

last_vol = 50

def set_volume(percent):
    global last_vol
    percent = max(0, min(100, int(percent)))
    diff    = percent - last_vol

    if abs(diff) < 2:   
        return

    key     = "[char]175" if diff > 0 else "[char]174"
    presses = min(abs(diff) // 2, 20)  # cap at 20 presses

    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-c",
         f"$wsh = New-Object -ComObject WScript.Shell; "
         f"for($i=0; $i -lt {presses}; $i++) {{ $wsh.SendKeys({key}) }}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    last_vol = percent

VOL_OK = True
print("Volume ready")



BaseOptions           = mp.tasks.BaseOptions
HandLandmarker        = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode

latest_result = None
lock          = threading.Lock()

def on_result(result, output_image, timestamp_ms):
    global latest_result
    with lock:
        latest_result = result

options = HandLandmarkerOptions(
    base_options    = BaseOptions(model_asset_path='hand_landmarker.task'),
    running_mode    = VisionRunningMode.LIVE_STREAM,
    num_hands       = 1,
    min_hand_detection_confidence = 0.8,
    min_hand_presence_confidence  = 0.8,
    min_tracking_confidence       = 0.8,
    result_callback = on_result
)



class Smoother:
    def __init__(self, size=6):
        self.size   = size
        self.values = []

    def smooth(self, val):
        self.values.append(val)
        if len(self.values) > self.size:
            self.values.pop(0)
        return int(sum(self.values) / len(self.values))

sx = Smoother()
sy = Smoother()



class ModeSwitcher:
    def __init__(self, hold=20):
        self.hold    = hold
        self.count   = 0
        self.pending = "IDLE"
        self.mode    = "IDLE"

    def update(self, fingers):
        MAP       = {0:"IDLE", 1:"VOLUME", 2:"TYPING", 5:"GESTURE"}
        candidate = MAP.get(fingers, self.mode)
        if candidate == self.pending:
            self.count += 1
            if self.count >= self.hold:
                self.mode  = candidate
                self.count = 0
        else:
            self.pending = candidate
            self.count   = 1
        return self.mode

switcher = ModeSwitcher()



def count_fingers(lm):
    tips  = [8,12,16,20]
    base  = [6,10,14,18]
    count = sum(1 for t,b in zip(tips,base) if lm[t].y < lm[b].y)
    if lm[4].x < lm[3].x:
        count += 1
    return count



class TapDetector:
    def __init__(self):
        self.was_down = False
        self.cooldown = 0

    def update(self, iy, my):
        down  = (iy > my + 8)
        fired = False
        if down and not self.was_down and self.cooldown == 0:
            fired         = True
            self.cooldown = 30
        self.was_down = down
        if self.cooldown > 0:
            self.cooldown -= 1
        return fired, down

tapper = TapDetector()



KEYS = [
    ["Q","W","E","R","T","Y","U","I","O","P"],
    ["A","S","D","F","G","H","J","K","L"],
    ["Z","X","C","V","B","N","M","<","SPC"]
]
KW         = 58
KH         = 58
GAP        = 5
KB_START_Y = 310

def get_row_start_x(row_len, screen_w):
    total = row_len * (KW + GAP) - GAP
    return (screen_w - total) // 2

def draw_keyboard(frame, typed, hovered=None):
    sw = frame.shape[1]
    for r, row in enumerate(KEYS):
        row_x = get_row_start_x(len(row), sw)
        for c, key in enumerate(row):
            x = row_x + c * (KW + GAP)
            y = KB_START_Y + r * (KH + GAP)
            if key == hovered:
                cv2.rectangle(frame, (x,y), (x+KW,y+KH), (0,255,255), -1)
                cv2.putText(frame, key, (x+12,y+40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,0,0), 2)
            else:
                overlay = frame.copy()
                cv2.rectangle(overlay, (x,y), (x+KW,y+KH), (50,50,50), -1)
                cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
                cv2.rectangle(frame, (x,y), (x+KW,y+KH), (200,200,200), 1)
                cv2.putText(frame, key, (x+12,y+40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255,255,255), 2)

    bar_x1 = 40
    bar_x2 = sw - 40
    cv2.rectangle(frame, (bar_x1,265), (bar_x2,305), (30,30,30), -1)
    cv2.rectangle(frame, (bar_x1,265), (bar_x2,305), (0,255,255), 1)
    display = typed[-40:] if len(typed) > 40 else typed
    cv2.putText(frame, display, (bar_x1+10, 293),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

def get_key_at(px, py, sw):
    for r, row in enumerate(KEYS):
        row_x = get_row_start_x(len(row), sw)
        for c, key in enumerate(row):
            x = row_x + c * (KW + GAP)
            y = KB_START_Y + r * (KH + GAP)
            if x < px < x+KW and y < py < y+KH:
                return key
    return None


cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  720)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 560)

ts      = 0
typed   = ""
vol_pct = 50

print("0=IDLE | 1=VOLUME | 2=TYPING | 5=GESTURE | Q=quit")

with HandLandmarker.create_from_options(options) as detector:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame   = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        ts      += 1

        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detector.detect_async(mp_image, ts)

        with lock:
            result = latest_result

        hovered = None
        fingers = 0

        if result and result.hand_landmarks:
            lm = result.hand_landmarks[0]

            for pt in lm:
                cv2.circle(frame, (int(pt.x*w), int(pt.y*h)), 4, (0,220,0), -1)

            ix = sx.smooth(int(lm[8].x * w))
            iy = sy.smooth(int(lm[8].y * h))
            my = int(lm[12].y * h)
            tx = int(lm[4].x * w)
            ty = int(lm[4].y * h)

            fingers = count_fingers(lm)
            mode    = switcher.update(fingers)

            

            if mode == "VOLUME":
                cv2.circle(frame, (tx,ty), 14, (255,0,255), -1)
                cv2.circle(frame, (ix,iy), 14, (255,0,255), -1)
                cv2.line(frame,   (tx,ty), (ix,iy), (255,0,255), 3)

                dist    = float(np.hypot(ix-tx, iy-ty))
                vol_pct = int(np.interp(dist, [30,200], [0,100]))
                set_volume(vol_pct)

               

                cv2.rectangle(frame, (w-60,80),  (w-20,400), (60,60,60),   -1)
                cv2.rectangle(frame, (w-60,80),  (w-20,400), (100,100,100), 2)
                by = int(np.interp(vol_pct, [0,100], [400,80]))
                cv2.rectangle(frame, (w-60,by),  (w-20,400), (0,200,255),  -1)
                cv2.putText(frame, f"{vol_pct}%", (w-75,425),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)
                cv2.putText(frame, "PINCH to change volume",
                            (w//2-160, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)

           

            elif mode == "TYPING":
                cv2.circle(frame, (ix,iy), 12, (0,255,255), -1)
                hovered        = get_key_at(ix, iy, w)
                fired, tapping = tapper.update(iy, my)

                if tapping:
                    cv2.putText(frame, "TAP!", (w//2-40, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 3)

                if fired and hovered:
                    if   hovered == "<":   typed = typed[:-1]
                    elif hovered == "SPC": typed += " "
                    else:                  typed += hovered

            

            elif mode == "GESTURE":
                cv2.putText(frame, "GESTURE MODE",
                            (w//2-120, h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,100,0), 3)

        else:
            tapper.was_down = False

        if switcher.mode == "TYPING":
            draw_keyboard(frame, typed, hovered)

       


        mode        = switcher.mode
        COLORS      = {
            "IDLE"   : (150,150,150),
            "VOLUME" : (0,200,255),
            "TYPING" : (0,255,100),
            "GESTURE": (255,100,0)
        }
        label       = f"MODE: {mode}   fingers: {fingers}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.rectangle(frame, (0,0), (w,45), (20,20,20), -1)
        cv2.putText(frame, label, (w//2-lw//2, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS[mode], 2)

        hints = ["0=IDLE","1=VOLUME","2=TYPING","5=GESTURE"]
        for i, t in enumerate(hints):
            cv2.putText(frame, t, (10, h-80+i*20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100,100,100), 1)

        cv2.imshow("Gesture Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
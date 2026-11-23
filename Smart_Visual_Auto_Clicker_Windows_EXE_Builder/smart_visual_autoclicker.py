import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, os, threading, time
from datetime import datetime

try:
    import pyautogui
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    from pynput import mouse, keyboard
except ImportError as e:
    pyautogui = cv2 = np = Image = ImageTk = mouse = keyboard = None
    IMPORT_ERROR = str(e)
else:
    IMPORT_ERROR = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MACRO_FILE = os.path.join(APP_DIR, "recording.json")
TARGET_DIR = os.path.join(APP_DIR, "targets")
os.makedirs(TARGET_DIR, exist_ok=True)

class SmartClicker:
    def __init__(self, root):
        self.root = root
        root.title("Smart Visual Auto-Clicker")
        root.geometry("780x720")
        root.minsize(700, 650)
        self.events = []
        self.recording = False
        self.playing = False
        self.stop_event = threading.Event()
        self.mouse_listener = None
        self.key_listener = None
        self.last_event_time = None
        self.targets = []
        self.target_thread = None
        self.target_enabled = False
        self.build_ui()
        self.load_macro()
        self.refresh_targets()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        if IMPORT_ERROR:
            messagebox.showerror(
                "Missing dependencies",
                "Install the required packages first:\n\n"
                "python -m pip install -r requirements.txt\n\n"
                f"Details: {IMPORT_ERROR}"
            )

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="SMART VISUAL AUTO-CLICKER", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Record mouse + keyboard actions, replay them, or find and click saved logos.",
                  wraplength=740).pack(anchor="w", pady=(2, 12))

        # Recorder controls
        rec = ttk.LabelFrame(outer, text="1. Record / Play", padding=10)
        rec.pack(fill="x", pady=5)
        row = ttk.Frame(rec); row.pack(fill="x")
        self.record_btn = ttk.Button(row, text="● Start Recording", command=self.toggle_record)
        self.record_btn.pack(side="left", padx=(0, 8))
        self.play_btn = ttk.Button(row, text="▶ Play", command=self.start_playback)
        self.play_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(row, text="■ Stop", command=self.stop_all)
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(row, text="Save Recording", command=self.save_macro).pack(side="left", padx=8)
        ttk.Button(row, text="Load Recording", command=self.choose_macro).pack(side="left", padx=8)

        settings = ttk.Frame(rec); settings.pack(fill="x", pady=(10, 0))
        ttk.Label(settings, text="Loop count (0 = forever):").pack(side="left")
        self.loop_var = tk.StringVar(value="1")
        ttk.Entry(settings, textvariable=self.loop_var, width=7).pack(side="left", padx=(5, 18))
        ttk.Label(settings, text="Playback speed:").pack(side="left")
        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Scale(settings, from_=0.25, to=3.0, variable=self.speed_var, orient="horizontal", length=180).pack(side="left", padx=7)
        self.speed_label = ttk.Label(settings, text="1.00x")
        self.speed_label.pack(side="left")
        self.speed_var.trace_add("write", lambda *_: self.speed_label.config(text=f"{self.speed_var.get():.2f}x"))
        ttk.Label(rec, text="Recording captures mouse movement/clicks, scrolls, key presses and releases. "
                           "Avoid typing passwords or sensitive information while recording.",
                  wraplength=720, foreground="#9b5a00").pack(anchor="w", pady=(8, 0))

        # Logo matching
        vis = ttk.LabelFrame(outer, text="2. Find a logo anywhere on screen", padding=10)
        vis.pack(fill="x", pady=5)
        vrow = ttk.Frame(vis); vrow.pack(fill="x")
        ttk.Button(vrow, text="Add logo image…", command=self.add_target).pack(side="left")
        ttk.Button(vrow, text="Remove selected", command=self.remove_target).pack(side="left", padx=8)
        ttk.Button(vrow, text="Capture screen region…", command=self.capture_target).pack(side="left", padx=8)
        self.target_list = tk.Listbox(vis, height=4, exportselection=False)
        self.target_list.pack(fill="x", pady=8)
        opts = ttk.Frame(vis); opts.pack(fill="x")
        self.threshold_var = tk.DoubleVar(value=0.88)
        ttk.Label(opts, text="Match sensitivity:").pack(side="left")
        ttk.Scale(opts, from_=0.60, to=0.99, variable=self.threshold_var, orient="horizontal", length=180).pack(side="left", padx=8)
        self.threshold_label = ttk.Label(opts, text="0.88")
        self.threshold_label.pack(side="left")
        self.threshold_var.trace_add("write", lambda *_: self.threshold_label.config(text=f"{self.threshold_var.get():.2f}"))
        self.click_target_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Click when found", variable=self.click_target_var).pack(side="left", padx=16)
        self.scan_btn = ttk.Button(opts, text="Start logo scan", command=self.toggle_scan)
        self.scan_btn.pack(side="right")

        # Status + safety
        bottom = ttk.LabelFrame(outer, text="Status / Safety", padding=10)
        bottom.pack(fill="both", expand=True, pady=5)
        self.status_var = tk.StringVar(value="Ready. Add a logo or start a recording.")
        ttk.Label(bottom, textvariable=self.status_var, wraplength=720).pack(anchor="w")
        ttk.Label(bottom, text="Emergency stop: press ESC while this app is active, or click Stop. "
                               "Playback uses screen coordinates; keep the same screen layout and window positions.",
                  wraplength=720, foreground="#555").pack(anchor="w", pady=(8, 4))
        self.log = tk.Text(bottom, height=7, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    def set_status(self, text):
        self.root.after(0, self.status_var.set, text)
        self.root.after(0, self.add_log, text)

    def add_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def toggle_record(self):
        if not all([mouse, keyboard]):
            messagebox.showerror("Unavailable", "Install dependencies first.")
            return
        if self.recording:
            self.recording = False
            if self.mouse_listener: self.mouse_listener.stop()
            if self.key_listener: self.key_listener.stop()
            self.record_btn.config(text="● Start Recording")
            self.set_status(f"Recording stopped. Captured {len(self.events)} events.")
            return
        if self.playing:
            messagebox.showinfo("Busy", "Stop playback before recording.")
            return
        self.events = []
        self.last_event_time = time.time()
        self.recording = True
        self.record_btn.config(text="Ⅱ Stop Recording")
        self.set_status("Recording started. Perform the mouse and keyboard actions you want to replay.")
        self.mouse_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener.start(); self.key_listener.start()

    def record_event(self, item):
        if not self.recording: return
        now = time.time()
        item["delay"] = max(0, now - (self.last_event_time or now))
        self.last_event_time = now
        self.events.append(item)

    def on_move(self, x, y):
        # Reduce noisy mouse-move recordings: keep a point only after ~0.06 sec.
        now = time.time()
        if not hasattr(self, "_last_move") or now - self._last_move > 0.06:
            self._last_move = now
            self.record_event({"type":"move", "x":int(x), "y":int(y)})

    def on_click(self, x, y, button, pressed):
        self.record_event({"type":"click", "x":int(x), "y":int(y), "button":str(button).split(".")[-1], "pressed":bool(pressed)})

    def on_scroll(self, x, y, dx, dy):
        self.record_event({"type":"scroll", "x":int(x), "y":int(y), "dx":int(dx), "dy":int(dy)})

    def on_key_press(self, key):
        self._record_key(key, True)

    def on_key_release(self, key):
        self._record_key(key, False)

    def _record_key(self, key, pressed):
        try:
            name = key.char if key.char is not None else str(key).replace("Key.", "")
        except AttributeError:
            name = str(key).replace("Key.", "")
        self.record_event({"type":"key", "key":name, "pressed":pressed})

    def start_playback(self):
        if self.recording:
            messagebox.showinfo("Recording", "Stop recording before playback.")
            return
        if self.playing: return
        if not self.events:
            messagebox.showinfo("No recording", "Record some actions or load a recording first.")
            return
        try: loops = int(self.loop_var.get())
        except ValueError:
            messagebox.showerror("Invalid loop count", "Enter a whole number. Use 0 for forever.")
            return
        self.stop_event.clear()
        self.playing = True
        threading.Thread(target=self.play_worker, args=(loops,), daemon=True).start()
        self.set_status("Playback started. Move the mouse to a screen corner or press Stop to abort.")

    def play_worker(self, loops):
        count = 0
        try:
            while not self.stop_event.is_set() and (loops == 0 or count < loops):
                for ev in self.events:
                    if self.stop_event.is_set(): break
                    delay = ev.get("delay", 0) / max(0.1, self.speed_var.get())
                    if self.stop_event.wait(delay): break
                    self.execute_event(ev)
                count += 1
            self.set_status("Playback stopped." if self.stop_event.is_set() else f"Playback complete ({count} loop(s)).")
        except Exception as e:
            self.set_status(f"Playback error: {e}")
        finally:
            self.playing = False

    def execute_event(self, ev):
        typ = ev["type"]
        if typ == "move":
            pyautogui.moveTo(ev["x"], ev["y"], duration=0)
        elif typ == "click":
            btn = ev.get("button", "left")
            if ev.get("pressed", True): pyautogui.mouseDown(ev["x"], ev["y"], button=btn)
            else: pyautogui.mouseUp(ev["x"], ev["y"], button=btn)
        elif typ == "scroll":
            pyautogui.moveTo(ev["x"], ev["y"], duration=0)
            pyautogui.scroll(ev.get("dy", 0))
        elif typ == "key":
            key = ev.get("key", "")
            if key in ("ctrl_l","ctrl_r"): key = "ctrl"
            if key in ("shift_l","shift_r"): key = "shift"
            if key in ("alt_l","alt_r"): key = "alt"
            if key == "cmd": key = "win"
            try:
                if ev.get("pressed", True): pyautogui.keyDown(key)
                else: pyautogui.keyUp(key)
            except Exception:
                pass

    def stop_all(self):
        self.stop_event.set()
        if self.recording:
            self.recording = False
            try:
                self.mouse_listener.stop(); self.key_listener.stop()
            except Exception: pass
            self.record_btn.config(text="● Start Recording")
        self.set_status("Stop requested.")

    def save_macro(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="recording.json",
                                             filetypes=[("JSON recording","*.json")])
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"events":self.events}, f, indent=2)
        self.set_status(f"Saved {len(self.events)} events to {path}")

    def choose_macro(self):
        path = filedialog.askopenfilename(filetypes=[("JSON recording","*.json")])
        if not path: return
        self.load_macro(path)

    def load_macro(self, path=MACRO_FILE):
        if not os.path.exists(path): return
        try:
            with open(path, "r", encoding="utf-8") as f: data = json.load(f)
            self.events = data.get("events", [])
            self.set_status(f"Loaded recording with {len(self.events)} events.")
        except Exception as e:
            self.set_status(f"Could not load recording: {e}")

    def add_target(self):
        path = filedialog.askopenfilename(filetypes=[("Images","*.png *.jpg *.jpeg *.bmp")])
        if not path: return
        import shutil
        dest = os.path.join(TARGET_DIR, os.path.basename(path))
        if os.path.abspath(path) != os.path.abspath(dest): shutil.copy2(path, dest)
        self.refresh_targets()

    def capture_target(self):
        if not pyautogui:
            messagebox.showerror("Unavailable", "Install dependencies first."); return
        self.root.iconify()
        messagebox.showinfo("Capture logo", "After closing this message, drag a rectangle around the logo. Press ENTER to accept or ESC to cancel.")
        try:
            shot = pyautogui.screenshot()
            # Use OpenCV selectROI in a separate window.
            frame = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            roi = cv2.selectROI("Select logo region - ENTER to save / ESC to cancel", frame, False, False)
            cv2.destroyAllWindows()
            x,y,w,h = [int(v) for v in roi]
            if w > 0 and h > 0:
                name = f"target_{int(time.time())}.png"
                cv2.imwrite(os.path.join(TARGET_DIR, name), frame[y:y+h, x:x+w])
                self.refresh_targets()
        except Exception as e:
            messagebox.showerror("Capture failed", str(e))
        finally:
            self.root.deiconify()

    def refresh_targets(self):
        self.targets = [os.path.join(TARGET_DIR, f) for f in os.listdir(TARGET_DIR)
                        if f.lower().endswith((".png",".jpg",".jpeg",".bmp"))]
        if hasattr(self, "target_list"):
            self.target_list.delete(0, "end")
            for p in self.targets: self.target_list.insert("end", os.path.basename(p))

    def remove_target(self):
        sel = self.target_list.curselection()
        if not sel: return
        path = self.targets[sel[0]]
        try: os.remove(path)
        except OSError: pass
        self.refresh_targets()

    def toggle_scan(self):
        if self.target_enabled:
            self.target_enabled = False
            self.scan_btn.config(text="Start logo scan")
            self.set_status("Logo scanning stopped.")
            return
        if not self.targets:
            messagebox.showinfo("No logos", "Add a logo image or capture a screen region first.")
            return
        self.target_enabled = True
        self.scan_btn.config(text="Stop logo scan")
        threading.Thread(target=self.scan_worker, daemon=True).start()
        self.set_status("Scanning screen for saved logos…")

    def scan_worker(self):
        last_clicked = {}
        while self.target_enabled and not self.stop_event.is_set():
            try:
                screen = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2GRAY)
                for path in list(self.targets):
                    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if template is None: continue
                    th, tw = template.shape[:2]
                    sh, sw = screen.shape[:2]
                    if th > sh or tw > sw: continue
                    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(result)
                    if max_val >= self.threshold_var.get():
                        x = max_loc[0] + tw // 2
                        y = max_loc[1] + th // 2
                        name = os.path.basename(path)
                        now = time.time()
                        # Cooldown prevents repeated clicks on the same visible match.
                        if now - last_clicked.get(name, 0) > 4:
                            self.set_status(f"Found {name} (match {max_val:.2f}) at {x},{y}.")
                            if self.click_target_var.get():
                                pyautogui.click(x, y)
                            last_clicked[name] = now
                time.sleep(0.6)
            except Exception as e:
                self.set_status(f"Logo scan error: {e}")
                time.sleep(1)
        self.root.after(0, lambda: self.scan_btn.config(text="Start logo scan"))

    def on_close(self):
        self.stop_all()
        self.target_enabled = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartClicker(root)
    root.mainloop()

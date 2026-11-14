# G8X 音量調整條：從電腦用 adb 調 LG G8X 的媒體音量（75 段刻度）。
#
# 做法：呼叫系統 AudioService 的 setStreamVolume，並帶上 LG 的 FLAG_HIFI_DAC_VOLUME（0x20000）。
# 不帶這個旗標時 LG 會把數值當成 15 段刻度（寫 2 實際變 10）；帶了就是 75 段，一格就是一格。
# 2026-11-15 實測：service call audio 11 i32 3 i32 6 i32 131072 → 耳機 5→6。
#
# 注意：交易代碼 11（setStreamVolume）是從這支手機的 framework.jar 讀出來的，
# 只適用 LG G8X（Android 12）。換手機或系統更新後要重查。

import re
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

ADB = "adb"  # adb on PATH, or put the full path to adb.exe here
TXN_SET_STREAM_VOLUME = 11
STREAM_MUSIC = 3
FLAG_HIFI_DAC_VOLUME = 0x20000
MAX_STEPS = 75
BIG_JUMP = 10          # 一次往上超過這麼多格要先確認，避免耳機突然爆音
POLL_MS = 2000

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW：呼叫 adb 時不要閃黑框


def adb_shell(cmd):
    r = subprocess.run([ADB, "-d", "shell", cmd], capture_output=True, text=True,
                       timeout=8, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or "adb 失敗")
    return r.stdout


def read_volume():
    """回傳 (目前輸出裝置名稱, 該裝置的音量格數)。"""
    out = adb_shell('dumpsys audio | grep -A8 "^- STREAM_MUSIC:"')
    cur = re.search(r"Current: (.*)", out)
    dev = re.search(r"Devices: (\S+)", out)
    if not cur or not dev:
        raise RuntimeError("讀不到媒體音量")
    values = {name: int(v) for name, v in re.findall(r"\(([^)]+)\): (\d+)", cur.group(1))}
    device = dev.group(1).split(",")[0]
    if device not in values:
        raise RuntimeError(f"找不到裝置 {device} 的音量")
    return device, values[device]


def write_volume(index):
    adb_shell(f"service call audio {TXN_SET_STREAM_VOLUME} i32 {STREAM_MUSIC} i32 {index} "
              f"i32 {FLAG_HIFI_DAC_VOLUME} s16 com.android.shell")


class App:
    def __init__(self, root):
        self.root = root
        self.current = None      # 手機上的實際格數
        self.dragging = False
        self.busy = False

        root.title("G8X 音量")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        self.label = tk.Label(root, text="連線中…", font=("Microsoft JhengHei UI", 14))
        self.label.pack(padx=12, pady=(10, 4))

        row = tk.Frame(root)
        row.pack(padx=12, pady=4)
        tk.Button(row, text="－", width=3, command=lambda: self.step(-1)).pack(side="left")
        self.scale = tk.Scale(row, from_=0, to=MAX_STEPS, orient="horizontal", length=420,
                              showvalue=True, resolution=1)
        self.scale.pack(side="left", padx=6)
        tk.Button(row, text="＋", width=3, command=lambda: self.step(+1)).pack(side="left")

        self.status = tk.Label(root, text="", fg="gray")
        self.status.pack(padx=12, pady=(0, 8))

        self.scale.bind("<ButtonPress-1>", lambda e: setattr(self, "dragging", True))
        self.scale.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<MouseWheel>", lambda e: self.step(+1 if e.delta > 0 else -1))
        root.bind("<Up>", lambda e: self.step(+1))
        root.bind("<Right>", lambda e: self.step(+1))
        root.bind("<Down>", lambda e: self.step(-1))
        root.bind("<Left>", lambda e: self.step(-1))

        self.poll()

    # ---- 背景執行 adb，避免視窗卡住 ----
    def run_bg(self, work, done):
        if self.busy:
            return
        self.busy = True

        def worker():
            try:
                result, err = work(), None
            except Exception as ex:  # adb 沒接上、逾時等
                result, err = None, ex
            self.root.after(0, lambda: self.finish(done, result, err))

        threading.Thread(target=worker, daemon=True).start()

    def finish(self, done, result, err):
        self.busy = False
        if err:
            self.status.config(text=f"錯誤：{err}", fg="red")
        else:
            done(result)

    def show(self, device_and_value):
        device, value = device_and_value
        self.current = value
        if not self.dragging:
            self.scale.set(value)
        # 手機的音量介面顯示的是百分比（格數 × 100 / 75，無條件捨去），這裡一併顯示方便對照
        self.label.config(text=f"{device}　{value} / {MAX_STEPS}　（手機顯示 {value * 100 // MAX_STEPS}）")
        self.status.config(text="已同步", fg="gray")

    # ---- 讀取 ----
    def poll(self):
        if not self.dragging:
            self.run_bg(read_volume, self.show)
        self.root.after(POLL_MS, self.poll)

    # ---- 寫入 ----
    def apply(self, target):
        target = max(0, min(MAX_STEPS, int(target)))
        if self.current is not None and target - self.current > BIG_JUMP:
            ok = messagebox.askyesno("音量確認",
                                     f"要從 {self.current} 一次調到 {target}（+{target - self.current} 格）？",
                                     parent=self.root)
            if not ok:
                self.scale.set(self.current)
                return

        def work():
            write_volume(target)
            return read_volume()

        self.run_bg(work, self.show)

    def on_release(self, _event):
        self.dragging = False
        self.apply(self.scale.get())

    def step(self, delta):
        base = self.current if self.current is not None else self.scale.get()
        self.scale.set(base + delta)
        self.apply(base + delta)


if __name__ == "__main__":
    try:  # 告訴 Windows 我們自己處理高解析度，字才不會糊
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()

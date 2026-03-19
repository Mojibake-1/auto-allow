"""
屏幕截取覆盖层
"""

import tkinter as tk
from PIL import Image, ImageTk, ImageGrab


class ScreenCaptureOverlay(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.screenshot = ImageGrab.grab()
        sw, sh = self.screenshot.size

        self.overrideredirect(True)
        self.geometry(f"{sw}x{sh}+0+0")
        self.attributes('-topmost', True)
        self.configure(cursor="cross")

        self.canvas = tk.Canvas(self, width=sw, height=sh, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        overlay = self.screenshot.copy().convert("RGBA")
        dark = Image.new("RGBA", (sw, sh), (0, 0, 0, 100))
        overlay = Image.alpha_composite(overlay, dark).convert("RGB")
        self._bg = ImageTk.PhotoImage(overlay)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._bg)
        self.canvas.create_text(sw // 2, 40,
                                text="🎯 拖动鼠标框选目标按钮  |  ESC 取消",
                                fill="#ffd700",
                                font=("Microsoft YaHei", 18, "bold"))

        self.sx = self.sy = 0
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _press(self, e):
        self.sx, self.sy = e.x, e.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                                  outline="#00ff88", width=2,
                                                  dash=(6, 3))

    def _drag(self, e):
        self.canvas.coords(self.rect, self.sx, self.sy, e.x, e.y)

    def _release(self, e):
        x1, y1 = min(self.sx, e.x), min(self.sy, e.y)
        x2, y2 = max(self.sx, e.x), max(self.sy, e.y)
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.destroy()
            self.callback(self.screenshot.crop((x1, y1, x2, y2)))
        else:
            self.destroy()

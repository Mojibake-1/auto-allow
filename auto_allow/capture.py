"""
屏幕截取覆盖层
"""

import tkinter as tk
import logging
import numpy as np
from PIL import Image, ImageTk, ImageGrab

logger = logging.getLogger(__name__)


def robust_grab(bbox=None):
    """
    可靠的屏幕截取，在 Parsec 等远控环境下自动降级。
    PIL.ImageGrab.grab() 在某些远控驱动下会返回全黑图像，
    此函数检测到全黑后使用 mss (DXGI) 作为 fallback。
    """
    try:
        img = ImageGrab.grab(bbox=bbox)
        # 快速检测是否全黑：采样 100 个像素
        arr = np.array(img)
        if arr.size > 0:
            # 取少量采样点检查亮度
            flat = arr.reshape(-1, arr.shape[-1]) if arr.ndim == 3 else arr.reshape(-1)
            step = max(1, len(flat) // 100)
            samples = flat[::step]
            if isinstance(samples[0], np.ndarray):
                mean_val = samples.mean()
            else:
                mean_val = float(samples.mean())
            if mean_val > 2:  # 不是全黑
                return img
        logger.warning("ImageGrab.grab 返回黑屏，尝试 mss 截取")
    except Exception as e:
        logger.warning("ImageGrab.grab 失败: %s，尝试 mss 截取", e)

    # fallback: 使用 mss（DXGI 截屏）
    try:
        import mss
        with mss.mss() as sct:
            if bbox:
                monitor = {
                    "left": bbox[0], "top": bbox[1],
                    "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1],
                }
            else:
                monitor = sct.monitors[0]  # 全屏
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
    except ImportError:
        logger.error("mss 未安装，无法在远控环境下截屏。请运行: pip install mss")
    except Exception as e:
        logger.error("mss 截屏失败: %s", e)

    # 最终 fallback：返回原始 ImageGrab 结果（可能全黑）
    return ImageGrab.grab(bbox=bbox)


class ScreenCaptureOverlay(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.screenshot = robust_grab()
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

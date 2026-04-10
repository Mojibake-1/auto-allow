"""
Screen capture helpers with multi-monitor support.
"""

from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageGrab, ImageTk

logger = logging.getLogger(__name__)

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


@dataclass(frozen=True)
class ScreenRegion:
    key: str
    label: str
    left: int
    top: int
    width: int
    height: int
    is_primary: bool = False
    is_all: bool = False

    @property
    def bbox(self):
        return (
            self.left,
            self.top,
            self.left + self.width,
            self.top + self.height,
        )


def _mss_monitors():
    try:
        import mss

        with mss.mss() as sct:
            return [dict(monitor) for monitor in sct.monitors]
    except ImportError:
        logger.warning("mss is not installed, monitor enumeration is limited")
    except Exception:
        logger.exception("Failed to enumerate monitors with mss")
    return []


def _primary_monitor_index(monitors):
    for index, monitor in enumerate(monitors, start=1):
        if (
            monitor["left"] <= 0 < monitor["left"] + monitor["width"]
            and monitor["top"] <= 0 < monitor["top"] + monitor["height"]
        ):
            return index
    return 1


def _build_region_label(index, width, height, left, top, is_primary):
    role = "主屏" if is_primary else "扩展屏"
    return f"屏幕 {index}（{role}）  {width}x{height}  坐标({left}, {top})"


def _fallback_regions():
    try:
        primary = ImageGrab.grab()
        all_screens = ImageGrab.grab(all_screens=True)
    except Exception:
        return [
            ScreenRegion(
                key="all",
                label="所有屏幕（同时监控）",
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_primary=True,
                is_all=True,
            )
        ]

    return [
        ScreenRegion(
            key="all",
            label=f"所有屏幕（同时监控）  {all_screens.width}x{all_screens.height}",
            left=0,
            top=0,
            width=all_screens.width,
            height=all_screens.height,
            is_all=True,
        ),
        ScreenRegion(
            key="monitor:1",
            label=f"屏幕 1（主屏）  {primary.width}x{primary.height}  坐标(0, 0)",
            left=0,
            top=0,
            width=primary.width,
            height=primary.height,
            is_primary=True,
        ),
    ]


def list_screen_regions():
    monitors = _mss_monitors()
    if len(monitors) <= 1:
        return _fallback_regions()

    all_monitor = monitors[0]
    physical_monitors = monitors[1:]
    primary_index = _primary_monitor_index(physical_monitors)

    regions = [
        ScreenRegion(
            key="all",
            label=(
                "所有屏幕（同时监控）  "
                f"{all_monitor['width']}x{all_monitor['height']}"
            ),
            left=all_monitor["left"],
            top=all_monitor["top"],
            width=all_monitor["width"],
            height=all_monitor["height"],
            is_all=True,
        )
    ]

    for index, monitor in enumerate(physical_monitors, start=1):
        is_primary = index == primary_index
        regions.append(
            ScreenRegion(
                key=f"monitor:{index}",
                label=_build_region_label(
                    index,
                    monitor["width"],
                    monitor["height"],
                    monitor["left"],
                    monitor["top"],
                    is_primary,
                ),
                left=monitor["left"],
                top=monitor["top"],
                width=monitor["width"],
                height=monitor["height"],
                is_primary=is_primary,
            )
        )

    return regions


def resolve_screen_region(region_key="all"):
    regions = list_screen_regions()
    if region_key == "primary":
        for region in regions:
            if region.is_primary:
                return region

    for region in regions:
        if region.key == region_key:
            return region

    for region in regions:
        if region.is_all:
            return region

    return regions[0]


def robust_grab(bbox=None, all_screens=False):
    """
    Grab a screen region and fall back to mss if Pillow returns a black frame.
    """
    use_all_screens = bool(
        all_screens
        or (
            bbox is not None
            and (bbox[0] < 0 or bbox[1] < 0 or bbox[2] < 0 or bbox[3] < 0)
        )
    )

    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=use_all_screens)
        arr = np.array(img)
        if arr.size > 0:
            flat = arr.reshape(-1, arr.shape[-1]) if arr.ndim == 3 else arr.reshape(-1)
            step = max(1, len(flat) // 100)
            samples = flat[::step]
            if float(samples.mean()) > 2:
                return img
        logger.warning("ImageGrab returned a black frame, falling back to mss")
    except Exception as exc:
        logger.warning("ImageGrab failed: %s, falling back to mss", exc)

    try:
        import mss

        with mss.mss() as sct:
            if bbox:
                monitor = {
                    "left": bbox[0],
                    "top": bbox[1],
                    "width": max(bbox[2] - bbox[0], 1),
                    "height": max(bbox[3] - bbox[1], 1),
                }
            elif use_all_screens:
                monitor = sct.monitors[0]
            elif len(sct.monitors) > 1:
                monitor = sct.monitors[1]
            else:
                monitor = sct.monitors[0]

            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except ImportError:
        logger.error("mss is not installed")
    except Exception as exc:
        logger.error("mss grab failed: %s", exc)

    return ImageGrab.grab(bbox=bbox, all_screens=use_all_screens)


def capture_screen_region(region):
    return robust_grab(bbox=region.bbox, all_screens=region.is_all)


def native_left_click(x, y):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Native click is only available on Windows")

    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _geometry_string(width, height, left, top):
    return f"{width}x{height}{left:+d}{top:+d}"


class ScreenCaptureOverlay(tk.Toplevel):
    def __init__(self, parent, callback, region=None):
        super().__init__(parent)
        self.callback = callback
        self.region = region or resolve_screen_region("all")
        self.screenshot = capture_screen_region(self.region)
        sw, sh = self.screenshot.size

        self.overrideredirect(True)
        self.geometry(_geometry_string(sw, sh, self.region.left, self.region.top))
        self.attributes("-topmost", True)
        self.configure(cursor="cross")

        self.canvas = tk.Canvas(self, width=sw, height=sh, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        overlay = self.screenshot.copy().convert("RGBA")
        dark = Image.new("RGBA", (sw, sh), (0, 0, 0, 100))
        overlay = Image.alpha_composite(overlay, dark).convert("RGB")
        self._bg = ImageTk.PhotoImage(overlay)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._bg)
        self.canvas.create_text(
            sw // 2,
            40,
            text=f"拖动鼠标框选目标按钮 | 当前范围：{self.region.label} | ESC 取消",
            fill="#ffd700",
            font=("Microsoft YaHei", 18, "bold"),
        )

        self.sx = self.sy = 0
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda event: self.destroy())
        self.focus_force()

    def _press(self, event):
        self.sx, self.sy = event.x, event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#00ff88",
            width=2,
            dash=(6, 3),
        )

    def _drag(self, event):
        self.canvas.coords(self.rect, self.sx, self.sy, event.x, event.y)

    def _release(self, event):
        x1, y1 = min(self.sx, event.x), min(self.sy, event.y)
        x2, y2 = max(self.sx, event.x), max(self.sy, event.y)
        self.destroy()
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.callback(self.screenshot.crop((x1, y1, x2, y2)))

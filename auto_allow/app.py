"""
主应用 — AutoAllowApp
"""

import tkinter as tk
from tkinter import messagebox
import pyautogui
from PIL import Image, ImageTk, ImageGrab, ImageDraw
import cv2
import numpy as np
import pystray
from pystray import MenuItem as TrayItem
import threading
import time
import os
import json
import glob

from .constants import (
    CONFIG_DIR, HISTORY_DIR, CONFIG_PATH,
    MAX_HISTORY, HISTORY_CROP_W, HISTORY_CROP_H,
    DEFAULT_INTERVAL, DEFAULT_CONFIDENCE, DEFAULT_COOLDOWN,
)
from .themes import get_theme, DEFAULT_THEME
from .icon import generate_icon
from .templates import TemplateManager
from .capture import ScreenCaptureOverlay
from .widget import FloatingWidget
from .settings import SettingsDialog
from .history import HistoryViewer


class AutoAllowApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()   # 主窗口隐藏，只用浮窗和托盘

        # 加载主题（需先读 config 获取 theme id）
        self.current_theme_id = self._read_theme_from_config()
        self.c = get_theme(self.current_theme_id)

        # 状态
        self.monitoring = False
        self.click_count = 0
        self.running = True
        self.last_click_time = {}
        self.settings_win = None
        self._capture_callback = None
        self._last_mouse_pos = None       # 鼠标活动检测
        self._last_mouse_move_time = 0
        self._is_software_clicking = False

        # 配置变量
        self.interval = tk.DoubleVar(value=DEFAULT_INTERVAL)
        self.confidence = tk.DoubleVar(value=DEFAULT_CONFIDENCE)
        self.cooldown = tk.DoubleVar(value=DEFAULT_COOLDOWN)

        # 初始化
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(HISTORY_DIR, exist_ok=True)
        self.icon_img = generate_icon()
        self.tpl_mgr = TemplateManager()
        self.click_history = []   # [(timestamp, filepath, name, idx), ...]
        self._load_history()
        self._load_config()

        # 创建 UI
        self.widget = FloatingWidget(self)
        self.widget.update_template_count(self.tpl_mgr.count())
        self._create_tray()

        # 全局热键
        self.root.bind_all("<F6>", lambda e: self.toggle_monitoring())

    # ── 读取主题 ID（config 可能还没完整加载）──────────
    def _read_theme_from_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                return cfg.get('theme', DEFAULT_THEME)
        except Exception:
            pass
        return DEFAULT_THEME

    # ── 系统托盘 ──────────────────────────────────────
    def _create_tray(self):

        def _make_menu():
            return pystray.Menu(
                TrayItem("显示 / 隐藏浮窗", self._tray_toggle_widget,
                         default=True),
                pystray.Menu.SEPARATOR,
                TrayItem("▶ 开始监控", self._tray_start,
                         visible=lambda item: not self.monitoring),
                TrayItem("⏹ 停止监控", self._tray_stop,
                         visible=lambda item: self.monitoring),
                pystray.Menu.SEPARATOR,
                TrayItem("📷 截取新模板", self._tray_capture),
                TrayItem("⚙ 设置...", self._tray_settings),
                pystray.Menu.SEPARATOR,
                TrayItem("❌ 退出", self._tray_quit),
            )

        self.tray = pystray.Icon(
            "auto_allow", self.icon_img, "⚡ Auto Allow", _make_menu())

        threading.Thread(target=self.tray.run, daemon=True).start()

    def _tray_toggle_widget(self):
        self.root.after(0, self._do_toggle_widget)

    def _do_toggle_widget(self):
        if self.widget.winfo_viewable():
            self.widget.hide()
        else:
            self.widget.show()

    def _tray_start(self):
        self.root.after(0, lambda: self._start_monitoring())

    def _tray_stop(self):
        self.root.after(0, lambda: self._stop_monitoring())

    def _tray_capture(self):
        self.root.after(0, lambda: self.start_capture())

    def _tray_settings(self):
        self.root.after(0, lambda: self.show_settings())

    def _tray_quit(self):
        self.root.after(0, lambda: self._quit())

    # ── 公共操作 ──────────────────────────────────────
    def toggle_monitoring(self):
        if self.monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        if self.tpl_mgr.count() == 0:
            messagebox.showwarning("提示", "请先截取至少一个目标按钮模板！")
            return
        self.monitoring = True
        self.last_click_time = {}
        self.widget.set_monitoring_ui(True)
        self.widget.set_status("监控中...", self.c['success'])
        self.widget.set_last_action(
            f"正在扫描 {self.tpl_mgr.count()} 个模板...")
        self._update_tray_tooltip("监控中...")
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _stop_monitoring(self):
        self.monitoring = False
        self.widget.set_monitoring_ui(False)
        self.widget.set_status("已暂停", self.c['dim'])
        self.widget.set_last_action("已暂停监控")
        self._update_tray_tooltip("已暂停")

    def _update_tray_tooltip(self, status):
        try:
            self.tray.title = f"⚡ Auto Allow - {status}"
        except Exception:
            pass

    def start_capture(self, on_done=None):
        self._capture_callback = on_done
        self.widget.hide()
        if self.settings_win:
            self.settings_win.withdraw()
        self.root.after(300, self._do_capture)

    def _do_capture(self):
        ScreenCaptureOverlay(self.root, self._on_captured)

    def _on_captured(self, region):
        name = self.tpl_mgr.add(region)
        self.widget.show()
        self.widget.update_template_count(self.tpl_mgr.count())
        self.widget.set_last_action(
            f"✅ 已添加「{name}」({region.width}×{region.height})")
        self.save_config()
        if self._capture_callback:
            self._capture_callback()
            self._capture_callback = None

    def test_scan(self):
        """测试扫描：截屏一次，标出所有匹配位置，显示预览"""
        if self.tpl_mgr.count() == 0:
            messagebox.showwarning("提示", "请先截取至少一个模板！")
            return

        self.widget.set_last_action("🔍 正在测试扫描...")
        screenshot = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        threshold = self.confidence.get()

        # 在截图副本上画标记
        marked = screenshot.copy()
        draw = ImageDraw.Draw(marked)
        matches = []

        for name, tpl_cv in self.tpl_mgr.cv_list():
            th, tw = tpl_cv.shape[:2]
            sh, sw = screen_cv.shape[:2]
            if tw > sw or th > sh:
                continue

            result = cv2.matchTemplate(screen_cv, tpl_cv,
                                        cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            x1, y1 = max_loc
            x2, y2 = x1 + tw, y1 + th

            if max_val >= threshold:
                # 超过阈值 → 绿框 + 会被点击
                draw.rectangle([x1, y1, x2, y2], outline="#00ff00", width=3)
                label = f"✅ {name}: {max_val:.3f}"
                draw.text((x1, y1 - 18), label, fill="#00ff00")
                matches.append((name, max_val, "✅ 会点击"))
            elif max_val >= 0.70:
                # 接近阈值 → 黄框 + 不会点
                draw.rectangle([x1, y1, x2, y2], outline="#ffdd00", width=2)
                label = f"⚠ {name}: {max_val:.3f}"
                draw.text((x1, y1 - 18), label, fill="#ffdd00")
                matches.append((name, max_val, "⚠ 不点击(低于阈值)"))
            else:
                matches.append((name, max_val, "❌ 未匹配"))

        # 显示预览窗口
        self._show_test_preview(marked, matches, threshold)

    def _show_test_preview(self, marked_img, matches, threshold):
        """显示测试扫描结果的预览窗口"""
        preview = tk.Toplevel(self.root)
        preview.title("🔍 测试扫描结果")
        preview.attributes('-topmost', True)
        preview.configure(bg=self.c['bg'])

        # 缩放图片以适合屏幕
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        scale = min((sw * 0.7) / marked_img.width,
                    (sh * 0.6) / marked_img.height, 1.0)
        pw = int(marked_img.width * scale)
        ph = int(marked_img.height * scale)
        resized = marked_img.resize((pw, ph), Image.LANCZOS)

        preview.geometry(f"{pw + 20}x{ph + 150}")

        # 图片
        preview._img = ImageTk.PhotoImage(resized)
        tk.Label(preview, image=preview._img, bg=self.c['bg']).pack(
            padx=10, pady=(10, 5))

        # 匹配结果列表
        info_frame = tk.Frame(preview, bg=self.c['card'])
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(info_frame, text=f"阈值: {threshold:.2f}",
                 font=("Microsoft YaHei", 10, "bold"),
                 fg=self.c['fg'], bg=self.c['card']).pack(anchor='w', padx=8, pady=4)

        for name, val, status in matches:
            color = self.c['success'] if "✅" in status else (
                self.c['warning'] if "⚠" in status else self.c['dim'])
            tk.Label(info_frame,
                     text=f"  {status}  「{name}」 置信度: {val:.4f}",
                     font=("Consolas", 9), fg=color,
                     bg=self.c['card'], anchor='w').pack(fill=tk.X, padx=8)

        tk.Frame(info_frame, bg=self.c['card'], height=6).pack()

        # 提示
        tip = "💡 绿框=会被点击  黄框=接近但低于阈值  看不到框=完全不匹配"
        tk.Label(preview, text=tip, font=("Microsoft YaHei", 8),
                 fg=self.c['dim'], bg=self.c['bg']).pack(pady=(0, 8))

        self.widget.set_last_action(f"🔍 测试完成: {len([m for m in matches if '✅' in m[2]])} 个匹配")

    def view_history(self):
        """打开点击历史截图查看器"""
        HistoryViewer(self)

    def show_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self.settings_win = SettingsDialog(self)

    def _quit(self):
        self.running = False
        self.monitoring = False
        self.save_config()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ── 核心监控循环 ──────────────────────────────────
    def _monitor_loop(self):
        self._last_mouse_pos = pyautogui.position()
        self._last_mouse_move_time = 0

        while self.monitoring and self.running:
            try:
                # ── 鼠标活动检测：用户操作时自动暂停 ──
                current_pos = pyautogui.position()
                now = time.time()

                if not self._is_software_clicking:
                    if current_pos != self._last_mouse_pos:
                        self._last_mouse_move_time = now
                        self._last_mouse_pos = current_pos
                        self.root.after(0, self.widget.set_status,
                                        "⏸ 用户操作中", self.c['warning'])
                        time.sleep(0.1)
                        continue

                self._last_mouse_pos = current_pos

                # 鼠标停止后等 0.5 秒再恢复扫描
                if self._last_mouse_move_time > 0 and now - self._last_mouse_move_time < 0.5:
                    time.sleep(0.1)
                    continue

                # 从暂停恢复 → 更新状态
                if self._last_mouse_move_time > 0:
                    self._last_mouse_move_time = 0
                    self.root.after(0, self.widget.set_status,
                                    "监控中...", self.c['success'])

                screenshot = ImageGrab.grab()
                screen_np = np.array(screenshot)
                screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                screen_gray = cv2.cvtColor(screen_cv, cv2.COLOR_BGR2GRAY)
                del screen_np  # 释放中间数组
                threshold = self.confidence.get()
                cd = self.cooldown.get()
                now = time.time()

                for name, tpl_bgr, tpl_gray in self.tpl_mgr.cv_gray_list():
                    if name in self.last_click_time:
                        if now - self.last_click_time[name] < cd:
                            continue

                    th, tw = tpl_gray.shape[:2]
                    sh, sw = screen_gray.shape[:2]
                    if tw > sw or th > sh:
                        continue

                    # Step 1: 灰度快速预匹配（单通道，速度 ~3x）
                    result = cv2.matchTemplate(screen_gray, tpl_gray,
                                                cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(result)

                    if max_val >= threshold:
                        # Step 2: 彩色验证（仅对匹配区域小范围验证）
                        x, y = max_loc
                        pad = 4
                        ry1, ry2 = max(y - pad, 0), min(y + th + pad, sh)
                        rx1, rx2 = max(x - pad, 0), min(x + tw + pad, sw)
                        roi_bgr = screen_cv[ry1:ry2, rx1:rx2]
                        final_conf = max_val

                        if roi_bgr.shape[0] >= th and roi_bgr.shape[1] >= tw:
                            color_res = cv2.matchTemplate(
                                roi_bgr, tpl_bgr, cv2.TM_CCOEFF_NORMED)
                            _, color_val, _, _ = cv2.minMaxLoc(color_res)
                            if color_val < threshold:
                                continue  # 彩色验证未通过，跳过
                            final_conf = color_val

                        cx = x + tw // 2
                        cy = y + th // 2

                        # 保存点击上下文截图（点击前截取）
                        snap_path = self._save_click_snapshot(
                            screenshot, max_loc, tw, th, name)

                        # 记住鼠标位置 → 点击 → 恢复原位
                        orig_x, orig_y = pyautogui.position()
                        self._is_software_clicking = True
                        pyautogui.click(cx, cy)
                        pyautogui.moveTo(orig_x, orig_y)
                        self._is_software_clicking = False
                        self._last_mouse_pos = pyautogui.position()

                        self.last_click_time[name] = time.time()
                        self.click_count += 1

                        ts = time.strftime("%H:%M:%S")
                        self.root.after(0, self._on_clicked,
                                        name, cx, cy, final_conf, ts,
                                        snap_path)
                        time.sleep(0.5)
                        break

                # 释放大数组节省内存
                del screen_cv, screen_gray, screenshot

                time.sleep(self.interval.get())

            except pyautogui.FailSafeException:
                self.root.after(0, self._emergency_stop)
                return
            except Exception as e:
                self.root.after(0, self.widget.set_last_action,
                                f"⚠ 错误: {str(e)[:40]}")
                time.sleep(3)

    def _save_click_snapshot(self, screenshot, loc, tw, th, name):
        """以匹配区域为中心截取上下文截图，保留最近 MAX_HISTORY 张"""
        try:
            sw, sh = screenshot.size
            # 以按钮为中心，向上多截一些（看到命令内容）
            cx, cy = loc[0] + tw // 2, loc[1] + th // 2
            x1 = max(cx - HISTORY_CROP_W // 2, 0)
            y1 = max(cy - HISTORY_CROP_H * 2 // 3, 0)  # 上方多截
            x2 = min(x1 + HISTORY_CROP_W, sw)
            y2 = min(y1 + HISTORY_CROP_H, sh)

            crop = screenshot.crop((x1, y1, x2, y2))

            ts_file = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{ts_file}_{name}.png"
            filepath = os.path.join(HISTORY_DIR, filename)
            crop.save(filepath)

            ts_display = time.strftime("%H:%M:%S")
            self.click_history.append((ts_display, filepath, name,
                                       self.click_count))

            # 只保留最近 MAX_HISTORY 条
            if len(self.click_history) > MAX_HISTORY:
                old = self.click_history.pop(0)
                try:
                    if os.path.exists(old[1]):
                        os.remove(old[1])
                except Exception:
                    pass

            return filepath
        except Exception:
            return None

    def _on_clicked(self, name, x, y, conf, ts, snap_path=None):
        self.widget.update_count(self.click_count)
        self.widget.set_status(f"✅ 点击了「{name}」", self.c['warning'])
        self.widget.set_last_action(
            f"[{ts}] 🖱「{name}」({x},{y}) 置信:{conf:.2f}")
        self._update_tray_tooltip(f"已点击 {self.click_count} 次")
        self.root.after(1500, lambda: (
            self.widget.set_status("监控中...", self.c['success'])
            if self.monitoring else None))

    def _emergency_stop(self):
        self._stop_monitoring()
        messagebox.showwarning("紧急停止", "鼠标移至屏幕左上角，已紧急停止！")

    # ── 配置 ──────────────────────────────────────────
    def save_config(self):
        try:
            cfg = {
                'interval': self.interval.get(),
                'confidence': self.confidence.get(),
                'cooldown': self.cooldown.get(),
                'theme': self.current_theme_id,
            }
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.interval.set(cfg.get('interval', DEFAULT_INTERVAL))
                self.confidence.set(cfg.get('confidence', DEFAULT_CONFIDENCE))
                self.cooldown.set(cfg.get('cooldown', DEFAULT_COOLDOWN))
                self.current_theme_id = cfg.get('theme', DEFAULT_THEME)
        except Exception:
            pass

    def _load_history(self):
        """启动时从磁盘加载已有的历史截图"""
        try:
            files = sorted(glob.glob(os.path.join(HISTORY_DIR, "*.png")))
            # 只保留最近 MAX_HISTORY 个
            if len(files) > MAX_HISTORY:
                for old in files[:-MAX_HISTORY]:
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                files = files[-MAX_HISTORY:]

            for filepath in files:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                # 文件名格式: 20260317_143005_模板1
                parts = fname.split('_', 2)
                if len(parts) >= 3:
                    ts = parts[1]  # HHMMSS
                    ts_display = f"{ts[:2]}:{ts[2:4]}:{ts[4:6]}" if len(ts) == 6 else ts
                    name = parts[2]
                else:
                    ts_display = "--:--:--"
                    name = fname

                idx = len(self.click_history) + 1
                self.click_history.append((ts_display, filepath, name, idx))
        except Exception:
            pass

    # ── 启动 ──────────────────────────────────────────
    def run(self):
        self.root.mainloop()

"""
主应用 — AutoAllowApp
"""

import tkinter as tk
from tkinter import messagebox
import pyautogui
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import pystray
from pystray import MenuItem as TrayItem
import threading
import time
import os
import json
import glob
import logging

logger = logging.getLogger(__name__)

from .constants import (
    CONFIG_DIR, HISTORY_DIR, CONFIG_PATH,
    MAX_HISTORY, HISTORY_CROP_W, HISTORY_CROP_H,
    DEFAULT_INTERVAL, DEFAULT_CONFIDENCE, DEFAULT_COOLDOWN,
)
from .themes import get_theme, DEFAULT_THEME
from .icon import generate_icon
from .templates import TemplateManager
from .capture import ScreenCaptureOverlay, robust_grab
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
        self._monitoring = False
        self.click_count = 0
        self._running = True
        self.last_click_time = {}
        self.settings_win = None
        self._capture_callback = None
        self._last_mouse_pos = None       # 鼠标活动检测
        self._last_mouse_move_time = 0
        self._is_software_clicking = False
        self._lock = threading.Lock()  # 保护跨线程共享状态

    @property
    def monitoring(self):
        with self._lock:
            return self._monitoring

    @monitoring.setter
    def monitoring(self, value):
        with self._lock:
            self._monitoring = value

    @property
    def running(self):
        with self._lock:
            return self._running

    @running.setter
    def running(self, value):
        with self._lock:
            self._running = value

        # 配置变量
        self.interval = tk.DoubleVar(value=DEFAULT_INTERVAL)
        self.confidence = tk.DoubleVar(value=DEFAULT_CONFIDENCE)
        self.cooldown = tk.DoubleVar(value=DEFAULT_COOLDOWN)

        # 线程安全的配置快照（监控线程读取这些而非 DoubleVar）
        self._cached_interval = DEFAULT_INTERVAL
        self._cached_confidence = DEFAULT_CONFIDENCE
        self._cached_cooldown = DEFAULT_COOLDOWN

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

    def apply_theme(self, theme_id):
        """实时切换主题，无需重启"""
        self.current_theme_id = theme_id
        self.c = get_theme(theme_id)
        self.save_config()

        # 保存旧浮窗状态
        try:
            was_visible = self.widget.winfo_viewable()
            old_x = self.widget.winfo_x()
            old_y = self.widget.winfo_y()
        except Exception:
            was_visible = True
            old_x = self.root.winfo_screenwidth() - FloatingWidget.EXPANDED_W - 20
            old_y = self.root.winfo_screenheight() - FloatingWidget.EXPANDED_H - 80

        # 停止动画再销毁，避免 after 回调异常
        try:
            self.widget._stop_pulse()
            if self.widget._collapse_timer:
                self.widget.after_cancel(self.widget._collapse_timer)
                self.widget._collapse_timer = None
            self.widget.destroy()
        except Exception:
            pass

        # 用新主题创建浮窗
        self.widget = FloatingWidget(self)
        self.widget.update_template_count(self.tpl_mgr.count())
        self.widget.update_count(self.click_count)

        # 恢复位置
        self.widget._pos_x = old_x
        self.widget._pos_y = old_y
        self.widget.geometry(
            f"{FloatingWidget.EXPANDED_W}x{FloatingWidget.EXPANDED_H}"
            f"+{old_x}+{old_y}")

        # 恢复监控状态显示
        if self.monitoring:
            self.widget.set_monitoring_ui(True)
            self.widget.set_status("监控中...", self.c['success'])

        if not was_visible:
            self.widget.hide()

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
        with self._lock:
            self.last_click_time = {}
        # 缓存配置供监控线程安全读取
        self._cached_interval = self.interval.get()
        self._cached_confidence = self.confidence.get()
        self._cached_cooldown = self.cooldown.get()
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
        if name is None:
            self.widget.set_last_action("⚠ 模板数量已达上限，请先删除旧模板")
        else:
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
        screenshot = robust_grab()
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

                screenshot = robust_grab()
                screen_np = np.array(screenshot)
                screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                screen_gray = cv2.cvtColor(screen_cv, cv2.COLOR_BGR2GRAY)
                del screen_np  # 释放中间数组
                threshold = self._cached_confidence
                cd = self._cached_cooldown
                now = time.time()

                for name, tpl_bgr, tpl_gray in self.tpl_mgr.cv_gray_list():
                    with self._lock:
                        last_t = self.last_click_time.get(name, 0)
                    if now - last_t < cd:
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

                        # Step 3: ROI 快速二次验证（缩小 TOCTOU 窗口）
                        try:
                            scr_w, scr_h = screenshot.size
                            roi_grab = robust_grab(
                                bbox=(max(x - 2, 0), max(y - 2, 0),
                                      min(x + tw + 2, scr_w),
                                      min(y + th + 2, scr_h)))
                            roi_arr = cv2.cvtColor(
                                np.array(roi_grab), cv2.COLOR_RGB2BGR)
                            if (roi_arr.shape[0] >= th
                                    and roi_arr.shape[1] >= tw):
                                recheck = cv2.matchTemplate(
                                    roi_arr, tpl_bgr,
                                    cv2.TM_CCOEFF_NORMED)
                                _, rv, _, _ = cv2.minMaxLoc(recheck)
                                if rv < threshold:
                                    continue  # 目标已变化，跳过
                        except Exception:
                            pass  # 二次验证失败不阻塞主流程

                        # 保存点击上下文截图（点击前截取）
                        snap_path = self._save_click_snapshot(
                            screenshot, max_loc, tw, th, name)

                        # 记住鼠标位置 → 点击 → 恢复原位
                        orig_x, orig_y = pyautogui.position()
                        self._is_software_clicking = True
                        try:
                            pyautogui.click(cx, cy)
                            pyautogui.moveTo(orig_x, orig_y)
                        finally:
                            self._is_software_clicking = False
                            self._last_mouse_pos = pyautogui.position()

                        with self._lock:
                            self.last_click_time[name] = time.time()
                            self.click_count += 1

                        ts = time.strftime("%H:%M:%S")
                        self.root.after(0, self._on_clicked,
                                        name, cx, cy, final_conf, ts,
                                        snap_path)
                        time.sleep(0.5)
                        break

                # 释放大数组节省内存
                try:
                    del screen_cv, screen_gray, screenshot
                except NameError:
                    pass

                time.sleep(self._cached_interval)

            except pyautogui.FailSafeException:
                self.root.after(0, self._emergency_stop)
                return
            except Exception as e:
                logger.error("监控循环异常: %s", e, exc_info=True)
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
            with self._lock:
                count = self.click_count
                self.click_history.append((ts_display, filepath, name,
                                           count))
                if len(self.click_history) > MAX_HISTORY:
                    old = self.click_history.pop(0)
                else:
                    old = None
            if old:
                try:
                    if os.path.exists(old[1]):
                        os.remove(old[1])
                except Exception:
                    pass

            return filepath
        except Exception as e:
            logger.warning("保存点击截图失败: %s", e)
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
            # 同步更新线程安全的配置快照
            self._cached_interval = cfg['interval']
            self._cached_confidence = cfg['confidence']
            self._cached_cooldown = cfg['cooldown']
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                iv = max(0.2, min(float(cfg.get('interval', DEFAULT_INTERVAL)), 30.0))
                cf = max(0.5, min(float(cfg.get('confidence', DEFAULT_CONFIDENCE)), 1.0))
                cd = max(0.0, min(float(cfg.get('cooldown', DEFAULT_COOLDOWN)), 60.0))
                self.interval.set(iv)
                self.confidence.set(cf)
                self.cooldown.set(cd)
                self._cached_interval = iv
                self._cached_confidence = cf
                self._cached_cooldown = cd
                self.current_theme_id = cfg.get('theme', DEFAULT_THEME)
                self.c = get_theme(self.current_theme_id)
        except Exception as e:
            logger.warning("配置加载失败，使用默认值: %s", e)

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

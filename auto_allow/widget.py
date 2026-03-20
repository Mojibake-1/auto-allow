"""
浮窗控件（自动展开/折叠）
"""

import math
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw


class FloatingWidget(tk.Toplevel):
    """悬浮控制面板：鼠标悬停展开，离开后自动折叠为小圆角图标"""

    COLLAPSED_W = 52
    COLLAPSED_H = 52
    EXPANDED_W = 320
    EXPANDED_H = 200
    COLLAPSE_DELAY = 200   # 鼠标离开后多久折叠 (ms)

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.95)
        self.configure(bg=self.c['bg'])

        # 状态
        self.is_expanded = True
        self._collapse_timer = None
        self._status_color = self.c['dim']
        self._status_text = "待机中"
        self._count = 0
        self._tpl_count = 0
        self._last_action = "截取按钮模板后点击 ▶ 开始"
        self._offset_x = 0
        self._offset_y = 0
        self._pulse_phase = 0
        self._pulse_job = None

        # 初始位置：屏幕右下角
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        self._pos_x = scr_w - self.EXPANDED_W - 20
        self._pos_y = scr_h - self.EXPANDED_H - 80
        self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}"
                      f"+{self._pos_x}+{self._pos_y}")

        # 构建两种视图
        self.collapsed_frame = tk.Frame(self, bg=self.c['bg'])
        self.expanded_frame = tk.Frame(self, bg=self.c['bg'])
        self._build_collapsed_view()
        self._build_expanded_view()

        # 初始显示展开状态
        self.expanded_frame.pack(fill=tk.BOTH, expand=True)

        # 鼠标悬停追踪
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # 首次显示后设置圆角
        self.after(100, lambda: self._apply_rounded_corners(8))

        # 3 秒后自动折叠（给用户时间看到界面）
        self._collapse_timer = self.after(2500, self._collapse)

    # ── 圆角 / 圆形（Windows API）─────────────────
    def _apply_rounded_corners(self, radius):
        try:
            import ctypes
            hwnd = int(self.winfo_id())
            w = self.winfo_width()
            h = self.winfo_height()
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, radius, radius)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def _apply_circular_region(self):
        try:
            import ctypes
            hwnd = int(self.winfo_id())
            w = self.winfo_width()
            h = self.winfo_height()
            rgn = ctypes.windll.gdi32.CreateEllipticRgn(0, 0, w + 1, h + 1)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    # ── 工具 ────────────────────────────────────────────
    @staticmethod
    def _hex_to_rgb(hex_color):
        """将 '#rrggbb' 转为 (r, g, b) 元组"""
        h = hex_color.lstrip('#')
        if len(h) < 6: return (255, 255, 255)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _generate_aa_frames(self):
        """用 PIL 在 4X 分辨率下预渲染 36 帧高帧率抗锯齿雷达动画"""
        self._anim_frames = []
        sz = self.COLLAPSED_W
        sc = 4
        big_size = sz * sc
        
        ar, ag, ab = self._hex_to_rgb(self.c.get('accent', '#4a9eff'))
        bg_r, bg_g, bg_b = self._hex_to_rgb(self.c.get('bg', '#0f0f1a'))
        dim_r, dim_g, dim_b = self._hex_to_rgb(self.c.get('dim', '#8888aa'))

        # 计算透明色键：与 bg 色差 1 单位，肉眼不可分辨但 OS 可区分
        tr = min(255, bg_r + 1) if bg_r < 128 else max(0, bg_r - 1)
        self._trans_color_rgb = (tr, bg_g, bg_b)
        self._trans_color_hex = f'#{tr:02x}{bg_g:02x}{bg_b:02x}'

        # 4x 超采样圆形 mask（缩放后边缘自动抗锯齿）
        big_mask = Image.new('L', (big_size, big_size), 0)
        ImageDraw.Draw(big_mask).ellipse([0, 0, big_size - 1, big_size - 1], fill=255)
        self._small_mask = big_mask.resize((sz, sz), Image.LANCZOS)

        cx, cy = big_size // 2, big_size // 2
        r_orb = big_size // 2 - 6 * sc
        r_arc = big_size // 2 - 3 * sc
        arc_width = int(2 * sc)

        base_layer = Image.new('RGB', (big_size, big_size), (bg_r, bg_g, bg_b))
        draw_b = ImageDraw.Draw(base_layer)

        for i in range(r_orb, 0, -1):
            t = i / r_orb
            red = max(0, min(255, int(ar * 0.7 + 60 * (1 - t))))
            grn = max(0, min(255, int(ag * 0.7 + 60 * (1 - t))))
            blu = max(0, min(255, int(ab * 0.85 + 20 * (1 - t))))
            draw_b.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(red, grn, blu))

        hr = r_orb // 3
        for i in range(hr, 0, -1):
            blend = 0.3 * (1 - i / hr)
            base_cr = min(255, int(ar * 0.85 + 40))
            base_cg = min(255, int(ag * 0.85 + 30))
            base_cb = min(255, int(ab * 0.85 + 25))
            pr = int(min(255, base_cr + (255 - base_cr) * blend))
            pg = int(min(255, base_cg + (255 - base_cg) * blend))
            pb = int(min(255, base_cb + (255 - base_cb) * blend))
            draw_b.ellipse([cx - hr + 1.5*sc - i, cy - hr - 1.5*sc - i,
                            cx - hr + 1.5*sc + i, cy - hr - 1.5*sc + i], fill=(pr, pg, pb))

        s = big_size / 72
        # 精准居中计算
        # span X: 4s to 28s = 24s. Center of shape = 16s
        # span Y: 0s to 46s = 46s. Center of shape = 23s
        ox = cx - 16*s
        oy = cy - 23*s
        bolt = [
            (ox + 16*s, oy + 0*s), (ox + 4*s, oy + 23*s),
            (ox + 13*s, oy + 23*s), (ox + 8*s, oy + 46*s),
            (ox + 28*s, oy + 18*s), (ox + 18*s, oy + 18*s),
            (ox + 24*s, oy + 0*s),
        ]
        draw_b.polygon(bolt, fill=(255, 255, 255))

        track_r = int(dim_r * 0.4 + bg_r * 0.6)
        track_g = int(dim_g * 0.4 + bg_g * 0.6)
        track_b = int(dim_b * 0.4 + bg_b * 0.6)

        idle_frame = base_layer.copy()
        draw_i = ImageDraw.Draw(idle_frame)
        for w in range(arc_width):
            draw_i.arc([cx - r_arc + w, cy - r_arc + w, cx + r_arc - w, cy + r_arc - w],
                       start=0, end=360, fill=(track_r, track_g, track_b))
        _small = idle_frame.resize((sz, sz), Image.LANCZOS)
        _masked = Image.new('RGB', (sz, sz), self._trans_color_rgb)
        _masked.paste(_small, mask=self._small_mask)
        self._idle_frame = ImageTk.PhotoImage(_masked)

        for frame_idx in range(36):
            frame = base_layer.copy()
            draw_f = ImageDraw.Draw(frame)
            start_angle = frame_idx * 10
            
            for w in range(arc_width):
                draw_f.arc([cx - r_arc + w, cy - r_arc + w, cx + r_arc - w, cy + r_arc - w],
                           start=0, end=360, fill=(track_r, track_g, track_b))
            
            for w in range(arc_width):
                draw_f.arc([cx - r_arc + w, cy - r_arc + w, cx + r_arc - w, cy + r_arc - w],
                           start=start_angle, end=start_angle + 120, fill=(ar, ag, ab))
            
            _small = frame.resize((sz, sz), Image.LANCZOS)
            _masked = Image.new('RGB', (sz, sz), self._trans_color_rgb)
            _masked.paste(_small, mask=self._small_mask)
            self._anim_frames.append(ImageTk.PhotoImage(_masked))

    def _build_collapsed_view(self):
        c = self.c
        f = self.collapsed_frame
        sz = self.COLLAPSED_W

        self.mini_canvas = tk.Canvas(f, width=sz, height=sz,
                                      bg=c['bg'], highlightthickness=0,
                                      cursor="hand2")
        self.mini_canvas.pack(fill=tk.BOTH, expand=True)

        # 4X 超采样预渲染抗锯齿帧
        self._generate_aa_frames()
        self._frame_idx = 0
        self._img_item = self.mini_canvas.create_image(sz // 2, sz // 2, image=self._idle_frame)

        # 拖动
        self.mini_canvas.bind("<Button-1>", self._start_drag)
        self.mini_canvas.bind("<B1-Motion>", self._do_drag)

    # ── 展开视图 ──────────────────────────────────────
    def _build_expanded_view(self):
        c = self.c

        border = tk.Frame(self.expanded_frame, bg=c['border'], bd=0)
        border.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        main = tk.Frame(border, bg=c['bg'])
        main.pack(fill=tk.BOTH, expand=True)

        # ── 标题栏（可拖动）──
        title_bar = tk.Frame(main, bg=c['card'], height=30)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text="  ⚡ Auto Allow",
                 font=("Segoe UI", 10, "bold"),
                 fg=c['accent'], bg=c['card']).pack(side=tk.LEFT)

        # 关闭按钮（隐藏到托盘）
        close_btn = tk.Label(title_bar, text=" ✕ ",
                              font=("Consolas", 10),
                              fg=c['dim'], bg=c['card'], cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(0, 4))
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=c['danger']))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=c['dim']))

        # 拖动绑定
        title_bar.bind("<Button-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._do_drag)

        # ── 状态行 ──
        status_row = tk.Frame(main, bg=c['bg'])
        status_row.pack(fill=tk.X, padx=12, pady=(8, 2))

        self.dot = tk.Canvas(status_row, width=12, height=12,
                              bg=c['bg'], highlightthickness=0)
        self.dot.pack(side=tk.LEFT)
        self._dot_id = self.dot.create_oval(1, 1, 11, 11, fill=c['dim'],
                                             outline='')

        self.status_lbl = tk.Label(status_row, text="待机中",
                                    font=("Microsoft YaHei", 10),
                                    fg=c['dim'], bg=c['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=(6, 0))

        self.count_lbl = tk.Label(status_row, text="🖱 0",
                                   font=("Segoe UI", 10, "bold"),
                                   fg=c['warning'], bg=c['bg'])
        self.count_lbl.pack(side=tk.RIGHT)

        self.tpl_lbl = tk.Label(status_row, text="📌 0模板",
                                 font=("Microsoft YaHei", 9),
                                 fg=c['dim'], bg=c['bg'])
        self.tpl_lbl.pack(side=tk.RIGHT, padx=(0, 10))

        # ── 按钮行 ──
        btn_row = tk.Frame(main, bg=c['bg'])
        btn_row.pack(fill=tk.X, padx=12, pady=(6, 4))

        self.toggle_btn = tk.Button(
            btn_row, text="▶  开始", font=("Microsoft YaHei", 11, "bold"),
            fg='#fff', bg=c['success'], activebackground='#00c080',
            activeforeground='#fff', bd=0, padx=14, pady=4, cursor="hand2",
            command=self.app.toggle_monitoring)
        self.toggle_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for emoji, bg_c, fg_c, cmd in [
            ("📷", c['accent'],  '#fff',     self.app.start_capture),
            ("🔍", c['card'],    c['warning'], self.app.test_scan),
            ("📋", c['card'],    c['fg'],     self.app.view_history),
            ("⚙",  c['card'],    c['dim'],    self.app.show_settings),
        ]:
            tk.Frame(btn_row, width=5, bg=c['bg']).pack(side=tk.LEFT)
            tk.Button(btn_row, text=emoji, font=("Segoe UI", 11),
                      fg=fg_c, bg=bg_c, activebackground=c['border'],
                      bd=0, padx=6, pady=2, cursor="hand2",
                      command=cmd).pack(side=tk.LEFT)

        # ── 最近动作 ──
        self.last_lbl = tk.Label(main, text="截取按钮模板后点击 ▶ 开始",
                                  font=("Microsoft YaHei", 8),
                                  fg=c['dim'], bg=c['bg'], anchor='w')
        self.last_lbl.pack(fill=tk.X, padx=12, pady=(3, 7))

    # ── 展开/折叠逻辑 ────────────────────────────────
    def _on_enter(self, e):
        # 取消折叠定时器
        if self._collapse_timer:
            self.after_cancel(self._collapse_timer)
            self._collapse_timer = None
        if not self.is_expanded:
            self._expand()

    def _on_leave(self, e):
        # 检查鼠标是否真的离开了窗口区域
        try:
            mx, my = self.winfo_pointerxy()
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            if wx <= mx <= wx + ww and wy <= my <= wy + wh:
                return  # 鼠标还在窗口内（移到子控件上了）
        except Exception:
            pass

        if self.is_expanded and self._collapse_timer is None:
            self._collapse_timer = self.after(self.COLLAPSE_DELAY,
                                               self._collapse)

    def _expand(self):
        self.is_expanded = True
        self.collapsed_frame.pack_forget()
        self.expanded_frame.pack(fill=tk.BOTH, expand=True)

        # 同步状态到展开视图
        self.status_lbl.configure(text=self._status_text, fg=self._status_color)
        self.dot.itemconfig(self._dot_id, fill=self._status_color)
        self.count_lbl.configure(text=f"🖱 {self._count}")
        self.tpl_lbl.configure(text=f"📌 {self._tpl_count}模板")
        self.last_lbl.configure(text=self._last_action)

        # 重新设置监控按钮状态
        if self.app.monitoring:
            self.toggle_btn.configure(text="⏹ 停止", bg=self.c['danger'],
                                       activebackground='#ee5555')
        else:
            self.toggle_btn.configure(text="▶  开始", bg=self.c['success'],
                                       activebackground='#00c080')

        x, y = self.winfo_x(), self.winfo_y()
        # 保证不超出屏幕
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        x = min(x, scr_w - self.EXPANDED_W - 5)
        y = min(y, scr_h - self.EXPANDED_H - 5)
        self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}+{x}+{y}")
        # 取消透明色键，恢复正常 bg
        try:
            self.attributes('-transparentcolor', '')
        except Exception:
            pass
        self.configure(bg=self.c['bg'])
        self.collapsed_frame.configure(bg=self.c['bg'])
        self.mini_canvas.configure(bg=self.c['bg'])
        self.attributes('-alpha', 0.95)
        self.after(20, lambda: self._apply_rounded_corners(8))

    def _collapse(self):
        self._collapse_timer = None
        self.is_expanded = False
        self.expanded_frame.pack_forget()
        self.collapsed_frame.pack(fill=tk.BOTH, expand=True)

        x, y = self.winfo_x(), self.winfo_y()
        self.geometry(f"{self.COLLAPSED_W}x{self.COLLAPSED_H}+{x}+{y}")
        
        # 透明色键方案：圆形外部像素 = trans_color → OS 渲染为透明
        trans = self._trans_color_hex
        self.configure(bg=trans)
        self.collapsed_frame.configure(bg=trans)
        self.mini_canvas.configure(bg=trans)
        try:
            self.attributes('-transparentcolor', trans)
        except Exception:
            pass

        if self.app.monitoring:
            self._start_pulse()
        else:
            self.mini_canvas.itemconfig(self._img_item, image=self._idle_frame)

    # ── 脉冲动画 ──────────────────────────────────────
    def _start_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
        self._pulse_phase = 0
        self._do_pulse()

    def _stop_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        # 恢复默认外观
        if not self.is_expanded:
            self.mini_canvas.itemconfig(self._img_item, image=self._idle_frame)
            self.attributes('-alpha', 0.95)

    def _do_pulse(self):
        """丝滑自转弧线脉冲效果"""
        if self.is_expanded or not self.app.monitoring:
            self._pulse_job = None
            return

        self._frame_idx = (self._frame_idx + 1) % 36
        
        # 呼吸效果：轻微 alpha 渐变增强质感
        val = (math.sin(self._frame_idx / 36.0 * math.pi * 2) + 1) / 2
        alpha = 0.85 + 0.15 * val

        try:
            self.attributes('-alpha', alpha)
            # 通过播放预渲染帧实现硬件级平滑动画
            self.mini_canvas.itemconfig(self._img_item, image=self._anim_frames[self._frame_idx])
        except Exception:
            pass

        self._pulse_job = self.after(30, self._do_pulse)  # 提高帧率让动作丝滑

    # ── 拖动 ──────────────────────────────────────────
    def _start_drag(self, e):
        self._offset_x = e.x
        self._offset_y = e.y

    def _do_drag(self, e):
        x = self.winfo_x() + e.x - self._offset_x
        y = self.winfo_y() + e.y - self._offset_y
        if self.is_expanded:
            self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}+{x}+{y}")
        else:
            self.geometry(f"{self.COLLAPSED_W}x{self.COLLAPSED_H}+{x}+{y}")

    # ── 显示/隐藏 ────────────────────────────────────
    def show(self):
        self.deiconify()
        self.lift()

    def hide(self):
        self.withdraw()

    # ── 状态更新（同时更新内部缓存和当前可见的 UI）────
    def set_status(self, text, color):
        self._status_text = text
        self._status_color = color
        if self.is_expanded:
            self.status_lbl.configure(text=text, fg=color)
            self.dot.itemconfig(self._dot_id, fill=color)

    def set_monitoring_ui(self, active):
        if self.is_expanded:
            if active:
                self.toggle_btn.configure(text="⏹ 停止", bg=self.c['danger'],
                                           activebackground='#ee5555')
            else:
                self.toggle_btn.configure(text="▶  开始",
                                           bg=self.c['success'],
                                           activebackground='#00c080')
        if active and not self.is_expanded:
            self._start_pulse()
        elif not active:
            self._stop_pulse()

    def update_count(self, n):
        self._count = n
        if self.is_expanded:
            self.count_lbl.configure(text=f"🖱 {n}")

    def update_template_count(self, n):
        self._tpl_count = n
        if self.is_expanded:
            self.tpl_lbl.configure(text=f"📌 {n}模板")

    def set_last_action(self, text):
        self._last_action = text
        if self.is_expanded:
            self.last_lbl.configure(text=text)

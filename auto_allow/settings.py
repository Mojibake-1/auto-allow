"""
设置对话框（含主题选择）
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from .themes import get_theme_list


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c
        self.title("⚙ Auto Allow 设置")
        self.geometry("460x640")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.configure(bg=self.c['bg'])

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        c = self.c

        # ── 模板管理 ──
        tk.Label(self, text="🎯 目标按钮模板",
                 font=("Microsoft YaHei", 12, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(anchor='w', padx=16, pady=(12, 6))

        list_outer = tk.Frame(self, bg=c['border'])
        list_outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 6))

        list_inner = tk.Frame(list_outer, bg=c['card'])
        list_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 可滚动区域
        canvas = tk.Canvas(list_inner, bg=c['card'], highlightthickness=0,
                           height=200)
        scrollbar = tk.Scrollbar(list_inner, orient=tk.VERTICAL,
                                  command=canvas.yview)
        self.tpl_frame = tk.Frame(canvas, bg=c['card'])

        self.tpl_frame.bind("<Configure>",
                             lambda e: canvas.configure(
                                 scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.tpl_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮行
        btn_row = tk.Frame(self, bg=c['bg'])
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        for text, cmd, bg_c in [
            ("📷 截取新模板", self._capture, c['accent']),
            ("🗑 删除选中", self._remove, c['card']),
            ("🗑 全部清除", self._clear, c['card']),
        ]:
            tk.Button(btn_row, text=text, font=("Microsoft YaHei", 9),
                      fg='#fff' if bg_c == c['accent'] else c['dim'],
                      bg=bg_c, activebackground=c['accent_h'] if bg_c == c['accent'] else c['border'],
                      bd=0, padx=10, pady=4, cursor="hand2",
                      command=cmd).pack(side=tk.LEFT, padx=(0, 6))

        # ── 参数设置 ──
        tk.Label(self, text="⚙ 参数设置",
                 font=("Microsoft YaHei", 12, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(anchor='w', padx=16, pady=(4, 6))

        params = tk.Frame(self, bg=c['card'], highlightbackground=c['border'],
                          highlightthickness=1)
        params.pack(fill=tk.X, padx=16, pady=(0, 8))

        self._slider_row(params, "扫描间隔（秒）", self.app.interval, 0.5, 10.0)
        self._slider_row(params, "匹配置信度", self.app.confidence, 0.70, 1.0)
        self._slider_row(params, "点击冷却（秒）", self.app.cooldown, 0.5, 15.0)
        tk.Frame(params, bg=c['card'], height=6).pack()

        # ── 主题选择 ──
        tk.Label(self, text="🎨 界面主题",
                 font=("Microsoft YaHei", 12, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(anchor='w', padx=16, pady=(4, 6))

        theme_frame = tk.Frame(self, bg=c['card'],
                               highlightbackground=c['border'],
                               highlightthickness=1)
        theme_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        inner_theme = tk.Frame(theme_frame, bg=c['card'])
        inner_theme.pack(fill=tk.X, padx=12, pady=8)

        theme_list = get_theme_list()
        self.theme_var = tk.StringVar(value=self.app.current_theme_id)

        for theme_id, display_name in theme_list:
            row = tk.Frame(inner_theme, bg=c['card'])
            row.pack(fill=tk.X, pady=1)

            rb = tk.Radiobutton(
                row, text=display_name, variable=self.theme_var,
                value=theme_id,
                font=("Microsoft YaHei", 10),
                fg=c['fg'], bg=c['card'],
                selectcolor=c['input'],
                activebackground=c['card'],
                activeforeground=c['accent'],
                cursor="hand2",
            )
            rb.pack(side=tk.LEFT, padx=4, pady=2)

        tk.Label(inner_theme, text="💡 切换主题后需重启生效",
                 font=("Microsoft YaHei", 8),
                 fg=c['dim'], bg=c['card']).pack(anchor='w', padx=4, pady=(4, 0))

        # 保存按钮
        tk.Button(self, text="💾 保存设置", font=("Microsoft YaHei", 10, "bold"),
                  fg='#fff', bg=c['success'], activebackground='#00c080',
                  bd=0, padx=20, pady=6, cursor="hand2",
                  command=self._save).pack(pady=(0, 12))

        self._refresh_list()

    def _slider_row(self, parent, label, var, lo, hi):
        c = self.c
        row = tk.Frame(parent, bg=c['card'])
        row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(row, text=label, font=("Microsoft YaHei", 9),
                 fg=c['fg'], bg=c['card'], width=16, anchor='w').pack(side=tk.LEFT)
        tk.Scale(row, from_=lo, to=hi, resolution=0.05, orient=tk.HORIZONTAL,
                 variable=var, bg=c['card'], fg=c['fg'],
                 troughcolor=c['input'], highlightthickness=0, bd=0,
                 length=200, font=("Consolas", 8),
                 activebackground=c['accent']).pack(side=tk.RIGHT, fill=tk.X,
                                                     expand=True)

    def _refresh_list(self):
        for w in self.tpl_frame.winfo_children():
            w.destroy()
        c = self.c
        templates = self.app.tpl_mgr.pil_list()
        self._thumbs = []
        self.sel_idx = tk.IntVar(value=-1)

        if not templates:
            tk.Label(self.tpl_frame, text="📭 还没有模板",
                     font=("Microsoft YaHei", 10), fg=c['dim'],
                     bg=c['card']).pack(pady=20)
            return

        for idx, (name, pil) in enumerate(templates):
            row = tk.Frame(self.tpl_frame, bg=c['input'])
            row.pack(fill=tk.X, pady=1, padx=4)

            tk.Radiobutton(row, variable=self.sel_idx, value=idx,
                           bg=c['input'], fg=c['fg'],
                           selectcolor=c['input'],
                           activebackground=c['input']).pack(side=tk.LEFT, padx=4)

            ratio = min(100 / max(pil.width, 1), 30 / max(pil.height, 1), 2.0)
            tw, th = max(int(pil.width * ratio), 1), max(int(pil.height * ratio), 1)
            thumb = ImageTk.PhotoImage(pil.resize((tw, th), Image.LANCZOS))
            self._thumbs.append(thumb)
            tk.Label(row, image=thumb, bg=c['input']).pack(side=tk.LEFT, padx=4)

            tk.Label(row, text=f"{name}  ({pil.width}×{pil.height})",
                     font=("Microsoft YaHei", 9), fg=c['fg'],
                     bg=c['input']).pack(side=tk.LEFT, padx=4)

    def _capture(self):
        self.withdraw()
        self.app.start_capture(on_done=lambda: self._on_return())

    def _on_return(self):
        self.deiconify()
        self._refresh_list()

    def _remove(self):
        if not hasattr(self, 'sel_idx'):
            return
        idx = self.sel_idx.get()
        if 0 <= idx < self.app.tpl_mgr.count():
            self.app.tpl_mgr.remove(idx)
            self._refresh_list()
            self.app.widget.update_template_count(self.app.tpl_mgr.count())

    def _clear(self):
        if self.app.tpl_mgr.count() == 0:
            return
        if messagebox.askyesno("确认", "删除所有模板？", parent=self):
            self.app.tpl_mgr.clear()
            self._refresh_list()
            self.app.widget.update_template_count(0)

    def _save(self):
        # 保存主题选择
        new_theme = self.theme_var.get()
        if new_theme != self.app.current_theme_id:
            self.app.current_theme_id = new_theme
            messagebox.showinfo("主题已更改",
                                f"已切换到「{new_theme}」主题\n请重启程序以应用新主题",
                                parent=self)
        self.app.save_config()
        self._close()

    def _close(self):
        self.app.save_config()
        self.destroy()
        self.app.settings_win = None

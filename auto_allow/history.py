"""
历史记录查看器
"""

import os
import tkinter as tk
from PIL import Image, ImageTk
from .constants import MAX_HISTORY, HISTORY_DIR


class HistoryViewer(tk.Toplevel):
    """点击历史截图查看器"""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c
        self.title("📋 点击历史截图")
        self.geometry("560x620")
        self.resizable(False, True)
        self.attributes('-topmost', True)
        self.configure(bg=self.c['bg'])

        self._thumbs = []
        self._wheel_bindings = []
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        c = self.c

        # 标题
        hdr = tk.Frame(self, bg=c['bg'])
        hdr.pack(fill=tk.X, padx=16, pady=(12, 6))

        tk.Label(hdr, text="📋 点击历史截图",
                 font=("Microsoft YaHei", 13, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(side=tk.LEFT)

        count = len(self.app.click_history)
        tk.Label(hdr, text=f"共 {count} / {MAX_HISTORY} 条",
                 font=("Microsoft YaHei", 10),
                 fg=c['dim'], bg=c['bg']).pack(side=tk.RIGHT)

        # 可滚动区域
        container = tk.Frame(self, bg=c['bg'])
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        canvas = tk.Canvas(container, bg=c['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL,
                                  command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=c['bg'])

        self.scroll_frame.bind("<Configure>",
                                lambda e: canvas.configure(
                                    scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮绑定（仅在本窗口内生效）
        def _on_mousewheel(e):
            try:
                canvas.yview_scroll(-e.delta // 120, "units")
            except tk.TclError:
                pass
        bind_id = canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._wheel_bindings.append((canvas, "<MouseWheel>", bind_id))

        # 填充历史记录（最新的在上面）
        if not self.app.click_history:
            tk.Label(self.scroll_frame, text="📭 还没有点击记录\n开始监控后会自动保存",
                     font=("Microsoft YaHei", 11), fg=c['dim'],
                     bg=c['bg']).pack(pady=40)
            return

        for ts, filepath, name, idx in reversed(self.app.click_history):
            self._add_history_item(ts, filepath, name, idx)

        # 提示
        tk.Label(self, text="💡 点击截图可查看原始大小  |  截图保存在 ~/.auto_allow/history/",
                 font=("Microsoft YaHei", 8), fg=c['dim'],
                 bg=c['bg']).pack(pady=(0, 8))

    def _add_history_item(self, ts, filepath, name, idx):
        c = self.c

        card = tk.Frame(self.scroll_frame, bg=c['card'],
                        highlightbackground=c['border'],
                        highlightthickness=1)
        card.pack(fill=tk.X, pady=3)

        # 标题行
        info = tk.Frame(card, bg=c['card'])
        info.pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(info, text=f"#{idx}", font=("Consolas", 9, "bold"),
                 fg=c['accent'], bg=c['card']).pack(side=tk.LEFT)
        tk.Label(info, text=f"  [{ts}]  「{name}」",
                 font=("Microsoft YaHei", 9), fg=c['fg'],
                 bg=c['card']).pack(side=tk.LEFT)

        # 缩略图
        try:
            if os.path.exists(filepath):
                with Image.open(filepath) as img:
                    pil = img.convert("RGB")
                # 缩放到预览大小
                ratio = min(500 / max(pil.width, 1),
                           160 / max(pil.height, 1), 1.0)
                tw = max(int(pil.width * ratio), 1)
                th = max(int(pil.height * ratio), 1)
                thumb = ImageTk.PhotoImage(pil.resize((tw, th), Image.LANCZOS))
                self._thumbs.append(thumb)

                img_label = tk.Label(card, image=thumb, bg=c['card'],
                                      cursor="hand2")
                img_label.pack(padx=8, pady=(2, 6))

                # 点击打开原图（带路径校验）
                fp = filepath
                img_label.bind("<Button-1>",
                               lambda e, p=fp: self._safe_open(p))
            else:
                tk.Label(card, text="(截图文件已删除)",
                         font=("Microsoft YaHei", 9), fg=c['dim'],
                         bg=c['card']).pack(padx=8, pady=6)
        except Exception as ex:
            tk.Label(card, text=f"(加载失败: {str(ex)[:30]})",
                     font=("Microsoft YaHei", 9), fg=c['danger'],
                     bg=c['card']).pack(padx=8, pady=6)

    def _on_close(self):
        """清理全局绑定后关闭"""
        for widget, event, bind_id in self._wheel_bindings:
            try:
                widget.unbind_all(event)
            except Exception:
                pass
        self._wheel_bindings.clear()
        self.destroy()

    def _safe_open(self, filepath):
        """路径校验后调用 os.startfile"""
        try:
            real = os.path.realpath(filepath)
            allowed = os.path.realpath(HISTORY_DIR)
            # 使用 commonpath 做目录边界校验（防止同前缀兄弟目录绕过）
            if (os.path.commonpath([real, allowed]) == allowed
                    and real.lower().endswith('.png')):
                os.startfile(real)
        except Exception:
            pass

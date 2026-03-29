"""
浮窗控件（自动展开/折叠）— PyQt5 版

使用 Qt.WA_TranslucentBackground 实现完全透明的折叠态小球，
彻底解决 tkinter 方案中的黑色背景问题。

PyQt5 窗口运行在独立的 QApplication 线程中，通过 queue + tkinter
的 root.after() 桥接与主线程通信。
"""

import sys
import math
import threading
import queue
import logging

from PyQt5.QtCore import (
    Qt, QTimer, QRectF, pyqtSignal, QObject,
)
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QRadialGradient,
    QFont, QPainterPath,
)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton,
)

logger = logging.getLogger(__name__)


# ── 折叠态：圆形小球 ────────────────────────────────────────
class CollapsedBall(QWidget):
    SIZE = 52

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._phase = 0
        self._monitoring = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_monitoring(self, active):
        self._monitoring = active
        if active and not self._timer.isActive():
            self._timer.start(30)
        elif not active:
            self._timer.stop()
            self._phase = 0
        self.update()

    def _tick(self):
        self._phase = (self._phase + 10) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        sz = self.SIZE
        cx, cy = sz / 2, sz / 2
        r_outer = sz / 2 - 1
        r_ball = sz / 2 - 5
        r_arc = sz / 2 - 2.5

        AR, AG, AB = 74, 158, 255   # accent = #4a9eff

        # ① 外发光光晕
        for i in range(6, 0, -1):
            glow_alpha = int(12 * (7 - i))
            glow_r = r_outer + i * 0.8
            glow_grad = QRadialGradient(cx, cy, glow_r)
            glow_grad.setColorAt(0.5, QColor(AR, AG, AB, glow_alpha))
            glow_grad.setColorAt(1.0, QColor(AR, AG, AB, 0))
            p.setBrush(QBrush(glow_grad))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r,
                                  glow_r * 2, glow_r * 2))

        # ② 球体主体
        base_grad = QRadialGradient(cx, cy, r_ball)
        base_grad.setColorAt(0.0, QColor(112, 171, 237))
        base_grad.setColorAt(0.5, QColor(72, 131, 227))
        base_grad.setColorAt(1.0, QColor(52, 111, 217))
        p.setBrush(QBrush(base_grad))
        p.setPen(Qt.NoPen)
        ball_rect = QRectF(cx - r_ball, cy - r_ball,
                            r_ball * 2, r_ball * 2)
        p.drawEllipse(ball_rect)

        # ③ 高光
        hl1 = QRadialGradient(cx - r_ball * 0.25, cy - r_ball * 0.3,
                               r_ball * 0.45)
        hl1.setColorAt(0.0, QColor(160, 210, 255, 100))
        hl1.setColorAt(0.5, QColor(103, 164, 242, 50))
        hl1.setColorAt(1.0, QColor(103, 164, 242, 0))
        p.setBrush(QBrush(hl1))
        p.drawEllipse(QRectF(cx - r_ball * 0.6, cy - r_ball * 0.65,
                              r_ball * 0.7, r_ball * 0.55))

        hl2 = QRadialGradient(cx - r_ball * 0.2, cy - r_ball * 0.38,
                               r_ball * 0.15)
        hl2.setColorAt(0.0, QColor(255, 255, 255, 180))
        hl2.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl2))
        p.drawEllipse(QRectF(cx - r_ball * 0.3, cy - r_ball * 0.48,
                              r_ball * 0.2, r_ball * 0.18))

        # ④ 闪电 ⚡
        bolt = QPainterPath()
        s = sz / 72.0
        ox = cx - 16 * s
        oy = cy - 23 * s
        bolt.moveTo(ox + 16*s, oy)
        bolt.lineTo(ox + 4*s,  oy + 23*s)
        bolt.lineTo(ox + 13*s, oy + 23*s)
        bolt.lineTo(ox + 8*s,  oy + 46*s)
        bolt.lineTo(ox + 28*s, oy + 18*s)
        bolt.lineTo(ox + 18*s, oy + 18*s)
        bolt.lineTo(ox + 24*s, oy)
        bolt.closeSubpath()
        p.setBrush(QColor(0, 30, 80, 80))
        p.save()
        p.translate(0.8, 0.8)
        p.drawPath(bolt)
        p.restore()
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawPath(bolt)

        # ⑤ 轨道环
        track_pen = QPen(QColor(60, 60, 75, 160), 2.0)
        track_pen.setCapStyle(Qt.RoundCap)
        p.setPen(track_pen)
        p.setBrush(Qt.NoBrush)
        arc_rect = QRectF(cx - r_arc, cy - r_arc, r_arc * 2, r_arc * 2)
        p.drawEllipse(arc_rect)

        # ⑥ 旋转弧线（顺时针）
        if self._monitoring:
            arc_pen = QPen(QColor(AR, AG, AB, 255), 2.5)
            arc_pen.setCapStyle(Qt.RoundCap)
            p.setPen(arc_pen)
            p.drawArc(arc_rect, -self._phase * 16, -120 * 16)

        # ⑦ 边缘高光环
        rim_pen = QPen(QColor(120, 180, 255, 40), 0.8)
        p.setPen(rim_pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ball_rect)

        p.end()


# ── 展开态：卡片面板 ────────────────────────────────────────
class ExpandedCard(QWidget):
    CARD_W = 320
    CARD_H = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget#card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0f1a, stop:1 #1a1a2e);
                border-radius: 8px;
                border: 1px solid rgba(74, 158, 255, 60);
            }
            QLabel { color: #aab; }
        """)

        card = QWidget(self)
        card.setObjectName("card")
        card.setFixedSize(self.CARD_W, self.CARD_H)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("""
            background: rgba(255,255,255,6);
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom: 1px solid rgba(255,255,255,10);
        """)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 8, 0)

        icon_lbl = QLabel("⚡")
        icon_lbl.setFont(QFont("Segoe UI", 10))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        tb_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Auto Allow")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_lbl.setStyleSheet(
            "color: #4a9eff; background: transparent; border: none;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFont(QFont("Consolas", 9))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #556;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background: rgba(255,80,80,80); color: #ff5050; }
        """)
        close_btn.clicked.connect(self._on_close)
        tb_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # 状态行
        status_row = QWidget()
        status_row.setStyleSheet("background: transparent;")
        sr_layout = QHBoxLayout(status_row)
        sr_layout.setContentsMargins(12, 8, 12, 2)

        self.dot_lbl = QLabel("●")
        self.dot_lbl.setFont(QFont("Segoe UI", 8))
        self.dot_lbl.setStyleSheet("color: #8888aa; background: transparent;")
        sr_layout.addWidget(self.dot_lbl)

        self.status_lbl = QLabel("待机中")
        self.status_lbl.setFont(QFont("Microsoft YaHei", 10))
        self.status_lbl.setStyleSheet(
            "color: #8888aa; background: transparent;")
        sr_layout.addWidget(self.status_lbl)
        sr_layout.addStretch()

        self.tpl_lbl = QLabel("📌 0模板")
        self.tpl_lbl.setFont(QFont("Microsoft YaHei", 9))
        self.tpl_lbl.setStyleSheet("color: #8888aa; background: transparent;")
        sr_layout.addWidget(self.tpl_lbl)

        self.count_lbl = QLabel("🖱 0")
        self.count_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.count_lbl.setStyleSheet(
            "color: #ffc107; background: transparent;")
        sr_layout.addWidget(self.count_lbl)

        layout.addWidget(status_row)

        # 按钮行
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        br_layout = QHBoxLayout(btn_row)
        br_layout.setContentsMargins(12, 4, 12, 4)
        br_layout.setSpacing(5)

        self.toggle_btn = QPushButton("▶  开始")
        self.toggle_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedHeight(30)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #00c853, stop:1 #00e676);
                color: white; border: none; border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover { background: #00e676; }
        """)
        br_layout.addWidget(self.toggle_btn, stretch=2)

        self._fn_buttons = {}
        for emoji, name in [("📷", "capture"), ("🔍", "scan"),
                             ("📋", "history"), ("⚙", "settings")]:
            btn = QPushButton(emoji)
            btn.setFont(QFont("Segoe UI", 11))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,10);
                    color: #888; border: none; border-radius: 6px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,25); color: white;
                }
            """)
            br_layout.addWidget(btn)
            self._fn_buttons[name] = btn

        layout.addWidget(btn_row)

        # 信息行
        self.info_lbl = QLabel("截取按钮模板后点击 ▶ 开始")
        self.info_lbl.setFont(QFont("Microsoft YaHei", 8))
        self.info_lbl.setStyleSheet(
            "color: #556; background: transparent; padding: 3px 12px;")
        layout.addWidget(self.info_lbl)

        layout.addStretch()

    def _on_close(self):
        # 信号通过父级 FloatingWidget 处理
        parent = self.parent()
        if parent and hasattr(parent, '_on_hide_request'):
            parent._on_hide_request()

    def set_status(self, text, color):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"color: {color}; background: transparent;")
        self.dot_lbl.setStyleSheet(
            f"color: {color}; background: transparent;")

    def set_monitoring_ui(self, active):
        if active:
            self.toggle_btn.setText("⏹ 停止")
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background: #e53935; color: white;
                    border: none; border-radius: 6px; padding: 0 14px;
                }
                QPushButton:hover { background: #ff5252; }
            """)
        else:
            self.toggle_btn.setText("▶  开始")
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #00c853, stop:1 #00e676);
                    color: white; border: none; border-radius: 6px;
                    padding: 0 14px;
                }
                QPushButton:hover { background: #00e676; }
            """)


# ── 桥接信号 ────────────────────────────────────────────────
class _WidgetSignals(QObject):
    """跨线程信号：tkinter 主线程 → Qt 线程"""
    set_status = pyqtSignal(str, str)          # text, color
    set_monitoring_ui = pyqtSignal(bool)       # active
    update_count = pyqtSignal(int)             # n
    update_template_count = pyqtSignal(int)    # n
    set_last_action = pyqtSignal(str)          # text
    show_signal = pyqtSignal()
    hide_signal = pyqtSignal()
    destroy_signal = pyqtSignal()
    stop_pulse = pyqtSignal()


# ── 主悬浮窗 ────────────────────────────────────────────────
class _QtFloatingWidget(QWidget):
    COLLAPSE_DELAY = 200
    COLLAPSED_W = 52
    COLLAPSED_H = 52
    EXPANDED_W = 320
    EXPANDED_H = 200

    def __init__(self, signals, cmd_queue):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._signals = signals
        self._cmd_queue = cmd_queue  # 发回 tkinter 的命令队列
        self._monitoring = False
        self._expanded = True
        self._drag_pos = None
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._collapse)

        # 两种视图
        self.ball = CollapsedBall(self)
        self.card = ExpandedCard(self)
        self.ball.hide()
        self.card.show()

        # 连接按钮 → 发消息回 tkinter
        self.card.toggle_btn.clicked.connect(
            lambda: self._cmd_queue.put(('toggle_monitoring',)))
        self.card._fn_buttons['capture'].clicked.connect(
            lambda: self._cmd_queue.put(('start_capture',)))
        self.card._fn_buttons['scan'].clicked.connect(
            lambda: self._cmd_queue.put(('test_scan',)))
        self.card._fn_buttons['history'].clicked.connect(
            lambda: self._cmd_queue.put(('view_history',)))
        self.card._fn_buttons['settings'].clicked.connect(
            lambda: self._cmd_queue.put(('show_settings',)))

        # 连接跨线程信号
        signals.set_status.connect(self._do_set_status)
        signals.set_monitoring_ui.connect(self._do_set_monitoring_ui)
        signals.update_count.connect(self._do_update_count)
        signals.update_template_count.connect(self._do_update_template_count)
        signals.set_last_action.connect(self._do_set_last_action)
        signals.show_signal.connect(self._do_show)
        signals.hide_signal.connect(self._do_hide)
        signals.destroy_signal.connect(self._do_destroy)
        signals.stop_pulse.connect(self._do_stop_pulse)

        # 初始大小
        self.setFixedSize(self.card.size())

        # 初始位置：屏幕右下角
        screen = QApplication.primaryScreen().geometry()
        self._pos_x = screen.width() - self.EXPANDED_W - 20
        self._pos_y = screen.height() - self.EXPANDED_H - 80
        self.move(self._pos_x, self._pos_y)

        # 2.5 秒后自动折叠
        QTimer.singleShot(2500, self._collapse)

    # ── 绘制 ──
    def paintEvent(self, event):
        pass  # 完全透明

    # ── 鼠标事件 ──
    def enterEvent(self, event):
        self._collapse_timer.stop()
        if not self._expanded:
            self._expand()

    def leaveEvent(self, event):
        if self._expanded:
            self._collapse_timer.start(self.COLLAPSE_DELAY)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPos() - self._drag_pos
            self.move(new_pos)
            self._pos_x = new_pos.x()
            self._pos_y = new_pos.y()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── 折叠/展开 ──
    def _expand(self):
        self._expanded = True
        self.ball.hide()
        self.card.show()
        self.card.set_monitoring_ui(self._monitoring)
        self.setFixedSize(self.card.size())

    def _collapse(self):
        self._expanded = False
        self.card.hide()
        self.ball.show()
        self.ball.set_monitoring(self._monitoring)
        self.setFixedSize(self.ball.SIZE, self.ball.SIZE)

    # ── 隐藏请求 ──
    def _on_hide_request(self):
        self.hide()

    # ── 信号处理 ──
    def _do_set_status(self, text, color):
        self.card.set_status(text, color)

    def _do_set_monitoring_ui(self, active):
        self._monitoring = active
        self.card.set_monitoring_ui(active)
        self.ball.set_monitoring(active)

    def _do_update_count(self, n):
        self.card.count_lbl.setText(f"🖱 {n}")

    def _do_update_template_count(self, n):
        self.card.tpl_lbl.setText(f"📌 {n}模板")

    def _do_set_last_action(self, text):
        self.card.info_lbl.setText(text)

    def _do_show(self):
        self.show()
        self.raise_()

    def _do_hide(self):
        self.hide()

    def _do_destroy(self):
        self._collapse_timer.stop()
        self.ball._timer.stop()
        self.hide()

    def _do_stop_pulse(self):
        self._monitoring = False
        self.ball.set_monitoring(False)


# ── Qt 事件循环线程 ─────────────────────────────────────────
_qt_app = None
_qt_app_lock = threading.Lock()


def _ensure_qt_app():
    global _qt_app
    with _qt_app_lock:
        if _qt_app is None:
            _qt_app = QApplication.instance()
            if _qt_app is None:
                _qt_app = QApplication(sys.argv)
        return _qt_app


def _qt_thread_main(cmd_queue, ready_event, widget_holder, signals_holder):
    """在独立线程中运行 Qt 事件循环"""
    app = _ensure_qt_app()
    signals = _WidgetSignals()
    signals_holder.append(signals)
    w = _QtFloatingWidget(signals, cmd_queue)
    widget_holder.append(w)
    w.show()
    ready_event.set()
    app.exec_()


# ── 对外接口：兼容旧版 API ─────────────────────────────────
class FloatingWidget:
    """
    对 app.py 暴露的接口完全兼容旧版 tkinter FloatingWidget。

    内部通过 pyqtSignal 跨线程驱动 Qt 窗口。
    """
    COLLAPSED_W = 52
    COLLAPSED_H = 52
    EXPANDED_W = 320
    EXPANDED_H = 200

    def __init__(self, app):
        self.app = app
        self.c = app.c

        self._signals = None
        self._cmd_queue = queue.Queue()
        self._qt_widget = None

        # 使用 list 作为 holder 让子线程写入引用
        widget_holder = []
        signals_holder = []
        ready = threading.Event()

        self._qt_thread = threading.Thread(
            target=_qt_thread_main,
            args=(self._cmd_queue, ready, widget_holder, signals_holder),
            daemon=True,
        )
        self._qt_thread.start()
        ready.wait(timeout=5)

        if signals_holder:
            self._signals = signals_holder[0]
        if widget_holder:
            self._qt_widget = widget_holder[0]

        # 轮询命令队列，桥接回 tkinter
        self._poll_commands()

    def _poll_commands(self):
        """从 Qt 线程的命令队列读取，分发到 app 方法"""
        try:
            while not self._cmd_queue.empty():
                cmd = self._cmd_queue.get_nowait()
                name = cmd[0]
                if name == 'toggle_monitoring':
                    self.app.toggle_monitoring()
                elif name == 'start_capture':
                    self.app.start_capture()
                elif name == 'test_scan':
                    self.app.test_scan()
                elif name == 'view_history':
                    self.app.view_history()
                elif name == 'show_settings':
                    self.app.show_settings()
        except Exception:
            pass
        # 每 50ms 轮询一次
        try:
            self.app.root.after(50, self._poll_commands)
        except Exception:
            pass

    # ── 公共 API（供 app.py 调用）──
    def set_status(self, text, color=None):
        if not self._signals:
            return
        if color is None:
            color = self.c.get('dim', '#8888aa')
        self._signals.set_status.emit(str(text), str(color))

    def set_monitoring_ui(self, active):
        if not self._signals:
            return
        self._signals.set_monitoring_ui.emit(bool(active))

    def update_count(self, n):
        if not self._signals:
            return
        self._signals.update_count.emit(int(n))

    def update_template_count(self, n):
        if not self._signals:
            return
        self._signals.update_template_count.emit(int(n))

    def set_last_action(self, text):
        if not self._signals:
            return
        self._signals.set_last_action.emit(str(text))

    def show(self):
        if not self._signals:
            return
        self._signals.show_signal.emit()

    def hide(self):
        if not self._signals:
            return
        self._signals.hide_signal.emit()

    def destroy(self):
        if not self._signals:
            return
        self._signals.destroy_signal.emit()

    def _stop_pulse(self):
        if not self._signals:
            return
        self._signals.stop_pulse.emit()

    # ── 兼容属性（供 app.py 中的 tkinter 调用）──
    @property
    def _collapse_timer(self):
        return None  # 不再用 tkinter after id

    @_collapse_timer.setter
    def _collapse_timer(self, value):
        pass  # 忽略

    @property
    def _pos_x(self):
        if self._qt_widget:
            return self._qt_widget._pos_x
        return 0

    @_pos_x.setter
    def _pos_x(self, value):
        if self._qt_widget:
            self._qt_widget._pos_x = value

    @property
    def _pos_y(self):
        if self._qt_widget:
            return self._qt_widget._pos_y
        return 0

    @_pos_y.setter
    def _pos_y(self, value):
        if self._qt_widget:
            self._qt_widget._pos_y = value

    def winfo_viewable(self):
        if self._qt_widget:
            return self._qt_widget.isVisible()
        return False

    def winfo_x(self):
        return self._pos_x

    def winfo_y(self):
        return self._pos_y

    def winfo_id(self):
        return 0

    def geometry(self, geo_str):
        """解析 'WxH+X+Y' 格式并移动 Qt 窗口"""
        pass  # Qt 窗口位置由自身管理

    def after_cancel(self, timer_id):
        pass  # Qt 用自己的 QTimer

    def after(self, ms, func, *args):
        pass  # 不需要

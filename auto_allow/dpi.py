"""
Windows DPI awareness helpers.
"""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger(__name__)

_DPI_AWARENESS_SET = False

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def enable_per_monitor_dpi_awareness():
    """
    Make the current process use physical-pixel coordinates on Windows.
    """
    global _DPI_AWARENESS_SET

    if _DPI_AWARENESS_SET or not hasattr(ctypes, "windll"):
        return False

    user32 = ctypes.windll.user32

    try:
        result = user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2)
        if result:
            _DPI_AWARENESS_SET = True
            return True
    except Exception:
        logger.debug("SetProcessDpiAwarenessContext unavailable", exc_info=True)

    try:
        shcore = ctypes.windll.shcore
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        if shcore.SetProcessDpiAwareness(2) == 0:
            _DPI_AWARENESS_SET = True
            return True
    except Exception:
        logger.debug("SetProcessDpiAwareness unavailable", exc_info=True)

    try:
        if user32.SetProcessDPIAware():
            _DPI_AWARENESS_SET = True
            return True
    except Exception:
        logger.debug("SetProcessDPIAware unavailable", exc_info=True)

    return False

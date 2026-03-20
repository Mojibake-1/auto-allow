"""
模板管理器
"""

import os
import re
import glob
import cv2
import numpy as np
from PIL import Image
from .constants import TEMPLATES_DIR

MAX_TEMPLATES = 20  # 最大模板数量限制


class TemplateManager:
    def __init__(self):
        os.makedirs(TEMPLATES_DIR, exist_ok=True)
        self.templates = []   # [(name, pil, cv_bgr, cv_gray), ...]
        self.load_all()

    def load_all(self):
        self.templates = []
        for p in sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.png"))):
            if len(self.templates) >= MAX_TEMPLATES:
                break
            try:
                name = os.path.splitext(os.path.basename(p))[0]
                with Image.open(p) as img:
                    pil = img.convert("RGB")
                cv_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                cv_gray = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY)
                self.templates.append((name, pil, cv_bgr, cv_gray))
            except Exception:
                pass

    @staticmethod
    def _sanitize_name(name):
        """仅允许安全字符，防止路径遍历"""
        name = os.path.basename(name)
        name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)
        return name or '模板'

    def add(self, pil_img, name=None):
        if len(self.templates) >= MAX_TEMPLATES:
            return None  # 已达上限
        if name is None:
            i = len(self.templates) + 1
            while os.path.exists(os.path.join(TEMPLATES_DIR, f"模板{i}.png")):
                i += 1
            name = f"模板{i}"
        else:
            name = self._sanitize_name(name)
        pil_img.save(os.path.join(TEMPLATES_DIR, f"{name}.png"))
        cv_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        cv_gray = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY)
        self.templates.append((name, pil_img, cv_bgr, cv_gray))
        return name

    def remove(self, idx):
        if 0 <= idx < len(self.templates):
            name = self.templates[idx][0]
            p = os.path.join(TEMPLATES_DIR, f"{name}.png")
            if os.path.exists(p):
                os.remove(p)
            self.templates.pop(idx)

    def clear(self):
        while self.templates:
            self.remove(0)

    def count(self):
        return len(self.templates)

    def cv_list(self):
        return [(t[0], t[2]) for t in self.templates]

    def cv_gray_list(self):
        """返回 (name, cv_bgr, cv_gray) 列表，用于灰度优先匹配"""
        return [(t[0], t[2], t[3]) for t in self.templates]

    def pil_list(self):
        return [(t[0], t[1]) for t in self.templates]

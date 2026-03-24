"""
图标生成
"""

import os
from PIL import Image, ImageDraw
from .constants import ICON_PATH


def generate_icon():
    """生成应用程序图标 (.ico)"""
    if os.path.exists(ICON_PATH):
        with Image.open(ICON_PATH) as img:
            return img.copy()

    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 渐变圆形背景
    for i in range(size // 2, 0, -1):
        t = i / (size // 2)
        r = int(80 + 28 * (1 - t))
        g = int(60 + 39 * (1 - t))
        b = int(220 + 35 * (1 - t))
        draw.ellipse([size // 2 - i, size // 2 - i,
                      size // 2 + i, size // 2 + i],
                     fill=(r, g, b, 255))

    # 闪电符号 ⚡
    bolt = [
        (128, 30), (75, 125), (115, 125),
        (95, 226), (180, 110), (135, 110), (158, 30)
    ]
    draw.polygon(bolt, fill=(255, 255, 255, 240))

    # 保存
    img.save(ICON_PATH, format='ICO',
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    return img

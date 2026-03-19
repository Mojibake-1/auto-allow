"""
颜色主题系统 — 可切换的 UI 主题
"""

# 预设主题
THEMES = {
    'deep_space': {
        'name': 'Deep Space',
        'display': '🌑 Deep Space（默认深空）',
        'bg': '#0f0f1a', 'card': '#1a1a2e', 'input': '#252540',
        'fg': '#e0e0f0', 'dim': '#8888aa',
        'accent': '#6c63ff', 'accent_h': '#7c73ff',
        'success': '#00d68f', 'danger': '#ff6b6b',
        'warning': '#ffd93d', 'border': '#2a2a4a',
    },
    'midnight_blue': {
        'name': 'Midnight Blue',
        'display': '🌊 Midnight Blue（深蓝）',
        'bg': '#0a1628', 'card': '#132238', 'input': '#1c3050',
        'fg': '#d6e4f0', 'dim': '#7a9bb5',
        'accent': '#4a9eff', 'accent_h': '#6ab0ff',
        'success': '#00c9a7', 'danger': '#ff6b8a',
        'warning': '#ffca28', 'border': '#1e3a5f',
    },
    'cyberpunk': {
        'name': 'Cyberpunk',
        'display': '💜 Cyberpunk（赛博朋克）',
        'bg': '#0d0015', 'card': '#1a0030', 'input': '#2a0050',
        'fg': '#f0e0ff', 'dim': '#9966cc',
        'accent': '#ff00ff', 'accent_h': '#ff44ff',
        'success': '#00ff88', 'danger': '#ff2266',
        'warning': '#ffaa00', 'border': '#3a0060',
    },
    'light': {
        'name': 'Light',
        'display': '☀️ Light（明亮）',
        'bg': '#f5f5f8', 'card': '#ffffff', 'input': '#eeeef2',
        'fg': '#2a2a3a', 'dim': '#8888aa',
        'accent': '#6c63ff', 'accent_h': '#7c73ff',
        'success': '#00b876', 'danger': '#e55050',
        'warning': '#e6a800', 'border': '#d8d8e0',
    },
}

DEFAULT_THEME = 'deep_space'


def get_theme(theme_id: str) -> dict:
    """获取指定主题的颜色字典，不包含 name/display 元数据"""
    theme_data = THEMES.get(theme_id, THEMES[DEFAULT_THEME]).copy()
    # 移除非颜色字段
    theme_data.pop('name', None)
    theme_data.pop('display', None)
    return theme_data


def get_theme_list() -> list:
    """返回 [(theme_id, display_name), ...] 列表"""
    return [(tid, t['display']) for tid, t in THEMES.items()]

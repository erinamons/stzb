"""
ui_utils.py - 通用UI绘制工具函数
从 main.py 的 AsyncGameClient 类中提取的独立绘制方法
"""

import sys, os
_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_client_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame


def draw_rounded_rect(surface, color, rect, radius=8, alpha=255):
    """绘制圆角矩形（支持透明度）"""
    if alpha < 255:
        s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color[:3], alpha), (0, 0, rect.width, rect.height), border_radius=radius)
        surface.blit(s, rect.topleft)
    else:
        pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_gradient_rect(surface, rect, color_top, color_bot, radius=8):
    """绘制垂直渐变圆角矩形"""
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    for y in range(rect.height):
        t = y / max(1, rect.height - 1)
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        pygame.draw.line(s, (r, g, b, 255), (0, y), (rect.width, y))
    # 裁切为圆角
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, rect.width, rect.height), border_radius=radius)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(s, rect.topleft)


def draw_button(screen, rect, text, color, button_list, font, **kwargs):
    """绘制按钮（带阴影、渐变、高光、悬停/按下效果）"""
    mouse_pos = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse_pos)
    pressed = hover and pygame.mouse.get_pressed()[0]
    draw_rect = rect.copy()
    radius = kwargs.get("radius", 6)

    # 阴影
    if not pressed:
        shadow_rect = draw_rect.copy()
        shadow_rect.y += 2
        draw_rounded_rect(screen, (0, 0, 0), shadow_rect, radius, alpha=60)

    # 按下偏移
    if pressed:
        draw_rect.y += 1

    # 渐变背景
    base = color
    if hover:
        base = tuple(min(c + 35, 255) for c in color)
    if pressed:
        base = tuple(max(c - 25, 0) for c in base)
    draw_gradient_rect(screen, draw_rect, base, tuple(max(c - 20, 0) for c in base), radius)

    # 高光（顶部1px亮线）
    highlight_rect = pygame.Rect(draw_rect.x + 2, draw_rect.y, draw_rect.width - 4, 1)
    hl_surf = pygame.Surface((highlight_rect.width, 1), pygame.SRCALPHA)
    hl_surf.fill((*[min(c + 60, 255) for c in base], 100))
    screen.blit(hl_surf, highlight_rect.topleft)

    # 边框
    border_c = tuple(min(c + 50, 255) for c in base) if hover else tuple(min(c + 20, 255) for c in base)
    pygame.draw.rect(screen, border_c, draw_rect, 1, border_radius=radius)

    # 文字
    txt = font.render(text, True, (255, 255, 255))
    screen.blit(txt, txt.get_rect(center=draw_rect.center))
    btn_data = {"action": kwargs.get("action"), "rect": rect, "text": text}
    for k, v in kwargs.items():
        if k != "action":
            btn_data[k] = v
    button_list.append(btn_data)


def draw_city_label(screen, cx, cy, hex_s, city_type, city_name, ui_font):
    """在城池格子中心绘制城名标签（颜色块方案）"""
    # 城池类型 → 颜色
    city_colors = {
        "州府": ((255, 215, 0), (180, 150, 30)),       # 金色
        "郡城": ((200, 200, 215), (140, 140, 160)),     # 银色
        "县城": ((180, 140, 90), (130, 95, 55)),        # 铜色
        "关口": ((220, 70, 70), (170, 45, 45)),         # 红色
    }
    if city_type not in city_colors:
        return
    text_color, border_color = city_colors[city_type]
    # 城名标签
    label_y = cy - int(hex_s) - 8
    txt_surf = ui_font.render(city_name, True, text_color)
    txt_rect = txt_surf.get_rect(center=(cx, label_y))
    bg_rect = txt_rect.inflate(8, 4)
    bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
    bg_surf.fill((20, 20, 28, 210))
    screen.blit(bg_surf, bg_rect.topleft)
    pygame.draw.rect(screen, border_color, bg_rect, 1, border_radius=3)
    screen.blit(txt_surf, txt_rect)

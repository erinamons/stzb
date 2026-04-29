# ui/hud.py - HUD 元素：顶部资源栏、消息栏、底部导航栏、圆形按钮、筛选弹窗、定位弹窗
# 从 main.py 的 draw() 方法中提取（行 1337-1556）
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_rounded_rect, draw_gradient_rect


def draw_top_bar(screen, client, ui_font, font):
    """绘制顶部资源栏（毛玻璃风格）"""
    top_bar = pygame.Surface((WINDOW_WIDTH, 65), pygame.SRCALPHA)
    top_bar.fill((15, 15, 20, 210))
    screen.blit(top_bar, (0, 0))
    pygame.draw.line(screen, (60, 55, 40), (0, 64), (WINDOW_WIDTH, 64), 1)

    # 资源配置
    res_items = [
        ("木材", "wood", (120, 180, 80)),
        ("铁矿", "iron", (160, 160, 180)),
        ("石料", "stone", (180, 150, 110)),
        ("粮食", "grain", (200, 200, 100)),
    ]
    rx = 15
    for label, key, color in res_items:
        val = client.resources[key]
        lbl_surf = font.render(label, True, color)
        screen.blit(lbl_surf, (rx, 8))
        val_surf = ui_font.render(f"{val:,}", True, color)
        screen.blit(val_surf, (rx + lbl_surf.get_width() + 4, 6))
        rx += val_surf.get_width() + lbl_surf.get_width() + 30

    # 货币资源（第二行）
    cur_items = [
        ("铜币", "copper", (200, 180, 80)),
        ("玉符", "jade", (100, 200, 255)),
        ("虎符", "tiger_tally", (255, 180, 100)),
    ]
    cx = 15
    for label, key, color in cur_items:
        val = client.currencies[key]
        lbl_surf = font.render(label, True, color)
        screen.blit(lbl_surf, (cx, 34))
        val_surf = ui_font.render(f"{val:,}", True, color)
        screen.blit(val_surf, (cx + lbl_surf.get_width() + 4, 32))
        cx += val_surf.get_width() + lbl_surf.get_width() + 30


def draw_message_bar(screen, client, ui_font):
    """绘制消息栏"""
    msg_bar = pygame.Surface((WINDOW_WIDTH, 36), pygame.SRCALPHA)
    msg_bar.fill((20, 20, 28, 200))
    screen.blit(msg_bar, (0, WINDOW_HEIGHT - 96))
    # 消息类型颜色区分
    msg_text = client.msg
    if "【提示】" in msg_text:
        msg_color = (255, 200, 100)
    elif "失败" in msg_text or "错误" in msg_text:
        msg_color = (255, 100, 100)
    elif "成功" in msg_text or "✓" in msg_text:
        msg_color = (100, 255, 130)
    else:
        msg_color = (210, 210, 220)
    msg_surf = ui_font.render(msg_text, True, msg_color)
    screen.blit(msg_surf, (20, WINDOW_HEIGHT - 92))


def draw_bottom_nav(screen, client, m_pos, m_prs, ui_font, font):
    """绘制底部导航栏（渐变风格）"""
    nav_bg = pygame.Surface((WINDOW_WIDTH, 60), pygame.SRCALPHA)
    nav_bg.fill((15, 15, 22, 230))
    screen.blit(nav_bg, (0, WINDOW_HEIGHT - 60))
    pygame.draw.line(screen, (60, 55, 40), (0, WINDOW_HEIGHT - 60), (WINDOW_WIDTH, WINDOW_HEIGHT - 60), 1)

    for btn in client.nav_buttons:
        hov = btn["rect"].collidepoint(m_pos) and not client.current_panel and not client.report_panel
        pressed = hov and m_prs
        draw_r = btn["rect"].copy()
        if pressed:
            draw_r.y += 1

        # 背景
        if hov:
            draw_gradient_rect(screen, draw_r, (55, 52, 65), (45, 42, 55), radius=0)
        else:
            draw_gradient_rect(screen, draw_r, (35, 33, 45), (25, 23, 35), radius=0)

        # 分隔线
        pygame.draw.line(screen, (50, 48, 55), (draw_r.right, draw_r.y + 8), (draw_r.right, draw_r.bottom - 8), 1)

        # 文字（居中显示）
        text_color = (255, 215, 0) if btn["name"] == "充值" else ((240, 240, 250) if hov else (170, 170, 180))
        txt = font.render(btn["name"], True, text_color)
        screen.blit(txt, txt.get_rect(center=draw_r.center))


def draw_right_buttons(screen, client, m_pos, m_prs, ui_font, font):
    """绘制右侧圆形按钮（定位、展开/收起、地图、筛选）"""
    btn_y, btn_r = 75, 25
    b4_pos = (WINDOW_WIDTH - 40, btn_y)
    b3_pos = (WINDOW_WIDTH - 100, btn_y)
    b2_pos = (WINDOW_WIDTH - 160, btn_y)
    b1_pos = (WINDOW_WIDTH - 220 if client.show_map_btns else WINDOW_WIDTH - 100, btn_y)

    # 目标格子信息
    target_t = client.selected_tile
    if not target_t:
        from hex_utils import pixel_to_hex
        from client_config import HEX_SIZE
        center_wx = (WINDOW_WIDTH / 2 - client.camera_x) / client.zoom
        center_wy = (WINDOW_HEIGHT / 2 - client.camera_y) / client.zoom
        cq, cr = pixel_to_hex(center_wx, center_wy, HEX_SIZE)
        target_t = client.map_dict.get((cq, cr))

    # 坐标信息浮窗
    if target_t:
        name_str = target_t.get("city_name") or target_t.get("region") or "未知"
        coord_str = f"({target_t['x']},{target_t['y']})"
        info_w, info_h = 120, 50
        info_rect = pygame.Rect(WINDOW_WIDTH - info_w - 5, btn_y + 32, info_w, info_h)
        draw_rounded_rect(screen, (30, 30, 42), info_rect, radius=6, alpha=210)
        pygame.draw.rect(screen, (80, 75, 55), info_rect, 1, border_radius=6)
        txt_reg = font.render(name_str[:6], True, (255, 255, 255))
        txt_cor = font.render(coord_str, True, (170, 170, 180))
        screen.blit(txt_reg, txt_reg.get_rect(center=(info_rect.centerx, info_rect.y + 16)))
        screen.blit(txt_cor, txt_cor.get_rect(center=(info_rect.centerx, info_rect.y + 36)))

    # 圆形按钮绘制函数
    def draw_circle_btn(pos, text, color, active=False):
        hov = math.hypot(m_pos[0] - pos[0], m_pos[1] - pos[1]) < btn_r
        # 阴影
        shadow_surf = pygame.Surface((btn_r * 2 + 6, btn_r * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(shadow_surf, (0, 0, 0, 60), (btn_r + 3, btn_r + 5), btn_r)
        screen.blit(shadow_surf, (pos[0] - btn_r - 3, pos[1] - btn_r - 3))
        # 背景渐变模拟
        if active:
            c1, c2 = (140, 95, 50), (100, 65, 35)
        elif hov:
            if m_prs:
                c1, c2 = (90, 45, 45), (70, 35, 35)
            else:
                c1, c2 = (110, 65, 65), (80, 50, 50)
        else:
            c1, c2 = (55, 40, 42), (40, 30, 32)
        pygame.draw.circle(screen, c1, pos, btn_r)
        pygame.draw.circle(screen, c2, (pos[0], pos[1] + 2), btn_r - 3)
        pygame.draw.circle(screen, c1, pos, btn_r - 3)
        # 边框
        border_c = (200, 180, 100) if active else ((180, 170, 160) if hov else color)
        pygame.draw.circle(screen, border_c, pos, btn_r, 2)
        # 文字
        ts = ui_font.render(text, True, (255, 255, 255) if hov else (200, 200, 210))
        screen.blit(ts, ts.get_rect(center=pos))

    draw_circle_btn(b4_pos, "定位", (255, 255, 255))
    draw_circle_btn(b1_pos, "收起" if client.show_map_btns else "展开", (255, 215, 0))
    if client.show_map_btns:
        draw_circle_btn(b2_pos, "筛选", (255, 255, 255), client.map_filter_open or client.filter_active)
        draw_circle_btn(b3_pos, "地图", (255, 255, 255), client.in_macro_map)


def draw_map_filter(screen, client, m_pos, ui_font, font):
    """绘制地图筛选弹窗"""
    if not client.map_filter_open:
        return

    fp_rect = pygame.Rect(WINDOW_WIDTH - 350, 120, 330, 480)
    # 阴影
    shadow = pygame.Surface((fp_rect.width + 8, fp_rect.height + 8), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 80))
    screen.blit(shadow, (fp_rect.x + 4, fp_rect.y + 4))
    # 背景
    draw_rounded_rect(screen, (28, 28, 35), fp_rect, radius=10, alpha=245)
    pygame.draw.rect(screen, (160, 145, 80), fp_rect, 2, border_radius=10)

    # 标题
    screen.blit(ui_font.render("地图信息筛选", True, (255, 215, 0)), (WINDOW_WIDTH - 320, 135))
    pygame.draw.line(screen, (60, 55, 45), (WINDOW_WIDTH - 340, 165), (WINDOW_WIDTH - 20, 165), 1)

    # 开关行
    def draw_toggle(x, y, label, active):
        screen.blit(font.render(label, True, (190, 190, 200)), (x, y + 3))
        toggle_rect = pygame.Rect(WINDOW_WIDTH - 90, y - 2, 50, 25)
        bg_c = (60, 140, 80) if active else (70, 70, 80)
        draw_rounded_rect(screen, bg_c, toggle_rect, radius=12)
        # 小圆点
        dot_x = toggle_rect.x + (toggle_rect.width - 16) if active else toggle_rect.x + 4
        pygame.draw.circle(screen, (255, 255, 255), (dot_x + 8, toggle_rect.centery), 8)

    draw_toggle(WINDOW_WIDTH - 330, 170, "始终开启地图筛选", client.filter_active)
    draw_toggle(WINDOW_WIDTH - 330, 200, "地图始终显示等级", client.show_levels)

    # 资源筛选
    screen.blit(ui_font.render("资源", True, (255, 215, 0)), (WINDOW_WIDTH - 330, 235))
    keys = ["WOODS", "IRON", "STONE", "PLAINS"]
    names = ["木", "铁", "石", "粮"]
    res_colors = [(120, 180, 80), (160, 160, 180), (180, 150, 110), (200, 200, 100)]
    for i in range(4):
        bx, by = WINDOW_WIDTH - 330 + i * 75, 260
        active = client.f_res[keys[i]]
        box_rect = pygame.Rect(bx, by, 60, 60)
        draw_rounded_rect(screen, res_colors[i] if active else (40, 40, 50), box_rect, radius=8, alpha=180 if active else 120)
        pygame.draw.rect(screen, res_colors[i] if active else (70, 70, 80), box_rect, 2, border_radius=8)
        icon_surf = ui_font.render(names[i], True, (255, 255, 255) if active else (120, 120, 130))
        screen.blit(icon_surf, icon_surf.get_rect(center=box_rect.center))

    # 等级筛选
    screen.blit(ui_font.render("土地等级", True, (255, 215, 0)), (WINDOW_WIDTH - 330, 335))
    for i in range(9):
        bx, by = WINDOW_WIDTH - 330 + (i % 3) * 100, 360 + (i // 3) * 40
        active = client.f_lvs[i + 1]
        box_rect = pygame.Rect(bx, by, 80, 30)
        bg_c = (55, 58, 68) if active else (35, 37, 45)
        draw_rounded_rect(screen, bg_c, box_rect, radius=5)
        pygame.draw.rect(screen, (255, 215, 0) if active else (65, 65, 75), box_rect, 1, border_radius=5)
        screen.blit(ui_font.render(f"Lv.{i + 1}", True, (240, 240, 250) if active else (120, 120, 130)),
                         (bx + 20, by + 5))


def draw_location_bookmark(screen, client, m_pos, ui_font, font):
    """绘制定位书签弹窗"""
    if not client.location_open:
        return

    lp_rect = pygame.Rect(WINDOW_WIDTH - 300, 120, 280, 300)
    # 阴影
    shadow = pygame.Surface((lp_rect.width + 8, lp_rect.height + 8), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 80))
    screen.blit(shadow, (lp_rect.x + 4, lp_rect.y + 4))
    # 背景
    draw_rounded_rect(screen, (28, 28, 35), lp_rect, radius=10, alpha=245)
    pygame.draw.rect(screen, (160, 145, 80), lp_rect, 2, border_radius=10)

    screen.blit(ui_font.render("定位书签", True, (255, 215, 0)), (WINDOW_WIDTH - 270, 135))
    pygame.draw.line(screen, (60, 55, 45), (WINDOW_WIDTH - 290, 165), (WINDOW_WIDTH - 20, 165), 1)

    p_rect = pygame.Rect(WINDOW_WIDTH - 280, 200, 240, 60)
    p_hov = p_rect.collidepoint(m_pos)
    p_bg = (50, 55, 65) if p_hov else (38, 40, 50)
    draw_rounded_rect(screen, p_bg, p_rect, radius=8)
    pygame.draw.rect(screen, (120, 180, 120) if p_hov else (80, 120, 80), p_rect, 1, border_radius=8)
    # 左侧竖条
    pygame.draw.rect(screen, (120, 180, 120), (p_rect.x, p_rect.y + 8, 4, p_rect.height - 16), border_radius=2)

    screen.blit(ui_font.render("我的主城", True, (200, 255, 200)),
                     (p_rect.x + 16, p_rect.y + 8))
    screen.blit(
        font.render(f"起兵之地 · 坐标: ({client.spawn_pos[0]}, {client.spawn_pos[1]})", True, (130, 170, 130)),
        (p_rect.x + 16, p_rect.y + 34))

# ui/recharge_panel.py - 充值面板模块
# 从 main.py 提取：充值面板绘制 + refresh_recharge_panel + 虎符兑换
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_button, draw_rounded_rect, draw_gradient_rect


def refresh_recharge_panel(client):
    """刷新充值面板的按钮点击区域（在 open_panel 时调用）"""
    client.panel_buttons = []
    px, py, pw, ph = 80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200
    # 关闭按钮
    client.panel_buttons.append({"action": "close", "rect": pygame.Rect(px + pw - 45, py + 10, 35, 35)})
    # Tab 按钮
    tab_y = py + 60
    client.panel_buttons.append({"action": "tab_jade", "rect": pygame.Rect(px + 40, tab_y, 80, 38)})
    client.panel_buttons.append({"action": "tab_tiger", "rect": pygame.Rect(px + 140, tab_y, 80, 38)})

    if client.recharge_tab == "jade":
        for i, t in enumerate([6, 30, 98, 198, 328, 648]):
            bx, by = px + 40 + (i % 3) * 235, py + 110 + (i // 3) * 220
            buy_rect = pygame.Rect(bx + 210 // 2 - 45, by + 190 - 45, 90, 32)
            client.panel_buttons.append(
                {"action": "recharge", "amount": t * 10, "price": t, "rect": buy_rect})
    elif client.recharge_tab == "tiger":
        cx = px + pw // 2
        ty = py + 140
        client.panel_buttons.append(
            {"action": "add_100", "rect": pygame.Rect(cx - 240, ty + 160, 130, 50), "text": "+100"})
        client.panel_buttons.append(
            {"action": "add_1000", "rect": pygame.Rect(cx - 80, ty + 160, 130, 50), "text": "+1000"})
        client.panel_buttons.append(
            {"action": "add_max", "rect": pygame.Rect(cx + 80, ty + 160, 130, 50), "text": "最大"})
        client.panel_buttons.append(
            {"action": "clear", "rect": pygame.Rect(cx - 240, ty + 230, 130, 50), "text": "清零"})
        client.panel_buttons.append(
            {"action": "exchange", "rect": pygame.Rect(cx - 80, ty + 230, 290, 50), "text": "确 认 兑 换"})


def draw_recharge_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制充值面板（统一样式）"""
    px, py, pw, ph = 80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200

    # 背景（不透明）
    pygame.draw.rect(screen, (22, 22, 32), (px, py, pw, ph), border_radius=10)
    pygame.draw.rect(screen, (70, 60, 50), pygame.Rect(px, py, pw, ph), 2, border_radius=10)

    # 标题栏
    title_h = 45
    title_rect = pygame.Rect(px, py, pw, title_h)
    draw_gradient_rect(screen, title_rect, (40, 35, 28), (28, 25, 22), radius=10)
    pygame.draw.rect(screen, (255, 215, 0), (px, py, 5, title_h), border_radius=3)
    screen.blit(title_font.render("充值中心", True, (255, 215, 0)), (px + 18, py + 10))

    # 关闭按钮
    close_r = pygame.Rect(px + pw - 45, py + 10, 35, 35)
    c_hov = close_r.collidepoint(m_pos)
    pygame.draw.rect(screen, (200, 70, 70) if c_hov else (150, 50, 50), close_r, border_radius=6)
    pygame.draw.rect(screen, (220, 100, 100) if c_hov else (180, 80, 80), close_r, 2, border_radius=6)
    screen.blit(font.render("X", True, (255, 255, 255)),
                     (close_r.centerx - 4, close_r.centery - 8))

    # Tab 按钮
    tab_y = py + 60
    jade_tab = pygame.Rect(px + 40, tab_y, 80, 38)
    tiger_tab = pygame.Rect(px + 140, tab_y, 80, 38)
    for tab_rect, text, active in [(jade_tab, "玉符", client.recharge_tab == "jade"),
                                   (tiger_tab, "虎符", client.recharge_tab == "tiger")]:
        bg = (50, 48, 60) if active else (35, 35, 45)
        pygame.draw.rect(screen, bg, tab_rect, border_radius=6)
        pygame.draw.rect(screen, (200, 180, 100) if active else (80, 80, 90), tab_rect, 2, border_radius=6)
        screen.blit(font.render(text, True, (255, 215, 0) if active else (160, 160, 170)),
                         (tab_rect.x + 12, tab_rect.y + 8))

    content_start = tab_y + 42
    pygame.draw.line(screen, (60, 55, 45), (px + 15, content_start), (px + pw - 15, content_start), 1)

    if client.recharge_tab == "jade":
        tiers = [6, 30, 98, 198, 328, 648]
        for i, t in enumerate(tiers):
            bx = px + 40 + (i % 3) * 235
            by = py + 110 + (i // 3) * 220
            rect = pygame.Rect(bx, by, 210, 190)
            hov = rect.collidepoint(m_pos)
            bg = (50, 50, 65) if hov else (35, 35, 50)
            pygame.draw.rect(screen, bg, rect, border_radius=8)
            pygame.draw.rect(screen, (100, 90, 70) if hov else (70, 70, 80), rect, 2, border_radius=8)
            screen.blit(title_font.render(f"{t * 10} 玉符", True, (150, 255, 150)),
                         (rect.centerx - title_font.size(f"{t * 10} 玉符")[0] // 2, rect.y + 40))
            screen.blit(title_font.render(f"¥ {t}", True, (255, 255, 255)),
                         (rect.centerx - title_font.size(f"¥ {t}")[0] // 2, rect.y + 80))
            buy_rect = pygame.Rect(bx + 210 // 2 - 45, by + 190 - 45, 90, 32)
            buy_hov = buy_rect.collidepoint(m_pos)
            buy_bg = (150, 110, 50) if buy_hov else (120, 90, 40)
            pygame.draw.rect(screen, buy_bg, buy_rect, border_radius=6)
            pygame.draw.rect(screen, (180, 140, 70), buy_rect, 2, border_radius=6)
            buy_txt = font.render("购买", True, (255, 255, 255))
            screen.blit(buy_txt, buy_txt.get_rect(center=buy_rect.center))

    elif client.recharge_tab == "tiger":
        cx_panel = px + pw // 2
        ty = py + 140

        # 玉符区
        jade_box = pygame.Rect(cx_panel - 180, ty, 140, 100)
        pygame.draw.rect(screen, (35, 35, 50), jade_box, border_radius=8)
        pygame.draw.rect(screen, (70, 70, 80), jade_box, 2, border_radius=8)
        screen.blit(title_font.render("玉符", True, (150, 255, 150)), (cx_panel - 130, ty + 10))
        screen.blit(font.render(f"拥有: {client.currencies['jade']}", True, (170, 170, 180)), (cx_panel - 160, ty + 60))
        screen.blit(font.render("-->", True, (255, 215, 0)), (cx_panel - 15, ty + 40))

        # 虎符区
        tiger_box = pygame.Rect(cx_panel + 40, ty, 140, 100)
        pygame.draw.rect(screen, (35, 35, 50), tiger_box, border_radius=8)
        pygame.draw.rect(screen, (255, 215, 0), tiger_box, 2, border_radius=8)
        screen.blit(title_font.render("虎符", True, (255, 215, 0)), (cx_panel + 90, ty + 10))
        screen.blit(font.render("可用于招募", True, (150, 150, 160)), (cx_panel + 65, ty + 60))

        screen.blit(font.render(f"兑换数量: {client.exchange_amount}", True, (255, 255, 255)), (cx_panel - 80, ty + 120))

        # 按钮（点击区在 refresh_recharge_panel 中注册，这里只绘制）
        for btn in client.panel_buttons:
            if btn.get("action", "").startswith("add_") or btn.get("action") in ["clear", "exchange"]:
                rect = btn["rect"]
                hov = rect.collidepoint(m_pos)
                if btn["action"] == "exchange":
                    bg = (140, 95, 45) if hov else (110, 75, 35)
                else:
                    bg = (60, 60, 75) if hov else (40, 40, 55)
                pygame.draw.rect(screen, bg, rect, border_radius=6)
                pygame.draw.rect(screen, (120, 115, 80) if hov else (80, 80, 90), rect, 2, border_radius=6)
                txt = ui_font.render(btn.get("text", ""), True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=rect.center))

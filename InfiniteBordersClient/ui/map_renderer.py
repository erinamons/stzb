# ui/map_renderer.py - 地图渲染模块
# 从 main.py 提取：地图六边形渲染、宏观地图、选中高亮、行军路线
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, HEX_SIZE, COLORS, MAP_COLS, MAP_ROWS
from hex_utils import hex_to_pixel, pixel_to_hex, get_map_pixel_size, draw_hex
from ui_utils import draw_rounded_rect, draw_city_label


def draw_map(screen, client, font, ui_font):
    """绘制主地图视图（六边形网格 + 城池标签 + 选中高亮 + 行军路线）"""
    screen.fill((18, 20, 28))

    m_pos = pygame.mouse.get_pos()
    hex_s = HEX_SIZE * client.zoom
    macro_mode = hex_s < 12
    margin = hex_s * 3

    cities_to_draw = []
    for t in client.game_map:
        q, r = t["x"], t["y"]
        wx, wy = hex_to_pixel(q, r, HEX_SIZE)
        sx = wx * client.zoom + client.camera_x
        sy = wy * client.zoom + client.camera_y

        # 视口外跳过
        if sx < -margin or sx > WINDOW_WIDTH + margin or sy < -margin or sy > WINDOW_HEIGHT + margin:
            continue

        # 确定颜色
        match_filter = True
        if client.filter_active:
            match_filter = (client.f_res.get(t["terrain"], False) and client.f_lvs.get(t["level"], False))
        city_type = t.get("city_type")
        if city_type:
            city_fill_colors = {
                "州府": (180, 155, 50),
                "郡城": (130, 135, 145),
                "县城": (120, 90, 55),
                "关口": (150, 55, 55),
            }
            bg_color = city_fill_colors.get(city_type, COLORS[t["terrain"]])
        else:
            bg_color = (40, 40, 40) if t["terrain"] == "MOUNTAIN" else (
                COLORS["PLAYER"] if t.get("owner") == 1 else COLORS[t["terrain"]])
        if client.filter_active and not match_filter:
            bg_color = (int(bg_color[0] * 0.3), int(bg_color[1] * 0.3), int(bg_color[2] * 0.3))

        # 绘制六边形
        border_c = COLORS["GRID"] if not macro_mode else None
        city_border = {
            "州府": (255, 215, 0),
            "郡城": (200, 200, 215),
            "县城": (160, 120, 75),
            "关口": (220, 70, 70),
        }
        if city_type and city_type in city_border:
            border_c = city_border[city_type]
        draw_hex(screen, int(sx), int(sy), hex_s, bg_color,
                 border_color=border_c, border_width=2 if city_type else 1)

        if not macro_mode:
            if city_type:
                cities_to_draw.append((t, int(sx), int(sy)))
            elif client.show_levels and t["level"] > 0 and (not client.filter_active or match_filter):
                txt = font.render(f"Lv{t['level']}", True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=(int(sx), int(sy))))

    # 城池标签
    if not macro_mode:
        for t, sx, sy in cities_to_draw:
            draw_city_label(screen, sx, sy, hex_s, t["city_type"], t["city_name"], ui_font)

    # 选中格子高亮
    if client.selected_tile:
        q, r = client.selected_tile["x"], client.selected_tile["y"]
        wx, wy = hex_to_pixel(q, r, HEX_SIZE)
        sx = int(wx * client.zoom + client.camera_x)
        sy = int(wy * client.zoom + client.camera_y)
        draw_hex(screen, sx, sy, hex_s, None,
                 border_color=(255, 215, 0), border_width=max(2, int(hex_s * 0.08)))

    # 行军路线
    for m in client.marches:
        sx_w, sy_w = hex_to_pixel(m["start_x"], m["start_y"], HEX_SIZE)
        ex_w, ey_w = hex_to_pixel(m["target_x"], m["target_y"], HEX_SIZE)
        sx = int(sx_w * client.zoom + client.camera_x)
        sy = int(sy_w * client.zoom + client.camera_y)
        ex = int(ex_w * client.zoom + client.camera_x)
        ey = int(ey_w * client.zoom + client.camera_y)
        lw = max(1, int(hex_s * 0.06))
        pygame.draw.line(screen, (0, 255, 127), (sx, sy), (ex, ey), lw)
        prog = 1.0 - (max(0, m["time_left"]) / m["max_time"])
        pygame.draw.circle(screen, (255, 50, 50),
                           (int(sx + (ex - sx) * prog), int(sy + (ey - sy) * prog)),
                           max(3, int(hex_s * 0.18)))


def draw_macro_map(screen, client, title_font, ui_font, font):
    """绘制宏观缩略地图（天下大势）——自动缩放适配窗口"""
    screen.fill((22, 24, 30))

    # 可用区域：标题栏(50px) 下方 ~ 底部导航栏(60px) 上方
    TOP_MARGIN = 50
    BOT_MARGIN = 60
    avail_w = WINDOW_WIDTH - 20   # 左右各留10px
    avail_h = WINDOW_HEIGHT - TOP_MARGIN - BOT_MARGIN - 10

    # 先用 m_hex=5 算出原始尺寸，然后按比例缩放到可用区域内
    m_hex_base = 5
    base_pw, base_ph = get_map_pixel_size(m_hex_base, MAP_COLS, MAP_ROWS)
    scale_w = avail_w / base_pw
    scale_h = avail_h / base_ph
    scale = min(scale_w, scale_h, 1.0)  # 不放大，只缩小
    m_hex = m_hex_base * scale

    map_pw, map_ph = get_map_pixel_size(m_hex, MAP_COLS, MAP_ROWS)
    ox = (WINDOW_WIDTH - map_pw) / 2
    oy = TOP_MARGIN + (avail_h - map_ph) / 2

    # 绘制地图六边形（地图已缩放至可用区域内，无需 clip 或遮罩）
    for t in client.game_map:
        q, r = t["x"], t["y"]
        px, py = hex_to_pixel(q, r, m_hex)
        sx, sy = int(px + ox), int(py + oy)
        if t["terrain"] == "MOUNTAIN":
            c = (28, 28, 32)
        elif t.get("owner") == 1:
            c = COLORS["PLAYER"]
        else:
            c = (80, 90, 75)
        draw_hex(screen, sx, sy, m_hex, c, border_color=(35, 35, 40), border_width=1)

    # 绘制所有城池标记
    all_cities = [t for t in client.game_map if t.get("city_type")]
    for city in all_cities:
        q, r = city["x"], city["y"]
        px, py = hex_to_pixel(q, r, m_hex)
        cx, cy = int(px + ox), int(py + oy)
        ct = city.get("city_type", "")

        if ct == "州府":
            pygame.draw.circle(screen, (200, 180, 80), (cx, cy), 8, 2)
            pygame.draw.circle(screen, (255, 215, 0), (cx, cy), 4)
            r_txt = title_font.render(city.get("region", ""), True, (255, 255, 255))
            r_rect = r_txt.get_rect(center=(cx, cy - 18))
            bg_surf = pygame.Surface((r_rect.width + 12, r_rect.height + 6), pygame.SRCALPHA)
            bg_surf.fill((35, 35, 48, 220))
            screen.blit(bg_surf, (r_rect.x - 6, r_rect.y - 3))
            pygame.draw.rect(screen, (160, 145, 80), r_rect.inflate(12, 6), 1, border_radius=4)
            screen.blit(r_txt, r_rect)
            c_txt = ui_font.render(city.get("city_name", ""), True, (255, 235, 150))
            c_rect = c_txt.get_rect(center=(cx, cy + 16))
            screen.blit(c_txt, c_rect)
        elif ct == "郡城":
            pygame.draw.circle(screen, (200, 200, 210), (cx, cy), 4)
            pygame.draw.circle(screen, (150, 150, 165), (cx, cy), 4, 1)
            c_txt = font.render(city.get("city_name", ""), True, (210, 210, 220))
            c_rect = c_txt.get_rect(center=(cx, cy + 12))
            screen.blit(c_txt, c_rect)
        elif ct == "县城":
            pygame.draw.circle(screen, (180, 130, 80), (cx, cy), 3)
            if city.get("level", 5) >= 5:
                c_txt = font.render(city.get("city_name", ""), True, (180, 150, 110))
                c_rect = c_txt.get_rect(center=(cx, cy + 10))
                screen.blit(c_txt, c_rect)
        elif ct == "关口":
            pts = [(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)]
            pygame.draw.polygon(screen, (220, 60, 60), pts)
            c_txt = font.render(city.get("city_name", ""), True, (220, 100, 100))
            c_rect = c_txt.get_rect(center=(cx, cy + 10))
            screen.blit(c_txt, c_rect)

    # 标题栏（不透明，绘制在最上层）
    top_bg = pygame.Surface((WINDOW_WIDTH, TOP_MARGIN), pygame.SRCALPHA)
    top_bg.fill((22, 24, 30, 255))
    screen.blit(top_bg, (0, 0))
    screen.blit(title_font.render("天下大势 · 时代战场", True, (255, 215, 0)), (30, 12))
    pygame.draw.line(screen, (60, 55, 40), (0, TOP_MARGIN - 1), (WINDOW_WIDTH, TOP_MARGIN - 1), 1)

    # 选中目标指示
    if client.selected_tile:
        q, r = client.selected_tile["x"], client.selected_tile["y"]
        px, py = hex_to_pixel(q, r, m_hex)
        sx, sy = int(px + ox), int(py + oy)
        pygame.draw.circle(screen, (255, 50, 50, 120), (sx, sy), 10)
        pygame.draw.circle(screen, (255, 215, 0), (sx, sy), 8, 2)
        pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 3)
        info = f"{client.selected_tile.get('region', '未知')} ({client.selected_tile['x']},{client.selected_tile['y']})"
        info_surf = ui_font.render(info, True, (255, 215, 0))
        screen.blit(info_surf, (WINDOW_WIDTH - info_surf.get_width() - 80, 14))

    # 关闭按钮
    cls_rect = pygame.Rect(WINDOW_WIDTH - 60, 8, 40, 34)
    m_pos = pygame.mouse.get_pos()
    hov = cls_rect.collidepoint(m_pos)
    c_col = (200, 60, 60) if hov else (120, 50, 50)
    draw_rounded_rect(screen, c_col, cls_rect, radius=8)
    ccx, ccy = cls_rect.centerx, cls_rect.centery
    pygame.draw.line(screen, (255, 255, 255), (ccx - 7, ccy - 7), (ccx + 7, ccy + 7), 3)
    pygame.draw.line(screen, (255, 255, 255), (ccx + 7, ccy - 7), (ccx - 7, ccy + 7), 3)
    client.macro_close_rect = cls_rect

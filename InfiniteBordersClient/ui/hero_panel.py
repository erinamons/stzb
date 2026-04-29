# ui/hero_panel.py - 武将面板模块
# 从 main.py 提取：武将列表、武将详情（属性+配点）、招募面板
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_rounded_rect, draw_button


def get_star_color(stars):
    """根据星级返回颜色"""
    if stars >= 5: return (255, 215, 0)
    if stars == 4: return (218, 112, 214)
    if stars == 3: return (100, 180, 255)
    return (180, 180, 180)


def draw_recruit_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制招募卡包面板"""
    panel_rect = pygame.Rect(100, 100, WINDOW_WIDTH - 200, WINDOW_HEIGHT - 300)
    pygame.draw.rect(screen, (20, 22, 28), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 160, 80), panel_rect, 2, border_radius=8)

    # 标题栏
    title_bg = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 45)
    pygame.draw.rect(screen, (35, 38, 48), title_bg, border_radius=8)
    screen.blit(title_font.render("📜 招募卡包", True, (255, 215, 0)), (panel_rect.x + 20, panel_rect.y + 8))
    temp_buttons = []
    close_rect = pygame.Rect(panel_rect.right - 40, panel_rect.y + 8, 30, 30)
    draw_button(screen, close_rect, "X", (150, 50, 50), temp_buttons, font, action="close")

    list_rect = pygame.Rect(panel_rect.x + 10, panel_rect.y + 55, panel_rect.width - 20, panel_rect.height - 65)
    screen.set_clip(list_rect)

    card_width = 250
    card_height = 150
    cols = min((list_rect.width - 20) // (card_width + 20), 3)
    card_spacing = 20
    start_x = list_rect.x + 10
    start_y = list_rect.y + 5

    rows = (len(client.card_packs) + cols - 1) // cols
    max_scroll = max(0, rows * (card_height + card_spacing) - list_rect.height + 10)
    client.recruit_scroll_y = max(-max_scroll, min(0, client.recruit_scroll_y))

    for i, pack in enumerate(client.card_packs):
        row = i // cols
        col = i % cols
        x = start_x + col * (card_width + card_spacing)
        y = start_y + row * (card_height + card_spacing) + client.recruit_scroll_y

        if y + card_height < list_rect.top or y > list_rect.bottom:
            continue

        card_rect = pygame.Rect(x, y, card_width, card_height)
        hov = card_rect.collidepoint(m_pos)
        bg_color = (45, 48, 58) if hov else (30, 32, 42)
        pygame.draw.rect(screen, bg_color, card_rect, border_radius=6)
        pygame.draw.rect(screen, (120, 100, 60), card_rect, 1, border_radius=6)

        name_surf = title_font.render(pack["name"], True, (255, 215, 0))
        screen.blit(name_surf, name_surf.get_rect(center=(card_rect.centerx, card_rect.y + 30)))

        is_tiger = pack['cost_type'] == 'tiger'
        cost_icon = "🐯" if is_tiger else "💰"
        cost_name = "虎符" if is_tiger else "铜币"
        cost_text = f"{cost_icon} 消耗: {pack['cost_amount']} {cost_name}"
        cost_color = (255, 200, 100) if is_tiger else (200, 200, 200)
        cost_surf = font.render(cost_text, True, cost_color)
        screen.blit(cost_surf, cost_surf.get_rect(center=(card_rect.centerx, card_rect.y + 90)))

        btn_rect = pygame.Rect(card_rect.x + card_rect.width // 2 - 40, card_rect.y + card_rect.height - 40, 80, 30)
        btn_color = (60, 90, 60) if hov else (50, 80, 50)
        draw_button(screen, btn_rect, "招募", btn_color, temp_buttons, font,
                   action="recruit", pack_id=pack["id"])

    client.panel_buttons = temp_buttons
    screen.set_clip(None)


def draw_hero_list(screen, client, m_pos, font, ui_font, title_font):
    """绘制武将列表面板"""
    panel_rect = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
    pygame.draw.rect(screen, (20, 22, 28), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 160, 80), panel_rect, 2, border_radius=8)

    # 标题栏
    title_bg = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 45)
    pygame.draw.rect(screen, (35, 38, 48), title_bg, border_radius=8)
    screen.blit(title_font.render(f"⚔ 武将名册 ({len(client.heroes_list)})", True, (255, 215, 0)),
                     (panel_rect.x + 20, panel_rect.y + 8))

    temp_buttons = []
    close_rect = pygame.Rect(panel_rect.right - 40, panel_rect.y + 8, 30, 30)
    draw_button(screen, close_rect, "X", (150, 50, 50), temp_buttons, font, action="close")

    # 筛选按钮栏
    filter_y = panel_rect.y + 52
    filter_btns = [
        {"action": "cycle_fac", "text": f"阵营: {client.filter_facs[client.idx_fac]}"},
        {"action": "cycle_trp", "text": f"兵种: {client.filter_trps[client.idx_trp]}"},
        {"action": "cycle_srt", "text": f"排序: {client.sort_opts[client.idx_srt]}"},
    ]
    for fi, fb in enumerate(filter_btns):
        fr = pygame.Rect(panel_rect.x + 15 + fi * 150, filter_y, 140, 32)
        hov = fr.collidepoint(m_pos)
        pygame.draw.rect(screen, (55, 58, 68) if hov else (40, 42, 52), fr, border_radius=4)
        pygame.draw.rect(screen, (100, 90, 60), fr, 1, border_radius=4)
        screen.blit(font.render(fb["text"], True, (200, 200, 210)), (fr.x + 10, fr.y + 8))
        temp_buttons.append({"action": fb["action"], "rect": fr})

    # 计算已上阵武将ID集合
    assigned_hero_ids = set()
    for t in client.troops_list:
        for slot in [t.get("slot1"), t.get("slot2"), t.get("slot3")]:
            if slot:
                assigned_hero_ids.add(slot)

    # 武将网格
    list_y = filter_y + 40
    list_rect = pygame.Rect(panel_rect.x + 5, list_y, panel_rect.width - 10, panel_rect.bottom - list_y - 10)
    screen.set_clip(list_rect)

    h_view = client.heroes_list
    if client.filter_facs[client.idx_fac] != "全部":
        h_view = [h for h in h_view if h["faction"] == client.filter_facs[client.idx_fac]]
    if client.filter_trps[client.idx_trp] != "全部":
        h_view = [h for h in h_view if h["troop_type"] == client.filter_trps[client.idx_trp]]
    srt = client.sort_opts[client.idx_srt]
    if srt == "稀有度":
        h_view.sort(key=lambda x: (-x["stars"], -x["level"], x["id"]))
    elif srt == "等级":
        h_view.sort(key=lambda x: (-x["level"], -x["stars"], x["id"]))
    elif srt == "统率":
        h_view.sort(key=lambda x: (-x["cost"], -x["stars"], x["id"]))
    elif srt == "阵营":
        h_view.sort(key=lambda x: (x["faction"], -x["stars"], x["id"]))
    elif srt == "兵种":
        h_view.sort(key=lambda x: (x["troop_type"], -x["stars"], x["id"]))
    client.displayed_heroes = h_view

    cols = 5
    card_w, card_h, card_gap = 140, 165, 8
    max_scroll = max(0, math.ceil(len(h_view) / cols) * (card_h + card_gap) - list_rect.height + 10)
    client.hero_scroll_y = max(-max_scroll, min(0, client.hero_scroll_y))

    for i, h in enumerate(h_view):
        col_i = i % cols
        row_i = i // cols
        bx = list_rect.x + 10 + col_i * (card_w + card_gap)
        by = list_rect.y + 5 + row_i * (card_h + card_gap) + client.hero_scroll_y
        if by + card_h < list_rect.top or by > list_rect.bottom:
            continue

        card_rect = pygame.Rect(bx, by, card_w, card_h)
        hov = card_rect.collidepoint(m_pos)
        star_c = get_star_color(h.get("stars", 3))
        is_assigned = h["id"] in assigned_hero_ids

        bg = (45, 48, 58) if hov else (28, 30, 38)
        pygame.draw.rect(screen, bg, card_rect, border_radius=6)
        border_c = (70, 70, 80) if is_assigned else star_c
        pygame.draw.rect(screen, border_c, card_rect, 2, border_radius=6)

        screen.blit(font.render(f"C{h.get('cost', 0)}", True, (255, 255, 255)), (bx + 6, by + 5))
        screen.blit(font.render(f"{h['faction']}·{h['troop_type']}", True, (130, 140, 170)), (bx + 40, by + 5))

        name_c = (160, 160, 160) if is_assigned else star_c
        n_surf = ui_font.render(h["name"], True, name_c)
        screen.blit(n_surf, n_surf.get_rect(center=(bx + card_w // 2, by + 38)))

        rank = h.get("rank", 0)
        if rank > 0:
            screen.blit(font.render(f"{rank}阶", True, (255, 215, 0)), (bx + card_w - 32, by + 5))

        star_y = by + 58
        for si in range(5):
            sx = bx + 8 + si * 22
            sc = (255, 215, 0) if si < rank else (50, 50, 60)
            screen.blit(font.render("★", True, sc), (sx, star_y))

        screen.blit(font.render(f"Lv.{h['level']}", True, (200, 200, 200)), (bx + 10, by + 80))

        # 状态标签：先画背景矩形，再画文字（避免背景覆盖文字）
        if is_assigned:
            tag_rect = pygame.Rect(bx + card_w - 50, by + card_h - 25, 45, 18)
            pygame.draw.rect(screen, (60, 30, 30), tag_rect, border_radius=3)
            tag_surf = font.render("已上阵", True, (180, 80, 80))
            screen.blit(tag_surf, tag_surf.get_rect(center=tag_rect.center))
        else:
            tag_rect = pygame.Rect(bx + card_w - 50, by + card_h - 25, 45, 18)
            pygame.draw.rect(screen, (25, 50, 25), tag_rect, border_radius=3)
            tag_surf = font.render("可上阵", True, (80, 180, 80))
            screen.blit(tag_surf, tag_surf.get_rect(center=tag_rect.center))

        troops_pct = h.get("troops", 0) / max(1, h.get("max_troops", 1))
        bar_x, bar_y, bar_w, bar_h = bx + 10, by + 100, card_w - 20, 6
        pygame.draw.rect(screen, (50, 50, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * troops_pct)
        if fill_w > 0:
            bar_c = (200, 60, 60) if troops_pct < 0.3 else ((255, 200, 80) if troops_pct < 0.6 else (100, 200, 100))
            pygame.draw.rect(screen, bar_c, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        screen.blit(font.render(f"兵:{h.get('troops', 0)}/{h.get('max_troops', 0)}", True, (150, 150, 160)),
                         (bx + 10, by + 110))

        stam_pct = h.get("stamina", 100) / max(1, h.get("max_stamina", 100))
        sbar_y = bar_y + 18
        pygame.draw.rect(screen, (50, 50, 60), (bar_x, sbar_y, bar_w, bar_h), border_radius=3)
        sfill_w = int(bar_w * stam_pct)
        if sfill_w > 0:
            pygame.draw.rect(screen, (60, 140, 255), (bar_x, sbar_y, sfill_w, bar_h), border_radius=3)
        screen.blit(font.render(f"体:{h.get('stamina', 100)}/{h.get('max_stamina', 100)}", True, (130, 150, 200)),
                         (bx + 10, by + 128))

        temp_buttons.append({"action": "view_hero", "rect": card_rect, "hero_id": h["id"]})

    client.panel_buttons = temp_buttons
    screen.set_clip(None)


def draw_hero_detail(screen, client, m_pos, font, ui_font, title_font):
    """绘制武将详情面板（属性页 + 配点页）"""
    dh = client.detail_hero
    px, py, pw, ph = 200, 80, 600, 650
    d_rect = pygame.Rect(px, py, pw, ph)

    dark_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    dark_overlay.fill((0, 0, 0, 180))
    screen.blit(dark_overlay, (0, 0))

    pygame.draw.rect(screen, (20, 22, 28), d_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 160, 80), d_rect, 2, border_radius=8)

    detail_buttons = []

    # 武将名 + 品质色星星
    star_c = (255, 215, 0) if dh.get('stars', 3) >= 5 else ((218, 112, 214) if dh.get('stars', 3) == 4 else (200, 200, 200))
    name_text = f"{dh['name']}  {'★' * dh.get('stars', 3)}"
    screen.blit(title_font.render(name_text, True, star_c), (px + 20, py + 15))

    rank = dh.get('rank', 0)
    if rank > 0:
        rank_surf = font.render(f"{rank}阶", True, (255, 215, 0))
        screen.blit(rank_surf, (px + 20 + title_font.size(name_text)[0] + 10, py + 20))

    close_rect = pygame.Rect(px + pw - 40, py + 15, 30, 30)
    draw_button(screen, close_rect, "X", (150, 50, 50), detail_buttons, font, action="close_detail")

    # Tab 按钮
    tab_width = 80
    tab_height = 35
    tab_y = py + 60
    tab_attr_rect = pygame.Rect(px + 20, tab_y, tab_width, tab_height)
    tab_points_rect = pygame.Rect(px + 20 + tab_width + 10, tab_y, tab_width, tab_height)
    detail_buttons.append({"action": "tab_attr", "rect": tab_attr_rect})
    detail_buttons.append({"action": "tab_points", "rect": tab_points_rect})

    for rect, text, is_active in [(tab_attr_rect, "属性", client.detail_tab == 0),
                                   (tab_points_rect, "配点", client.detail_tab == 1)]:
        color = (70, 72, 88) if not is_active else (90, 92, 108)
        pygame.draw.rect(screen, color, rect, border_radius=4)
        pygame.draw.rect(screen, (180, 160, 80) if is_active else (80, 80, 90), rect, 1, border_radius=4)
        txt = ui_font.render(text, True, (255, 215, 0) if is_active else (160, 160, 170))
        screen.blit(txt, txt.get_rect(center=rect.center))

    if client.detail_tab == 0:
        _draw_attr_tab(screen, client, dh, px, py, pw, font, ui_font, detail_buttons)
    else:
        _draw_points_tab(screen, client, dh, px, py, pw, font, ui_font, detail_buttons)

    # 详情面板是全屏覆盖层，独占所有按钮（不保留底层面板按钮，避免点击穿透）
    client.panel_buttons = detail_buttons


def _draw_attr_tab(screen, client, dh, px, py, pw, font, ui_font, detail_buttons):
    """属性页"""
    y_offset = py + 110

    # 基本信息栏
    info_line = f"兵种：{dh['troop_type']}  攻击距离：{dh['range']}  统率：{dh['cost']}"
    info_bg = pygame.Rect(px + 15, y_offset - 5, pw - 30, 28)
    pygame.draw.rect(screen, (30, 32, 40), info_bg, border_radius=4)
    screen.blit(font.render(info_line, True, (180, 190, 210)), (px + 22, y_offset))
    y_offset += 32

    # 等级 + 经验条
    screen.blit(ui_font.render(f"Lv.{dh['level']}", True, (255, 255, 255)), (px + 20, y_offset))
    exp_need = dh['level'] * 100
    exp_current = dh.get('exp', 0)
    exp_percent = min(1.0, exp_current / exp_need) if exp_need > 0 else 0
    exp_bar_width = 200
    exp_bar_bg = pygame.Rect(px + 100, y_offset + 5, exp_bar_width, 15)
    exp_bar_fill = pygame.Rect(px + 100, y_offset + 5, int(exp_bar_width * exp_percent), 15)
    pygame.draw.rect(screen, (50, 50, 60), exp_bar_bg, border_radius=7)
    if exp_bar_fill.width > 0:
        pygame.draw.rect(screen, (0, 180, 0), exp_bar_fill, border_radius=7)
    screen.blit(font.render(f"{exp_current}/{exp_need}", True, (180, 180, 180)), (px + 100 + exp_bar_width + 5, y_offset + 3))
    y_offset += 30

    # 兵力条
    troops_percent = dh['troops'] / max(1, dh['max_troops'])
    troops_bar_bg = pygame.Rect(px + 20, y_offset, 250, 15)
    troops_bar_fill = pygame.Rect(px + 20, y_offset, int(250 * troops_percent), 15)
    pygame.draw.rect(screen, (50, 50, 60), troops_bar_bg, border_radius=7)
    if troops_bar_fill.width > 0:
        t_color = (180, 50, 50) if troops_percent < 0.3 else ((255, 200, 80) if troops_percent < 0.6 else (100, 200, 100))
        pygame.draw.rect(screen, t_color, troops_bar_fill, border_radius=7)
    screen.blit(font.render(f"兵力：{dh['troops']}/{dh['max_troops']}", True, (200, 200, 200)), (px + 280, y_offset))
    y_offset += 28

    # 体力条
    stamina = dh.get('stamina', 100)
    max_stamina = dh.get('max_stamina', 100)
    stamina_percent = stamina / max(1, max_stamina)
    stamina_bar_bg = pygame.Rect(px + 20, y_offset, 250, 15)
    stamina_bar_fill = pygame.Rect(px + 20, y_offset, int(250 * stamina_percent), 15)
    pygame.draw.rect(screen, (50, 50, 60), stamina_bar_bg, border_radius=7)
    if stamina_bar_fill.width > 0:
        pygame.draw.rect(screen, (50, 140, 255), stamina_bar_fill, border_radius=7)
    screen.blit(font.render(f"体力：{stamina}/{max_stamina}", True, (200, 200, 200)), (px + 280, y_offset))
    y_offset += 35

    # 五维属性
    attrs = [("攻击", dh['atk'], dh['atk_g'], (255, 100, 100)),
             ("防御", dh['def'], dh['def_g'], (100, 180, 255)),
             ("谋略", dh['strg'], dh['strg_g'], (200, 100, 255)),
             ("攻城", dh['sie'], dh['sie_g'], (255, 180, 80)),
             ("速度", dh['spd'], dh['spd_g'], (100, 255, 150))]
    col_width = 280
    for i, (name, val, g, color) in enumerate(attrs):
        x = px + 20 + (i % 2) * col_width
        y = y_offset + (i // 2) * 30
        pygame.draw.rect(screen, color, (x, y + 2, 4, 14), border_radius=2)
        screen.blit(font.render(f"{name}: {val} (+{g})", True, (220, 220, 230)), (x + 10, y))
    y_offset += 90

    # 战法信息
    skill_bg = pygame.Rect(px + 15, y_offset - 5, pw - 30, 105)
    pygame.draw.rect(screen, (28, 30, 38), skill_bg, border_radius=4)
    pygame.draw.rect(screen, (60, 60, 70), skill_bg, 1, border_radius=4)

    screen.blit(font.render("【自带战法】", True, (255, 200, 100)), (px + 22, y_offset))
    screen.blit(ui_font.render(f"{dh['skills'][0]}", True, (255, 220, 130)), (px + 120, y_offset))
    y_offset += 30
    screen.blit(font.render("【学习战法1】", True, (180, 180, 190)), (px + 22, y_offset))
    screen.blit(ui_font.render(f"{dh['skills'][1]}", True, (170, 170, 180)), (px + 120, y_offset))
    y_offset += 30
    screen.blit(font.render("【学习战法2】", True, (180, 180, 190)), (px + 22, y_offset))
    screen.blit(ui_font.render(f"{dh['skills'][2]}", True, (170, 170, 180)), (px + 120, y_offset))


def _draw_points_tab(screen, client, dh, px, py, pw, font, ui_font, detail_buttons):
    """配点页"""
    y_offset = py + 120
    rank = dh.get('rank', 0)

    # 固定5颗星星显示
    for i in range(5):
        x = px + 20 + i * 30
        y = y_offset
        color = (255, 215, 0) if i < rank else (60, 60, 70)
        star_txt = ui_font.render("★", True, color)
        screen.blit(star_txt, (x, y))

    screen.blit(font.render(f"  {rank}/5阶", True, (200, 200, 200)), (px + 20 + 5 * 30, y_offset + 5))
    y_offset += 35

    # 升阶区域
    if rank < 5:
        mat_template_id = dh.get('template_id')
        assigned_ids = set()
        for t in client.troops_list:
            for slot in [t.get("slot1"), t.get("slot2"), t.get("slot3")]:
                if slot:
                    assigned_ids.add(slot)
        materials = [h for h in client.heroes_list
                     if h.get('template_id') == mat_template_id
                     and h['id'] != dh['id']
                     and h['id'] not in assigned_ids]

        screen.blit(font.render(f"升阶材料（同名武将卡 x{len(materials)}）：", True, (200, 180, 100)),
                         (px + 20, y_offset))
        y_offset += 22

        sel_mat = getattr(client, 'rank_up_material', None)
        for mi, mat in enumerate(materials[:4]):
            mx = px + 20 + mi * 90
            my = y_offset
            mr = pygame.Rect(mx, my, 85, 30)
            is_sel = (sel_mat == mat['id'])
            mat_bg = (80, 70, 40) if is_sel else (40, 42, 52)
            pygame.draw.rect(screen, mat_bg, mr, border_radius=4)
            mat_border = (255, 215, 0) if is_sel else (70, 70, 80)
            pygame.draw.rect(screen, mat_border, mr, 1, border_radius=4)
            screen.blit(font.render(f"{mat['name']} Lv{mat['level']}", True,
                                  (255, 215, 0) if is_sel else (160, 160, 170)), (mx + 5, my + 8))
            detail_buttons.append({"action": "select_material", "rect": mr, "material_id": mat['id']})

        y_offset += 38

        if sel_mat and materials:
            btn_rect = pygame.Rect(px + 20, y_offset, 120, 32)
            draw_button(screen, btn_rect, "确认升阶", (120, 90, 40), detail_buttons, font,
                       action="rank_up", hero_id=dh['id'])
        elif materials:
            screen.blit(font.render("↑ 请先点击选择一张材料卡 ↑", True, (150, 140, 100)), (px + 20, y_offset + 5))
        else:
            screen.blit(font.render("（没有可用的同名武将卡作为材料）", True, (120, 100, 100)), (px + 20, y_offset + 5))
        y_offset += 40
    else:
        screen.blit(ui_font.render("✦ 已满阶 ✦", True, (255, 215, 0)), (px + 20, y_offset))
        y_offset += 35

    pygame.draw.line(screen, (60, 60, 70), (px + 20, y_offset), (px + pw - 20, y_offset))
    y_offset += 10

    # 属性配点
    bonus_pts = rank * 10
    screen.blit(ui_font.render(f"可用属性点：{dh['unallocated']}", True, (255, 215, 0)), (px + 20, y_offset))
    screen.blit(font.render(f"（升阶累计 +{bonus_pts}）", True, (120, 120, 140)), (px + 200, y_offset + 3))
    y_offset += 35

    attrs = [
        ("攻击", "atk", dh['p_atk'], dh['atk'], dh['atk_g']),
        ("防御", "def", dh['p_def'], dh['def'], dh['def_g']),
        ("谋略", "strg", dh['p_strg'], dh['strg'], dh['strg_g']),
        ("速度", "spd", dh['p_spd'], dh['spd'], dh['spd_g']),
    ]
    for name, key, p_val, final_val, growth in attrs:
        base_val = final_val - p_val
        screen.blit(ui_font.render(name, True, (220, 220, 230)), (px + 20, y_offset))
        screen.blit(font.render(f"{base_val}", True, (160, 160, 170)), (px + 70, y_offset + 3))
        if p_val > 0:
            screen.blit(font.render(f"+{p_val}", True, (100, 255, 100)), (px + 110, y_offset + 3))
        screen.blit(font.render(f"  成长{growth}", True, (120, 120, 140)), (px + 150, y_offset + 3))

        btn_x = px + pw - 180
        if dh['unallocated'] > 0:
            btn_add = pygame.Rect(btn_x, y_offset - 3, 40, 28)
            draw_button(screen, btn_add, "+1", (60, 90, 60), detail_buttons, font,
                       action="add_point", hero_id=dh['id'], attr=key)
        if p_val > 0:
            btn_sub = pygame.Rect(btn_x + 48, y_offset - 3, 40, 28)
            draw_button(screen, btn_sub, "-1", (90, 60, 60), detail_buttons, font,
                       action="sub_point", hero_id=dh['id'], attr=key)
        if dh['unallocated'] > 0:
            btn_max = pygame.Rect(btn_x + 96, y_offset - 3, 50, 28)
            draw_button(screen, btn_max, "最大", (90, 70, 50), detail_buttons, font,
                       action="max_point", hero_id=dh['id'], attr=key)

        y_offset += 38

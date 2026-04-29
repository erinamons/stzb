# ui/troops_panel.py - 部队管理面板模块
# 从 main.py 提取：部队列表、部队编辑、位置选择弹窗
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_button


def draw_troops_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制部队管理面板（左侧部队列表 + 右侧武将列表）"""
    panel_rect = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
    # 面板背景（不透明）
    pygame.draw.rect(screen, (20, 22, 28), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 160, 80), panel_rect, 2, border_radius=8)

    # 标题栏
    title_bg = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 45)
    pygame.draw.rect(screen, (35, 38, 48), title_bg, border_radius=8)
    screen.blit(title_font.render("⚔ 部队管理", True, (255, 215, 0)),
                (panel_rect.x + 20, panel_rect.y + 8))

    # 关闭按钮
    temp_buttons = []
    close_rect = pygame.Rect(panel_rect.right - 40, panel_rect.y + 8, 30, 30)
    draw_button(screen, close_rect, "X", (150, 50, 50), temp_buttons, font, action="close")

    # 位置标签（与战斗系统对齐：slot1=前锋, slot2=中军, slot3=大营）
    slot_labels = ["前锋", "中军", "大营"]
    slot_colors = [(255, 100, 100), (255, 215, 0), (100, 180, 255)]

    # --- 左侧：部队列表 ---
    left_w = 420
    left_rect = pygame.Rect(panel_rect.x + 10, panel_rect.y + 55, left_w, panel_rect.height - 65)
    screen.set_clip(left_rect)

    card_height = 180
    card_gap = 10
    rows = len(client.troops_list)
    max_scroll = max(0, rows * (card_height + card_gap) - left_rect.height + 10)
    client.troops_scroll_y = max(-max_scroll, min(0, client.troops_scroll_y))

    for i, t in enumerate(client.troops_list):
        x = left_rect.x + 5
        y = left_rect.y + 5 + i * (card_height + card_gap) + client.troops_scroll_y

        if y + card_height < left_rect.top or y > left_rect.bottom:
            continue

        card_rect = pygame.Rect(x, y, left_w - 10, card_height)
        hov = card_rect.collidepoint(m_pos)
        bg = (45, 48, 58) if hov else (30, 32, 42)
        pygame.draw.rect(screen, bg, card_rect, border_radius=6)
        pygame.draw.rect(screen, (100, 90, 60), card_rect, 1, border_radius=6)

        # 部队名称
        screen.blit(ui_font.render(t["name"], True, (255, 215, 0)), (x + 15, y + 10))

        # 阵型竖向布局
        for si, slot_key in enumerate(["slot1", "slot2", "slot3"]):
            hid = t.get(slot_key)
            hero = None
            if hid:
                hero = next((h for h in client.heroes_list if h["id"] == hid), None)

            sy = y + 42 + si * 38
            label_w = 40
            pygame.draw.rect(screen, (*slot_colors[si], 40), (x + 10, sy, label_w, 28), border_radius=4)
            pygame.draw.rect(screen, slot_colors[si], (x + 10, sy, label_w, 28), 1, border_radius=4)
            label_surf = font.render(slot_labels[si], True, slot_colors[si])
            screen.blit(label_surf, label_surf.get_rect(center=(x + 10 + label_w // 2, sy + 14)))

            if hero:
                name_surf = font.render(hero["name"], True, (230, 230, 230))
                screen.blit(name_surf, (x + 60, sy + 5))
                stars_str = "★" * hero.get("stars", 3)
                star_color = (255, 215, 0) if hero.get("stars", 3) >= 5 else (180, 180, 180)
                screen.blit(font.render(stars_str, True, star_color), (x + 60 + name_surf.get_width() + 8, sy + 5))
                info = f"{hero.get('troop_type', '')}  统率{hero.get('cost', 0)}"
                screen.blit(font.render(info, True, (130, 130, 150)), (x + 60, sy + 20))
            else:
                screen.blit(font.render("空", True, (80, 80, 90)), (x + 60, sy + 8))

        total_t = t.get('total_troops', 0)
        screen.blit(font.render(f"总兵力: {total_t}", True, (150, 255, 150)),
                     (x + 15, y + card_height - 32))

        # 编辑按钮
        btn_rect = pygame.Rect(x + left_w - 95, y + card_height - 35, 65, 28)
        draw_button(screen, btn_rect, "编辑", (70, 70, 100), temp_buttons,
                    font, action="edit_troop", troop_id=t["id"])

    screen.set_clip(None)

    # --- 右侧：武将列表（区分已上阵/未上阵）---
    right_x = panel_rect.x + left_w + 20
    right_w = panel_rect.right - right_x - 10
    right_y = panel_rect.y + 55
    right_h = panel_rect.height - 65

    # 计算已上阵武将ID集合
    assigned_hero_ids = set()
    assigned_list = []
    free_list = []
    for t in client.troops_list:
        for si, slot_key in enumerate(["slot1", "slot2", "slot3"]):
            hid = t.get(slot_key)
            if hid:
                assigned_hero_ids.add(hid)
                hero = next((h for h in client.heroes_list if h["id"] == hid), None)
                if hero:
                    # 记录所属部队和位置
                    assigned_list.append({**hero, "_troop_name": t["name"], "_slot_label": slot_labels[si], "_slot_color": slot_colors[si]})

    for h in client.heroes_list:
        if h["id"] not in assigned_hero_ids:
            free_list.append(h)

    # 计算右侧内容总高度
    header_h = 60  # 已上阵标题 + 分隔 + 未上阵标题
    assigned_total = len(assigned_list) * 34 + 6
    free_total = len(free_list) * 34 + 6
    content_h = header_h + assigned_total + free_total
    right_content_rect = pygame.Rect(right_x, right_y, right_w, right_h)
    # 右侧独立滚动
    right_max_scroll = max(0, content_h - right_h + 10)
    if not hasattr(client, 'troops_right_scroll_y'):
        client.troops_right_scroll_y = 0
    client.troops_right_scroll_y = max(-right_max_scroll, min(0, client.troops_right_scroll_y))

    # 绘制右侧背景
    right_bg = pygame.Surface((right_w, right_h), pygame.SRCALPHA)
    right_bg.fill((25, 27, 35, 200))
    screen.blit(right_bg, (right_x, right_y))
    pygame.draw.rect(screen, (60, 60, 70), right_content_rect, 1, border_radius=4)
    screen.set_clip(right_content_rect)

    ry = right_y + client.troops_right_scroll_y

    # --- 已上阵区标题 ---
    sec_y = ry
    sec_bg = pygame.Rect(right_x, sec_y, right_w, 28)
    pygame.draw.rect(screen, (50, 35, 35), sec_bg, border_radius=4)
    screen.blit(ui_font.render(f"已上阵 ({len(assigned_list)})", True, (255, 130, 130)),
                (right_x + 10, sec_y + 3))

    # --- 已上阵列表 ---
    assigned_start_y = ry + 32
    for idx, h in enumerate(assigned_list):
        iy = assigned_start_y + idx * 34
        if iy + 34 < right_y or iy > right_y + right_h:
            continue
        if idx % 2 == 0:
            row_bg = pygame.Rect(right_x + 2, iy, right_w - 4, 32)
            pygame.draw.rect(screen, (35, 30, 30), row_bg, border_radius=3)

        # 部队位置小标签
        troop_label = font.render(f"[{h['_troop_name']}·{h['_slot_label']}]", True, h['_slot_color'])
        screen.blit(troop_label, (right_x + 6, iy + 3))

        # 武将名
        star_c = (255, 215, 0) if h.get("stars", 3) >= 5 else (220, 220, 220)
        name_s = font.render(h["name"], True, star_c)
        screen.blit(name_s, (right_x + 6, iy + 17))
        info_s = font.render(f"{'★' * h.get('stars', 3)} {h.get('faction', '')}·{h.get('troop_type', '')}", True, (120, 120, 140))
        screen.blit(info_s, (right_x + 6 + name_s.get_width() + 6, iy + 17))

    # --- 未上阵区标题 ---
    free_y = assigned_start_y + assigned_total
    free_bg = pygame.Rect(right_x, free_y, right_w, 28)
    pygame.draw.rect(screen, (30, 50, 35), free_bg, border_radius=4)
    screen.blit(ui_font.render(f"未上阵 ({len(free_list)})", True, (100, 255, 130)),
                (right_x + 10, free_y + 3))

    # --- 未上阵列表 ---
    free_start_y = free_y + 32
    for idx, h in enumerate(free_list):
        iy = free_start_y + idx * 34
        if iy + 34 < right_y or iy > right_y + right_h:
            continue
        if idx % 2 == 0:
            row_bg = pygame.Rect(right_x + 2, iy, right_w - 4, 32)
            pygame.draw.rect(screen, (30, 32, 40), row_bg, border_radius=3)

        # 品质颜色指示
        star_c = (255, 215, 0) if h.get("stars", 3) >= 5 else ((180, 120, 220) if h.get("stars", 3) == 4 else (140, 140, 140))
        pygame.draw.rect(screen, star_c, (right_x + 4, iy + 6, 3, 22), border_radius=2)

        name_c = (255, 215, 0) if h.get("stars", 3) >= 5 else (220, 220, 220)
        name_s = font.render(h["name"], True, name_c)
        screen.blit(name_s, (right_x + 12, iy + 3))
        info_s = font.render(f"{'★' * h.get('stars', 3)} {h.get('faction', '')}·{h.get('troop_type', '')} Lv{h.get('level', 1)}", True, (120, 120, 140))
        screen.blit(info_s, (right_x + 12 + name_s.get_width() + 6, iy + 3))

        troops_info = font.render(f"兵:{h.get('troops', 0)}/{h.get('max_troops', 0)}", True, (100, 120, 140))
        screen.blit(troops_info, (right_x + 12, iy + 17))

        # "配置"按钮——点击后进入编辑面板
        btn_rect = pygame.Rect(right_x + right_w - 60, iy + 4, 50, 24)
        draw_button(screen, btn_rect, "配置", (50, 85, 50), temp_buttons,
                    font, action="quick_assign", hero_id=h["id"])

    screen.set_clip(None)
    client.panel_buttons = temp_buttons


def draw_edit_troop_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制部队编辑面板（阵型预览 + 可用武将列表 + 位置选择弹窗）"""
    if not client.editing_troop:
        client.current_panel = None
        return

    panel_rect = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
    # 面板背景（不透明）
    pygame.draw.rect(screen, (20, 22, 28), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 160, 80), panel_rect, 2, border_radius=8)

    # 标题栏
    title_bg = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 45)
    pygame.draw.rect(screen, (35, 38, 48), title_bg, border_radius=8)
    screen.blit(title_font.render(f"⚔ 编辑部队：{client.editing_troop['name']}", True, (255, 215, 0)),
                (panel_rect.x + 20, panel_rect.y + 8))
    temp_buttons = []
    close_rect = pygame.Rect(panel_rect.right - 40, panel_rect.y + 8, 30, 30)
    draw_button(screen, close_rect, "X", (150, 50, 50), temp_buttons, font, action="close")

    # 位置标签（与战斗系统对齐：slot1=前锋, slot2=中军, slot3=大营）
    slot_labels = ["前锋", "中军", "大营"]
    slot_colors = [(255, 100, 100), (255, 215, 0), (100, 180, 255)]
    slot_descriptions = ["前排 · 承受攻击", "中排 · 攻守兼备", "后排 · 安全输出"]

    # 左侧：阵型预览（竖向布局，上方为前锋，下方为大营）
    formation_x = panel_rect.x + 30
    formation_y = panel_rect.y + 70
    slot_w, slot_h = 260, 120
    slot_gap = 10

    for i, slot_name in enumerate(slot_labels):
        sy = formation_y + i * (slot_h + slot_gap)
        slot_rect = pygame.Rect(formation_x, sy, slot_w, slot_h)

        # 槽位背景
        bg = (38, 40, 52)
        pygame.draw.rect(screen, bg, slot_rect, border_radius=6)

        # 位置标签色带（左侧竖条）
        color_bar = pygame.Rect(formation_x, sy, 6, slot_h)
        pygame.draw.rect(screen, slot_colors[i], color_bar, border_radius=3)

        # 位置名称和描述
        screen.blit(ui_font.render(slot_name, True, slot_colors[i]),
                     (formation_x + 16, sy + 8))
        screen.blit(font.render(slot_descriptions[i], True, (100, 100, 120)),
                     (formation_x + 16, sy + 34))

        # 武将信息
        hero_id = client.troop_edit_cache.get(f"slot{i + 1}")
        if hero_id:
            hero = next((h for h in client.heroes_list if h["id"] == hero_id), None)
            if hero:
                h_name_color = (255, 215, 0) if hero.get("stars", 3) >= 5 else (230, 230, 230)
                screen.blit(ui_font.render(hero["name"], True, h_name_color),
                             (formation_x + 16, sy + 55))
                stars_str = "★" * hero.get("stars", 3)
                screen.blit(font.render(stars_str, True, (255, 215, 0)),
                             (formation_x + 16 + ui_font.size(hero["name"])[0] + 8, sy + 58))
                info = f"{hero.get('troop_type', '')}  统率{hero.get('cost', 0)}  攻距{hero.get('range', 2)}"
                screen.blit(font.render(info, True, (140, 140, 160)),
                             (formation_x + 16, sy + 80))
                # 卸下按钮
                btn_rect = pygame.Rect(formation_x + slot_w - 60, sy + slot_h - 32, 50, 25)
                draw_button(screen, btn_rect, "卸下", (120, 50, 50), temp_buttons,
                            font, action="remove_hero", slot=i + 1)
            else:
                screen.blit(font.render("（武将不存在）", True, (120, 80, 80)),
                             (formation_x + 16, sy + 65))
                btn_rect = pygame.Rect(formation_x + slot_w - 60, sy + slot_h - 32, 50, 25)
                draw_button(screen, btn_rect, "卸下", (80, 60, 60), temp_buttons,
                            font, action="remove_hero", slot=i + 1)
        else:
            # 空槽虚线框
            inner = pygame.Rect(formation_x + 12, sy + 50, slot_w - 24, 35)
            pygame.draw.rect(screen, (60, 60, 70), inner, 1, border_radius=4)
            screen.blit(font.render("空槽位", True, (80, 80, 90)),
                         (formation_x + 16, sy + 58))
            # 添加按钮
            btn_rect = pygame.Rect(formation_x + slot_w - 60, sy + slot_h - 32, 50, 25)
            draw_button(screen, btn_rect, "添加", (50, 90, 50), temp_buttons,
                        font, action="add_hero", slot=i + 1)

    # 右侧：可用武将列表
    list_x = formation_x + slot_w + 30
    list_y = formation_y
    list_w = panel_rect.right - list_x - 15
    list_h = panel_rect.bottom - list_y - 60

    # 列表标题
    list_title_bg = pygame.Rect(list_x, list_y - 5, list_w, 32)
    pygame.draw.rect(screen, (35, 38, 48), list_title_bg, border_radius=4)
    screen.blit(ui_font.render(f"可用武将 ({len(client.available_heroes)})", True, (255, 215, 0)),
                (list_x + 10, list_y))

    # 列表内容区域
    list_content_rect = pygame.Rect(list_x, list_y + 32, list_w, list_h - 32)
    pygame.draw.rect(screen, (25, 27, 35), list_content_rect, border_radius=4)
    screen.set_clip(list_content_rect)

    if not hasattr(client, "available_heroes_scroll_y"):
        client.available_heroes_scroll_y = 0
    item_height = 38
    total_height = len(client.available_heroes) * item_height
    max_scroll = max(0, total_height - list_content_rect.height + 10)
    client.available_heroes_scroll_y = max(-max_scroll, min(0, client.available_heroes_scroll_y))

    for idx, h in enumerate(client.available_heroes):
        iy = list_y + 38 + idx * item_height + client.available_heroes_scroll_y
        if iy + item_height < list_content_rect.top or iy > list_content_rect.bottom:
            continue
        # 交替行背景
        if idx % 2 == 0:
            row_bg = pygame.Rect(list_x + 2, iy, list_w - 4, item_height - 2)
            pygame.draw.rect(screen, (30, 32, 40), row_bg, border_radius=3)

        # 武将品质颜色指示
        star_c = (255, 215, 0) if h.get("stars", 3) >= 5 else ((180, 120, 220) if h.get("stars", 3) == 4 else (140, 140, 140))
        pygame.draw.rect(screen, star_c, (list_x + 6, iy + 8, 3, 22), border_radius=2)

        # 武将信息
        name_c = (255, 215, 0) if h.get("stars", 3) >= 5 else (220, 220, 220)
        screen.blit(font.render(h["name"], True, name_c), (list_x + 16, iy + 3))
        stars_str = "★" * h.get("stars", 3)
        screen.blit(font.render(stars_str, True, star_c), (list_x + 16 + font.size(h["name"])[0] + 6, iy + 3))

        info = f"{h.get('faction', '')}·{h.get('troop_type', '')}  统率{h.get('cost', 0)}"
        screen.blit(font.render(info, True, (120, 120, 140)), (list_x + 16, iy + 20))

        # 配置按钮
        btn_rect = pygame.Rect(list_x + list_w - 70, iy + 5, 60, 28)
        draw_button(screen, btn_rect, "配置", (50, 85, 50), temp_buttons,
                    font, action="assign_hero", hero_id=h["id"])

    # 先解除裁剪，再绘制底部按钮
    screen.set_clip(None)

    # 底部按钮栏：返回 + 确定
    btn_bar_y = panel_rect.bottom - 50
    back_rect = pygame.Rect(panel_rect.x + 20, btn_bar_y, 120, 36)
    draw_button(screen, back_rect, "← 返回", (60, 60, 75), temp_buttons, font, action="close")
    confirm_rect = pygame.Rect(panel_rect.right - 160, btn_bar_y, 140, 36)
    draw_button(screen, confirm_rect, "确定保存", (50, 100, 60), temp_buttons, font, action="confirm_troop_edit")

    client.panel_buttons = temp_buttons
    screen.set_clip(None)

    # 位置选择弹窗（覆盖层，当 slot_picker_hero_id 有值时显示）
    # 弹窗会替换 panel_buttons，防止点击穿透到编辑面板底层的按钮
    if client.slot_picker_hero_id is not None:
        _draw_slot_picker(screen, client, m_pos, font, ui_font)


def _draw_slot_picker(screen, client, m_pos, font, ui_font):
    """绘制位置选择弹窗"""
    picker_hero = next((h for h in client.heroes_list if h["id"] == client.slot_picker_hero_id), None)
    if not picker_hero:
        return

    slot_labels = ["前锋", "中军", "大营"]
    slot_colors = [(255, 100, 100), (255, 215, 0), (100, 180, 255)]
    slot_descs = ["前排 · 承受攻击", "中排 · 攻守兼备", "后排 · 安全输出"]

    # 弹窗遮罩
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    screen.blit(overlay, (0, 0))

    pw, ph = 320, 320
    px = WINDOW_WIDTH // 2 - pw // 2
    py = WINDOW_HEIGHT // 2 - ph // 2
    picker_rect = pygame.Rect(px, py, pw, ph)

    pygame.draw.rect(screen, (25, 28, 38), picker_rect, border_radius=10)
    pygame.draw.rect(screen, (180, 160, 80), picker_rect, 2, border_radius=10)

    # 标题
    screen.blit(ui_font.render(f"选择 {picker_hero['name']} 的上阵位置", True, (255, 215, 0)),
                (px + 20, py + 15))

    # 三个位置按钮
    slot_btns = []
    for i in range(3):
        slot = i + 1
        occupied = client.troop_edit_cache.get(f"slot{slot}") is not None
        sr = pygame.Rect(px + 20, py + 55 + i * 70, pw - 40, 58)

        # 按钮背景
        hov = sr.collidepoint(m_pos)
        if occupied:
            bg_c = (55, 45, 45) if not hov else (70, 55, 55)
            border_c = (120, 80, 80)
        else:
            bg_c = (40, 50, 45) if not hov else (55, 68, 58)
            border_c = slot_colors[i]

        pygame.draw.rect(screen, bg_c, sr, border_radius=6)
        pygame.draw.rect(screen, border_c, sr, 2, border_radius=6)

        # 左侧色条
        pygame.draw.rect(screen, slot_colors[i], (sr.x, sr.y, 5, sr.height), border_radius=3)

        # 位置名 + 描述
        screen.blit(ui_font.render(slot_labels[i], True, slot_colors[i]),
                     (sr.x + 15, sr.y + 6))
        screen.blit(font.render(slot_descs[i], True, (140, 140, 160)),
                     (sr.x + 15, sr.y + 30))

        # 已占用提示
        if occupied:
            occ_hero_id = client.troop_edit_cache.get(f"slot{slot}")
            occ_hero = next((h for h in client.heroes_list if h["id"] == occ_hero_id), None)
            occ_name = occ_hero["name"] if occ_hero else "???"
            screen.blit(font.render(f"替换: {occ_name}", True, (200, 130, 130)),
                         (sr.x + 200, sr.y + 18))

        # 可点击（只注册按钮区域，不绘制）
        slot_btns.append({"action": "pick_slot", "slot": slot, "rect": sr})

    # 取消按钮
    cancel_rect = pygame.Rect(px + pw // 2 - 50, py + ph - 42, 100, 32)
    draw_button(screen, cancel_rect, "取消", (80, 50, 50), slot_btns, font, action="cancel_slot_pick")

    # 弹窗覆盖层，替换所有按钮防止点击穿透到底层面板
    client.panel_buttons = slot_btns

# ui/building_panel.py - 主城建筑面板模块
# 从 main.py 提取：draw_building_panel, draw_building_detail, CN_NUMS, RES_NAMES
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_rounded_rect, draw_gradient_rect, draw_button

# 中文数字映射
CN_NUMS = {1: "壹", 2: "贰", 3: "叁", 4: "肆", 5: "伍", 6: "陆", 7: "柒", 8: "捌"}

# 资源名称映射（英文key → 中文名）
RES_NAMES = {"wood": "木材", "iron": "铁矿", "stone": "石料", "grain": "粮草", "copper": "铜币"}

# 建筑效果字段中文名称映射（英文key → 中文名）
EFFECT_NAMES = {
    "durability": "城池耐久",
    "cost_cap": "COST上限",
    "troop_slots": "出征队伍数",
    "vanguard_slots": "前锋武将槽",
    "troop_capacity": "带兵上限",
    "speed_bonus": "速度加成",
    "defense_bonus": "防御加成",
    "strategy_bonus": "谋略加成",
    "attack_bonus": "攻击加成",
    "copper_per_hour": "铜币/时",
    "wood_per_hour": "木材/时",
    "iron_per_hour": "铁矿/时",
    "grain_per_hour": "粮草/时",
    "stone_per_hour": "石料/时",
    "storage_cap": "资源上限",
    "recruit_speed_bonus": "征兵加速%",
    "reserve_cap": "预备兵上限",
    "wall_durability": "城墙耐久",
    "damage_reduction": "伤害减免%",
    "vision_range": "视野范围",
    "alliance_share": "同盟共享",
    "garrison_bonus": "守军加成%",
    "exchange_enabled": "资源兑换",
    "physical_damage_reduction": "物理减伤%",
    "strategy_damage_reduction": "策略减伤%",
    "cost_cap_bonus": "COST上限+",
    "fame_cap": "名望上限",
    "faction_bonus_atk": "阵营攻击",
    "faction_bonus_def": "阵营防御",
    "faction_bonus_strg": "阵营谋略",
    "faction_bonus_spd": "阵营速度",
}


def draw_building_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制阶梯式建筑面板"""
    px, py, pw, ph = 80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200

    # 背景（不透明）
    pygame.draw.rect(screen, (22, 22, 32), (px, py, pw, ph), border_radius=10)
    pygame.draw.rect(screen, (70, 60, 50), pygame.Rect(px, py, pw, ph), 2, border_radius=10)

    # 标题栏
    title_h = 45
    title_rect = pygame.Rect(px, py, pw, title_h)
    draw_gradient_rect(screen, title_rect, (40, 35, 28), (28, 25, 22), radius=10)
    pygame.draw.rect(screen, (255, 215, 0), (px, py, 5, title_h), border_radius=3)
    screen.blit(title_font.render("主城建筑", True, (255, 215, 0)), (px + 18, py + 10))
    hint = font.render("点击建筑查看详情 | 滚轮翻页", True, (110, 110, 120))
    screen.blit(hint, (px + pw - hint.get_width() - 18, py + 16))

    # 关闭按钮
    close_r = pygame.Rect(px + pw - 45, py + 10, 35, 35)
    c_hov = close_r.collidepoint(m_pos)
    pygame.draw.rect(screen, (200, 70, 70) if c_hov else (150, 50, 50), close_r, border_radius=6)
    pygame.draw.rect(screen, (220, 100, 100) if c_hov else (180, 80, 80), close_r, 2, border_radius=6)
    screen.blit(font.render("X", True, (255, 255, 255)),
                     (close_r.centerx - 4, close_r.centery - 8))

    # 获取城主府等级
    palace_bld = next((b for b in client.buildings_data if b["key"] == "palace"), None)
    palace_level = palace_bld["current_level"] if palace_bld else 0
    palace_text = f"城主府 Lv.{palace_level}" if palace_level > 0 else "城主府 未建造"
    p_surf = ui_font.render(palace_text, True, (255, 215, 0) if palace_level > 0 else (120, 120, 130))
    screen.blit(p_surf, (px + pw // 2 - p_surf.get_width() // 2, py + 16))

    # 内容区（可滚动）
    content_y = py + title_h + 5
    content_rect = pygame.Rect(px + 5, content_y, pw - 10, ph - title_h - 10)
    draw_rounded_rect(screen, (18, 18, 26), content_rect, radius=6, alpha=210)
    screen.set_clip(content_rect)

    # 阶梯式布局参数
    CARD_W = 130
    CARD_H = 72
    CARD_GAP = 8
    LEVEL_LABEL_W = 36
    LEVEL_LINE_GAP = 4
    ROW_GAP = 6
    START_X = content_rect.x + 14
    START_Y = content_rect.y + 10

    # 按 layout_row 分组
    row_groups = {}
    for b in client.buildings_data:
        row = b.get("layout_row", 0)
        if row not in row_groups:
            row_groups[row] = []
        row_groups[row].append(b)

    cur_y = START_Y + client.building_scroll_y

    for row_num in sorted(row_groups.keys()):
        buildings_in_row = row_groups[row_num]
        buildings_in_row.sort(key=lambda b: b.get("layout_col", 0))

        row_label = CN_NUMS.get(row_num, str(row_num)) if row_num > 0 else "主"

        # 绘制行标签
        label_surf = ui_font.render(row_label, True, (200, 180, 120))
        label_x = START_X
        label_y_pos = cur_y + (CARD_H - label_surf.get_height()) // 2
        screen.blit(label_surf, (label_x, label_y_pos))

        # 绘制连接线
        line_x = label_x + LEVEL_LABEL_W
        line_color = (80, 70, 55)
        pygame.draw.line(screen, line_color,
                         (line_x, cur_y + CARD_H // 2),
                         (line_x + LEVEL_LINE_GAP, cur_y + CARD_H // 2), 2)

        card_x = line_x + LEVEL_LINE_GAP + 4
        for b in buildings_in_row:
            if card_x + CARD_W > content_rect.right - 5:
                card_x = line_x + LEVEL_LINE_GAP + 4
                cur_y += CARD_H + ROW_GAP
                pygame.draw.line(screen, line_color,
                                 (line_x, cur_y + CARD_H // 2),
                                 (line_x + LEVEL_LINE_GAP, cur_y + CARD_H // 2), 2)

            card_rect = pygame.Rect(card_x, cur_y, CARD_W, CARD_H)

            if card_rect.bottom < content_rect.top - 10 or card_rect.top > content_rect.bottom + 10:
                card_x += CARD_W + CARD_GAP
                continue

            level = b["current_level"]
            hov = card_rect.collidepoint(m_pos)

            if level == -1:
                bg_color = (30, 30, 38) if not hov else (40, 38, 48)
                border_color = (55, 55, 65) if not hov else (80, 75, 90)
                text_color = (90, 90, 100)
            elif level == 0:
                bg_color = (35, 38, 30) if not hov else (45, 48, 38)
                border_color = (80, 90, 60) if not hov else (110, 120, 80)
                text_color = (160, 180, 140)
            else:
                bg_color = (35, 38, 42) if not hov else (45, 48, 52)
                border_color = (90, 85, 70) if not hov else (120, 110, 85)
                text_color = (200, 200, 210)

            if level >= b["max_level"] and level > 0:
                border_color = (200, 180, 80) if not hov else (240, 220, 100)

            pygame.draw.rect(screen, bg_color, card_rect, border_radius=6)
            pygame.draw.rect(screen, border_color, card_rect, 2, border_radius=6)

            screen.blit(font.render(b["name"], True, text_color), (card_rect.x + 6, card_rect.y + 5))

            if level >= 0:
                lv_str = f"Lv.{level}/{b['max_level']}"
                lv_color = (255, 215, 0) if level >= b["max_level"] else (140, 140, 150)
                screen.blit(font.render(lv_str, True, lv_color), (card_rect.x + 6, card_rect.y + 24))
            else:
                prereq_text = f"需城主府Lv.{b.get('unlock_palace_level', '?')}"
                screen.blit(font.render(prereq_text, True, (100, 80, 80)), (card_rect.x + 6, card_rect.y + 24))

            if level >= 0 and level < b["max_level"] and b.get("next_cost"):
                cost = b["next_cost"]
                cost_parts = []
                for rk, rv in cost.items():
                    if rv and rv > 0:
                        cost_parts.append(f"{RES_NAMES.get(rk, rk)}{rv}")
                if cost_parts:
                    cost_str = " ".join(cost_parts[:3])
                    if len(cost_parts) > 3:
                        cost_str += "..."
                    screen.blit(font.render(cost_str, True, (160, 140, 100)), (card_rect.x + 6, card_rect.y + 44))
            elif level >= b["max_level"] and level > 0:
                screen.blit(font.render("★ 已满级", True, (255, 215, 0)), (card_rect.x + 6, card_rect.y + 44))
            elif level == -1 and b.get("prereq_met"):
                screen.blit(font.render("✓ 可解锁", True, (100, 200, 100)), (card_rect.x + 6, card_rect.y + 44))
            elif level == -1:
                screen.blit(font.render("🔒 未解锁", True, (100, 80, 80)), (card_rect.x + 6, card_rect.y + 44))
            elif level == 0:
                screen.blit(font.render("免费建造", True, (100, 200, 100)), (card_rect.x + 6, card_rect.y + 44))

            card_x += CARD_W + CARD_GAP

        cur_y += CARD_H + ROW_GAP

    screen.set_clip(None)

    # 收集本面板所有按钮，最后整体赋值（避免残留按钮导致点击穿透）
    temp_buttons = []
    temp_buttons.append({"action": "close", "rect": close_r})

    # 注册建筑卡片点击区域（将按钮rect裁剪到内容区域内，避免幽灵按钮）
    cur_y = START_Y + client.building_scroll_y
    for row_num in sorted(row_groups.keys()):
        buildings_in_row = sorted(row_groups[row_num], key=lambda b: b.get("layout_col", 0))
        line_x = START_X + LEVEL_LABEL_W
        card_x = line_x + LEVEL_LINE_GAP + 4
        for b in buildings_in_row:
            if card_x + CARD_W > content_rect.right - 5:
                card_x = line_x + LEVEL_LINE_GAP + 4
                cur_y += CARD_H + ROW_GAP
            card_rect = pygame.Rect(card_x, cur_y, CARD_W, CARD_H)
            # 计算卡片与内容区的交集（只有交集区域才可点击）
            clip_rect = card_rect.clip(content_rect) if card_rect.colliderect(content_rect) else None
            if clip_rect:
                temp_buttons.append({
                    "action": "building_detail",
                    "building_key": b["key"],
                    "rect": clip_rect,  # 使用裁剪后的rect
                })
            card_x += CARD_W + CARD_GAP
        cur_y += CARD_H + ROW_GAP

    client.panel_buttons = temp_buttons


def draw_building_detail(screen, client, m_pos, font, ui_font, title_font):
    """绘制建筑详情弹窗（覆盖在建筑面板上方）"""
    if not client.building_detail:
        return

    detail = client.building_detail
    dpx, dpy = 120, 120
    dpw, dph = WINDOW_WIDTH - 320, WINDOW_HEIGHT - 300

    pygame.draw.rect(screen, (15, 15, 20), (dpx, dpy, dpw, dph), border_radius=10)
    pygame.draw.rect(screen, (120, 100, 60), pygame.Rect(dpx, dpy, dpw, dph), 2, border_radius=10)

    # 标题栏
    title_h = 42
    title_rect = pygame.Rect(dpx, dpy, dpw, title_h)
    draw_gradient_rect(screen, title_rect, (38, 33, 25), (26, 23, 18), radius=10)
    pygame.draw.rect(screen, (255, 200, 80), (dpx, dpy, 4, title_h), border_radius=3)
    screen.blit(title_font.render(
        f"{detail.get('name', '?')} 详情", True, (255, 215, 0)),
        (dpx + 16, dpy + 8))

    # 关闭按钮
    close_r = pygame.Rect(dpx + dpw - 40, dpy + 8, 30, 30)
    c_hov = close_r.collidepoint(m_pos)
    pygame.draw.rect(screen, (200, 70, 70) if c_hov else (150, 50, 50), close_r, border_radius=5)
    pygame.draw.rect(screen, (220, 100, 100) if c_hov else (180, 80, 80), close_r, 1, border_radius=5)
    screen.blit(font.render("X", True, (255, 255, 255)),
                     (close_r.centerx - 4, close_r.centery - 7))

    # 基础信息
    level_configs = detail.get("levels", [])
    current_level = detail.get("current_level", -1)
    max_level = detail.get("max_level", 1)

    info_y = dpy + title_h + 8
    info_texts = [
        (f"当前等级: {current_level if current_level >= 0 else '未解锁'}", (180, 180, 190)),
        (f"最大等级: {max_level}", (140, 140, 150)),
        (f"描述: {detail.get('description', '无')}", (130, 130, 140)),
    ]
    for txt, color in info_texts:
        screen.blit(ui_font.render(txt, True, color), (dpx + 16, info_y))
        info_y += 24

    # 前置条件
    prereqs = detail.get("prerequisites", [])
    if prereqs:
        prereq_str = "前置: " + ", ".join(
            f"{p.get('name', p.get('key', '?'))} Lv.{p.get('level', '?')}" for p in prereqs
        )
        screen.blit(ui_font.render(prereq_str, True, (180, 160, 120)), (dpx + 16, info_y))
        info_y += 24

    info_y += 6
    pygame.draw.line(screen, (60, 55, 45), (dpx + 12, info_y), (dpx + dpw - 12, info_y), 1)
    info_y += 8

    # 等级配置表格
    headers = ["等级", "木材", "铁矿", "石料", "粮草", "铜币", "效果"]
    col_widths = [45, 60, 60, 60, 60, 60, dpw - 45 - 60 * 5 - 32]
    hx = dpx + 16
    for i, h in enumerate(headers):
        screen.blit(font.render(h, True, (200, 190, 150)), (hx, info_y))
        hx += col_widths[i]
    info_y += 22
    pygame.draw.line(screen, (60, 55, 45), (dpx + 12, info_y), (dpx + dpw - 12, info_y), 1)
    info_y += 4

    # 滚动等级配置列表
    list_rect = pygame.Rect(dpx + 8, info_y, dpw - 16, dpy + dph - info_y - 52)
    draw_rounded_rect(screen, (16, 16, 22), list_rect, radius=4, alpha=200)
    screen.set_clip(list_rect)

    detail_scroll = client.building_detail_scroll_y
    row_y = list_rect.y + 6 + detail_scroll

    for lc in level_configs:
        if row_y + 20 < list_rect.top or row_y > list_rect.bottom:
            row_y += 22
            continue

        lv = lc.get("level", 0)
        is_current = (lv == current_level)

        if is_current:
            hl_rect = pygame.Rect(list_rect.x, row_y - 2, list_rect.width, 22)
            draw_rounded_rect(screen, (50, 45, 30), hl_rect, radius=3, alpha=120)

        row_color = (255, 220, 120) if is_current else (170, 170, 180)
        rx = list_rect.x + 8
        values = [
            f"Lv.{lv}",
            str(lc.get("cost_wood", 0)),
            str(lc.get("cost_iron", 0)),
            str(lc.get("cost_stone", 0)),
            str(lc.get("cost_grain", 0)),
            str(lc.get("cost_copper", 0)),
        ]
        effects = lc.get("effects", {})
        if isinstance(effects, dict):
            parts = []
            for k, v in effects.items():
                cn_name = EFFECT_NAMES.get(k, k)
                if isinstance(v, bool):
                    parts.append(f"{cn_name}:{'✅' if v else '❌'}")
                else:
                    parts.append(f"{cn_name}:{v}")
            effect_str = " ".join(parts)
        elif isinstance(effects, str):
            effect_str = effects
        else:
            effect_str = str(effects) if effects else "-"
        if len(effect_str) > 30:
            effect_str = effect_str[:28] + ".."
        values.append(effect_str)

        for i, v in enumerate(values):
            screen.blit(font.render(v, True, row_color), (rx, row_y))
            rx += col_widths[i]
        row_y += 22

    screen.set_clip(None)

    # 底部按钮：建造/升级 / 返回（弹窗覆盖层，替换底层按钮防止穿透）
    btn_y = dpy + dph - 48
    detail_buttons = []
    detail_buttons.append({"action": "close_building_detail", "rect": close_r})

    back_rect = pygame.Rect(dpx + dpw // 2 - 140, btn_y, 120, 36)
    draw_button(screen, back_rect, "返回", (60, 55, 45), detail_buttons, font, action="close_building_detail")

    # 从建筑列表查找该建筑的 can_unlock 状态（仅 current_level=-1 时需要）
    bld_key = detail.get("key", "")
    bld_list_item = next((b for b in client.buildings_data if b["key"] == bld_key), None)
    can_unlock = bld_list_item.get("can_unlock", False) if bld_list_item else False

    if current_level == -1:
        if can_unlock:
            # 前置满足，显示"建造"按钮
            build_rect = pygame.Rect(dpx + dpw // 2 + 20, btn_y, 120, 36)
            draw_button(screen, build_rect, "建造", (60, 100, 50), detail_buttons, font,
                       action="upgrade_building", building_key=bld_key)
        else:
            # 前置不满足，显示"未解锁"
            lock_rect = pygame.Rect(dpx + dpw // 2 + 20, btn_y, 120, 36)
            draw_rounded_rect(screen, (50, 40, 40), lock_rect, radius=6, alpha=200)
            pygame.draw.rect(screen, (120, 80, 80), lock_rect, 1, border_radius=6)
            lock_surf = font.render("🔒 未解锁", True, (160, 120, 120))
            screen.blit(lock_surf, lock_surf.get_rect(center=lock_rect.center))
    elif current_level >= 0 and current_level < max_level:
        upgrade_rect = pygame.Rect(dpx + dpw // 2 + 20, btn_y, 120, 36)
        draw_button(screen, upgrade_rect, "升级", (100, 80, 30), detail_buttons, font,
                   action="upgrade_building", building_key=bld_key)
    elif current_level >= max_level and current_level > 0:
        max_rect = pygame.Rect(dpx + dpw // 2 + 20, btn_y, 120, 36)
        draw_rounded_rect(screen, (60, 55, 30), max_rect, radius=6, alpha=200)
        pygame.draw.rect(screen, (160, 140, 60), max_rect, 1, border_radius=6)
        max_surf = font.render("已满级", True, (200, 180, 80))
        screen.blit(max_surf, max_surf.get_rect(center=max_rect.center))

    client.panel_buttons = detail_buttons

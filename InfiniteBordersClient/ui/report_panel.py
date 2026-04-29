# ui/report_panel.py - 战报面板模块
# 从 main.py 提取：战报历史列表、详细战报渲染
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui_utils import draw_rounded_rect, draw_gradient_rect, draw_button


def draw_report_history(screen, client, font, ui_font, title_font):
    """绘制战报历史列表面板"""
    px, py, pw, ph = 80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200

    # 背景（不透明）
    pygame.draw.rect(screen, (22, 22, 32), (px, py, pw, ph), border_radius=10)
    pygame.draw.rect(screen, (70, 60, 50), pygame.Rect(px, py, pw, ph), 2, border_radius=10)

    # 标题栏（战报历史）
    title_h = 45
    title_rect = pygame.Rect(px, py, pw, title_h)
    draw_gradient_rect(screen, title_rect, (40, 35, 28), (28, 25, 22), radius=10)
    pygame.draw.rect(screen, (255, 215, 0), (px, py, 5, title_h), border_radius=3)
    screen.blit(title_font.render("战报历史", True, (255, 215, 0)), (px + 18, py + 10))
    total_text = f"共 {len(client.report_history)} 场战斗"
    total_surf = font.render(total_text, True, (130, 130, 140))
    screen.blit(total_surf, (px + pw - total_surf.get_width() - 18, py + 16))

    # 列表区域（可滚动）
    list_y = py + title_h
    list_rect = pygame.Rect(px + 5, list_y, pw - 10, ph - title_h - 5)
    draw_rounded_rect(screen, (18, 18, 26), list_rect, radius=6, alpha=210)
    screen.set_clip(list_rect)

    item_h = 65
    item_gap = 5
    start_y = list_y + 8

    for i, rpt in enumerate(client.report_history):
        iy = start_y + i * (item_h + item_gap) + client.report_history_scroll_y
        if iy + item_h < list_rect.y or iy > list_rect.bottom:
            continue

        item_rect = pygame.Rect(list_rect.x + 10, iy, list_rect.width - 20, item_h)
        is_win = rpt.get("is_victory", 0) == 1
        if is_win:
            bg_c, border_c, badge_color = (30, 40, 30), (60, 120, 60), (80, 200, 100)
            badge_text = "胜利"
        else:
            bg_c, border_c, badge_color = (40, 28, 28), (120, 60, 60), (200, 80, 80)
            badge_text = "失败"

        draw_rounded_rect(screen, bg_c, item_rect, radius=6, alpha=220)
        pygame.draw.rect(screen, border_c, item_rect, 1, border_radius=6)
        pygame.draw.rect(screen, badge_color, (item_rect.x, item_rect.y + 5, 4, item_h - 10), border_radius=2)

        # 胜负标记
        badge_r = pygame.Rect(item_rect.x + 15, item_rect.y + 8, 42, 22)
        draw_rounded_rect(screen, badge_color, badge_r, radius=4, alpha=80)
        bs = font.render(badge_text, True, badge_color)
        screen.blit(bs, bs.get_rect(center=badge_r.center))

        # 坐标和时间
        screen.blit(ui_font.render(f"坐标: ({rpt.get('tile_x', '?')}, {rpt.get('tile_y', '?')})",
                     True, (180, 180, 190)), (item_rect.x + 68, item_rect.y + 10))
        ct = rpt.get("created_at", "")
        if ct:
            screen.blit(font.render(ct, True, (120, 120, 135)), (item_rect.x + 68, item_rect.y + 35))

        # 摘要
        report = rpt.get("report")
        if report:
            hdr = report.get("header", {})
            rt = hdr.get("result_text", "")
            if len(rt) > 30:
                rt = rt[:30] + "..."
            if rt:
                screen.blit(font.render(rt, True, (150, 150, 165)), (item_rect.x + 280, item_rect.y + 10))
            tb = hdr.get("total_battles", None)
            bi = f"{tb}场" if tb else f"{hdr.get('total_rounds', '?')}回合"
            screen.blit(font.render(bi, True, (140, 140, 155)), (item_rect.x + 280, item_rect.y + 35))

        arrow = font.render(">", True, (100, 100, 110))
        screen.blit(arrow, (item_rect.right - 25, item_rect.centery - arrow.get_height() // 2))

    screen.set_clip(None)

    # 关闭按钮
    temp_buttons = []
    close_r = pygame.Rect(px + pw - 45, py + 10, 35, 35)
    draw_button(screen, close_r, "X", (150, 50, 50), temp_buttons, font, action="close")
    client.panel_buttons = temp_buttons

    if not client.report_history:
        es = font.render("暂无战报记录", True, (100, 100, 110))
        screen.blit(es, es.get_rect(center=(px + pw // 2, py + ph // 2)))


def draw_detailed_report(screen, client, ui_font, font):
    """绘制详细战报面板（实时推送或历史查看共用）"""
    data = client.report_panel
    is_victory = data.get("is_victory", False)
    if isinstance(is_victory, int):
        is_victory = bool(is_victory)
    report = data.get("report")

    panel_rect = pygame.Rect(80, 40, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
    pygame.draw.rect(screen, (22, 22, 32), panel_rect, border_radius=10)

    # 颜色主题
    if is_victory:
        title_color = (100, 255, 130)
        border_color = (80, 160, 80)
        title_bg_start = (30, 45, 30)
        title_bg_end = (22, 32, 22)
    else:
        title_color = (255, 100, 100)
        border_color = (160, 70, 70)
        title_bg_start = (45, 28, 28)
        title_bg_end = (35, 20, 20)

    pygame.draw.rect(screen, border_color, panel_rect, 2, border_radius=10)

    # 标题栏
    title_bg = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 48)
    draw_gradient_rect(screen, title_bg, title_bg_start, title_bg_end, radius=10)
    pygame.draw.rect(screen, title_color, (panel_rect.x, panel_rect.y, 5, 48), border_radius=3)

    title_text = "大捷" if is_victory else "战败"
    screen.blit(font.render(title_text, True, title_color), (panel_rect.x + 18, panel_rect.y + 10))
    hint_surf = ui_font.render("鼠标滚轮查看 | 点击关闭", True, (110, 110, 120))
    screen.blit(hint_surf, (panel_rect.x + panel_rect.width - hint_surf.get_width() - 18, panel_rect.y + 16))

    # 内容区
    content_rect = pygame.Rect(panel_rect.x + 10, panel_rect.y + 56, panel_rect.width - 20, panel_rect.height - 66)
    draw_rounded_rect(screen, (18, 18, 26), content_rect, radius=6, alpha=210)
    screen.set_clip(content_rect)

    # === 构建渲染行列表 ===
    render_lines = []
    CX = content_rect.x + 12
    LINE_H = 22

    def add_line(text, color=(195, 195, 205), indent=0):
        render_lines.append((text, color, indent))

    def add_blank(size=8):
        render_lines.append(("", None, -size))

    if report is None:
        add_line(data.get("error", "战斗数据异常"), (255, 100, 100))
    else:
        header = report.get("header", {})
        add_line(f"进攻方: {header.get('attacker_name', '?')}  vs  防守方: {header.get('defender_name', '?')}", (180, 180, 190))
        add_line(f"战斗时间: {header.get('time', '?')}  |  总回合: {header.get('total_rounds', '?')}", (130, 130, 140))
        add_line(f"结果: {header.get('result_text', '?')}", title_color)
        add_blank()

        # 阵容信息
        add_line("=== 初始阵容 ===", (220, 200, 140))
        add_blank(4)

        for side_label, heroes_key in [("进攻方", "attacker_heroes"), ("防守方", "defender_heroes")]:
            add_line(f"【{side_label}: {header.get('attacker_name' if heroes_key == 'attacker_heroes' else 'defender_name', '?')}】",
                     (180, 200, 180) if heroes_key == "attacker_heroes" else (200, 180, 180))
            for h in report.get(heroes_key, []):
                hp_pct = int(h["remaining_troops"] / max(h["initial_troops"], 1) * 100)
                status = "存活" if h["is_alive"] else "阵亡"
                status_color = (130, 255, 150) if h["is_alive"] else (255, 100, 100)
                add_line(f"  {h['position']}  {h['name']}  兵力{h['initial_troops']}  "
                         f"攻{h['attack']} 防{h['defense']} 谋{h['strategy']} 速{h['speed']}  "
                         f"战法:{h['skill']}", (170, 170, 180))
                add_line(f"    -> 剩余{h['remaining_troops']} ({hp_pct}%)  {status}", status_color, indent=1)
            add_blank(4)

        # 指挥战法
        cmd_skills = report.get("command_skills", [])
        if cmd_skills:
            add_line("=== 战斗前指挥战法 ===", (220, 200, 140))
            for cs in cmd_skills:
                add_line(f"  {cs['caster']} 发动 {cs['skill']}: {cs['effect']}", (170, 190, 210))
            add_blank(4)

        # 回合详情
        for rd in report.get("rounds", []):
            rd_num = rd.get('round', 0)
            if rd_num < 0:
                events = rd.get("events", [])
                for ev in events:
                    if ev["type"] == "battle_break":
                        bd = ev["data"]
                        add_line(f"========== 第{bd.get('battle_num', '?')}场战斗 ==========", (255, 200, 50))
                        add_line(f"  进攻方剩余兵力: {bd.get('attacker_troops', 0)}  "
                                 f"防守方剩余兵力: {bd.get('defender_troops', 0)}", (170, 170, 180))
                        add_blank()
                continue
            add_line(f"--- 第{rd['round']}回合 ---", (255, 215, 0))
            events = rd.get("events", [])
            for ev in events:
                ev_type = ev["type"]
                ev_data = ev["data"]

                if ev_type == "action_order":
                    order_str = " > ".join(ev_data.get("order", []))
                    add_line(f"  出手顺序: {order_str}", (140, 140, 155))
                elif ev_type == "dot_damage":
                    add_line(f"  {ev_data.get('target', '?')} 受到{ev_data.get('dot_type', '?')}伤害{ev_data.get('damage', 0)}点",
                             (220, 160, 120))
                elif ev_type == "prepare_done":
                    add_line(f"  {ev_data.get('hero', '?')} 的战法【{ev_data.get('skill', '?')}】准备完成",
                             (180, 200, 255))
                elif ev_type == "hero_action":
                    hero_name = ev_data.get("hero", "?")
                    actions = ev_data.get("actions", [])
                    for act in actions:
                        act_type = act.get("type", "")
                        if act_type == "active_skill":
                            add_line(f"  {hero_name} 发动战法【{act.get('skill', '?')}】", (100, 220, 255))
                        elif act_type == "pending_skill":
                            add_line(f"  {hero_name} 释放准备完成的战法【{act.get('skill', '?')}】", (100, 220, 255))
                        elif act_type == "start_prepare":
                            add_line(f"  {hero_name} 开始准备战法【{act.get('skill', '?')}】({act.get('turns', '?')}回合)",
                                     (150, 170, 200))
                        elif act_type == "hesitation":
                            add_line(f"  {hero_name} 犹豫，无法发动【{act.get('skill', '?')}】", (180, 160, 140))
                        elif act_type == "preparing":
                            add_line(f"  {hero_name} 战法【{act.get('skill', '?')}】准备中", (150, 150, 160))
                        elif act_type == "active_fail":
                            add_line(f"  {hero_name} 发动【{act.get('skill', '?')}】失败", (160, 140, 130))
                        elif act_type == "normal_attack":
                            remaining_str = f" (兵:{act.get('target_remaining', '?')})" if act.get('target_remaining') is not None else ""
                            add_line(f"  {hero_name} 对【{act.get('target', '?')}】普攻，造成{act.get('damage', 0)}伤害{remaining_str}",
                                     (255, 160, 140))
                        elif act_type == "no_target":
                            add_line(f"  {hero_name} 无有效攻击目标", (140, 140, 150))
                elif ev_type == "skill_effect":
                    eff = ev_data
                    eff_type = eff.get("effect_type", "")
                    hero = eff.get("hero", "?")
                    if eff_type == "damage":
                        add_line(f"    -> 对【{eff.get('target', '?')}】造成{eff.get('damage', 0)}伤害({eff.get('damage_type', '?')})",
                                 (255, 120, 120), indent=1)
                    elif eff_type == "heal":
                        add_line(f"    -> 恢复【{eff.get('target', '?')}】{eff.get('amount', 0)}兵力",
                                 (100, 255, 140), indent=1)
                    elif eff_type == "control":
                        add_line(f"    -> {eff.get('target', '?')} 陷入{eff.get('control_type', '?')}状态，持续{eff.get('duration', '?')}",
                                 (210, 140, 255), indent=1)
                    elif eff_type == "status":
                        dur_text = eff.get('duration', '')
                        dur_str = f"，持续{dur_text}" if dur_text else ""
                        add_line(f"    -> {eff.get('target', '?')} 获得{eff.get('status_type', '?')}状态{dur_str}",
                                 (140, 210, 255), indent=1)
                    elif eff_type == "modify_attr":
                        remaining_str = f" -> {eff.get('current_value', '?')}" if eff.get('current_value') is not None else ""
                        add_line(f"    -> {eff.get('target', '?')} 的{eff.get('attr_name', '?')} "
                                 f"{eff.get('modify_type', '?')}{eff.get('value', '?')}{remaining_str}，持续{eff.get('duration', '?')}",
                                 (180, 200, 130), indent=1)

            add_blank(4)

        # 战后统计
        add_line("=== 战损统计 ===", (220, 200, 140))
        add_blank(4)
        for side_label, heroes_key in [("进攻方", "attacker_heroes"), ("防守方", "defender_heroes")]:
            heroes = report.get(heroes_key, [])
            if not heroes:
                continue
            total_init = sum(h["initial_troops"] for h in heroes)
            total_remain = sum(h["remaining_troops"] for h in heroes)
            add_line(f"【{side_label}】总兵: {total_init} -> {total_remain} (损{total_init - total_remain})",
                     (180, 180, 190))
            for h in heroes:
                loss = h["initial_troops"] - h["remaining_troops"]
                cast_info = ""
                if h.get("skill_cast_count"):
                    casts = " ".join(f"{sk}x{ct}" for sk, ct in h["skill_cast_count"].items())
                    cast_info = f"  战法: {casts}" if casts else ""
                status = "存活" if h["is_alive"] else "阵亡"
                sc = (130, 220, 140) if h["is_alive"] else (255, 100, 100)
                add_line(f"  {h['position']} {h['name']}: 初始{h['initial_troops']} 剩{h['remaining_troops']} 损{loss} [{status}]{cast_info}",
                         sc)

    # === 渲染所有行（支持自动换行） ===
    max_w = content_rect.width - 24
    y_cursor = 0
    for text, color, indent in render_lines:
        if indent < 0:
            y_cursor += (-indent)
            continue

        x_offset = CX + indent * 16
        avail_w = max_w - indent * 16

        # 自动换行
        words = []
        i = 0
        while i < len(text):
            if ord(text[i]) > 127:
                words.append(text[i])
                i += 1
            elif text[i] == ' ':
                i += 1
            else:
                j = i
                while j < len(text) and ord(text[j]) <= 127 and text[j] != ' ':
                    j += 1
                words.append(text[i:j])
                i = j

        cur = ""
        for word in words:
            test = cur + word
            w, _ = ui_font.size(test)
            if w > avail_w and cur:
                y_pos = content_rect.y + 6 + y_cursor + client.report_scroll_y
                if content_rect.top - 20 <= y_pos <= content_rect.bottom:
                    screen.blit(ui_font.render(cur, True, color), (x_offset, y_pos))
                y_cursor += LINE_H
                cur = word
            else:
                cur = test
        if cur:
            y_pos = content_rect.y + 6 + y_cursor + client.report_scroll_y
            if content_rect.top - 20 <= y_pos <= content_rect.bottom:
                screen.blit(ui_font.render(cur, True, color), (x_offset, y_pos))
            y_cursor += LINE_H

    screen.set_clip(None)

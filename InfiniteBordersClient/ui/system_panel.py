# ui/system_panel.py - 系统面板模块
# 个人信息、修改用户名、修改密码、退出登录
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_client_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
import json
import urllib.request
import urllib.error
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, SERVER_HOST, SERVER_PORT
from ui_utils import draw_rounded_rect, draw_gradient_rect, draw_button

# 颜色
BG_COLOR = (22, 22, 32)
PANEL_BG = (30, 32, 42)
INPUT_BG = (40, 42, 55)
INPUT_ACTIVE = (55, 58, 78)
INPUT_BORDER = (80, 85, 110)
TEXT_WHITE = (220, 220, 225)
TEXT_GRAY = (150, 150, 160)
TEXT_DIM = (100, 105, 120)
ACCENT_GOLD = (255, 215, 0)
ACCENT_BLUE = (70, 130, 255)
ACCENT_GREEN = (100, 255, 140)
ACCENT_RED = (255, 100, 100)
ACCENT_CYAN = (80, 200, 255)


def refresh_system_panel(client):
    """打开系统面板时初始化状态。"""
    client.panel_buttons = []
    client.system_tab = 0  # 0=个人信息, 1=修改用户名, 2=修改密码
    # 修改用户名相关
    client.sys_new_username = ""
    client.sys_username_active = False
    client.sys_username_msg = ""
    client.sys_username_msg_color = TEXT_WHITE
    client.sys_username_busy = False
    # 修改密码相关
    client.sys_old_password = ""
    client.sys_new_password = ""
    client.sys_password_active = "old"  # "old" or "new"
    client.sys_password_msg = ""
    client.sys_password_msg_color = TEXT_WHITE
    client.sys_password_busy = False


def draw_system_panel(screen, client, m_pos, font, ui_font, title_font):
    """绘制系统面板。"""
    px, py, pw, ph = 80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200

    # 背景
    pygame.draw.rect(screen, BG_COLOR, (px, py, pw, ph), border_radius=10)
    pygame.draw.rect(screen, (70, 60, 50), (px, py, pw, ph), 2, border_radius=10)

    # 标题栏
    title_h = 48
    draw_gradient_rect(screen, pygame.Rect(px, py, pw, title_h), (40, 35, 28), (28, 25, 22), radius=10)
    pygame.draw.rect(screen, ACCENT_GOLD, (px, py, 5, title_h), border_radius=3)
    screen.blit(title_font.render("系统设置", True, ACCENT_GOLD), (px + 18, py + 10))

    # 关闭按钮
    client.panel_buttons.append({"action": "close", "rect": pygame.Rect(px + pw - 45, py + 10, 35, 35)})

    # Tab 按钮
    tab_names = ["个人信息", "修改用户名", "修改密码"]
    tab_y = py + title_h + 8
    tab_w = 120
    for i, name in enumerate(tab_names):
        tab_rect = pygame.Rect(px + 20 + i * (tab_w + 10), tab_y, tab_w, 36)
        is_active = getattr(client, 'system_tab', 0) == i
        if is_active:
            draw_rounded_rect(screen, (60, 55, 40), tab_rect, radius=6, alpha=200)
            pygame.draw.rect(screen, ACCENT_GOLD, tab_rect, 1, border_radius=6)
        else:
            draw_rounded_rect(screen, (35, 37, 48), tab_rect, radius=6, alpha=180)
        color = ACCENT_GOLD if is_active else TEXT_GRAY
        text_surf = font.render(name, True, color)
        screen.blit(text_surf, text_surf.get_rect(center=tab_rect.center))
        client.panel_buttons.append({"action": f"sys_tab_{i}", "rect": tab_rect})

    # 内容区
    content_y = tab_y + 50
    content_x = px + 30
    content_w = pw - 60

    tab = getattr(client, 'system_tab', 0)

    if tab == 0:
        _draw_personal_info(screen, client, content_x, content_y, content_w, ui_font, font)
    elif tab == 1:
        _draw_change_username(screen, client, content_x, content_y, content_w, ui_font, font)
    elif tab == 2:
        _draw_change_password(screen, client, content_x, content_y, content_w, ui_font, font)


def _draw_personal_info(screen, client, cx, cy, cw, ui_font, font):
    """绘制个人信息页面。"""
    # 信息卡片
    card_rect = pygame.Rect(cx, cy, cw, 200)
    draw_rounded_rect(screen, PANEL_BG, card_rect, radius=8, alpha=220)
    pygame.draw.rect(screen, (55, 58, 72), card_rect, 1, border_radius=8)

    y = cy + 20
    # 用户名
    screen.blit(ui_font.render("用户名", True, TEXT_DIM), (cx + 25, y))
    screen.blit(ui_font.render(client.username or "未知", True, TEXT_WHITE), (cx + 120, y))
    y += 40
    # 玩家ID
    screen.blit(ui_font.render("玩家ID", True, TEXT_DIM), (cx + 25, y))
    screen.blit(ui_font.render(str(client.player_id or "未知"), True, TEXT_WHITE), (cx + 120, y))
    y += 40
    # 坐标
    spawn = getattr(client, 'spawn_pos', (0, 0))
    screen.blit(ui_font.render("出生坐标", True, TEXT_DIM), (cx + 25, y))
    screen.blit(ui_font.render(f"({spawn[0]}, {spawn[1]})", True, TEXT_WHITE), (cx + 120, y))

    # 退出登录按钮
    y = cy + 230
    btn_rect = pygame.Rect(cx + cw // 2 - 80, y, 160, 42)
    draw_rounded_rect(screen, (120, 40, 40), btn_rect, radius=6, alpha=200)
    pygame.draw.rect(screen, ACCENT_RED, btn_rect, 1, border_radius=6)
    text_surf = ui_font.render("退出登录", True, ACCENT_RED)
    screen.blit(text_surf, text_surf.get_rect(center=btn_rect.center))
    client.panel_buttons.append({"action": "logout", "rect": btn_rect})

    # 提示
    y += 60
    hint = font.render("退出登录后将返回登录界面", True, TEXT_DIM)
    screen.blit(hint, hint.get_rect(center=(cx + cw // 2, y)))


def _draw_input_box(screen, rect, placeholder, text, active, font, password=False):
    """绘制输入框，返回 rect。"""
    color = INPUT_ACTIVE if active else INPUT_BG
    border_color = ACCENT_BLUE if active else INPUT_BORDER
    pygame.draw.rect(screen, color, rect, border_radius=6)
    pygame.draw.rect(screen, border_color, rect, 1, border_radius=6)

    if password and text:
        display = "●" * len(text)
    elif text:
        display = text
    else:
        display = placeholder
        # 绘制占位符
        surf = font.render(display, True, TEXT_DIM)
        screen.blit(surf, (rect.x + 12, rect.y + (rect.h - surf.get_height()) // 2))
        return rect

    color = TEXT_WHITE if text else TEXT_DIM
    surf = font.render(display, True, color)
    screen.blit(surf, (rect.x + 12, rect.y + (rect.h - surf.get_height()) // 2))
    return rect


def _draw_change_username(screen, client, cx, cy, cw, ui_font, font):
    """绘制修改用户名页面。"""
    new_name = getattr(client, 'sys_new_username', '')
    active = getattr(client, 'sys_username_active', False)
    msg = getattr(client, 'sys_username_msg', '')
    msg_color = getattr(client, 'sys_username_msg_color', TEXT_WHITE)
    busy = getattr(client, 'sys_username_busy', False)

    # 说明
    screen.blit(ui_font.render("修改用户名", True, ACCENT_GOLD), (cx, cy))
    screen.blit(font.render("修改后下次登录需使用新用户名", True, TEXT_DIM), (cx, cy + 30))

    # 当前用户名
    y = cy + 70
    screen.blit(font.render("当前用户名:", True, TEXT_GRAY), (cx, y))
    screen.blit(ui_font.render(client.username, True, TEXT_WHITE), (cx + 110, y - 2))

    # 新用户名输入框
    y = cy + 110
    screen.blit(font.render("新用户名:", True, TEXT_GRAY), (cx, y))
    input_rect = pygame.Rect(cx + 110, y - 4, 300, 32)
    _draw_input_box(screen, input_rect, "请输入新用户名", new_name, active, font)
    client.panel_buttons.append({"action": "sys_username_input", "rect": input_rect})

    # 提交按钮
    y = cy + 170
    btn_rect = pygame.Rect(cx + 110, y, 120, 36)
    btn_color = (60, 60, 80) if busy else (50, 80, 50)
    draw_rounded_rect(screen, btn_color, btn_rect, radius=6, alpha=200)
    pygame.draw.rect(screen, ACCENT_GREEN if not busy else TEXT_DIM, btn_rect, 1, border_radius=6)
    btn_text = "提交中..." if busy else "确认修改"
    text_surf = font.render(btn_text, True, ACCENT_GREEN if not busy else TEXT_DIM)
    screen.blit(text_surf, text_surf.get_rect(center=btn_rect.center))
    if not busy:
        client.panel_buttons.append({"action": "sys_submit_username", "rect": btn_rect})

    # 消息
    if msg:
        y = cy + 220
        screen.blit(font.render(msg, True, msg_color), (cx + 110, y))


def _draw_change_password(screen, client, cx, cy, cw, ui_font, font):
    """绘制修改密码页面。"""
    old_pwd = getattr(client, 'sys_old_password', '')
    new_pwd = getattr(client, 'sys_new_password', '')
    active_field = getattr(client, 'sys_password_active', 'old')
    msg = getattr(client, 'sys_password_msg', '')
    msg_color = getattr(client, 'sys_password_msg_color', TEXT_WHITE)
    busy = getattr(client, 'sys_password_busy', False)
    has_pwd = bool(getattr(client, '_has_password', None))

    # 说明
    screen.blit(ui_font.render("修改密码", True, ACCENT_GOLD), (cx, cy))
    if has_pwd:
        hint_text = "需要验证旧密码才能设置新密码"
    else:
        hint_text = "当前账号无密码，可直接设置密码"
    screen.blit(font.render(hint_text, True, TEXT_DIM), (cx, cy + 30))

    y = cy + 75
    if has_pwd:
        # 旧密码
        screen.blit(font.render("旧密码:", True, TEXT_GRAY), (cx, y))
        old_rect = pygame.Rect(cx + 80, y - 4, 300, 32)
        _draw_input_box(screen, old_rect, "请输入旧密码", old_pwd, active_field == "old", font, password=True)
        client.panel_buttons.append({"action": "sys_old_pwd_input", "rect": old_rect})
        y += 55

    # 新密码
    screen.blit(font.render("新密码:", True, TEXT_GRAY), (cx, y))
    new_rect = pygame.Rect(cx + 80, y - 4, 300, 32)
    _draw_input_box(screen, new_rect, "请输入新密码（至少3位）", new_pwd,
                    active_field == "new", font, password=True)
    client.panel_buttons.append({"action": "sys_new_pwd_input", "rect": new_rect})

    # 提交按钮
    y += 55
    btn_rect = pygame.Rect(cx + 80, y, 120, 36)
    btn_color = (60, 60, 80) if busy else (50, 80, 50)
    draw_rounded_rect(screen, btn_color, btn_rect, radius=6, alpha=200)
    pygame.draw.rect(screen, ACCENT_GREEN if not busy else TEXT_DIM, btn_rect, 1, border_radius=6)
    btn_text = "提交中..." if busy else "确认修改"
    text_surf = font.render(btn_text, True, ACCENT_GREEN if not busy else TEXT_DIM)
    screen.blit(text_surf, text_surf.get_rect(center=btn_rect.center))
    if not busy:
        client.panel_buttons.append({"action": "sys_submit_password", "rect": btn_rect})

    # 消息
    if msg:
        y += 50
        screen.blit(font.render(msg, True, msg_color), (cx + 80, y))


def handle_system_event(client, event):
    """处理系统面板的键盘事件。返回 True 表示事件已消费。"""
    tab = getattr(client, 'system_tab', 0)

    if event.type == pygame.KEYDOWN:
        if tab == 1:  # 修改用户名
            return _handle_username_key(client, event)
        elif tab == 2:  # 修改密码
            return _handle_password_key(client, event)

    return False


def _handle_username_key(client, event):
    if not getattr(client, 'sys_username_active', False):
        return False
    if getattr(client, 'sys_username_busy', False):
        return False

    if event.key == pygame.K_BACKSPACE:
        client.sys_new_username = client.sys_new_username[:-1]
    elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
        _do_change_username(client)
    elif event.unicode and event.unicode.isprintable() and len(client.sys_new_username) < 16:
        client.sys_new_username += event.unicode
    return True


def _handle_password_key(client, event):
    if getattr(client, 'sys_password_busy', False):
        return False
    active = getattr(client, 'sys_password_active', 'old')
    has_pwd = getattr(client, '_has_password', None)

    # Tab 切换输入框
    if event.key == pygame.K_TAB and has_pwd:
        client.sys_password_active = "new" if active == "old" else "old"
        return True

    if event.key == pygame.K_BACKSPACE:
        if active == "old":
            client.sys_old_password = client.sys_old_password[:-1]
        else:
            client.sys_new_password = client.sys_new_password[:-1]
        return True
    elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
        _do_change_password(client)
        return True
    elif event.unicode and event.unicode.isprintable():
        if active == "old" and len(client.sys_old_password) < 32:
            client.sys_old_password += event.unicode
        elif active == "new" and len(client.sys_new_password) < 32:
            client.sys_new_password += event.unicode
        return True

    return False


def _do_change_username(client):
    """执行修改用户名。"""
    if getattr(client, 'sys_username_busy', False):
        return

    new_name = client.sys_new_username.strip()
    if not new_name or len(new_name) < 2:
        client.sys_username_msg = "用户名至少 2 个字符"
        client.sys_username_msg_color = ACCENT_RED
        return

    client.sys_username_busy = True
    client.sys_username_msg = ""

    def _request():
        try:
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/players/{client.player_id}"
            data = json.dumps({"username": new_name}).encode()
            req = urllib.request.Request(url, data=data, method="PUT",
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                client.sys_username_msg = "修改成功！下次登录生效"
                client.sys_username_msg_color = ACCENT_GREEN
            else:
                client.sys_username_msg = result.get("message", "修改失败")
                client.sys_username_msg_color = ACCENT_RED
        except Exception as e:
            client.sys_username_msg = f"请求失败: {e}"
            client.sys_username_msg_color = ACCENT_RED
        finally:
            client.sys_username_busy = False

    import threading
    threading.Thread(target=_request, daemon=True).start()


def _do_change_password(client):
    """执行修改密码。"""
    if getattr(client, 'sys_password_busy', False):
        return

    has_pwd = getattr(client, '_has_password', None)
    old_pwd = getattr(client, 'sys_old_password', '')
    new_pwd = getattr(client, 'sys_new_password', '')

    if has_pwd and not old_pwd:
        client.sys_password_msg = "请输入旧密码"
        client.sys_password_msg_color = ACCENT_RED
        return

    if not new_pwd or len(new_pwd.strip()) < 3:
        client.sys_password_msg = "新密码至少 3 个字符"
        client.sys_password_msg_color = ACCENT_RED
        return

    client.sys_password_busy = True
    client.sys_password_msg = ""

    def _request():
        try:
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/account/password"
            data = json.dumps({
                "username": client.username,
                "old_password": old_pwd,
                "new_password": new_pwd.strip(),
            }).encode()
            req = urllib.request.Request(url, data=data, method="PUT",
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                client.sys_password_msg = "密码修改成功！"
                client.sys_password_msg_color = ACCENT_GREEN
                client.sys_old_password = ""
                client.sys_new_password = ""
            else:
                client.sys_password_msg = result.get("message", "修改失败")
                client.sys_password_msg_color = ACCENT_RED
        except Exception as e:
            client.sys_password_msg = f"请求失败: {e}"
            client.sys_password_msg_color = ACCENT_RED
        finally:
            client.sys_password_busy = False

    import threading
    threading.Thread(target=_request, daemon=True).start()


def handle_system_click(client, action):
    """处理系统面板按钮点击，返回 True 表示需要关闭面板。"""
    if action == "sys_tab_0":
        client.system_tab = 0
    elif action == "sys_tab_1":
        client.system_tab = 1
    elif action == "sys_tab_2":
        client.system_tab = 2
    elif action == "sys_username_input":
        client.sys_username_active = True
    elif action == "sys_old_pwd_input":
        client.sys_password_active = "old"
    elif action == "sys_new_pwd_input":
        client.sys_password_active = "new"
    elif action == "sys_submit_username":
        _do_change_username(client)
    elif action == "sys_submit_password":
        _do_change_password(client)
    elif action == "logout":
        return True  # 通知主循环退出

    return False

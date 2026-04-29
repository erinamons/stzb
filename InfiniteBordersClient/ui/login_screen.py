# ui/login_screen.py - 登录/注册界面
# 注册：HTTP POST /api/register（含密码）
# 登录：WebSocket 连接 /ws/{username} → 发送 auth 消息 → 接收 res_login → 请求地图
import sys
import os

_client_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_client_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
import json
import asyncio
import urllib.request
import urllib.error
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, SERVER_HOST, SERVER_PORT


# 颜色主题（暗色）
BG_COLOR = (18, 18, 24)
PANEL_COLOR = (30, 32, 42)
PANEL_BORDER = (55, 58, 72)
INPUT_BG = (40, 42, 55)
INPUT_ACTIVE = (50, 55, 75)
INPUT_BORDER = (80, 85, 110)
TEXT_WHITE = (220, 220, 225)
TEXT_GRAY = (140, 145, 160)
TEXT_DIM = (90, 95, 110)
ACCENT_BLUE = (70, 130, 255)
ACCENT_GREEN = (80, 200, 120)
ACCENT_RED = (220, 80, 80)
ACCENT_YELLOW = (220, 180, 60)
ACCENT_CYAN = (80, 200, 220)
BTN_LOGIN = (55, 110, 230)
BTN_LOGIN_HOVER = (70, 130, 255)
BTN_REGISTER = (50, 160, 100)
BTN_REGISTER_HOVER = (65, 185, 120)


class LoginScreen:
    """登录/注册界面。"""

    def __init__(self, screen, fonts):
        self.screen = screen
        self.title_font, self.ui_font, self.font = fonts
        self.username = ""
        self.password = ""
        self.is_register = False  # False=登录, True=注册
        self.active_input = "username"  # "username" or "password"
        self.status_msg = ""
        self.status_color = TEXT_WHITE
        self.busy = False  # 防止重复提交
        self.error_msg = ""  # 输入验证错误

        # 服务器在线状态（后台线程定时检测）
        self.server_online = None  # None=检测中, True=在线, False=离线
        self._check_server()

        # 输入框位置（居中面板内）
        panel_w, panel_h = 400, 340
        px = (WINDOW_WIDTH - panel_w) // 2
        py = (WINDOW_HEIGHT - panel_h) // 2 - 20
        self.panel_rect = pygame.Rect(px, py, panel_w, panel_h)

        self.user_rect = pygame.Rect(px + 40, py + 105, panel_w - 80, 40)
        self.pass_rect = pygame.Rect(px + 40, py + 185, panel_w - 80, 40)
        self.submit_rect = pygame.Rect(px + 40, py + 250, panel_w - 80, 42)
        self.toggle_rect = pygame.Rect(px + 40, py + 310, panel_w - 80, 24)

    def draw(self):
        self.screen.fill(BG_COLOR)

        # 标题
        title = self.title_font.render("InfiniteBorders", True, ACCENT_BLUE)
        self.screen.blit(title, ((WINDOW_WIDTH - title.get_width()) // 2, self.panel_rect.y - 60))
        subtitle = self.ui_font.render("六边形沙盘战略", True, TEXT_GRAY)
        self.screen.blit(subtitle, ((WINDOW_WIDTH - subtitle.get_width()) // 2, self.panel_rect.y - 30))

        # 面板背景
        pygame.draw.rect(self.screen, PANEL_COLOR, self.panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, PANEL_BORDER, self.panel_rect, width=1, border_radius=12)

        # 模式标签
        mode_text = "注册新账号" if self.is_register else "账号登录"
        mode_surf = self.ui_font.render(mode_text, True, TEXT_WHITE)
        self.screen.blit(mode_surf, (self.panel_rect.x + 40, self.panel_rect.y + 25))

        # 服务器地址 + 在线状态
        srv_text = self.font.render(f"服务器: {SERVER_HOST}:{SERVER_PORT}", True, TEXT_DIM)
        self.screen.blit(srv_text, (self.panel_rect.x + 40, self.panel_rect.y + 55))
        # 状态指示灯（紧跟在服务器地址右侧）
        indicator_x = self.panel_rect.x + 40 + srv_text.get_width() + 10
        indicator_y = self.panel_rect.y + 55 + srv_text.get_height() // 2
        if self.server_online is None:
            color = ACCENT_YELLOW
            label = "检测中"
        elif self.server_online:
            color = ACCENT_GREEN
            label = "在线"
        else:
            color = ACCENT_RED
            label = "离线"
        pygame.draw.circle(self.screen, color, (indicator_x, indicator_y), 5)
        status_label = self.font.render(label, True, color)
        self.screen.blit(status_label, (indicator_x + 10, indicator_y - status_label.get_height() // 2))

        # 用户名输入框
        self._draw_input(self.user_rect, "用户名", self.username,
                         self.active_input == "username")

        # 密码输入框
        pass_display = "●" * len(self.password) if self.password else ""
        placeholder = "密码（可选）" if self.is_register else "密码（无密码账号直接登录）"
        self._draw_input(self.pass_rect, placeholder, pass_display,
                         self.active_input == "password")

        # 提交按钮
        btn_color = BTN_REGISTER if self.is_register else BTN_LOGIN
        btn_hover = BTN_REGISTER_HOVER if self.is_register else BTN_LOGIN_HOVER
        btn_text = "注册" if self.is_register else "登录"
        mouse_pos = pygame.mouse.get_pos()
        if self.submit_rect.collidepoint(mouse_pos) and not self.busy:
            btn_color = btn_hover
        pygame.draw.rect(self.screen, btn_color, self.submit_rect, border_radius=8)
        btn_surf = self.ui_font.render(btn_text, True, TEXT_WHITE)
        self.screen.blit(btn_surf, (
            self.submit_rect.x + (self.submit_rect.width - btn_surf.get_width()) // 2,
            self.submit_rect.y + (self.submit_rect.height - btn_surf.get_height()) // 2
        ))

        # 切换登录/注册
        toggle_text = "已有账号？点击登录" if self.is_register else "没有账号？点击注册"
        toggle_surf = self.font.render(toggle_text, True, ACCENT_CYAN if self.toggle_rect.collidepoint(mouse_pos) else TEXT_GRAY)
        self.screen.blit(toggle_surf, (
            self.toggle_rect.x + (self.toggle_rect.width - toggle_surf.get_width()) // 2,
            self.toggle_rect.y + 2
        ))

        # 状态消息
        if self.status_msg:
            status_surf = self.ui_font.render(self.status_msg, True, self.status_color)
            self.screen.blit(status_surf, (
                (WINDOW_WIDTH - status_surf.get_width()) // 2,
                self.panel_rect.bottom + 20
            ))
            # 错误状态时显示重试提示
            if self.status_color == ACCENT_RED:
                hint_surf = self.font.render("请检查后重新登录", True, TEXT_DIM)
                self.screen.blit(hint_surf, (
                    (WINDOW_WIDTH - hint_surf.get_width()) // 2,
                    self.panel_rect.bottom + 48
                ))

        # 输入验证错误
        if self.error_msg:
            err_surf = self.font.render(self.error_msg, True, ACCENT_YELLOW)
            self.screen.blit(err_surf, (
                (WINDOW_WIDTH - err_surf.get_width()) // 2,
                self.submit_rect.y - 22
            ))

    def _draw_input(self, rect, placeholder, value, active):
        """绘制输入框。"""
        bg = INPUT_ACTIVE if active else INPUT_BG
        border = ACCENT_BLUE if active else INPUT_BORDER
        pygame.draw.rect(self.screen, bg, rect, border_radius=6)
        pygame.draw.rect(self.screen, border, rect, width=1, border_radius=6)

        if value:
            text_surf = self.ui_font.render(value, True, TEXT_WHITE)
            self.screen.blit(text_surf, (rect.x + 12, rect.y + (rect.height - text_surf.get_height()) // 2))
        else:
            ph_surf = self.font.render(placeholder, True, TEXT_DIM)
            self.screen.blit(ph_surf, (rect.x + 12, rect.y + (rect.height - ph_surf.get_height()) // 2))

        # 光标闪烁
        if active and not self.busy:
            import time
            if int(time.time() * 2) % 2 == 0:
                if value:
                    cursor_x = rect.x + 12 + self.ui_font.size(value)[0]
                else:
                    cursor_x = rect.x + 12
                pygame.draw.line(self.screen, TEXT_WHITE,
                                 (cursor_x, rect.y + 8),
                                 (cursor_x, rect.y + rect.height - 8), width=1)

    def handle_event(self, event):
        """处理事件，返回操作结果。
        
        Returns:
            None: 等待更多输入
            ("login", username, password): 用户点击登录
            ("register", username, password): 用户点击注册
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 点击输入框切换焦点
            if self.user_rect.collidepoint(event.pos):
                self.active_input = "username"
                self.error_msg = ""
            elif self.pass_rect.collidepoint(event.pos):
                self.active_input = "password"
                self.error_msg = ""
            # 点击提交按钮
            elif self.submit_rect.collidepoint(event.pos) and not self.busy:
                return self._validate_and_submit()
            # 点击切换模式
            elif self.toggle_rect.collidepoint(event.pos) and not self.busy:
                self.is_register = not self.is_register
                self.status_msg = ""
                self.error_msg = ""

        elif event.type == pygame.KEYDOWN and not self.busy:
            if event.key == pygame.K_TAB:
                # Tab 切换输入框
                self.active_input = "password" if self.active_input == "username" else "username"
                self.error_msg = ""
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                return self._validate_and_submit()
            elif event.key == pygame.K_BACKSPACE:
                if self.active_input == "username":
                    self.username = self.username[:-1]
                else:
                    self.password = self.password[:-1]
                self.error_msg = ""
            elif event.unicode and event.unicode.isprintable():
                # 限制长度
                if self.active_input == "username" and len(self.username) < 16:
                    self.username += event.unicode
                elif self.active_input == "password" and len(self.password) < 32:
                    self.password += event.unicode
                self.error_msg = ""

        return None

    def _validate_and_submit(self):
        """验证输入并返回操作结果。"""
        username = self.username.strip()
        password = self.password

        if not username or len(username) < 2:
            self.error_msg = "用户名至少 2 个字符"
            return None
        if len(username) > 16:
            self.error_msg = "用户名最多 16 个字符"
            return None
        if self.is_register and password and len(password) < 3:
            self.error_msg = "密码至少 3 个字符"
            return None

        if self.is_register:
            return ("register", username, password)
        else:
            return ("login", username, password)

    def set_status(self, msg, color=TEXT_WHITE):
        """设置状态消息。"""
        self.status_msg = msg
        self.status_color = color

    def set_busy(self, busy):
        """设置忙碌状态。"""
        self.busy = busy

    def _check_server(self):
        """后台线程定时检测服务器是否在线，每5秒检测一次。"""
        import threading, time

        def _ping():
            while not hasattr(self, '_stop_check') or not self._stop_check:
                try:
                    url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/health"
                    req = urllib.request.Request(url, method="GET")
                    resp = urllib.request.urlopen(req, timeout=2)
                    self.server_online = (resp.getcode() == 200)
                except Exception:
                    self.server_online = False
                time.sleep(5)

        t = threading.Thread(target=_ping, daemon=True)
        t.start()


async def do_register(username, password):
    """通过 HTTP POST 注册新玩家（使用标准库，避免额外依赖）。
    
    Returns:
        (True, "") 注册成功
        (False, error_msg) 注册失败
    """
    try:
        url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/register"
        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        # 在线程池中执行同步 HTTP 请求，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=5))
        data = json.loads(response.read().decode("utf-8"))
        if data.get("ok"):
            return (True, "")
        else:
            return (False, data.get("message", "注册失败"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            return (False, body.get("message", f"HTTP {e.code}"))
        except:
            return (False, f"HTTP {e.code}")
    except Exception as e:
        return (False, f"注册请求失败: {e}")

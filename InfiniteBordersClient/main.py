# client/main.py - 薄壳入口（状态管理 + 事件分发 + 组合渲染）
import sys
import os

# 确保父目录在 sys.path 中（用于导入 shared 协议模块）
_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_client_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pygame
import asyncio
import websockets
import json
import urllib.request
import urllib.error
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, HEX_SIZE, COLORS, WS_URL, FPS, MAP_COLS, MAP_ROWS, RES_MAP, SERVER_HOST, SERVER_PORT
from shared.protocol import MsgType, build_packet
from hex_utils import hex_to_pixel, pixel_to_hex, get_hex_vertices_list, get_map_pixel_size, draw_hex

# 拆分后的子模块
from ui_utils import draw_rounded_rect, draw_gradient_rect, draw_button, draw_city_label
from ui.hud import (
    draw_top_bar, draw_message_bar, draw_bottom_nav,
    draw_right_buttons, draw_map_filter, draw_location_bookmark
)
from ui.map_renderer import draw_map, draw_macro_map
from ui.recharge_panel import refresh_recharge_panel as _refresh_recharge_panel, draw_recharge_panel
from ui.hero_panel import draw_recruit_panel, draw_hero_list, draw_hero_detail, get_star_color
from ui.troops_panel import draw_troops_panel, draw_edit_troop_panel
from ui.building_panel import draw_building_panel, draw_building_detail
from ui.report_panel import draw_report_history, draw_detailed_report
from ui.system_panel import (
    refresh_system_panel, draw_system_panel, handle_system_event, handle_system_click
)
from ui.login_screen import LoginScreen, do_register, ACCENT_CYAN, ACCENT_GREEN, ACCENT_RED


class AsyncGameClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("InfiniteBorders - 六边形沙盘")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("simhei", 14)
        self.ui_font = pygame.font.SysFont("simhei", 18)
        self.title_font = pygame.font.SysFont("simhei", 24)

        self.game_map = []
        self.map_dict = {}  # {(x, y): tile_data} 六边形用 dict 比 2d list 更方便
        self.resources = {"wood": 0, "iron": 0, "stone": 0, "grain": 0}
        self.currencies = {"copper": 0, "jade": 0, "tiger_tally": 0}
        self.marches, self.card_packs, self.heroes_list = [], [], []
        self.troops_list = []

        self.report_panel, self.current_panel, self.detail_hero = None, None, None
        self.report_scroll_y, self.hero_scroll_y = 0, 0

        # 账号信息
        self.player_id = None
        self.username = ""
        self._login_error = None  # 登录失败时传递给下一个 LoginScreen
        self.troops_scroll_y = 0
        self.troops_right_scroll_y = 0  # 部队面板右侧武将列表滚动
        self.recruit_scroll_y = 0
        self.available_heroes_scroll_y = 0
        self.detail_tab = 0  # 0=属性页, 1=配点页
        self.panel_buttons = []

        self.zoom = 1.0
        self.camera_x, self.camera_y = 0.0, 0.0
        self.in_macro_map = False

        self.show_map_btns = True
        self.map_filter_open = False
        self.location_open = False
        self.show_levels = True

        self.filter_active = False
        self.f_res = {"WOODS": True, "IRON": True, "STONE": True, "PLAINS": True}
        self.f_lvs = {i: True for i in range(1, 10)}

        self.spawn_pos = (10, 15)
        self.recharge_tab = "jade"
        # 预创建面板遮罩（不透明，避免每帧重新创建 Surface）
        self.panel_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.panel_overlay.fill((15, 15, 22))
        self.exchange_amount = 0

        self.filter_facs = ["全部", "魏", "蜀", "吴", "群", "汉"]
        self.idx_fac = 0
        self.filter_trps = ["全部", "步兵", "骑兵", "弓兵"]
        self.idx_trp = 0
        self.sort_opts = ["稀有度", "等级", "统率", "阵营", "兵种"]
        self.idx_srt = 0

        self.is_dragging, self.drag_start_mouse, self.drag_start_camera = False, (0, 0), (0, 0)
        self.selected_tile, self.msg, self.connected = None, "正在连接...", False
        self.nav_menus = ["武将", "招募", "内政", "势力", "国家", "天下", "排行", "系统", "充值", "部队", "战报"]
        btn_w = WINDOW_WIDTH / len(self.nav_menus)
        self.nav_buttons = [{"name": n, "rect": pygame.Rect(i * btn_w, WINDOW_HEIGHT - 60, btn_w, 60)} for i, n in enumerate(self.nav_menus)]

        self.editing_troop = None
        self.troop_edit_cache = {}  # 本地暂存的部队编辑数据 {"slot1": id/None, "slot2": id/None, "slot3": id/None}
        self.available_heroes = []
        self.rank_up_material = None  # 当前选中的升阶材料武将ID
        self.slot_picker_hero_id = None  # 等待选择位置的武将ID

        # 战报历史
        self.report_history = []  # 战报列表（服务端返回）
        self.report_history_scroll_y = 0

        # 主城建筑系统
        self.buildings_data = []     # 建筑列表（服务端返回）
        self.building_detail = None  # 当前查看的建筑详情
        self.building_scroll_y = 0   # 建筑面板滚动偏移
        self.building_detail_scroll_y = 0  # 建筑详情弹窗内等级列表滚动
        self.building_effects = {}   # 建筑效果汇总（服务端推送）

        # 初始化相机：居中到地图中心格子（洛阳附近）
        center_q, center_r = MAP_COLS // 2, MAP_ROWS // 2
        cx, cy = hex_to_pixel(center_q, center_r, HEX_SIZE)
        self.zoom = 0.5
        self.camera_x = WINDOW_WIDTH / 2 - cx * self.zoom
        self.camera_y = WINDOW_HEIGHT / 2 - cy * self.zoom

        # WebSocket 引用（network_loop 中赋值）
        self.ws = None

    # ====== 兼容旧 _draw_* 方法的薄封装（子模块已改用 ui_utils 的独立函数）======

    def _draw_rounded_rect(self, surface, color, rect, radius=8, alpha=255):
        draw_rounded_rect(surface, color, rect, radius, alpha)

    def _draw_gradient_rect(self, surface, rect, color_top, color_bot, radius=8):
        draw_gradient_rect(surface, rect, color_top, color_bot, radius)

    def _draw_button(self, rect, text, color, button_list, font=None, **kwargs):
        if font is None:
            font = self.font
        draw_button(self.screen, rect, text, color, button_list, font, **kwargs)

    def _draw_city_label(self, cx, cy, hex_s, city_type, city_name):
        draw_city_label(self.screen, cx, cy, hex_s, city_type, city_name, self.ui_font)

    # ====== 数据方法 ======

    def build_map_dict(self, data):
        """从服务端数据构建 map_dict"""
        self.game_map = data
        self.map_dict = {}
        for t in data:
            self.map_dict[(t["x"], t["y"])] = t

    def refresh_recharge_panel(self):
        """代理到 recharge_panel 模块"""
        _refresh_recharge_panel(self)

    def open_panel(self, panel_name):
        self.current_panel = panel_name
        self.panel_buttons = []
        self.map_filter_open = False
        self.location_open = False
        if panel_name == "recharge":
            self.exchange_amount = 0
            self.refresh_recharge_panel()
        elif panel_name == "recruit":
            self.recruit_scroll_y = 0
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_PACKS, {}))))
        elif panel_name == "report_history":
            self.report_history_scroll_y = 0
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_REPORT_HISTORY, {}))))
        elif panel_name == "hero":
            self.hero_scroll_y = 0
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_HEROES, {}))))
            # 同时请求部队数据，用于判断武将"已上阵/未上阵"状态
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_TROOPS, {}))))
        elif panel_name == "troops":
            self.troops_scroll_y = 0
            self.troops_right_scroll_y = 0
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_TROOPS, {}))))
            # 部队面板右侧需要 heroes_list 来显示已上阵/未上阵武将，每次都刷新
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_HEROES, {}))))
        elif panel_name == "building":
            self.building_scroll_y = 0
            asyncio.create_task(self.ws.send(json.dumps(build_packet(MsgType.REQ_BUILDINGS, {}))))
        elif panel_name == "system":
            # 查询是否有密码（用于修改密码页面提示）
            refresh_system_panel(self)
            self._check_has_password()
        elif panel_name == "edit_troop":
            self.available_heroes_scroll_y = 0
            if not self.editing_troop:
                self.current_panel = None
                return
            # 创建本地暂存副本（不立即发协议，确定时一次性提交）
            self.troop_edit_cache = {
                "slot1": self.editing_troop.get("slot1"),
                "slot2": self.editing_troop.get("slot2"),
                "slot3": self.editing_troop.get("slot3"),
            }
            # 收集所有部队中已上阵的武将ID（排除当前编辑部队）
            all_used_ids = set()
            all_used_names = set()  # 跨部队已上阵的武将名称
            for t in self.troops_list:
                if t["id"] != self.editing_troop["id"]:
                    for s in range(1, 4):
                        sid = t.get(f"slot{s}")
                        if sid:
                            all_used_ids.add(sid)
                            hero = next((h for h in self.heroes_list if h["id"] == sid), None)
                            if hero:
                                all_used_names.add(hero["name"])
            # 再排除当前部队暂存中占用的武将ID和名称
            for i in range(1, 4):
                sid = self.troop_edit_cache.get(f"slot{i}")
                if sid:
                    all_used_ids.add(sid)
                    hero = next((h for h in self.heroes_list if h["id"] == sid), None)
                    if hero:
                        all_used_names.add(hero["name"])
            # 排除已上阵的武将 + 跨部队同名的武将
            self.available_heroes = [h for h in self.heroes_list if h["id"] not in all_used_ids and h["name"] not in all_used_names]

    # ====== 事件处理（保留原逻辑，难以进一步拆分）======

    def handle_events(self, ws):
        mouse_pos = pygame.mouse.get_pos()
        mouse_down = pygame.mouse.get_pressed()[0]
        ui_hovered = (mouse_pos[1] < 65 or mouse_pos[1] > WINDOW_HEIGHT - 60 or
                      self.current_panel or self.report_panel or self.map_filter_open or self.location_open)

        btn_y, btn_r = 75, 25
        b4_pos = (WINDOW_WIDTH - 40, btn_y)
        b3_pos = (WINDOW_WIDTH - 100, btn_y)
        b2_pos = (WINDOW_WIDTH - 160, btn_y)
        b1_pos = (WINDOW_WIDTH - 220 if self.show_map_btns else WINDOW_WIDTH - 100, btn_y)

        panel_action_done = False  # 防止同一帧内重复处理面板按钮

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                # 系统面板输入拦截（用户名/密码输入框）
                if self.current_panel == "system":
                    if handle_system_event(self, event):
                        continue
                # 空格出征
                elif event.key == pygame.K_SPACE and self.selected_tile and not ui_hovered and not self.in_macro_map:
                    if self.troops_list:
                        troop_id = self.troops_list[0]["id"]
                        asyncio.create_task(ws.send(json.dumps(
                            build_packet(MsgType.CMD_MARCH, {"x": self.selected_tile["x"], "y": self.selected_tile["y"],
                                                             "troop_id": troop_id}))))
                    else:
                        self.msg = "没有可用部队！"

            elif event.type == pygame.MOUSEWHEEL:
                if self.in_macro_map:
                    if event.y > 0:
                        self.in_macro_map = False
                        self.zoom = 0.2
                        self.zoom = 0.5
                elif self.report_panel:
                    self.report_scroll_y = min(0, self.report_scroll_y + event.y * 30)
                elif self.current_panel == "hero" and not getattr(self, "detail_hero", None):
                    self.hero_scroll_y = min(0, self.hero_scroll_y + event.y * 50)
                elif self.current_panel == "troops" and not getattr(self, "detail_hero", None):
                    # 根据鼠标位置决定滚动左侧部队列表还是右侧武将列表
                    left_w = 420
                    panel_left = 80
                    panel_right = panel_left + 420 + 20  # 右侧起始x
                    mx, my = pygame.mouse.get_pos()
                    if mx >= panel_right:
                        self.troops_right_scroll_y = min(0, self.troops_right_scroll_y + event.y * 40)
                    else:
                        self.troops_scroll_y = min(0, self.troops_scroll_y + event.y * 50)
                elif self.current_panel == "edit_troop" and not getattr(self, "detail_hero", None):
                    self.available_heroes_scroll_y = min(0,
                                                         getattr(self, "available_heroes_scroll_y", 0) + event.y * 35)
                elif self.current_panel == "recruit" and not getattr(self, "detail_hero", None):
                    self.recruit_scroll_y = min(0, self.recruit_scroll_y + event.y * 50)
                elif self.current_panel == "report_history" and not self.report_panel:
                    self.report_history_scroll_y = min(0, self.report_history_scroll_y + event.y * 40)
                elif self.current_panel == "building":
                    if self.building_detail:
                        self.building_detail_scroll_y = min(0, self.building_detail_scroll_y + event.y * 25)
                    else:
                        self.building_scroll_y = min(0, self.building_scroll_y + event.y * 50)
                elif not ui_hovered:
                    old_zoom = self.zoom
                    self.zoom += event.y * 0.1
                    if self.zoom <= 0.15:
                        self.in_macro_map = True
                        self.zoom = 0.15
                    else:
                        self.zoom = min(self.zoom, 2.5)
                        if self.zoom != old_zoom:
                            # 以当前鼠标位置为锚点缩放
                            mx, my = pygame.mouse.get_pos()
                            self.camera_x = mx - (mx - self.camera_x) * (self.zoom / old_zoom)
                            self.camera_y = my - (my - self.camera_y) * (self.zoom / old_zoom)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.report_panel:
                    self.report_panel = None
                    continue

                if self.in_macro_map:
                    if getattr(self, "macro_close_rect", None) and self.macro_close_rect.collidepoint(event.pos):
                        self.in_macro_map = False
                        self.zoom = 0.5
                    elif event.pos[1] > 50 and event.pos[1] < WINDOW_HEIGHT - 60:
                        # 用与 draw_macro_map 相同的缩放逻辑
                        TOP_MARGIN = 50
                        BOT_MARGIN = 60
                        avail_w = WINDOW_WIDTH - 20
                        avail_h = WINDOW_HEIGHT - TOP_MARGIN - BOT_MARGIN - 10
                        m_hex_base = 5
                        base_pw, base_ph = get_map_pixel_size(m_hex_base, MAP_COLS, MAP_ROWS)
                        scale = min(avail_w / base_pw, avail_h / base_ph, 1.0)
                        m_hex = m_hex_base * scale
                        map_pw, map_ph = get_map_pixel_size(m_hex, MAP_COLS, MAP_ROWS)
                        ox = (WINDOW_WIDTH - map_pw) / 2
                        oy = TOP_MARGIN + (avail_h - map_ph) / 2
                        macro_wx = event.pos[0] - ox
                        macro_wy = event.pos[1] - oy
                        q, r = pixel_to_hex(macro_wx, macro_wy, m_hex)
                        if 0 <= q < MAP_COLS and 0 <= r < MAP_ROWS and (q, r) in self.map_dict:
                            self.selected_tile = self.map_dict[(q, r)]
                            self.in_macro_map = False
                            self.zoom = 0.5
                            cx, cy = hex_to_pixel(q, r, HEX_SIZE)
                            self.camera_x = WINDOW_WIDTH / 2 - cx * self.zoom
                            self.camera_y = WINDOW_HEIGHT / 2 - cy * self.zoom
                    return

                # 面板打开时，忽略右侧四个地图控制按钮（防止穿透）
                if self.current_panel:
                    pass
                else:
                    # 右侧按钮
                    d1 = (event.pos[0] - b1_pos[0]) ** 2 + (event.pos[1] - b1_pos[1]) ** 2
                    d2 = (event.pos[0] - b2_pos[0]) ** 2 + (event.pos[1] - b2_pos[1]) ** 2
                    d3 = (event.pos[0] - b3_pos[0]) ** 2 + (event.pos[1] - b3_pos[1]) ** 2
                    d4 = (event.pos[0] - b4_pos[0]) ** 2 + (event.pos[1] - b4_pos[1]) ** 2
                    if d4 < btn_r ** 2:
                        # 定位（返回主城）
                        cx, cy = hex_to_pixel(*self.spawn_pos, HEX_SIZE)
                        self.camera_x = WINDOW_WIDTH / 2 - cx * self.zoom
                        self.camera_y = WINDOW_HEIGHT / 2 - cy * self.zoom
                        return
                    if d1 < btn_r ** 2:
                        # 展开/收起
                        self.show_map_btns = not self.show_map_btns
                        return
                    if self.show_map_btns:
                        if d2 < btn_r ** 2:
                            # 筛选
                            self.map_filter_open = not self.map_filter_open
                            self.location_open = False
                            return
                        if d3 < btn_r ** 2:
                            # 地图（宏观）
                            self.in_macro_map = True
                            self.zoom = 0.15
                            return

                # 筛选弹窗内的地形复选框（面板打开时不处理）
                if self.map_filter_open and not self.current_panel:
                    fp_rect = pygame.Rect(WINDOW_WIDTH - 265, 115, 250, 300)
                    if fp_rect.collidepoint(event.pos):
                        rx = fp_rect.x + 10
                        for i, (k, name, c) in enumerate([
                            ("WOODS", "森林", (80, 160, 80)), ("IRON", "铁矿", (160, 160, 180)),
                            ("STONE", "石料", (180, 150, 110)), ("PLAINS", "平原", (160, 180, 100)),
                        ]):
                            box = pygame.Rect(rx, fp_rect.y + 45 + i * 32, 22, 22)
                            if box.collidepoint(event.pos):
                                self.f_res[k] = not self.f_res[k]
                                self.filter_active = any(self.f_res.values())
                                return
                        for lv in range(1, 10):
                            bx = rx + 10 + (lv - 1) % 5 * 46
                            by = fp_rect.y + 195 + (lv - 1) // 5 * 35
                            box = pygame.Rect(bx, by, 40, 28)
                            if box.collidepoint(event.pos):
                                self.f_lvs[lv] = not self.f_lvs[lv]
                                return
                        return

                # 定位弹窗内按钮（面板打开时不处理）
                if self.location_open and not self.current_panel:
                    lp_rect = pygame.Rect(WINDOW_WIDTH - 265, 115, 250, 210)
                    if lp_rect.collidepoint(event.pos):
                        presets = [
                            ("洛阳", (60, 60)), ("邺城", (58, 35)), ("成都", (24, 67)),
                            ("建业", (81, 69)), ("长安", (50, 42)), ("许昌", (63, 49)),
                        ]
                        for i, (_, (pq, pr)) in enumerate(presets):
                            p_btn = pygame.Rect(lp_rect.x + 15 + (i % 3) * 78, lp_rect.y + 45 + (i // 3) * 50, 70, 38)
                            if p_btn.collidepoint(event.pos):
                                cx, cy = hex_to_pixel(pq, pr, HEX_SIZE)
                                self.camera_x = WINDOW_WIDTH / 2 - cx * self.zoom
                                self.camera_y = WINDOW_HEIGHT / 2 - cy * self.zoom
                                self.location_open = False
                                return
                    return

                # 顶部资源栏或底部导航栏点击（面板打开时只处理底部导航）
                bg_rect = pygame.Rect(0, 0, WINDOW_WIDTH, 65)

                if bg_rect.collidepoint(event.pos) and not self.current_panel:
                    # 顶栏点击——展开定位面板
                    self.location_open = not self.location_open
                    self.map_filter_open = False
                    return

                # 面板打开时，优先检查面板内按钮（不限位置）
                panel_action_done = False
                panel_rect = None
                if self.current_panel:
                    # 统一面板区域：用于判断点击是否在面板外
                    panel_rect = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
                    if self.current_panel == "recharge":
                        panel_rect = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
                    elif self.current_panel == "recruit":
                        panel_rect = pygame.Rect(100, 100, WINDOW_WIDTH - 200, WINDOW_HEIGHT - 300)

                if self.current_panel and self.panel_buttons:
                    for btn in self.panel_buttons:
                        if btn.get("rect") and btn["rect"].collidepoint(event.pos):
                            act = btn.get("action")
                            if act == "close":
                                self.current_panel = None
                                self.editing_troop = None
                                self.slot_picker_hero_id = None
                            panel_action_done = True
                            return
                    # 面板打开但没命中任何按钮：检查是否点击在面板外
                    if panel_rect and not panel_rect.collidepoint(event.pos) and event.pos[1] < WINDOW_HEIGHT - 60:
                        self.current_panel = None
                        self.editing_troop = None
                        self.building_detail = None
                        self.slot_picker_hero_id = None
                        return

                # 底部导航栏
                nav_clicked = False
                if event.pos[1] > WINDOW_HEIGHT - 60:
                    # 再检查底部导航栏按钮（仅在面板未打开时）
                    if not self.current_panel:
                        nav_name_map = {
                            "充值": "recharge", "招募": "recruit", "武将": "hero",
                            "部队": "troops", "内政": "building", "战报": "report_history",
                            "系统": "system",
                        }
                        for btn in self.nav_buttons:
                            if btn["rect"].collidepoint(event.pos):
                                panel = nav_name_map.get(btn["name"])
                                if panel:
                                    self.open_panel(panel)
                                nav_clicked = True
                                break

                    if not nav_clicked and not bg_rect.collidepoint(event.pos):
                        self.current_panel = None
                        self.editing_troop = None
                    return

                if not ui_hovered:
                    self.is_dragging, self.drag_start_mouse, self.drag_start_camera = True, event.pos, (self.camera_x,
                                                                                                        self.camera_y)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.is_dragging = False
                if abs(event.pos[0] - self.drag_start_mouse[0]) < 5 and abs(
                        event.pos[1] - self.drag_start_mouse[1]) < 5 and not ui_hovered and not self.in_macro_map:
                    # 屏幕坐标 → 世界坐标 → 六边形格子坐标
                    world_x = (event.pos[0] - self.camera_x) / self.zoom
                    world_y = (event.pos[1] - self.camera_y) / self.zoom
                    q, r = pixel_to_hex(world_x, world_y, HEX_SIZE)
                    if 0 <= q < MAP_COLS and 0 <= r < MAP_ROWS and (q, r) in self.map_dict:
                        self.selected_tile = self.map_dict[(q, r)]
                        # 视口裁剪时确保选中格子可见：居中相机到该格子
                        cx, cy = hex_to_pixel(q, r, HEX_SIZE)
                        self.camera_x = WINDOW_WIDTH / 2 - cx * self.zoom
                        self.camera_y = WINDOW_HEIGHT / 2 - cy * self.zoom

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                self.camera_x, self.camera_y = self.drag_start_camera[0] + (event.pos[0] - self.drag_start_mouse[0]), \
                                               self.drag_start_camera[1] + (event.pos[1] - self.drag_start_mouse[1])


        # 面板按钮点击（统一处理所有面板的按钮事件）
        # 使用 self.mouse_just_down 防止按住鼠标持续触发
        if mouse_down and not getattr(self, '_prev_mouse_down', False) and not panel_action_done:
            for btn in self.panel_buttons:
                if btn.get("rect") and btn["rect"].collidepoint(pygame.mouse.get_pos()):
                    act = btn.get("action")
                    if not act:
                        continue
                    if act == "close":
                        self.current_panel = None
                        self.editing_troop = None
                        self.slot_picker_hero_id = None
                    elif act and act.startswith("sys_") or act == "logout":
                        if handle_system_click(self, act):
                            # 退出登录
                            self.current_panel = None
                            self._logout_requested = True
                    elif act == "tab_jade":
                        self.recharge_tab = "jade"
                        self.exchange_amount = 0
                        self.refresh_recharge_panel()
                    elif act == "tab_tiger":
                        self.recharge_tab = "tiger"
                        self.exchange_amount = 0
                        self.refresh_recharge_panel()
                    elif act == "recharge":
                        amount = btn.get("amount")
                        if amount is not None:
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.CMD_RECHARGE, {"amount": amount}))))
                    elif act == "add_100":
                        self.exchange_amount = min(self.currencies["jade"], self.exchange_amount + 100)
                    elif act == "add_1000":
                        self.exchange_amount = min(self.currencies["jade"], self.exchange_amount + 1000)
                    elif act == "add_max":
                        self.exchange_amount = self.currencies["jade"]
                    elif act == "clear":
                        self.exchange_amount = 0
                    elif act == "exchange":
                        if self.exchange_amount > 0:
                            asyncio.create_task(ws.send(json.dumps(
                                build_packet(MsgType.CMD_EXCHANGE, {"amount": self.exchange_amount}))))
                            self.exchange_amount = 0
                    elif act == "recruit":
                        pack_id = btn.get("pack_id")
                        if pack_id is not None:
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.CMD_RECRUIT, {"pack_id": pack_id}))))
                    elif act == "cycle_fac":
                        self.idx_fac = (self.idx_fac + 1) % len(self.filter_facs)
                        self.open_panel("hero")
                    elif act == "cycle_trp":
                        self.idx_trp = (self.idx_trp + 1) % len(self.filter_trps)
                        self.open_panel("hero")
                    elif act == "cycle_srt":
                        self.idx_srt = (self.idx_srt + 1) % len(self.sort_opts)
                        self.open_panel("hero")
                    elif act == "edit_troop":
                        troop_id = btn.get("troop_id")
                        if troop_id is not None:
                            self.editing_troop = next((t for t in self.troops_list if t["id"] == troop_id), None)
                            self.open_panel("edit_troop")
                    elif act == "remove_hero":
                        slot = btn.get("slot")
                        if slot is not None:
                            # 本地暂存：清空槽位，将被替换的武将加回可用列表
                            old_hero_id = self.troop_edit_cache.get(f"slot{slot}")
                            self.troop_edit_cache[f"slot{slot}"] = None
                            if old_hero_id and old_hero_id not in [
                                self.troop_edit_cache.get(f"slot{i}") for i in range(1, 4)
                            ]:
                                old_hero = next((h for h in self.heroes_list if h["id"] == old_hero_id), None)
                                if old_hero and old_hero not in self.available_heroes:
                                    self.available_heroes.append(old_hero)
                    elif act == "add_hero":
                        slot = btn.get("slot")
                        if slot is not None and self.available_heroes:
                            hero = self.available_heroes[0]
                            # 同名武将检查：同部队内不允许同名
                            for i in range(1, 4):
                                if i == slot:
                                    continue
                                other_id = self.troop_edit_cache.get(f"slot{i}")
                                if other_id:
                                    other = next((h for h in self.heroes_list if h["id"] == other_id), None)
                                    if other and other["name"] == hero["name"]:
                                        self.msg = f"部队中已有同名武将【{hero['name']}】！"
                                        return
                            # 本地暂存：将第一个可用武将放入槽位
                            hero = self.available_heroes.pop(0)
                            self.troop_edit_cache[f"slot{slot}"] = hero["id"]
                    elif act == "assign_hero":
                        # 弹出位置选择弹窗
                        hero_id = btn.get("hero_id")
                        if hero_id is not None:
                            self.slot_picker_hero_id = hero_id
                    elif act == "pick_slot":
                        slot = btn.get("slot")
                        hero_id = self.slot_picker_hero_id
                        if hero_id is not None and slot is not None:
                            # 同名武将检查：同部队内不允许同名
                            new_hero = next((h for h in self.heroes_list if h["id"] == hero_id), None)
                            if new_hero:
                                for i in range(1, 4):
                                    if i == slot:
                                        continue
                                    other_id = self.troop_edit_cache.get(f"slot{i}")
                                    if other_id:
                                        other = next((h for h in self.heroes_list if h["id"] == other_id), None)
                                        if other and other["name"] == new_hero["name"]:
                                            self.msg = f"部队中已有同名武将【{new_hero['name']}】！"
                                            self.slot_picker_hero_id = None
                                            break
                                else:
                                    # 本地暂存：将武将放入选定槽位
                                    old_hero_id = self.troop_edit_cache.get(f"slot{slot}")
                                    self.troop_edit_cache[f"slot{slot}"] = hero_id
                                    # 将被替换的武将加回可用列表
                                    if old_hero_id and old_hero_id not in [
                                        self.troop_edit_cache.get(f"slot{i}") for i in range(1, 4)
                                    ]:
                                        old_hero = next((h for h in self.heroes_list if h["id"] == old_hero_id), None)
                                        if old_hero and old_hero not in self.available_heroes:
                                            self.available_heroes.append(old_hero)
                                    # 从可用列表移除已选武将
                                    self.available_heroes = [h for h in self.available_heroes if h["id"] != hero_id]
                                    self.slot_picker_hero_id = None
                    elif act == "quick_assign":
                        # 从部队面板快速配置——打开编辑面板
                        hero_id = btn.get("hero_id")
                        if hero_id is not None:
                            if self.troops_list:
                                troop = next((t for t in self.troops_list if t["id"] == self.troops_list[0]["id"]), None)
                                if troop:
                                    self.editing_troop = troop
                                    self.slot_picker_hero_id = None
                                    self.open_panel("edit_troop")
                            else:
                                self.msg = "没有可用部队！"
                    elif act == "cancel_slot_pick":
                        self.slot_picker_hero_id = None
                    elif act == "confirm_troop_edit":
                        # 确定按钮：一次性提交本地暂存到服务端
                        cache = self.troop_edit_cache
                        asyncio.create_task(ws.send(json.dumps(build_packet(MsgType.CMD_EDIT_TROOP, {
                            "troop_id": self.editing_troop["id"],
                            "slot1": cache.get("slot1"),
                            "slot2": cache.get("slot2"),
                            "slot3": cache.get("slot3")
                        }))))
                        # 同步本地数据并刷新部队列表
                        self.editing_troop["slot1"] = cache.get("slot1")
                        self.editing_troop["slot2"] = cache.get("slot2")
                        self.editing_troop["slot3"] = cache.get("slot3")
                        self.slot_picker_hero_id = None
                        self.open_panel("troops")  # 会发 REQ_TROOPS 请求刷新数据
                        self.msg = "部队配置已保存！"
                    elif act == "close_detail":
                        self.detail_hero = None
                    elif act == "view_hero":
                        hero_id = btn.get("hero_id")
                        if hero_id is not None:
                            self.detail_hero = next((h for h in self.heroes_list if h["id"] == hero_id), None)
                    # --- 主城建筑系统按钮 ---
                    elif act == "building_detail":
                        building_key = btn.get("building_key")
                        if building_key:
                            self.building_detail = None  # 清空旧数据
                            self.building_detail_scroll_y = 0
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.REQ_BUILDING_DETAIL, {"building_key": building_key}))))
                    elif act == "upgrade_building":
                        building_key = btn.get("building_key")
                        if building_key:
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.CMD_UPGRADE_BUILDING, {"building_key": building_key}))))
                    elif act == "close_building_detail":
                        self.building_detail = None
                    elif act == "cheat_lvl":
                        hero_id = btn.get("hero_id")
                        if hero_id is not None:
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.CMD_CHEAT_LVL, {"hero_id": hero_id}))))
                    elif act == "rank_up":
                        hero_id = btn.get("hero_id")
                        if hero_id is not None:
                            material_id = getattr(self, 'rank_up_material', None)
                            asyncio.create_task(
                                ws.send(json.dumps(build_packet(MsgType.CMD_RANK_UP, {"hero_id": hero_id, "material_id": material_id}))))
                            self.rank_up_material = None
                    elif act == "select_material":
                        self.rank_up_material = btn.get("material_id")
                    elif act == "add_point":
                        hero_id = btn.get("hero_id")
                        attr = btn.get("attr")
                        if hero_id and attr:
                            asyncio.create_task(ws.send(json.dumps(build_packet(MsgType.CMD_ADD_POINT, {"hero_id": hero_id, "attr": attr}))))
                    elif act == "sub_point":
                        hero_id = btn.get("hero_id")
                        attr = btn.get("attr")
                        if hero_id and attr:
                            asyncio.create_task(ws.send(json.dumps(build_packet(MsgType.CMD_SUB_POINT, {"hero_id": hero_id, "attr": attr}))))
                    elif act == "max_point":
                        hero_id = btn.get("hero_id")
                        attr = btn.get("attr")
                        if hero_id and attr:
                            asyncio.create_task(ws.send(json.dumps(build_packet(MsgType.CMD_MAX_POINT, {"hero_id": hero_id, "attr": attr}))))
                    elif act == "tab_attr":
                        self.detail_tab = 0
                    elif act == "tab_points":
                        self.detail_tab = 1

        # 战报历史列表点击处理（同样使用边缘检测防重复触发）
        if self.current_panel == "report_history" and not self.report_panel:
            if mouse_down and not getattr(self, '_prev_mouse_down', False) and not panel_action_done:
                mpos = pygame.mouse.get_pos()
                rh_panel = pygame.Rect(80, 80, WINDOW_WIDTH - 160, WINDOW_HEIGHT - 200)
                list_start_y = rh_panel.y + 45
                item_h = 65
                if rh_panel.collidepoint(mpos) and mpos[1] >= list_start_y:
                    for i, rpt in enumerate(self.report_history):
                        iy = list_start_y + 8 + i * (item_h + 5) + self.report_history_scroll_y
                        if pygame.Rect(rh_panel.x + 15, iy, rh_panel.width - 30, item_h).collidepoint(mpos):
                            # 打开详细战报（复用现有 report_panel 渲染逻辑）
                            self.report_panel = {
                                "x": rpt["tile_x"],
                                "y": rpt["tile_y"],
                                "is_victory": rpt["is_victory"],
                                "report": rpt["report"]
                            }
                            self.report_scroll_y = 0

        # 记录当前帧鼠标状态，下一帧用于边缘检测
        self._prev_mouse_down = mouse_down

    def draw(self):
        if self.in_macro_map:
            draw_macro_map(self.screen, self, self.title_font, self.ui_font, self.font)
            return

        # 1. 绘制地图
        draw_map(self.screen, self, self.font, self.ui_font)

        # 2. HUD 层
        m_pos = pygame.mouse.get_pos()
        m_prs = pygame.mouse.get_pressed()[0]
        draw_top_bar(self.screen, self, self.ui_font, self.font)
        draw_message_bar(self.screen, self, self.ui_font)
        draw_bottom_nav(self.screen, self, m_pos, m_prs, self.ui_font, self.font)
        draw_right_buttons(self.screen, self, m_pos, m_prs, self.ui_font, self.font) if not self.current_panel else None
        if self.map_filter_open and not self.current_panel:
            draw_map_filter(self.screen, self, m_pos, self.ui_font, self.font)
        if self.location_open and not self.current_panel:
            draw_location_bookmark(self.screen, self, m_pos, self.ui_font, self.font)

        # 3. 面板遮罩层（面板打开时，先画不透明遮罩盖住地图和HUD半透明区域）
        if self.current_panel or self.report_panel:
            self.screen.blit(self.panel_overlay, (0, 0))

        # 4. 面板层
        if self.current_panel == "recharge":
            draw_recharge_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "recruit":
            draw_recruit_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "hero":
            if self.detail_hero:
                draw_hero_detail(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
            else:
                draw_hero_list(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "troops":
            draw_troops_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "edit_troop":
            draw_edit_troop_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "building":
            draw_building_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
            if self.building_detail:
                draw_building_detail(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "report_history" and not self.report_panel:
            draw_report_history(self.screen, self, self.font, self.ui_font, self.title_font)
        elif self.current_panel == "system":
            draw_system_panel(self.screen, self, m_pos, self.font, self.ui_font, self.title_font)

        # 5. 战报浮层
        if self.report_panel:
            draw_detailed_report(self.screen, self, self.ui_font, self.font)

        # 6. 遮罩模式下重绘 HUD（顶部栏+底部导航），保持在最上层
        if self.current_panel or self.report_panel:
            draw_top_bar(self.screen, self, self.ui_font, self.font)
            draw_message_bar(self.screen, self, self.ui_font)
            draw_bottom_nav(self.screen, self, m_pos, m_prs, self.ui_font, self.font)

    # ====== 网络消息处理 ======

    def _handle_login(self, data):
        if isinstance(data, dict):
            self.player_id = data.get("player_id")
            self.username = data.get("username", "")
            self.resources.update(data.get("resources", {}))
            self.currencies.update(data.get("currencies", {}))
            # 登录时不再包含地图数据，通过 req_map 单独请求
            # 设置出生点
            spawn = data.get("spawn")
            if spawn:
                self.spawn_pos = (spawn["x"], spawn["y"])
                # 初始化相机到出生点
                sx, sy = hex_to_pixel(self.spawn_pos[0], self.spawn_pos[1], HEX_SIZE)
                self.camera_x = WINDOW_WIDTH / 2 - sx * self.zoom
                self.camera_y = WINDOW_HEIGHT / 2 - sy * self.zoom
            self.connected = True
            self.msg = "已连接服务器"

    def _check_has_password(self):
        """检查当前账号是否有密码（用于系统面板提示）。"""
        try:
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/players"
            resp = urllib.request.urlopen(url, timeout=3)
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                me = next((p for p in data if p.get("id") == self.player_id), None)
                self._has_password = bool(me.get("has_password", False)) if me else False
            else:
                self._has_password = False
        except Exception:
            self._has_password = False

    def _handle_sync_state(self, data):
        if isinstance(data, dict):
            self.resources.update(data.get("resources", {}))
            self.currencies.update(data.get("currencies", {}))
            if "marches" in data:
                self.marches = data["marches"]

    def _handle_sync_map(self, data):
        """增量更新地图（服务端只推送变化的格子）"""
        if isinstance(data, list):
            for tile in data:
                key = (tile["x"], tile["y"])
                # 更新 game_map 中对应格子的数据（保留完整字段）
                existing = self.map_dict.get(key)
                if existing:
                    existing.update(tile)
                else:
                    # 未知新格子（正常情况下不应发生，保险起见追加）
                    self.game_map.append(tile)
                    self.map_dict[key] = tile

    def _handle_res_packs(self, data):
        self.card_packs = data

    def _handle_res_heroes(self, data):
        self.heroes_list = data
        if getattr(self, "detail_hero", None):
            for h in data:
                if h["id"] == self.detail_hero["id"]:
                    self.detail_hero = h
                    break

    def _handle_res_troops(self, data):
        self.troops_list = data
        if self.current_panel == "edit_troop" and self.editing_troop:
            # 同步更新编辑中的部队数据（保留滚动位置和暂存状态）
            updated = next((t for t in data if t["id"] == self.editing_troop["id"]), None)
            if updated:
                self.editing_troop = updated

    def _handle_res_buildings(self, data):
        self.buildings_data = data.get("buildings", [])
        # 如果当前打开了建筑详情弹窗，自动刷新详情数据
        if self.building_detail:
            key = self.building_detail.get("key", "")
            if key:
                self._pending_building_detail_refresh = key

    def _check_pending_building_detail_refresh(self, ws):
        """检查是否需要刷新建筑详情（在下一帧的渲染循环外执行 WebSocket 发送）"""
        key = getattr(self, '_pending_building_detail_refresh', None)
        if key:
            self._pending_building_detail_refresh = None
            asyncio.create_task(
                ws.send(json.dumps(build_packet(MsgType.REQ_BUILDING_DETAIL, {"building_key": key}))))

    def _handle_res_map(self, data):
        """处理地图数据（支持分批传输）。"""
        if not isinstance(data, dict):
            return
        tiles = data.get("tiles", [])
        is_first = data.get("batch", 0) == 0
        if is_first:
            self.game_map = []
            self.map_dict = {}

        for t in tiles:
            key = (t["x"], t["y"])
            self.game_map.append(t)
            self.map_dict[key] = t

        is_done = data.get("done", False)
        if is_done:
            total = len(self.game_map)
            self.msg = f"地图加载完成：{total} 格"
            # 地图加载完后初始化相机到出生点
            sx, sy = hex_to_pixel(self.spawn_pos[0], self.spawn_pos[1], HEX_SIZE)
            self.camera_x = WINDOW_WIDTH / 2 - sx * self.zoom
            self.camera_y = WINDOW_HEIGHT / 2 - sy * self.zoom

    async def network_loop(self, ws):
        """WebSocket 消息接收循环，分发处理各类服务端消息"""
        try:
            async for message in ws:
                packet = json.loads(message)
                msg_type, data = packet.get("type"), packet.get("data")

                if msg_type == MsgType.RES_LOGIN:
                    self._handle_login(data)
                elif msg_type == MsgType.RES_MAP:
                    self._handle_res_map(data)
                elif msg_type == MsgType.SYNC_STATE:
                    self._handle_sync_state(data)
                elif msg_type == "sync_map":
                    self._handle_sync_map(data)
                elif msg_type == MsgType.RES_PACKS:
                    self._handle_res_packs(data)
                elif msg_type == MsgType.RES_HEROES:
                    self._handle_res_heroes(data)
                elif msg_type == MsgType.RES_TROOPS:
                    self._handle_res_troops(data)
                elif msg_type == MsgType.RES_RECRUIT:
                    self.msg = data
                elif msg_type == MsgType.PUSH_REPORT:
                    self.report_panel, self.msg, self.report_scroll_y = data, "主公！收到前线战报！", 0
                elif msg_type == MsgType.RES_REPORT_HISTORY:
                    self.report_history = data.get("reports", [])
                elif msg_type == MsgType.RES_BUILDINGS:
                    self._handle_res_buildings(data)
                    self._check_pending_building_detail_refresh(ws)
                elif msg_type == MsgType.RES_BUILDING_DETAIL:
                    self.building_detail = data
                    self.building_detail_scroll_y = 0
                elif msg_type == MsgType.PUSH_BUILDING_EFFECTS:
                    self.building_effects = data.get("building_effects", {})
                elif msg_type == MsgType.ERROR:
                    self.msg = f"【提示】{data}"
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket 连接关闭: {e.code} - {e.reason}")
            self.connected, self.msg = False, f"连接已关闭: {e.reason}"
        except Exception as e:
            print(f"网络循环异常: {e}")
            import traceback
            traceback.print_exc()
            self.connected, self.msg = False, f"网络错误: {e}"

    # ====== 入口 ======

    async def run(self):
        """主循环：先显示登录界面，登录成功后进入游戏。退出登录后回到登录界面。"""
        while True:
            # ---- 登录阶段 ----
            login = LoginScreen(self.screen, (self.title_font, self.ui_font, self.font))
            # 传递上一次登录失败的消息
            if self._login_error:
                login.set_status(self._login_error, (220, 80, 80))
                self._login_error = None
            login_result = None
            self._logout_requested = False

            # 登录界面事件循环
            while True:
                self.clock.tick(FPS)
                login.draw()
                pygame.display.flip()

                # 先检查退出事件
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        sys.exit()
                    result = login.handle_event(event)
                    if result:
                        login_result = result

                if login_result:
                    action, username, password = login_result

                    if action == "register":
                        login.set_busy(True)
                        login.set_status("正在注册...", ACCENT_CYAN)
                        pygame.display.flip()
                        ok, msg = await do_register(username, password)
                        login.set_busy(False)
                        if ok:
                            login.set_status("注册成功！正在登录...", ACCENT_GREEN)
                            pygame.display.flip()
                            await asyncio.sleep(0.5)
                            # 注册成功后自动登录
                            login_result = ("login", username, password)
                            continue
                        else:
                            login.set_status(msg, ACCENT_RED)
                            login_result = None
                            continue

                    elif action == "login":
                        break  # 退出登录循环，进入游戏

                await asyncio.sleep(0)

            # ---- 连接服务器 ----
            username = login_result[1]
            password = login_result[2]
            login.set_busy(True)
            login.set_status("正在连接服务器...", (220, 220, 225))
            login.draw()
            pygame.display.flip()

            try:
                ws_url = f"{WS_URL}/{username}"
                async with websockets.connect(ws_url, max_size=None) as ws:
                    self.ws = ws

                    # 发送密码验证消息
                    auth_packet = json.dumps({"type": "auth", "data": {"password": password}})
                    await ws.send(auth_packet)

                    # 等待登录响应
                    login_msg = json.loads(await ws.recv())
                    if login_msg.get("type") == MsgType.ERROR:
                        error_text = login_msg.get("data", "登录失败")
                        self._show_login_error(error_text)
                        continue  # 回到外层循环，新 LoginScreen 会显示错误

                    # 处理 res_login
                    login_data = login_msg.get("data", {})
                    if login_data.get("spawn"):
                        self._handle_login(login_data)
                        # 请求地图数据
                        await ws.send(json.dumps(build_packet(MsgType.REQ_MAP, {})))
                    else:
                        self._show_login_error("登录失败：服务器返回数据异常")
                        continue  # 回到外层循环，新 LoginScreen 会显示错误

                    # 启动网络消息循环
                    asyncio.create_task(self.network_loop(ws))

                    # 进入游戏主循环
                    while True:
                        dt = self.clock.tick(FPS) / 1000.0
                        for m in self.marches:
                            m["time_left"] = max(0.0, m["time_left"] - dt)
                        self.handle_events(ws)
                        self.draw()
                        pygame.display.flip()
                        # 检测退出登录
                        if getattr(self, '_logout_requested', False):
                            break
                        await asyncio.sleep(0)
            except Exception as e:
                print(f"连接服务器失败: {e}")
                self._show_login_error(f"无法连接服务器，请检查网络后重试")

            # 连接失败或退出登录，清理状态后回到登录界面
            self.ws = None
            self.connected = False
            self.current_panel = None

    def _show_login_error(self, error_msg):
        """保存登录错误消息，传递给下一个 LoginScreen 显示。"""
        self._login_error = error_msg


if __name__ == "__main__":
    asyncio.run(AsyncGameClient().run())

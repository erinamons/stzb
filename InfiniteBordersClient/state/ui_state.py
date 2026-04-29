"""
UI 状态层 —— 管理所有界面状态（面板/滚动/筛选/编辑/导航按钮/相机）。
不包含渲染逻辑和游戏数据。
"""
import pygame
from client_config import WINDOW_WIDTH, WINDOW_HEIGHT


class UIState:
    """UI 相关状态，独立于游戏数据和渲染逻辑。"""

    def __init__(self):
        # 相机 / 视图
        self.zoom = 0.5
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.in_macro_map = False
        self.show_map_btns = True
        self.show_levels = True
        self.macro_close_rect = None

        # 拖拽
        self.is_dragging = False
        self.drag_start_mouse = (0, 0)
        self.drag_start_camera = (0, 0)

        # 面板
        self.current_panel = None
        self.panel_buttons = []

        # 筛选
        self.map_filter_open = False
        self.location_open = False
        self.filter_active = False
        self.f_res = {"WOODS": True, "IRON": True, "STONE": True, "PLAINS": True}
        self.f_lvs = {i: True for i in range(1, 10)}

        # 武将面板
        self.hero_scroll_y = 0
        self.detail_hero = None
        self.detail_tab = 0           # 0=属性页, 1=配点页
        self.filter_facs = ["全部", "魏", "蜀", "吴", "群", "汉"]
        self.idx_fac = 0
        self.filter_trps = ["全部", "步兵", "骑兵", "弓兵"]
        self.idx_trp = 0
        self.sort_opts = ["稀有度", "等级", "统率", "阵营", "兵种"]
        self.idx_srt = 0
        self.displayed_heroes = []

        # 充值面板
        self.recharge_tab = "jade"
        self.exchange_amount = 0

        # 部队面板
        self.troops_scroll_y = 0
        self.troops_right_scroll_y = 0
        self.editing_troop = None
        self.troop_edit_cache = {}
        self.available_heroes = []
        self.slot_picker_hero_id = None
        self.available_heroes_scroll_y = 0

        # 升阶
        self.rank_up_material = None

        # 招募
        self.recruit_scroll_y = 0

        # 战报
        self.report_scroll_y = 0
        self.report_history_scroll_y = 0

        # 建筑
        self.building_scroll_y = 0
        self.building_detail_scroll_y = 0

        # 底部导航按钮（固定布局）
        self.nav_menus = ["武将", "招募", "内政", "势力", "国家", "天下", "排行", "系统", "充值", "部队", "战报"]
        btn_w = WINDOW_WIDTH / len(self.nav_menus)
        self.nav_buttons = [
            {"name": n, "rect": pygame.Rect(i * btn_w, WINDOW_HEIGHT - 60, btn_w, 60)}
            for i, n in enumerate(self.nav_menus)
        ]

    # ========== 便捷属性 ==========

    @property
    def is_detail_open(self):
        return self.detail_hero is not None

    def ui_hovered(self):
        """检测鼠标是否在 UI 区域内（顶部栏 / 底部栏 / 面板 / 浮窗）。"""
        m_y = pygame.mouse.get_pos()[1]
        return (m_y < 65 or m_y > WINDOW_HEIGHT - 60
                or self.current_panel or self.report_panel
                or self.map_filter_open or self.location_open)

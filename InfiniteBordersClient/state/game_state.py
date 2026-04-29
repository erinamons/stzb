"""
游戏状态数据层 —— 管理所有游戏数据（资源/武将/部队/地图/建筑/战报/行军）。
与 UI 和网络层解耦，只负责数据存储和基础操作。
"""
from hex_utils import hex_to_pixel, pixel_to_hex
from client_config import HEX_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, MAP_COLS, MAP_ROWS


class GameState:
    """游戏核心数据，不包含任何 UI 逻辑。"""

    def __init__(self):
        # 地图数据
        self.game_map = []
        self.map_dict = {}          # {(x, y): tile_data}
        self.selected_tile = None
        self.spawn_pos = (10, 15)

        # 资源 & 货币
        self.resources = {"wood": 0, "iron": 0, "stone": 0, "grain": 0}
        self.currencies = {"copper": 0, "jade": 0, "tiger_tally": 0}

        # 行军
        self.marches = []

        # 武将 & 部队
        self.heroes_list = []
        self.troops_list = []

        # 卡包
        self.card_packs = []

        # 战报
        self.report_panel = None    # 实时推送的战报
        self.report_history = []    # 历史战报列表

        # 建筑系统
        self.buildings_data = []
        self.building_detail = None

        # 连接状态
        self.connected = False
        self.msg = "正在连接..."

    # ========== 地图操作 ==========

    def build_map_dict(self, data):
        """从服务端数据构建 map_dict。"""
        self.game_map = data
        self.map_dict = {}
        for t in data:
            self.map_dict[(t["x"], t["y"])] = t

    def update_map_tile(self, tile):
        """增量更新单个格子（sync_map）。"""
        key = (tile["x"], tile["y"])
        self.map_dict[key] = tile
        for i, gt in enumerate(self.game_map):
            if gt["x"] == tile["x"] and gt["y"] == tile["y"]:
                self.game_map[i] = tile
                break

    # ========== 查询辅助 ==========

    def get_hero_by_id(self, hero_id):
        """根据 ID 查找武将。"""
        return next((h for h in self.heroes_list if h["id"] == hero_id), None)

    def get_troop_by_id(self, troop_id):
        """根据 ID 查找部队。"""
        return next((t for t in self.troops_list if t["id"] == troop_id), None)

    def get_assigned_hero_ids(self, exclude_troop_id=None):
        """获取所有已上阵武将 ID 集合（可选排除某支部队）。"""
        ids = set()
        for t in self.troops_list:
            if t["id"] == exclude_troop_id:
                continue
            for s in range(1, 4):
                sid = t.get(f"slot{s}")
                if sid:
                    ids.add(sid)
        return ids

    def get_displayed_heroes(self, filter_facs, filter_trps, sort_opts, idx_fac, idx_trp, idx_srt):
        """根据筛选/排序条件返回武将列表。"""
        h_view = self.heroes_list
        if filter_facs[idx_fac] != "全部":
            h_view = [h for h in h_view if h["faction"] == filter_facs[idx_fac]]
        if filter_trps[idx_trp] != "全部":
            h_view = [h for h in h_view if h["troop_type"] == filter_trps[idx_trp]]
        srt = sort_opts[idx_srt]
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
        return h_view

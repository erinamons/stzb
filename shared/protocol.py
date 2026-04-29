# shared/protocol.py
# 服务端和客户端共享的通信协议定义（单一权威源）
# 两端均从此文件导入，禁止各自维护副本。

import sys
import os

# 确保父目录在 sys.path 中（支持被服务端和客户端引用）
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)


class MsgType:
    # ---- 基础协议 ----
    CMD_LOGIN = "cmd_login"
    CMD_MARCH = "cmd_march"
    CMD_RECHARGE = "cmd_recharge"
    CMD_EXCHANGE = "cmd_exchange"
    REQ_PACKS = "req_packs"
    RES_PACKS = "res_packs"
    CMD_RECRUIT = "cmd_recruit"
    RES_RECRUIT = "res_recruit"
    SYNC_STATE = "sync_state"
    RES_LOGIN = "res_login"
    PUSH_REPORT = "push_report"
    ERROR = "error"

    # ---- 武将系统 ----
    REQ_HEROES = "req_heroes"
    RES_HEROES = "res_heroes"
    CMD_ADD_POINT = "cmd_add_point"
    CMD_CHEAT_LVL = "cmd_cheat_lvl"
    CMD_RANK_UP = "cmd_rank_up"
    CMD_SUB_POINT = "cmd_sub_point"
    CMD_MAX_POINT = "cmd_max_point"

    # ---- 部队系统 ----
    REQ_TROOPS = "req_troops"
    RES_TROOPS = "res_troops"
    CMD_EDIT_TROOP = "cmd_edit_troop"
    CMD_RECRUIT_TROOPS = "cmd_recruit_troops"

    # ---- 战报系统 ----
    REQ_REPORT_HISTORY = "req_report_history"
    RES_REPORT_HISTORY = "res_report_history"

    # ---- 主城建筑系统 ----
    REQ_BUILDINGS = "req_buildings"
    RES_BUILDINGS = "res_buildings"
    CMD_UPGRADE_BUILDING = "cmd_upgrade_building"
    REQ_BUILDING_DETAIL = "req_building_detail"
    RES_BUILDING_DETAIL = "res_building_detail"
    PUSH_BUILDING_EFFECTS = "push_building_effects"  # 建筑效果汇总推送（升级后服务端主动推）

    # ---- GM 系统 ----
    CMD_RESET_DATABASE = "cmd_reset_database"  # GM重置数据库（需 _gm_token 验证）

    # ---- 地图系统 ----
    REQ_MAP = "req_map"
    RES_MAP = "res_map"


def build_packet(msg_type: str, data: dict) -> dict:
    """构建通信数据包。"""
    return {"type": msg_type, "data": data}

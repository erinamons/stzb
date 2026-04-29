# network.py - WebSocket 网络通信模块
# 从 main.py 的 AsyncGameClient.network_loop() 提取
import sys
import os

_client_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_client_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
import websockets
from shared.protocol import MsgType


async def network_loop(client, ws):
    """WebSocket 消息接收循环，分发处理各类服务端消息。
    
    client: AsyncGameClient 实例（用于读写共享状态）
    ws: websockets 连接对象
    """
    try:
        async for message in ws:
            packet = json.loads(message)
            msg_type, data = packet.get("type"), packet.get("data")

            if msg_type == MsgType.RES_LOGIN:
                _handle_login(client, data)
            elif msg_type == MsgType.RES_MAP:
                _handle_res_map(client, data)
            elif msg_type == MsgType.SYNC_STATE:
                _handle_sync_state(client, data)
            elif msg_type == "sync_map":
                _handle_sync_map(client, data)
            elif msg_type == MsgType.RES_PACKS:
                _handle_res_packs(client, data)
            elif msg_type == MsgType.RES_HEROES:
                _handle_res_heroes(client, data)
            elif msg_type == MsgType.RES_TROOPS:
                _handle_res_troops(client, data)
            elif msg_type == MsgType.RES_RECRUIT:
                client.msg = data
            elif msg_type == MsgType.PUSH_REPORT:
                client.report_panel = data
                client.msg = "主公！收到前线战报！"
                client.report_scroll_y = 0
            elif msg_type == MsgType.RES_REPORT_HISTORY:
                client.report_history = data.get("reports", [])
            elif msg_type == MsgType.RES_BUILDINGS:
                _handle_res_buildings(client, data)
            elif msg_type == MsgType.RES_BUILDING_DETAIL:
                client.building_detail = data
                client.building_detail_scroll_y = 0
            elif msg_type == MsgType.ERROR:
                client.msg = f"【提示】{data}"

    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket 连接关闭: {e.code} - {e.reason}")
        client.connected = False
        client.msg = f"连接已关闭: {e.reason}"
    except Exception as e:
        print(f"网络循环异常: {e}")
        import traceback
        traceback.print_exc()
        client.connected = False
        client.msg = f"网络错误: {e}"


def _handle_login(client, data):
    """处理登录响应：初始化资源、相机（地图数据通过 req_map 单独获取）。"""
    from hex_utils import hex_to_pixel
    from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, HEX_SIZE

    client.spawn_pos = (data["spawn"]["x"], data["spawn"]["y"])
    # 初始化相机到出生点
    sx, sy = hex_to_pixel(client.spawn_pos[0], client.spawn_pos[1], HEX_SIZE)
    client.camera_x = WINDOW_WIDTH / 2 - sx * client.zoom
    client.camera_y = WINDOW_HEIGHT / 2 - sy * client.zoom
    client.resources = data.get("resources", client.resources)
    client.currencies = data.get("currencies", client.currencies)
    client.connected = True
    client.msg = "服务器连接成功！"


def _handle_res_map(client, data):
    """处理地图数据响应（支持分批传输）。"""
    tiles = data.get("tiles", [])
    is_first = data.get("batch", 0) == 0
    if is_first:
        client.game_map = []
        client.map_dict = {}

    for t in tiles:
        key = (t["x"], t["y"])
        client.game_map.append(t)
        client.map_dict[key] = t

    is_done = data.get("done", False)
    if is_done:
        total = len(client.game_map)
        client.msg = f"地图加载完成：{total} 格"
        # 地图加载完后重新定位相机到出生点
        from hex_utils import hex_to_pixel
        from client_config import WINDOW_WIDTH, WINDOW_HEIGHT, HEX_SIZE
        sx, sy = hex_to_pixel(client.spawn_pos[0], client.spawn_pos[1], HEX_SIZE)
        client.camera_x = WINDOW_WIDTH / 2 - sx * client.zoom
        client.camera_y = WINDOW_HEIGHT / 2 - sy * client.zoom


def _handle_sync_state(client, data):
    """处理状态同步：资源、货币、行军"""
    client.resources = data["resources"]
    client.currencies = data["currencies"]
    client.marches = data["marches"]


def _handle_sync_map(client, data):
    """处理地图增量更新：只更新变化的格子"""
    for t in data:
        client.map_dict[(t["x"], t["y"])] = t
        # 同时更新 game_map 列表中的对应项
        for i, gt in enumerate(client.game_map):
            if gt["x"] == t["x"] and gt["y"] == t["y"]:
                client.game_map[i] = t
                break


def _handle_res_packs(client, data):
    """处理卡包列表响应"""
    client.card_packs = data
    if client.current_panel == "recruit":
        client.open_panel("recruit")


def _handle_res_heroes(client, data):
    """处理武将列表响应"""
    client.heroes_list = data
    # 如果正在查看武将详情，刷新详情数据
    if getattr(client, "detail_hero", None):
        for h in data:
            if h["id"] == client.detail_hero["id"]:
                client.detail_hero = h
                break
    # 如果正在编辑部队，重新计算可用武将
    if client.current_panel == "edit_troop":
        client.open_panel("edit_troop")


def _handle_res_troops(client, data):
    """处理部队列表响应"""
    client.troops_list = data
    if client.current_panel == "troops":
        client.open_panel("troops")
    elif client.current_panel == "edit_troop" and client.editing_troop:
        # 同步更新编辑中的部队数据（保留滚动位置和暂存状态）
        updated = next((t for t in data if t["id"] == client.editing_troop["id"]), None)
        if updated:
            client.editing_troop = updated


def _handle_res_buildings(client, data):
    """处理建筑列表响应"""
    client.buildings_data = data.get("buildings", [])
    if client.current_panel == "building":
        client.open_panel("building")

# ws_handlers/march_handler.py
# 行军出征处理
from shared.protocol import MsgType, build_packet
from models.schema import Tile, Troop, Hero
from hex_utils import get_neighbors, hex_distance
from core.connection_manager import manager


async def handle_march(username, state, db, db_player, msg_data):
    """处理行军出征请求。"""
    tx, ty = msg_data.get("x"), msg_data.get("y")
    troop_id = msg_data.get("troop_id")
    troop = db.query(Troop).filter(Troop.id == troop_id, Troop.owner_id == db_player.id).first()
    if not troop:
        await manager.send_to(username, build_packet(MsgType.ERROR, "部队不存在"))
        return
    if any(m.get("troop_id") == troop_id for m in state["marches"]):
        await manager.send_to(username, build_packet(MsgType.ERROR, "该部队已在行军"))
        return
    if not any([troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]):
        await manager.send_to(username, build_packet(MsgType.ERROR, "部队没有武将"))
        return

    # 体力检查
    stamina_needed = 10
    insufficient = []
    for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
        if hid:
            hero = db.query(Hero).get(hid)
            if hero and hero.stamina < stamina_needed:
                insufficient.append(hero.name)
    if insufficient:
        await manager.send_to(username, build_packet(MsgType.ERROR, f"{','.join(insufficient)} 体力不足，无法出征"))
        return

    target_tile = db.query(Tile).filter(Tile.x == tx, Tile.y == ty).first()
    if target_tile and target_tile.owner_id == state["id"]:
        await manager.send_to(username, build_packet(MsgType.ERROR, "这块土地已经是你的领地！不要重复出征！"))
        return
    if any(m["target_x"] == tx and m["target_y"] == ty for m in state["marches"]):
        await manager.send_to(username, build_packet(MsgType.ERROR, "已有部队正在前往该目标！"))
        return

    # 出征距离检查
    owned_tiles = {(t.x, t.y) for t in db.query(Tile).filter(Tile.owner_id == state["id"]).all()}
    marchable = False
    for (ox, oy) in owned_tiles:
        if (tx, ty) in get_neighbors(ox, oy):
            marchable = True
            break
    if not marchable:
        await manager.send_to(username, build_packet(MsgType.ERROR, "目标位置超出领地范围，只能向己方领地周围6格出征！"))
        return

    # 所有检查通过，扣除体力
    for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
        if hid:
            hero = db.query(Hero).get(hid)
            if hero:
                hero.stamina = max(0, hero.stamina - stamina_needed)
    db.commit()

    # 计算行军时间
    nearest_owner = min(owned_tiles, key=lambda p: hex_distance(p[0], p[1], tx, ty))
    dist = hex_distance(nearest_owner[0], nearest_owner[1], tx, ty)
    time_needed = max(3.0, dist * 100 / 90)
    state["marches"].append(
        {
            "id": str(__import__('time').time()),
            "troop_id": troop_id,
            "start_x": nearest_owner[0],
            "start_y": nearest_owner[1],
            "target_x": tx,
            "target_y": ty,
            "time_left": time_needed,
            "max_time": time_needed,
        }
    )
    await manager.send_to(
        username, build_packet(MsgType.ERROR, f"🚩 部队已出征！预计抵达需要 {int(time_needed)} 秒。")
    )

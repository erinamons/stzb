# ws_handlers/shop_handlers.py
# 商店相关：卡包列表、充值、兑换
from shared.protocol import MsgType, build_packet
from models.schema import Player, CardPack
from core.connection_manager import manager


async def handle_req_packs(username, db, msg_data):
    """查询卡包列表。"""
    try:
        packs = db.query(CardPack).all()
        await manager.send_to(
            username,
            build_packet(
                MsgType.RES_PACKS,
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "cost_type": p.cost_type,
                        "cost_amount": p.cost_amount,
                    }
                    for p in packs
                ],
            ),
        )
    except Exception as e:
        print(f"获取卡包列表错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, "获取卡包列表失败"))


async def handle_recharge(username, state, db, db_player, msg_data):
    """充值（GM功能）。"""
    try:
        db_player.jade += msg_data.get("amount", 0)
        db.commit()
        state["currencies"]["jade"] = db_player.jade
        await manager.send_to(username, build_packet(MsgType.ERROR, "充值成功！"))
    except Exception as e:
        print(f"充值错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, f"充值失败: {e}"))


async def handle_exchange(username, state, db, db_player, msg_data):
    """玉符兑换虎符。"""
    try:
        amount = msg_data.get("amount", 0)
        if db_player.jade >= amount:
            db_player.jade -= amount
            db_player.tiger_tally += amount
            db.commit()
            state["currencies"]["jade"] = db_player.jade
            state["currencies"]["tiger_tally"] = db_player.tiger_tally
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "玉符不足！请充值。"))
    except Exception as e:
        print(f"兑换错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, f"兑换失败: {e}"))

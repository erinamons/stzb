# ws_handlers/troop_handlers.py
# 部队管理：查询部队列表、编辑部队配置、征兵
from shared.protocol import MsgType, build_packet
from models.schema import Player, Hero, Troop
from core.connection_manager import manager


async def handle_req_troops(username, db, db_player, msg_data):
    """查询玩家部队列表。"""
    try:
        troops = db.query(Troop).filter(Troop.owner_id == db_player.id).all()
        troops_data = []
        for t in troops:
            total_troops = 0
            slot_heroes = {}
            for slot_key, hid in [("slot1", t.slot1_hero_id), ("slot2", t.slot2_hero_id), ("slot3", t.slot3_hero_id)]:
                if hid:
                    hero = db.query(Hero).get(hid)
                    if hero:
                        total_troops += hero.troops
                        slot_heroes[slot_key] = hero.name
                    else:
                        slot_heroes[slot_key] = "不存在"
                else:
                    slot_heroes[slot_key] = None
            troops_data.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "slot1": t.slot1_hero_id,
                    "slot2": t.slot2_hero_id,
                    "slot3": t.slot3_hero_id,
                    "slot1_name": slot_heroes.get("slot1"),
                    "slot2_name": slot_heroes.get("slot2"),
                    "slot3_name": slot_heroes.get("slot3"),
                    "total_troops": total_troops,
                }
            )
        await manager.send_to(username, build_packet(MsgType.RES_TROOPS, troops_data))
    except Exception as e:
        print(f"获取部队列表错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, "获取部队列表失败"))


async def handle_edit_troop(username, db, db_player, msg_data):
    """编辑部队配置（武将编组）。"""
    try:
        troop_id = msg_data.get("troop_id")
        slot1 = msg_data.get("slot1")
        slot2 = msg_data.get("slot2")
        slot3 = msg_data.get("slot3")
        troop = db.query(Troop).filter(Troop.id == troop_id, Troop.owner_id == db_player.id).first()
        if not troop:
            await manager.send_to(username, build_packet(MsgType.ERROR, "部队不存在"))
            return

        def hero_in_other_troop(hero_id, exclude_troop_id):
            if hero_id is None:
                return False
            return (
                db.query(Troop)
                .filter(
                    Troop.owner_id == db_player.id,
                    Troop.id != exclude_troop_id,
                    (Troop.slot1_hero_id == hero_id)
                    | (Troop.slot2_hero_id == hero_id)
                    | (Troop.slot3_hero_id == hero_id),
                )
                .first()
                is not None
            )

        if (
            hero_in_other_troop(slot1, troop_id)
            or hero_in_other_troop(slot2, troop_id)
            or hero_in_other_troop(slot3, troop_id)
        ):
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将已被其他部队使用"))
            return

        # 检查同一部队内是否重复
        slots = [s for s in [slot1, slot2, slot3] if s is not None]
        if len(set(slots)) != len(slots):
            await manager.send_to(username, build_packet(MsgType.ERROR, "部队中不能有重复武将"))
            return

        # 检查跨部队同名武将
        def hero_name_in_other_troop(hero_id, hero_name, exclude_troop_id):
            if hero_id is None or not hero_name:
                return False
            other_troops = db.query(Troop).filter(
                Troop.owner_id == db_player.id,
                Troop.id != exclude_troop_id,
            ).all()
            for ot in other_troops:
                for oid in [ot.slot1_hero_id, ot.slot2_hero_id, ot.slot3_hero_id]:
                    if oid and oid != hero_id:
                        oh = db.query(Hero).get(oid)
                        if oh and oh.name == hero_name:
                            return True
            return False

        name_conflict = False
        for hid in [slot1, slot2, slot3]:
            if hid:
                hero = db.query(Hero).get(hid)
                if hero and hero_name_in_other_troop(hid, hero.name, troop_id):
                    await manager.send_to(username, build_packet(MsgType.ERROR, f"武将【{hero.name}】已在其他部队中，同名武将只能出现在一个部队"))
                    name_conflict = True
                    break
        if name_conflict:
            return

        # 检查同部队内同名武将
        slot_hero_names = []
        for hid in [slot1, slot2, slot3]:
            if hid:
                hero = db.query(Hero).get(hid)
                if hero:
                    slot_hero_names.append(hero.name)
        if len(slot_hero_names) != len(set(slot_hero_names)):
            await manager.send_to(username, build_packet(MsgType.ERROR, "部队中不能有同名武将"))
            return

        # 统率检查
        max_cost = db_player.main_city_level * 3.0
        total_cost = 0
        for hid in [slot1, slot2, slot3]:
            if hid:
                hero = db.query(Hero).get(hid)
                total_cost += hero.cost
        if total_cost > max_cost:
            await manager.send_to(
                username, build_packet(MsgType.ERROR, f"统率超过上限 {max_cost} (当前 {total_cost})")
            )
            return

        troop.slot1_hero_id = slot1
        troop.slot2_hero_id = slot2
        troop.slot3_hero_id = slot3
        db.commit()
        await manager.send_to(username, build_packet(MsgType.ERROR, "部队配置成功"))
    except Exception as e:
        print(f"编辑部队错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, f"编辑部队失败: {e}"))


async def handle_recruit_troops(username, state, db, db_player, msg_data):
    """征兵：消耗资源增加武将兵力。"""
    try:
        hero_id = msg_data.get("hero_id")
        amount = msg_data.get("amount", 100)
        hero = db.query(Hero).filter(Hero.id == hero_id, Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        cost_wood = amount
        cost_iron = amount
        cost_stone = amount
        cost_grain = amount
        if (
            db_player.wood >= cost_wood
            and db_player.iron >= cost_iron
            and db_player.stone >= cost_stone
            and db_player.grain >= cost_grain
        ):
            db_player.wood -= cost_wood
            db_player.iron -= cost_iron
            db_player.stone -= cost_stone
            db_player.grain -= cost_grain
            hero.troops = min(hero.max_troops, hero.troops + amount)
            db.commit()
            state["resources"]["wood"] = db_player.wood
            state["resources"]["iron"] = db_player.iron
            state["resources"]["stone"] = db_player.stone
            state["resources"]["grain"] = db_player.grain
            await manager.send_to(
                username, build_packet(MsgType.ERROR, f"征兵成功，{hero.name}兵力+{amount}")
            )
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "资源不足，征兵失败"))
    except Exception as e:
        print(f"征兵错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"征兵失败: {e}"))

# ws_handlers/building_handlers.py
# 主城建筑系统：查询建筑列表、升级建筑、查看详情
from shared.protocol import MsgType, build_packet
from models.schema import Player, BuildingConfig, BuildingLevelConfig, PlayerBuilding
from core.connection_manager import manager


async def handle_req_buildings(username, state, db, db_player, msg_data):
    """查询玩家所有建筑（含可升级状态）。"""
    try:
        player_blds = db.query(PlayerBuilding).filter(
            PlayerBuilding.player_id == db_player.id
        ).all()
        pb_map = {pb.building_key: pb.level for pb in player_blds}

        all_configs = db.query(BuildingConfig).order_by(
            BuildingConfig.layout_row, BuildingConfig.sort_order
        ).all()

        buildings_data = []
        for bc in all_configs:
            current_level = pb_map.get(bc.building_key, -1)
            next_level = current_level + 1 if current_level >= 0 else None

            next_cost = None
            if next_level and next_level <= bc.max_level:
                blc = db.query(BuildingLevelConfig).filter(
                    BuildingLevelConfig.building_key == bc.building_key,
                    BuildingLevelConfig.level == next_level,
                ).first()
                if blc:
                    next_cost = {
                        "wood": blc.cost_wood,
                        "iron": blc.cost_iron,
                        "stone": blc.cost_stone,
                        "grain": blc.cost_grain,
                        "copper": blc.cost_copper,
                    }

            can_unlock = False
            prereq_met = False
            if current_level == -1:
                from building_configs import check_building_prerequisites
                ok, reason = check_building_prerequisites(db, db_player.id, bc.building_key)
                can_unlock = ok
                prereq_met = ok
            elif current_level < bc.max_level:
                prereq_met = True
                can_unlock = True

            current_effects = None
            if current_level > 0:
                cur_blc = db.query(BuildingLevelConfig).filter(
                    BuildingLevelConfig.building_key == bc.building_key,
                    BuildingLevelConfig.level == current_level,
                ).first()
                if cur_blc:
                    current_effects = cur_blc.effects

            buildings_data.append({
                "key": bc.building_key,
                "name": bc.building_name,
                "category": bc.category,
                "unlock_palace_level": bc.unlock_palace_level,
                "max_level": bc.max_level,
                "current_level": current_level,
                "current_effects": current_effects,
                "next_cost": next_cost,
                "can_unlock": can_unlock,
                "prereq_met": prereq_met,
                "description": bc.description,
                "prerequisites": bc.prerequisites,
                "layout_row": bc.layout_row,
                "layout_col": bc.layout_col,
            })

        await manager.send_to(username, build_packet(MsgType.RES_BUILDINGS, {
            "buildings": buildings_data,
            "palace_level": pb_map.get("palace", 0),
        }))
    except Exception as e:
        print(f"获取建筑列表错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"获取建筑列表失败: {e}"))


async def handle_upgrade_building(username, state, db, db_player, msg_data):
    """升级/建造建筑。"""
    try:
        building_key = msg_data.get("building_key")
        if not building_key:
            await manager.send_to(username, build_packet(MsgType.ERROR, "未指定建筑"))
            return

        bc = db.query(BuildingConfig).filter(
            BuildingConfig.building_key == building_key
        ).first()
        if not bc:
            await manager.send_to(username, build_packet(MsgType.ERROR, "建筑不存在"))
            return

        pb = db.query(PlayerBuilding).filter(
            PlayerBuilding.player_id == db_player.id,
            PlayerBuilding.building_key == building_key,
        ).first()

        if not pb or pb.level < 0:
            from building_configs import check_building_prerequisites
            ok, reason = check_building_prerequisites(db, db_player.id, building_key)
            if not ok:
                await manager.send_to(username, build_packet(MsgType.ERROR, f"无法建造: {reason}"))
                return
            pb = PlayerBuilding(
                player_id=db_player.id,
                building_key=building_key,
                level=0,
            )
            db.add(pb)
            db.flush()

        if pb.level >= bc.max_level:
            await manager.send_to(username, build_packet(MsgType.ERROR, f"{bc.building_name}已满级"))
            return

        from building_configs import check_building_prerequisites
        ok, reason = check_building_prerequisites(db, db_player.id, building_key)
        if not ok:
            await manager.send_to(username, build_packet(MsgType.ERROR, f"前置条件不满足: {reason}"))
            return

        next_lv = pb.level + 1
        blc = db.query(BuildingLevelConfig).filter(
            BuildingLevelConfig.building_key == building_key,
            BuildingLevelConfig.level == next_lv,
        ).first()
        if not blc:
            await manager.send_to(username, build_packet(MsgType.ERROR, f"等级配置缺失: {building_key} Lv{next_lv}"))
            return

        # 资源检查
        wood_ok = state["resources"]["wood"] >= blc.cost_wood
        iron_ok = state["resources"]["iron"] >= blc.cost_iron
        stone_ok = state["resources"]["stone"] >= blc.cost_stone
        grain_ok = state["resources"]["grain"] >= blc.cost_grain
        copper_ok = state["currencies"]["copper"] >= blc.cost_copper

        if not (wood_ok and iron_ok and stone_ok and grain_ok and copper_ok):
            lacking = []
            if not wood_ok: lacking.append(f"木材缺{blc.cost_wood - int(state['resources']['wood'])}")
            if not iron_ok: lacking.append(f"铁矿缺{blc.cost_iron - int(state['resources']['iron'])}")
            if not stone_ok: lacking.append(f"石料缺{blc.cost_stone - int(state['resources']['stone'])}")
            if not grain_ok: lacking.append(f"粮草缺{blc.cost_grain - int(state['resources']['grain'])}")
            if not copper_ok: lacking.append(f"铜币缺{blc.cost_copper - int(state['currencies']['copper'])}")
            await manager.send_to(username, build_packet(MsgType.ERROR, f"资源不足: {'，'.join(lacking)}"))
            return

        # 扣除资源
        state["resources"]["wood"] -= blc.cost_wood
        state["resources"]["iron"] -= blc.cost_iron
        state["resources"]["stone"] -= blc.cost_stone
        state["resources"]["grain"] -= blc.cost_grain
        state["currencies"]["copper"] -= blc.cost_copper
        db_player.wood = int(state["resources"]["wood"])
        db_player.iron = int(state["resources"]["iron"])
        db_player.stone = int(state["resources"]["stone"])
        db_player.grain = int(state["resources"]["grain"])
        db_player.copper = int(state["currencies"]["copper"])

        # 升级
        pb.level = next_lv

        # 城主府升级特殊处理：解锁新建筑 + 更新数据库字段
        if building_key == "palace":
            db_player.main_city_level = next_lv
            from building_configs import init_player_buildings
            init_player_buildings(db, db_player.id, next_lv)

        db.commit()

        # 升级后重算产出 + 建筑效果（仓库/校场/兵营/点将台等）
        manager.recalculate_production(username, db)
        manager.recalculate_building_effects(username, db)
        beff = manager.get_building_effects(username)

        # 同步 Player 数据库字段（troop_slots→max_troops, troop_capacity→hero.max_troops 在下次recruit时应用）
        if beff["troop_slots"] != db_player.max_troops:
            db_player.max_troops = beff["troop_slots"]
            db.commit()

        action = "建造" if next_lv == 1 else "升级"
        # 推送成功消息
        await manager.send_to(username, build_packet(MsgType.ERROR,
            f"✅ {bc.building_name}{action}成功！当前 {next_lv}/{bc.max_level} 级"))
        # 推送最新建筑效果到客户端（客户端可用于实时显示效果加成）
        await manager.send_to(username, build_packet(MsgType.PUSH_BUILDING_EFFECTS, {
            "building_effects": beff,
        }))
        # 推送更新后的建筑列表（客户端自动刷新面板数据）
        await handle_req_buildings(username, state, db, db_player, {})
        # 同步资源变动给客户端（升级扣费后）
        await manager.send_to(username, build_packet(MsgType.SYNC_STATE, {
            "resources": state["resources"],
            "currencies": state["currencies"],
        }))
    except Exception as e:
        print(f"升级建筑错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"升级建筑失败: {e}"))


async def handle_req_building_detail(username, state, db, db_player, msg_data):
    """查询建筑所有等级详情。"""
    try:
        building_key = msg_data.get("building_key")
        if not building_key:
            await manager.send_to(username, build_packet(MsgType.ERROR, "未指定建筑"))
            return

        bc = db.query(BuildingConfig).filter(
            BuildingConfig.building_key == building_key
        ).first()
        if not bc:
            await manager.send_to(username, build_packet(MsgType.ERROR, "建筑不存在"))
            return

        level_configs = db.query(BuildingLevelConfig).filter(
            BuildingLevelConfig.building_key == building_key
        ).order_by(BuildingLevelConfig.level).all()

        levels_data = []
        for lc in level_configs:
            levels_data.append({
                "level": lc.level,
                "cost_wood": lc.cost_wood,
                "cost_iron": lc.cost_iron,
                "cost_stone": lc.cost_stone,
                "cost_grain": lc.cost_grain,
                "cost_copper": lc.cost_copper,
                "effects": lc.effects,
            })

        pb = db.query(PlayerBuilding).filter(
            PlayerBuilding.player_id == db_player.id,
            PlayerBuilding.building_key == building_key,
        ).first()
        current_level = pb.level if pb else -1

        await manager.send_to(username, build_packet(MsgType.RES_BUILDING_DETAIL, {
            "key": bc.building_key,
            "name": bc.building_name,
            "category": bc.category,
            "max_level": bc.max_level,
            "current_level": current_level,
            "description": bc.description,
            "prerequisites": bc.prerequisites,
            "levels": levels_data,
        }))
    except Exception as e:
        print(f"获取建筑详情错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"获取建筑详情失败: {e}"))

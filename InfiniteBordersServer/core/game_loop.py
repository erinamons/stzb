# core/game_loop.py
# 服务器核心心跳循环 + FastAPI 启动事件
import asyncio
from shared.protocol import MsgType, build_packet
from models.database import SessionLocal
from models.schema import Player, Hero, Tile, Troop, NPCHero, BattleReport
from core.combat import CombatEngine
from core.connection_manager import manager
from config import TICK_RATE


async def _process_march(username, state, march, db):
    """处理行军抵达：触发战斗/占领。返回 True 表示该行军应被移除。"""
    tx, ty = march["target_x"], march["target_y"]
    target_tile = db.query(Tile).filter(Tile.x == tx, Tile.y == ty).first()
    if not target_tile or target_tile.owner_id == state["id"]:
        return True  # 无需战斗，直接移除

    try:
        troop = db.query(Troop).filter(
            Troop.id == march["troop_id"],
            Troop.owner_id == state["id"]
        ).first()
        if not troop:
            await manager.send_to(username,
                                  build_packet(MsgType.ERROR, "行军部队不存在，已取消"))
            return True

        attacker_heroes = []
        for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
            if hid:
                hero = db.query(Hero).get(hid)
                if hero:
                    attacker_heroes.append(hero)

        lv = target_tile.level
        defender = NPCHero(lv)
        defender_heroes = [defender]

        # 读取进攻方建筑效果（点将台/战营加成）
        attacker_building_effects = manager.get_building_effects(username)
        is_victory, report = CombatEngine.simulate_battle(
            attacker_heroes, defender_heroes,
            attacker_building_effects=attacker_building_effects
        )

        if is_victory:
            target_tile.owner_id = state["id"]
            db.commit()
            manager.recalculate_production(username, db)
            db.refresh(target_tile)
            changed_tile = {
                "x": target_tile.x,
                "y": target_tile.y,
                "terrain": target_tile.terrain,
                "level": target_tile.level,
                "owner": target_tile.owner_id,
            }
            await manager.send_to(username, build_packet("sync_map", [changed_tile]))
            await manager.send_to(username,
                                  build_packet(MsgType.ERROR, f"胜利！占领了土地({tx},{ty})"))
        else:
            await manager.send_to(username,
                                  build_packet(MsgType.ERROR, f"战败，未能占领土地({tx},{ty})"))

        # 保存战报到数据库
        battle_report = BattleReport(
            player_id=state["id"],
            tile_x=tx, tile_y=ty,
            is_victory=1 if is_victory else 0,
            report=report
        )
        db.add(battle_report)
        db.commit()

        await manager.send_to(
            username,
            build_packet(MsgType.PUSH_REPORT,
                         {"x": tx, "y": ty, "is_victory": is_victory, "report": report}),
        )
    except Exception as e:
        print(f"战斗处理异常: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(
            username,
            build_packet(MsgType.PUSH_REPORT,
                         {"x": tx, "y": ty, "is_victory": False,
                          "report": None, "error": f"战斗处理异常: {e}"}),
        )
    return True


async def game_loop():
    """服务器核心心跳循环：每秒 tick，累加资源、恢复体力、处理行军。"""
    print("⏳ 服务器时间轴引擎启动...")
    while True:
        await asyncio.sleep(TICK_RATE)
        db = SessionLocal()
        try:
            for username, state in list(manager.online_players.items()):
                # 获取玩家建筑效果（仓库上限、民居铜币产出等）
                beff = state.get("building_effects", {})
                storage_cap = beff.get("storage_cap", 50000)
                copper_per_hour = beff.get("copper_per_hour", 0)

                # 资源产出 — 同步累加到内存，并应用仓库上限
                for k in state["resources"]:
                    state["resources"][k] += state["production"][k]
                    # 仓库上限 clamp
                    if state["resources"][k] > storage_cap:
                        state["resources"][k] = storage_cap

                # 民居铜币产出（每秒 = per_hour / 3600），截断为整数避免浮点漂移
                if copper_per_hour > 0:
                    state["currencies"]["copper"] = int(state["currencies"]["copper"] + copper_per_hour / 3600.0)

                # 将资源写回数据库（每次tick）
                try:
                    db_player = db.query(Player).filter(Player.id == state["id"]).first()
                    if db_player:
                        db_player.wood = int(state["resources"]["wood"])
                        db_player.iron = int(state["resources"]["iron"])
                        db_player.stone = int(state["resources"]["stone"])
                        db_player.grain = int(state["resources"]["grain"])
                        db_player.copper = int(state["currencies"]["copper"])
                        db_player.jade = int(state["currencies"]["jade"])
                        db_player.tiger_tally = int(state["currencies"]["tiger_tally"])
                except Exception as e:
                    print(f"[资源存库失败] {username}: {e}")

                # 恢复武将体力（每秒恢复1点）
                db_heroes = db.query(Hero).filter(Hero.owner_id == state["id"]).all()
                for hero in db_heroes:
                    if hasattr(hero, 'stamina') and hasattr(hero, 'max_stamina'):
                        if hero.stamina < hero.max_stamina:
                            hero.stamina = min(hero.max_stamina, hero.stamina + 1)
                db.commit()

                # 处理行军
                marches_to_remove = []
                for march in state["marches"]:
                    march["time_left"] -= TICK_RATE
                    if march["time_left"] <= 0:
                        should_remove = await _process_march(username, state, march, db)
                        if should_remove:
                            marches_to_remove.append(march)

                for m in marches_to_remove:
                    state["marches"].remove(m)

                # 同步状态给客户端
                await manager.send_to(
                    username,
                    build_packet(
                        MsgType.SYNC_STATE,
                        {
                            "resources": state["resources"],
                            "currencies": state["currencies"],
                            "marches": state["marches"],
                        },
                    ),
                )
        except Exception as e:
            print(f"❌ 时间轴运算错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()


def setup_startup_event(app):
    """注册 FastAPI 启动事件。由 server.py 调用。"""

    @app.on_event("startup")
    async def startup_event():
        # 自动创建缺失的表（不影响已有数据）
        from models.database import Base, engine
        Base.metadata.create_all(bind=engine)
        print("数据库表检查完成")
        # 加载建筑配置（仅在表为空时）
        _db = SessionLocal()
        try:
            from building_configs import load_building_configs
            load_building_configs(_db)
        except Exception as e:
            print(f"建筑配置加载失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _db.close()
        asyncio.create_task(game_loop())

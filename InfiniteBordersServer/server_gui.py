import asyncio
import json
import math
import os
import random
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import time

# 确保父目录在 sys.path 中（用于导入 shared 协议模块）
_server_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_server_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from config import *
from shared.protocol import MsgType, build_packet
from models.database import SessionLocal
from models.schema import Player, Hero, Tile, HeroTemplate, CardPack, CardPackDrop, Troop, Skill, NPCHero, BattleReport, BuildingConfig, BuildingLevelConfig, PlayerBuilding
from core.combat import CombatEngine
from hex_utils import get_neighbors, hex_distance

from node_editor import NodeEditor

app = FastAPI(title="InfiniteBorders Backend")


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.online_players = {}

    async def connect(self, websocket: WebSocket, username: str, db: Session):
        try:
            await websocket.accept()
        except Exception as e:
            print(f"WebSocket 接受连接失败: {e}")
            return

        self.active_connections[username] = websocket
        db_player = db.query(Player).filter(Player.username == username).first()
        if not db_player:
            try:
                await websocket.send_text(json.dumps(build_packet(MsgType.ERROR, "玩家不存在，请初始化数据库！")))
                await websocket.close()
            except:
                pass
            return

        self.online_players[username] = {
            "id": db_player.id,
            "spawn_x": db_player.spawn_x,
            "spawn_y": db_player.spawn_y,
            "resources": {
                "wood": db_player.wood,
                "iron": db_player.iron,
                "stone": db_player.stone,
                "grain": db_player.grain,
            },
            "currencies": {
                "copper": db_player.copper,
                "jade": db_player.jade,
                "tiger_tally": db_player.tiger_tally,
            },
            "production": {"wood": 0, "iron": 0, "stone": 0, "grain": 0},
            "marches": [],
        }
        self.recalculate_production(username, db)

        try:
            map_data = [
                {
                    "x": t.x,
                    "y": t.y,
                    "terrain": t.terrain,
                    "level": t.level,
                    "owner": t.owner_id,
                    "region": t.region,
                    "city_type": t.city_type,
                    "city_name": t.city_name,
                }
                for t in db.query(Tile).all()
            ]
            await websocket.send_text(
                json.dumps(
                    build_packet(
                        MsgType.RES_LOGIN,
                        {
                            "spawn": {"x": db_player.spawn_x, "y": db_player.spawn_y},
                            "resources": self.online_players[username]["resources"],
                            "currencies": self.online_players[username]["currencies"],
                            "map": map_data,
                        },
                    )
                )
            )
        except Exception as e:
            print(f"发送登录数据失败: {e}")
            try:
                await websocket.close()
            except:
                pass
            return

    def recalculate_production(self, username: str, db: Session):
        p_id = self.online_players[username]["id"]
        self.online_players[username]["production"] = {"wood": 0, "iron": 0, "stone": 0, "grain": 0}
        # 领地产出（地图占领格子的资源）
        for t in db.query(Tile).filter(Tile.owner_id == p_id).all():
            if t.terrain in RES_MAP:
                self.online_players[username]["production"][RES_MAP[t.terrain]["key"]] += t.level * 10
        # 主城建筑产出（伐木场/炼铁场/磨坊/采石场）
        try:
            building_production_map = {
                "lumber_mill": "wood",
                "iron_smelter": "iron",
                "flour_mill": "grain",
                "quarry": "stone",
            }
            player_buildings = db.query(PlayerBuilding).filter(
                PlayerBuilding.player_id == p_id,
                PlayerBuilding.level > 0,
            ).all()
            for pb in player_buildings:
                if pb.building_key in building_production_map:
                    res_key = building_production_map[pb.building_key]
                    blc = db.query(BuildingLevelConfig).filter(
                        BuildingLevelConfig.building_key == pb.building_key,
                        BuildingLevelConfig.level == pb.level,
                    ).first()
                    if blc and blc.effects:
                        per_hour = blc.effects.get(f"{res_key}_per_hour", 0)
                        # 每小时产出 ÷ 3600 = 每秒产出（TICK_RATE=1秒）
                        self.online_players[username]["production"][res_key] += per_hour / 3600.0
        except Exception as e:
            print(f"[建筑产出计算警告] {username}: {e}")

    def is_tile_reachable(self, player_id: int, target_q: int, target_r: int, db: Session) -> bool:
        """
        检查目标格子是否与玩家领地相连。
        目标格子的邻居中至少有一个是玩家已占领的格子，才算相连。
        """
        # 目标格子的6个邻居
        for nq, nr in get_neighbors(target_q, target_r):
            neighbor = db.query(Tile).filter(Tile.x == nq, Tile.y == nr, Tile.owner_id == player_id).first()
            if neighbor:
                return True
        return False

    def get_territory_border(self, player_id: int, db: Session) -> set:
        """
        获取玩家领地的边界格子集合（有非己方邻居的己方格子）。
        用于客户端提示玩家可以出征的范围。
        """
        owned_tiles = {(t.x, t.y) for t in db.query(Tile).filter(Tile.owner_id == player_id).all()}
        border = set()
        for q, r in owned_tiles:
            for nq, nr in get_neighbors(q, r):
                if (nq, nr) not in owned_tiles:
                    border.add((q, r))
                    break
        return border

    def disconnect(self, username: str, db: Session = None):
        # P0-1 FIX: 断线前将内存中的资源写回数据库，防止产出丢失
        if username in self.online_players:
            state = self.online_players[username]
            if db:
                try:
                    player = db.query(Player).filter(Player.id == state["id"]).first()
                    if player:
                        player.wood = int(state["resources"]["wood"])
                        player.iron = int(state["resources"]["iron"])
                        player.stone = int(state["resources"]["stone"])
                        player.grain = int(state["resources"]["grain"])
                        player.copper = int(state["currencies"]["copper"])
                        player.jade = int(state["currencies"]["jade"])
                        player.tiger_tally = int(state["currencies"]["tiger_tally"])
                        db.commit()
                        print(f"[存库] {username} 断线，资源已持久化")
                except Exception as e:
                    print(f"[存库失败] {username}: {e}")
        if username in self.active_connections:
            del self.active_connections[username]
        if username in self.online_players:
            del self.online_players[username]

    async def send_to(self, username: str, packet: dict):
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_text(json.dumps(packet))
            except Exception as e:
                print(f"发送消息给 {username} 失败: {e}")


manager = ConnectionManager()


async def game_loop():
    print("⏳ 服务器时间轴引擎启动...")
    while True:
        await asyncio.sleep(TICK_RATE)
        db = SessionLocal()
        try:
            for username, state in list(manager.online_players.items()):
                # P0-1 FIX: 资源产出 — 同步累加到内存和数据库
                for k in state["resources"]:
                    state["resources"][k] += state["production"][k]
                # 将资源写回数据库（每次tick），防止进程崩溃丢失
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
                    # 确保属性存在（如果数据库未更新，则跳过）
                    if hasattr(hero, 'stamina') and hasattr(hero, 'max_stamina'):
                        if hero.stamina < hero.max_stamina:
                            hero.stamina = min(hero.max_stamina, hero.stamina + 1)
                db.commit()

                marches_to_remove = []
                for march in state["marches"]:
                    march["time_left"] -= TICK_RATE
                    if march["time_left"] <= 0:
                        tx, ty = march["target_x"], march["target_y"]
                        target_tile = db.query(Tile).filter(Tile.x == tx, Tile.y == ty).first()
                        if target_tile and target_tile.owner_id != state["id"]:
                            try:
                                troop = db.query(Troop).filter(Troop.id == march["troop_id"],
                                                               Troop.owner_id == state["id"]).first()
                                if not troop:
                                    await manager.send_to(username,
                                                          build_packet(MsgType.ERROR, "行军部队不存在，已取消"))
                                    marches_to_remove.append(march)
                                    continue

                                attacker_heroes = []
                                for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
                                    if hid:
                                        hero = db.query(Hero).get(hid)
                                        if hero:
                                            attacker_heroes.append(hero)

                                lv = target_tile.level
                                # P0-5 FIX: 使用正式NPC模型替代 class Dummy: pass
                                defender = NPCHero(lv)
                                defender_heroes = [defender]

                                is_victory, report = CombatEngine.simulate_battle(attacker_heroes, defender_heroes)

                                if is_victory:
                                    target_tile.owner_id = state["id"]
                                    db.commit()
                                    manager.recalculate_production(username, db)
                                    # P1-1 FIX: 只发送变化的tile，而非全量查询10000条
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
                            finally:
                                marches_to_remove.append(march)

                for m in marches_to_remove:
                    state["marches"].remove(m)

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


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    # P0-2 FIX: connect时使用独立Session，用完即关
    db = SessionLocal()
    try:
        print(f"尝试连接用户 {username}")
        await manager.connect(websocket, username, db)
        print(f"用户 {username} 连接成功")
    except Exception as e:
        print(f"连接建立失败: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close()
        db.close()
        return
    finally:
        db.close()  # 连接建立后立即关闭connect用的Session

    async def send_heroes():
        # P0-2 FIX: 每次调用创建独立Session
        _db = SessionLocal()
        try:
            db_player = _db.query(Player).filter(Player.username == username).first()
            if not db_player:
                await manager.send_to(username, build_packet(MsgType.ERROR, "玩家数据丢失"))
                return
            heroes = _db.query(Hero).filter(Hero.owner_id == db_player.id).all()
            h_data = []
            for h in heroes:
                t = h.template
                if not t:
                    print(f"警告：武将 {h.id} 的 template 为 None")
                    continue
                try:
                    total_pts = (h.level // 10) * 10 + h.bonus_points
                    used_pts = h.p_atk + h.p_def + h.p_strg + h.p_sie + h.p_spd

                    innate_skill_name = ""
                    if t.innate_skill_id:
                        skill = _db.query(Skill).filter(Skill.id == t.innate_skill_id).first()
                        if skill:
                            innate_skill_name = skill.name
                    skill_2_name = ""
                    if h.skill_2_id:
                        skill = _db.query(Skill).filter(Skill.id == h.skill_2_id).first()
                        if skill:
                            skill_2_name = skill.name
                    skill_3_name = ""
                    if h.skill_3_id:
                        skill = _db.query(Skill).filter(Skill.id == h.skill_3_id).first()
                        if skill:
                            skill_3_name = skill.name

                    atk = int(t.atk + (h.level - 1) * t.atk_g + h.p_atk)
                    defense = int(t.defs + (h.level - 1) * t.def_g + h.p_def)
                    strategy = int(t.strg + (h.level - 1) * t.strg_g + h.p_strg)
                    siege = int(t.sie + (h.level - 1) * t.sie_g + h.p_sie)
                    speed = int(t.spd + (h.level - 1) * t.spd_g + h.p_spd)

                    h_data.append({
                        "id": h.id,
                        "name": t.name,
                        "stars": t.stars,
                        "level": h.level,
                        "exp": h.exp,
                        "rank": h.rank,
                        "template_id": t.id,
                        "p_atk": h.p_atk,
                        "p_def": h.p_def,
                        "p_strg": h.p_strg,
                        "p_spd": h.p_spd,
                        "faction": t.faction,
                        "troop_type": t.troop_type,
                        "cost": t.cost,
                        "range": t.attack_range,
                        "atk": atk,
                        "atk_g": t.atk_g,
                        "def": defense,
                        "def_g": t.def_g,
                        "strg": strategy,
                        "strg_g": t.strg_g,
                        "sie": siege,
                        "sie_g": t.sie_g,
                        "spd": speed,
                        "spd_g": t.spd_g,
                        "unallocated": total_pts - used_pts,
                        "troops": h.troops,
                        "max_troops": h.max_troops,
                        "stamina": h.stamina,
                        "max_stamina": h.max_stamina,
                        "skills": [innate_skill_name, skill_2_name, skill_3_name],
                    })
                except Exception as e:
                    print(f"处理武将 {h.id} 时出错: {e}")
                    continue
            await manager.send_to(username, build_packet(MsgType.RES_HEROES, h_data))
        except Exception as e:
            print(f"send_heroes 错误: {e}")
            import traceback
            traceback.print_exc()
            await manager.send_to(username, build_packet(MsgType.ERROR, "获取武将列表失败"))
        finally:
            _db.close()

    try:
        while True:
            try:
                packet = json.loads(await websocket.receive_text())
            except WebSocketDisconnect:
                print(f"客户端 {username} 断开连接")
                raise
            except Exception as e:
                print(f"接收消息错误: {e}")
                import traceback
                traceback.print_exc()
                await manager.send_to(username, build_packet(MsgType.ERROR, "消息格式错误"))
                continue

            msg_type, msg_data = packet.get("type"), packet.get("data", {})
            if username not in manager.online_players:
                continue
            state = manager.online_players[username]

            # P0-2 FIX: 每次消息处理使用独立Session
            db = SessionLocal()
            try:
                db_player = db.query(Player).filter(Player.id == state["id"]).first()
                if not db_player:
                    await manager.send_to(username, build_packet(MsgType.ERROR, "玩家数据丢失"))
                    continue

                if msg_type == MsgType.CMD_MARCH:
                    tx, ty = msg_data.get("x"), msg_data.get("y")
                    troop_id = msg_data.get("troop_id")
                    troop = db.query(Troop).filter(Troop.id == troop_id, Troop.owner_id == db_player.id).first()
                    if not troop:
                        await manager.send_to(username, build_packet(MsgType.ERROR, "部队不存在"))
                        continue
                    if any(m.get("troop_id") == troop_id for m in state["marches"]):
                        await manager.send_to(username, build_packet(MsgType.ERROR, "该部队已在行军"))
                        continue
                    if not any([troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]):
                        await manager.send_to(username, build_packet(MsgType.ERROR, "部队没有武将"))
                        continue

                    # 体力检查（仅检查，不扣除）
                    stamina_needed = 10
                    insufficient = []
                    for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
                        if hid:
                            hero = db.query(Hero).get(hid)
                            if hero and hero.stamina < stamina_needed:
                                insufficient.append(hero.name)
                    if insufficient:
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"{','.join(insufficient)} 体力不足，无法出征"))
                        continue

                    target_tile = db.query(Tile).filter(Tile.x == tx, Tile.y == ty).first()
                    if target_tile and target_tile.owner_id == state["id"]:
                        await manager.send_to(username, build_packet(MsgType.ERROR, "这块土地已经是你的领地！不要重复出征！"))
                        continue
                    if any(m["target_x"] == tx and m["target_y"] == ty for m in state["marches"]):
                        await manager.send_to(username, build_packet(MsgType.ERROR, "已有部队正在前往该目标！"))
                        continue

                    # 出征距离检查：目标必须在任一己方占领格子的6邻居范围内
                    owned_tiles = {(t.x, t.y) for t in db.query(Tile).filter(Tile.owner_id == state["id"]).all()}
                    marchable = False
                    for (ox, oy) in owned_tiles:
                        if (tx, ty) in get_neighbors(ox, oy):
                            marchable = True
                            break
                    if not marchable:
                        await manager.send_to(username, build_packet(MsgType.ERROR, "目标位置超出领地范围，只能向己方领地周围6格出征！"))
                        continue

                    # 所有检查通过，扣除体力
                    for hid in [troop.slot1_hero_id, troop.slot2_hero_id, troop.slot3_hero_id]:
                        if hid:
                            hero = db.query(Hero).get(hid)
                            if hero:
                                hero.stamina = max(0, hero.stamina - stamina_needed)
                    db.commit()

                    # 从离目标最近的己方格子出发
                    nearest_owner = min(owned_tiles, key=lambda p: hex_distance(p[0], p[1], tx, ty))
                    dist = hex_distance(nearest_owner[0], nearest_owner[1], tx, ty)
                    time_needed = max(3.0, dist * 100 / 90)
                    state["marches"].append(
                        {
                            "id": str(time.time()),
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

                elif msg_type == MsgType.CMD_RECHARGE:
                    try:
                        db_player.jade += msg_data.get("amount", 0)
                        db.commit()
                        state["currencies"]["jade"] = db_player.jade
                        await manager.send_to(username, build_packet(MsgType.ERROR, "充值成功！"))
                    except Exception as e:
                        print(f"充值错误: {e}")
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"充值失败: {e}"))

                elif msg_type == MsgType.CMD_EXCHANGE:
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

                elif msg_type == MsgType.REQ_PACKS:
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

                elif msg_type == MsgType.REQ_HEROES:
                    await send_heroes()

                elif msg_type == MsgType.CMD_ADD_POINT:
                    try:
                        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
                        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
                        total_pts = (hero.level // 10) * 10 + hero.bonus_points
                        used_pts = hero.p_atk + hero.p_def + hero.p_strg + hero.p_sie + hero.p_spd
                        if total_pts - used_pts > 0:
                            if attr == "atk":
                                hero.p_atk += 1
                            elif attr == "def":
                                hero.p_def += 1
                            elif attr == "strg":
                                hero.p_strg += 1
                            elif attr == "spd":
                                hero.p_spd += 1
                            else:
                                await manager.send_to(username, build_packet(MsgType.ERROR, "无效属性"))
                                continue
                            db.commit()
                            await send_heroes()
                        else:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "没有可用属性点"))
                    except Exception as e:
                        print(f"加点错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"加点失败: {e}"))

                elif msg_type == MsgType.CMD_CHEAT_LVL:
                    # P1-2 FIX: GM命令权限验证 — 仅从GM工具可调用
                    if not msg_data.get("_gm_token"):
                        await manager.send_to(username, build_packet(MsgType.ERROR, "无权限"))
                        continue
                    try:
                        hero = db.query(Hero).filter(Hero.id == msg_data.get("hero_id"), Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
                        if hero.level < 50:
                            hero.level = min(50, hero.level + 10)
                            db.commit()
                            await manager.send_to(
                                username, build_packet(MsgType.ERROR, f"{hero.template.name} 升级啦！当前Lv.{hero.level}")
                            )
                            await send_heroes()
                        else:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "已达等级上限"))
                    except Exception as e:
                        print(f"升级错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"升级失败: {e}"))

                elif msg_type == MsgType.CMD_RESET_DATABASE:
                    # GM命令权限验证 — 仅从GM工具可调用
                    if not msg_data.get("_gm_token"):
                        await manager.send_to(username, build_packet(MsgType.ERROR, "无权限"))
                        continue
                    try:
                        print(f"[GM重置] 收到数据库重置请求，来源: {username}")
                        # 1. 踢掉所有在线玩家（关闭WebSocket连接）
                        kicked = list(manager.active_connections.keys())
                        for un in kicked:
                            try:
                                ws = manager.active_connections[un]
                                await ws.send_text(json.dumps(build_packet(
                                    MsgType.ERROR, "服务器数据库已重置，请重新连接"
                                )))
                                await ws.close()
                            except:
                                pass
                        manager.active_connections.clear()
                        manager.online_players.clear()
                        if kicked:
                            print(f"[GM重置] 已踢掉在线玩家: {kicked}")
                        # 2. 关闭当前 db session（init_database 会删库，session 必须先关）
                        db.close()
                        # 3. 调用 init_database() 删库重建
                        from init_db import init_database
                        init_database()
                        # 4. 重载建筑配置
                        new_db = SessionLocal()
                        try:
                            from building_configs import load_building_configs
                            load_building_configs(new_db)
                        except Exception as e:
                            print(f"[GM重置] 建筑配置重载失败: {e}")
                        finally:
                            new_db.close()
                        print("[GM重置] 数据库重置完成")
                        # 通知GM（此时GM连接已断开，但如果是GM自己触发的，走按钮路径更可靠）
                        # 不需要回复，GM按钮有自己的回调
                    except Exception as e:
                        print(f"[GM重置] 重置失败: {e}")
                        import traceback
                        traceback.print_exc()

                elif msg_type == MsgType.CMD_RANK_UP:
                    try:
                        hero_id = msg_data.get("hero_id")
                        # material_id: 被消耗的同名武将卡ID（用于升阶）
                        material_id = msg_data.get("material_id")
                        hero = db.query(Hero).filter(Hero.id == hero_id, Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
                        if hero.rank >= 5:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "已达最高阶"))
                            continue
                        # 升阶需要消耗一张同名武将卡（同template_id，且未被部队使用）
                        if not material_id:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "请选择一张同名武将卡用于升阶"))
                            continue
                        material = db.query(Hero).filter(
                            Hero.id == material_id,
                            Hero.owner_id == db_player.id,
                            Hero.template_id == hero.template_id,
                            Hero.id != hero_id
                        ).first()
                        if not material:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "无效的升阶材料（需同名武将卡）"))
                            continue
                        # 检查材料是否在部队中
                        mat_in_troop = db.query(Troop).filter(
                            Troop.owner_id == db_player.id,
                            (Troop.slot1_hero_id == material_id)
                            | (Troop.slot2_hero_id == material_id)
                            | (Troop.slot3_hero_id == material_id)
                        ).first()
                        if mat_in_troop:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "该武将卡正在部队中，无法用作升阶材料"))
                            continue
                        # 执行升阶：删除材料卡，目标武将升阶
                        db.delete(material)
                        hero.rank += 1
                        hero.bonus_points += 10
                        db.commit()
                        await send_heroes()
                        await manager.send_to(username, build_packet(MsgType.ERROR, 
                            f"{hero.name} 升阶成功！当前阶数 {hero.rank}/5，获得10点自由属性"))
                    except Exception as e:
                        print(f"升阶错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"升阶失败: {e}"))

                elif msg_type == MsgType.CMD_SUB_POINT:
                    try:
                        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
                        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
                        if attr == "atk" and hero.p_atk > 0:
                            hero.p_atk -= 1
                        elif attr == "def" and hero.p_def > 0:
                            hero.p_def -= 1
                        elif attr == "strg" and hero.p_strg > 0:
                            hero.p_strg -= 1
                        elif attr == "spd" and hero.p_spd > 0:
                            hero.p_spd -= 1
                        else:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "无法减少该属性"))
                            continue
                        db.commit()
                        await send_heroes()
                    except Exception as e:
                        print(f"减点错误: {e}")
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"减点失败: {e}"))

                elif msg_type == MsgType.CMD_MAX_POINT:
                    try:
                        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
                        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
                        total_pts = (hero.level // 10) * 10 + hero.bonus_points
                        used_pts = hero.p_atk + hero.p_def + hero.p_strg + hero.p_sie + hero.p_spd
                        available = total_pts - used_pts
                        if available <= 0:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "没有可用属性点"))
                            continue
                        if attr == "atk":
                            hero.p_atk += available
                        elif attr == "def":
                            hero.p_def += available
                        elif attr == "strg":
                            hero.p_strg += available
                        elif attr == "spd":
                            hero.p_spd += available
                        else:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "无效属性"))
                            continue
                        db.commit()
                        await send_heroes()
                    except Exception as e:
                        print(f"最大加点错误: {e}")
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"最大加点失败: {e}"))

                elif msg_type == MsgType.CMD_RECRUIT:
                    try:
                        pack = db.query(CardPack).filter(CardPack.id == msg_data.get("pack_id")).first()
                        if not pack:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "卡包不存在"))
                            continue
                        if pack.cost_type == "tiger" and db_player.tiger_tally >= pack.cost_amount:
                            db_player.tiger_tally -= pack.cost_amount
                        elif pack.cost_type == "copper" and db_player.copper >= pack.cost_amount:
                            db_player.copper -= pack.cost_amount
                        else:
                            await manager.send_to(
                                username,
                                build_packet(MsgType.ERROR, f"{'虎符' if pack.cost_type == 'tiger' else '铜币'}不足！"),
                            )
                            continue

                        drops = db.query(CardPackDrop).filter(CardPackDrop.pack_id == pack.id).all()
                        if not drops:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "卡包没有掉落配置"))
                            continue
                        t_id = random.choices([d.template_id for d in drops], weights=[d.weight for d in drops], k=1)[0]
                        t = db.query(HeroTemplate).filter(HeroTemplate.id == t_id).first()
                        if not t:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将模板不存在"))
                            continue

                        # 每次招募都创建独立武将实体（率土之滨模式：重复武将独立存在）
                        new_hero = Hero(
                            owner_id=db_player.id,
                            template_id=t.id,
                            name=t.name,
                            stars=t.stars,
                            attack=int(t.atk),
                            defense=int(t.defs),
                            strategy=int(t.strg),
                            speed=int(t.spd),
                            faction=t.faction,
                            troop_type=t.troop_type,
                            cost=t.cost,
                            rank=0,           # 初始阶为0，可升5次到满阶
                            duplicates=0,
                            bonus_points=0,
                            stamina=100,
                            max_stamina=100
                        )
                        db.add(new_hero)
                        db.commit()
                        msg = f"★金光一闪★ 获得 {t.stars}星【{t.faction}·{t.name}】！"

                        state["currencies"]["copper"] = db_player.copper
                        state["currencies"]["tiger_tally"] = db_player.tiger_tally
                        await manager.send_to(username, build_packet(MsgType.RES_RECRUIT, msg))
                        await send_heroes()
                    except Exception as e:
                        print(f"招募错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"招募失败: {e}"))

                elif msg_type == MsgType.REQ_TROOPS:
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

                elif msg_type == MsgType.CMD_EDIT_TROOP:
                    try:
                        troop_id = msg_data.get("troop_id")
                        slot1 = msg_data.get("slot1")
                        slot2 = msg_data.get("slot2")
                        slot3 = msg_data.get("slot3")
                        troop = db.query(Troop).filter(Troop.id == troop_id, Troop.owner_id == db_player.id).first()
                        if not troop:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "部队不存在"))
                            continue

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
                            continue

                        # 检查同一部队内是否重复（忽略空槽位 None）
                        slots = [s for s in [slot1, slot2, slot3] if s is not None]
                        if len(set(slots)) != len(slots):
                            await manager.send_to(username, build_packet(MsgType.ERROR, "部队中不能有重复武将"))
                            continue

                        # 检查跨部队同名武将：同名武将只能出现在一个部队中
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
                            continue

                        # 检查同部队内同名武将
                        slot_hero_names = []
                        for hid in [slot1, slot2, slot3]:
                            if hid:
                                hero = db.query(Hero).get(hid)
                                if hero:
                                    slot_hero_names.append(hero.name)
                        if len(slot_hero_names) != len(set(slot_hero_names)):
                            await manager.send_to(username, build_packet(MsgType.ERROR, "部队中不能有同名武将"))
                            continue

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
                            continue

                        troop.slot1_hero_id = slot1
                        troop.slot2_hero_id = slot2
                        troop.slot3_hero_id = slot3
                        db.commit()
                        await manager.send_to(username, build_packet(MsgType.ERROR, "部队配置成功"))
                    except Exception as e:
                        print(f"编辑部队错误: {e}")
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"编辑部队失败: {e}"))

                elif msg_type == MsgType.CMD_RECRUIT_TROOPS:
                    try:
                        hero_id = msg_data.get("hero_id")
                        amount = msg_data.get("amount", 100)
                        hero = db.query(Hero).filter(Hero.id == hero_id, Hero.owner_id == db_player.id).first()
                        if not hero:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
                            continue
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

                elif msg_type == MsgType.REQ_REPORT_HISTORY:
                    try:
                        page = msg_data.get("page", 1)
                        page_size = msg_data.get("page_size", 50)
                        # 按时间倒序查询该玩家的战报
                        query = db.query(BattleReport).filter(
                            BattleReport.player_id == state["id"]
                        ).order_by(BattleReport.id.desc())
                        total = query.count()
                        reports = query.offset((page - 1) * page_size).limit(page_size).all()
                        report_list = []
                        for r in reports:
                            report_list.append({
                                "id": r.id,
                                "tile_x": r.tile_x,
                                "tile_y": r.tile_y,
                                "is_victory": r.is_victory,
                                "report": r.report,
                                "created_at": r.created_at
                            })
                        await manager.send_to(username, build_packet(MsgType.RES_REPORT_HISTORY, {
                            "reports": report_list,
                            "total": total,
                            "page": page,
                            "page_size": page_size
                        }))
                    except Exception as e:
                        print(f"获取战报历史错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"获取战报历史失败: {e}"))

                # ============ 主城建筑系统 ============
                elif msg_type == MsgType.REQ_BUILDINGS:
                    try:
                        # 查询玩家所有建筑实例
                        player_blds = db.query(PlayerBuilding).filter(
                            PlayerBuilding.player_id == db_player.id
                        ).all()
                        pb_map = {pb.building_key: pb.level for pb in player_blds}

                        # 查询所有建筑配置
                        all_configs = db.query(BuildingConfig).order_by(
                            BuildingConfig.layout_row, BuildingConfig.sort_order
                        ).all()

                        buildings_data = []
                        for bc in all_configs:
                            current_level = pb_map.get(bc.building_key, -1)  # -1=未解锁
                            next_level = current_level + 1 if current_level >= 0 else None

                            # 获取下一级的消耗
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

                            # 检查前置条件是否满足
                            can_unlock = False
                            prereq_met = False
                            if current_level == -1:
                                # 未解锁：检查是否满足解锁条件
                                from building_configs import check_building_prerequisites
                                ok, reason = check_building_prerequisites(db, db_player.id, bc.building_key)
                                can_unlock = ok
                                prereq_met = ok
                            elif current_level < bc.max_level:
                                # 已解锁但未满级：检查前置是否还满足（通常已满足）
                                prereq_met = True
                                can_unlock = True

                            # 当前等级的效果
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
                                "current_level": current_level,       # -1=未解锁, 0=已解锁未建造, >=1=已建造
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

                elif msg_type == MsgType.CMD_UPGRADE_BUILDING:
                    try:
                        building_key = msg_data.get("building_key")
                        if not building_key:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "未指定建筑"))
                            continue

                        # 查询建筑配置
                        bc = db.query(BuildingConfig).filter(
                            BuildingConfig.building_key == building_key
                        ).first()
                        if not bc:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "建筑不存在"))
                            continue

                        # 查询玩家建筑实例
                        pb = db.query(PlayerBuilding).filter(
                            PlayerBuilding.player_id == db_player.id,
                            PlayerBuilding.building_key == building_key,
                        ).first()

                        if not pb or pb.level < 0:
                            # 建筑未解锁
                            from building_configs import check_building_prerequisites
                            ok, reason = check_building_prerequisites(db, db_player.id, building_key)
                            if not ok:
                                await manager.send_to(username, build_packet(MsgType.ERROR, f"无法建造: {reason}"))
                                continue
                            # 满足条件，创建建筑实例（从0级升到1级）
                            pb = PlayerBuilding(
                                player_id=db_player.id,
                                building_key=building_key,
                                level=0,
                            )
                            db.add(pb)
                            db.flush()

                        if pb.level >= bc.max_level:
                            await manager.send_to(username, build_packet(MsgType.ERROR, f"{bc.building_name}已满级"))
                            continue

                        # 再次检查前置（升级时也需要）
                        from building_configs import check_building_prerequisites
                        ok, reason = check_building_prerequisites(db, db_player.id, building_key)
                        if not ok:
                            await manager.send_to(username, build_packet(MsgType.ERROR, f"前置条件不满足: {reason}"))
                            continue

                        # 查询下一级消耗
                        next_lv = pb.level + 1
                        blc = db.query(BuildingLevelConfig).filter(
                            BuildingLevelConfig.building_key == building_key,
                            BuildingLevelConfig.level == next_lv,
                        ).first()
                        if not blc:
                            await manager.send_to(username, build_packet(MsgType.ERROR, f"等级配置缺失: {building_key} Lv{next_lv}"))
                            continue

                        # 检查资源是否足够
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
                            continue

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

                        # 如果是城主府升级，检查是否解锁新建筑
                        if building_key == "palace":
                            db_player.main_city_level = next_lv
                            from building_configs import init_player_buildings
                            init_player_buildings(db, db_player.id, next_lv)
                            # 重新计算产出（可能解锁了新资源建筑）
                            manager.recalculate_production(username, db)

                        db.commit()

                        action = "建造" if next_lv == 1 else "升级"
                        await manager.send_to(username, build_packet(MsgType.ERROR,
                            f"✅ {bc.building_name}{action}成功！当前 {next_lv}/{bc.max_level} 级"))
                    except Exception as e:
                        print(f"升级建筑错误: {e}")
                        import traceback
                        traceback.print_exc()
                        await manager.send_to(username, build_packet(MsgType.ERROR, f"升级建筑失败: {e}"))

                elif msg_type == MsgType.REQ_BUILDING_DETAIL:
                    try:
                        building_key = msg_data.get("building_key")
                        if not building_key:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "未指定建筑"))
                            continue

                        bc = db.query(BuildingConfig).filter(
                            BuildingConfig.building_key == building_key
                        ).first()
                        if not bc:
                            await manager.send_to(username, build_packet(MsgType.ERROR, "建筑不存在"))
                            continue

                        # 查询所有等级配置
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

                        # 玩家当前等级
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

            except Exception as e:
                print(f"消息处理异常: {e}")
                import traceback
                traceback.print_exc()
            finally:
                db.close()

    except WebSocketDisconnect:
        _db = SessionLocal()
        try:
            manager.disconnect(username, _db)
        finally:
            _db.close()
    except Exception as e:
        print(f"❌ 未捕获异常: {e}")
        import traceback
        traceback.print_exc()
        _db = SessionLocal()
        try:
            manager.disconnect(username, _db)
        finally:
            _db.close()


def start_server_thread():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())


class ServerGMConsole(tk.Tk):
    # ================= 战法效果模板库（完整版） =================
    EFFECT_TEMPLATES = {
        # 基础机制 - 伤害类
        "主动·群体攻击伤害（无需准备）": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军群体"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "对【目标】造成攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
        },
        "主动·群体策略伤害（无需准备）": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军群体"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "对【目标】造成策略伤害（伤害率【伤害率】%），受谋略属性影响。"
        },
        "主动·群体攻击伤害（需准备1回合）": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "1回合准备，对【目标】造成攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
        },
        "主动·群体策略伤害（需准备1回合）": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "1回合准备，对【目标】造成策略伤害（伤害率【伤害率】%），受谋略属性影响。"
        },
        "主动·单体多次攻击": {
            "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "对敌军单体发动【次数】次攻击（每次伤害率【伤害率】%），每次目标独立判定。"
        },
        "主动·单体多次策略伤害": {
            "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "对敌军单体发动【次数】次策略伤害（每次伤害率【伤害率】%），每次目标独立判定。"
        },
        "追击·攻击伤害": {
            "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "普通攻击后，对目标发动攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
        },
        "追击·策略伤害": {
            "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "普通攻击后，对目标发动策略伤害（伤害率【伤害率】%），受谋略属性影响。"
        },
        "被动·概率触发多次攻击": {
            "params": [{"name": "触发概率", "type": "number", "default": 30, "unit": "%"},
                       {"name": "次数", "type": "number", "default": 2, "unit": "次"},
                       {"name": "伤害率", "type": "number", "default": 80, "unit": "%"}],
            "description_template": "每回合有【触发概率】%的几率对敌军单体发动【次数】次攻击（每次伤害率【伤害率】%），自身无法发动主动战法。"
        },
        "分段/额外伤害": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                       {"name": "伤害率", "type": "number", "default": 100, "unit": "%"},
                       {"name": "额外伤害类型", "type": "choice", "options": ["火攻", "恐慌", "妖术"], "default": "火攻"},
                       {"name": "额外伤害率", "type": "number", "default": 80, "unit": "%"}],
            "description_template": "对【目标】造成策略伤害（伤害率【伤害率】%），并使目标在受到下一次伤害时额外引发【额外伤害类型】伤害（伤害率【额外伤害率】%）。"
        },

        # 控制类
        "控制·混乱": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】陷入混乱状态（无法行动，攻击目标随机），持续【持续时间】回合。"
        },
        "控制·犹豫": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】陷入犹豫状态（无法发动主动战法），持续【持续时间】回合。"
        },
        "控制·怯战": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】陷入怯战状态（无法进行普通攻击），持续【持续时间】回合。"
        },
        "控制·暴走": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】陷入暴走状态（攻击目标不分敌我），持续【持续时间】回合。"
        },
        "控制·禁疗": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】陷入禁疗状态（无法恢复兵力），持续【持续时间】回合。"
        },

        # 属性增减类
        "属性·提升友军": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                       {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                       {"name": "数值", "type": "number", "default": 20, "unit": "点"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使我军【目标】的【属性】属性提升【数值】点，持续【持续时间】回合。"
        },
        "属性·降低敌军": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                       {"name": "数值", "type": "number", "default": 20, "unit": "点"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使敌军【目标】的【属性】属性下降【数值】点，持续【持续时间】回合。"
        },
        "属性·吸取": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体"], "default": "敌军单体"},
                       {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                       {"name": "数值", "type": "number", "default": 15, "unit": "点"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "吸取【目标】【属性】各【数值】点，附加于自身和友军单体，持续【持续时间】回合。"
        },

        # 伤害增减类
        "伤害·提升友军": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                       {"name": "伤害类型", "type": "choice", "options": ["攻击伤害", "策略伤害", "追击战法伤害", "主动战法伤害"], "default": "攻击伤害"},
                       {"name": "提升幅度", "type": "number", "default": 20, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使我军【目标】的【伤害类型】提升【提升幅度】%，持续【持续时间】回合。"
        },
        "伤害·降低敌军": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "伤害类型", "type": "choice", "options": ["攻击伤害", "策略伤害"], "default": "攻击伤害"},
                       {"name": "降低幅度", "type": "number", "default": 20, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使敌军【目标】的【伤害类型】降低【降低幅度】%，持续【持续时间】回合。"
        },

        # 增益状态类
        "状态·先手": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【目标】进入先手状态（行动顺序优先），持续【持续时间】回合。"
        },
        "状态·连击": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军单体"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【目标】获得连击效果（每回合可进行两次普通攻击），持续【持续时间】回合。"
        },
        "状态·洞察": {
            "params": [{"name": "目标", "type": "choice", "options": ["自身", "我军单体", "我军全体"], "default": "自身"},
                       {"name": "持续时间", "type": "choice", "options": ["常驻", "2回合", "3回合", "4回合"], "default": "常驻"}],
            "description_template": "使【目标】进入洞察状态（免疫所有控制效果），持续【持续时间】。"
        },
        "状态·规避（1次）": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "使【目标】进入规避状态（免疫1次伤害），持续【持续时间】回合。"
        },
        "状态·规避（多次）": {
            "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"}],
            "description_template": "使我军全体进入规避状态（免疫接下来受到的【次数】次伤害）。"
        },
        "状态·援护": {
            "params": [{"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使自身进入援护状态（为友军全体抵挡普通攻击），持续【持续时间】回合。"
        },
        "状态·援护（交替）": {
            "params": [],
            "description_template": "前锋和中军会交替进入援护状态（为友军群体抵挡普通攻击）。"
        },

        # 恢复类
        "恢复·兵力": {
            "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军单体"},
                       {"name": "恢复率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "恢复【目标】兵力（恢复率【恢复率】%，受谋略属性影响）。"
        },
        "恢复·移除有害效果": {
            "params": [],
            "description_template": "移除我军全体有害效果。"
        },

        # 反击类
        "反击": {
            "params": [{"name": "位置", "type": "choice", "options": ["前锋", "中军", "全体"], "default": "前锋"},
                       {"name": "伤害率", "type": "number", "default": 60, "unit": "%"},
                       {"name": "伤害类型", "type": "choice", "options": ["攻击", "策略"], "default": "攻击"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【位置】受到普通攻击时进行反击（伤害率【伤害率】%，类型为【伤害类型】），持续【持续时间】回合。"
        },

        # 持续伤害类
        "持续·恐慌": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【目标】陷入恐慌状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
        },
        "持续·妖术": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【目标】陷入妖术状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
        },
        "持续·燃烧": {
            "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "使【目标】陷入燃烧状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
        },
        "持续·火攻": {
            "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"},
                       {"name": "提升幅度", "type": "number", "default": 5, "unit": "%"}],
            "description_template": "对敌军单体造成火攻伤害（伤害率【伤害率】%），并使目标受到的火攻和持续性伤害提升【提升幅度】%（可叠加）。"
        },

        # 其他基础机制
        "士气·降低敌军": {
            "params": [{"name": "数值", "type": "number", "default": 10, "unit": "点"}],
            "description_template": "使敌军士气降低【数值】点。"
        },
        "士气·提升我军": {
            "params": [{"name": "数值", "type": "number", "default": 8, "unit": "点"}],
            "description_template": "使我军全体每回合开始时士气提升【数值】点。"
        },
        "跳过准备回合（自身）": {
            "params": [{"name": "跳过几率", "type": "number", "default": 80, "unit": "%"}],
            "description_template": "每当自身发动需要准备的主战法时，有【跳过几率】%几率跳过准备回合。"
        },
        "跳过准备回合（友军）": {
            "params": [{"name": "跳过几率", "type": "number", "default": 75, "unit": "%"}],
            "description_template": "使友军单体主战法有【跳过几率】%的几率跳过1回合准备时间。"
        },
        "发动率提升（主动）": {
            "params": [{"name": "目标", "type": "choice", "options": ["友军单体", "友军群体"], "default": "友军单体"},
                       {"name": "提升幅度", "type": "number", "default": 120, "unit": "%"}],
            "description_template": "使【目标】在1回合内主动主战法发动率提高【提升幅度】%（可超过100%）。"
        },
        "发动率提升（追击）": {
            "params": [{"name": "提升幅度", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "使我军群体追击战法发动率提升【提升幅度】%。"
        },
        "伤害递增": {
            "params": [{"name": "增加率", "type": "number", "default": 40, "unit": "%"}],
            "description_template": "每次发动后，伤害率增加【增加率】%。"
        },
        "无视防御/规避": {
            "params": [],
            "description_template": "造成的伤害无视防御/规避。"
        },

        # 复合机制
        "复合·控制/减益结束后触发伤害/增益": {
            "params": [{"name": "生效回合", "type": "number", "default": 2, "unit": "回合"},
                       {"name": "控制类型", "type": "choice", "options": ["怯战", "犹豫", "混乱", "暴走", "禁疗"], "default": "怯战"},
                       {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "控制持续时间", "type": "number", "default": 2, "unit": "回合"},
                       {"name": "后续伤害类型", "type": "choice", "options": ["攻击", "策略"], "default": "策略"},
                       {"name": "后续伤害率", "type": "number", "default": 215, "unit": "%"},
                       {"name": "无视规避", "type": "choice", "options": ["否", "是"], "default": "是"}],
            "description_template": "战斗开始后前【生效回合】回合，使【控制目标】陷入【控制类型】状态，持续【控制持续时间】回合。效果结束后，对敌军全体发动一次【后续伤害类型】攻击（伤害率【后续伤害率】%）" + ("，造成的伤害无视规避" if "是" else "") + "。"
        },
        "复合·每回合概率怯战/犹豫": {
            "params": [{"name": "生效回合", "type": "number", "default": 3, "unit": "回合"},
                       {"name": "控制类型", "type": "choice", "options": ["怯战", "犹豫"], "default": "怯战"},
                       {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "触发概率", "type": "number", "default": 90, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
            "description_template": "战斗开始后前【生效回合】回合，使【控制目标】每回合有【触发概率】%的几率陷入【控制类型】状态，持续【持续时间】回合。"
        },
        "复合·首回合犹豫+后续降伤": {
            "params": [{"name": "生效回合", "type": "number", "default": 3, "unit": "回合"},
                       {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                       {"name": "首回合几率", "type": "number", "default": 100, "unit": "%"}],
            "description_template": "战斗开始后前【生效回合】回合，使【控制目标】发动主动战法时造成的伤害大幅下降，并在首回合有【首回合几率】%的几率使其陷入犹豫状态，无法发动主动战法。"
        },
        "复合·特定回合自身行动时施加增益/减益": {
            "params": [{"name": "触发回合", "type": "string", "default": "2,4,6", "description": "逗号分隔的回合数"},
                       {"name": "目标", "type": "choice", "options": ["我军全体", "我军群体"], "default": "我军全体"},
                       {"name": "效果", "type": "choice", "options": ["属性提升", "减伤"], "default": "属性提升"},
                       {"name": "属性1", "type": "choice", "options": ["谋略", "防御", "攻击", "速度"], "default": "谋略"},
                       {"name": "属性2", "type": "choice", "options": ["谋略", "防御", "攻击", "速度"], "default": "防御"},
                       {"name": "属性值", "type": "number", "default": 80, "unit": "点"},
                       {"name": "减伤幅度", "type": "number", "default": 20, "unit": "%"},
                       {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
            "description_template": "第【触发回合】回合自身行动时，使【目标】【效果】。"
        },
        "复合·每回合概率触发多层效果": {
            "params": [{"name": "触发概率", "type": "number", "default": 30, "unit": "%"},
                       {"name": "伤害率1", "type": "number", "default": 180, "unit": "%"},
                       {"name": "伤害率2", "type": "number", "default": 150, "unit": "%"}],
            "description_template": "每回合行动时有【触发概率】%几率对敌军大营和中军分别发动一次攻击（伤害率【伤害率1】%），同时使速度最高的友军单体对敌军大营及中军分别发动一次攻击（伤害率【伤害率2】%）。"
        },
        "复合·次数累计提升几率": {
            "params": [{"name": "累计次数", "type": "number", "default": 3, "unit": "次"},
                       {"name": "提升几率", "type": "number", "default": 5, "unit": "%"}],
            "description_template": "该效果每生效【累计次数】次后，生效几率提升【提升几率】%，可叠加。"
        },
        "复合·累计伤害次数触发": {
            "params": [{"name": "累计伤害次数", "type": "number", "default": 15, "unit": "次"},
                       {"name": "效果描述", "type": "string", "default": "触发效果"}],
            "description_template": "敌军全体累计造成【累计伤害次数】次伤害后，下回合自身发动：【效果描述】。"
        },
        "复合·兵力阈值触发额外伤害/恢复": {
            "params": [{"name": "阈值", "type": "number", "default": 50, "unit": "%"},
                       {"name": "比较方向", "type": "choice", "options": ["高于", "低于"], "default": "高于"},
                       {"name": "额外效果", "type": "choice", "options": ["伤害", "恢复"], "default": "伤害"},
                       {"name": "额外伤害率", "type": "number", "default": 86, "unit": "%"},
                       {"name": "恢复率", "type": "number", "default": 82, "unit": "%"}],
            "description_template": "对敌军群体造成策略攻击（伤害率【伤害率】%）并使其陷入燃烧状态，当目标兵力【比较方向】初始兵力【阈值】%时受到一次策略伤害（【额外伤害率】%）；同时使我军群体恢复兵力（恢复率【恢复率】%），当目标兵力【比较方向】初始兵力【阈值】%时恢复兵力（【恢复率】%）。"
        },
        "复合·宝物类型判定": {
            "params": [{"name": "伤害率", "type": "number", "default": 280, "unit": "%"}],
            "description_template": "对敌军群体发动攻击（伤害率【伤害率】%）。当授予不同宝物时，额外获得：剑-移除增益；刀-自身攻击伤害提升12%；长兵-目标攻击距离-1；弓-50%几率目标+1；其他-目标防御降低30%。"
        },
        "复合·回合数影响目标/效果": {
            "params": [{"name": "间隔回合", "type": "number", "default": 2, "unit": "回合"},
                       {"name": "效果描述", "type": "string", "default": "获得效果"},
                       {"name": "切换回合", "type": "number", "default": 3, "unit": "回合"}],
            "description_template": "每【间隔回合】回合使友军单体【效果描述】；第【切换回合】回合发动时目标调整为友军全体。"
        },
    }

    def __init__(self):
        super().__init__()
        self.title("InfiniteBorders 服务器控制台 (GM Tool)")
        self.geometry("800x600")
        self.resizable(True, True)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.create_tab_dashboard()
        self.create_tab_skill()
        self.create_tab_hero()
        self.create_tab_pack()
        self.create_tab_pack_drop()

    # -------------------- 运行状态标签页 --------------------
    def create_tab_dashboard(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🎮 运行状态")
        self.status_lbl = tk.Label(tab, text="当前状态: 🔴 已停止", fg="red", font=("Arial", 12))
        self.status_lbl.pack(pady=30)
        self.btn_start = tk.Button(
            tab,
            text="🚀 一键启动服务器",
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12),
            width=20,
            command=self.start_server,
        )
        self.btn_start.pack()

    # -------------------- 战法管理标签页 --------------------
    def create_tab_skill(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📜 战法管理")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        btn_add = ttk.Button(toolbar, text="新增战法", command=self.add_skill)
        btn_add.pack(side=tk.LEFT, padx=2)
        btn_edit = ttk.Button(toolbar, text="编辑战法", command=self.edit_skill)
        btn_edit.pack(side=tk.LEFT, padx=2)
        btn_del = ttk.Button(toolbar, text="删除战法", command=self.del_skill)
        btn_del.pack(side=tk.LEFT, padx=2)
        btn_config = ttk.Button(toolbar, text="配置效果", command=self.config_skill_effect)
        btn_config.pack(side=tk.LEFT, padx=2)
        btn_refresh = ttk.Button(toolbar, text="刷新", command=self.refresh_skill_tree)
        btn_refresh.pack(side=tk.LEFT, padx=2)

        columns = ("ID", "名称", "品质", "类型", "发动率", "距离", "目标", "兵种", "描述")
        self.skill_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)
        for col in columns:
            self.skill_tree.heading(col, text=col)
            self.skill_tree.column(col, width=100, anchor="center")
        self.skill_tree.column("描述", width=200)
        self.skill_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.refresh_skill_tree()

    def refresh_skill_tree(self):
        for item in self.skill_tree.get_children():
            self.skill_tree.delete(item)
        db = SessionLocal()
        skills = db.query(Skill).all()
        for s in skills:
            self.skill_tree.insert("", tk.END, values=(
                s.id, s.name, s.quality, s.skill_type, s.activation_rate,
                s.range, s.target_type, s.troop_type, s.description[:20] + "..."
            ))
        db.close()

    def add_skill(self):
        self._skill_dialog("新增战法")

    def edit_skill(self):
        selected = self.skill_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一条战法")
            return
        item = self.skill_tree.item(selected[0])
        skill_id = item['values'][0]
        self._skill_dialog("编辑战法", skill_id)

    def del_skill(self):
        selected = self.skill_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一条战法")
            return
        if messagebox.askyesno("确认", "删除战法将同时影响使用它的武将，确定删除吗？"):
            item = self.skill_tree.item(selected[0])
            skill_id = item['values'][0]
            db = SessionLocal()
            db.query(Skill).filter(Skill.id == skill_id).delete()
            db.commit()
            db.close()
            self.refresh_skill_tree()
            messagebox.showinfo("成功", "战法已删除")

    def _skill_dialog(self, title, skill_id=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("500x500")
        win.resizable(False, False)

        fields = {}
        labels = [
            ("名称", "name"),
            ("品质", "quality"),
            ("类型", "skill_type"),
            ("发动率", "activation_rate"),
            ("有效距离", "range"),
            ("目标类型", "target_type"),
            ("兵种限制", "troop_type"),
            ("描述", "description"),
        ]
        quality_opts = ["S", "A", "B", "C"]
        skill_type_opts = ["主动", "被动", "指挥", "追击"]
        target_opts = ["自己", "敌军单体", "敌军群体", "友军单体", "友军群体", "全体"]
        troop_opts = ["通用", "步兵", "骑兵", "弓兵"]

        row = 0
        for text, key in labels:
            ttk.Label(win, text=text).grid(row=row, column=0, padx=5, pady=5, sticky="e")
            if key in ["quality", "skill_type", "target_type", "troop_type"]:
                var = tk.StringVar()
                opts = {
                    "quality": quality_opts,
                    "skill_type": skill_type_opts,
                    "target_type": target_opts,
                    "troop_type": troop_opts
                }[key]
                combo = ttk.Combobox(win, textvariable=var, values=opts, state="readonly")
                combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
                fields[key] = var
            else:
                entry = ttk.Entry(win, width=30)
                entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
                fields[key] = entry
            row += 1

        if skill_id:
            db = SessionLocal()
            skill = db.query(Skill).get(skill_id)
            if skill:
                fields["name"].insert(0, skill.name)
                fields["quality"].set(skill.quality)
                fields["skill_type"].set(skill.skill_type)
                fields["activation_rate"].insert(0, str(skill.activation_rate))
                fields["range"].insert(0, str(skill.range))
                fields["target_type"].set(skill.target_type)
                fields["troop_type"].set(skill.troop_type)
                fields["description"].insert(0, skill.description)
            db.close()

        def save():
            name = fields["name"].get()
            if not name:
                messagebox.showerror("错误", "战法名称不能为空")
                return
            quality = fields["quality"].get()
            skill_type = fields["skill_type"].get()
            try:
                activation_rate = int(fields["activation_rate"].get())
                range_val = int(fields["range"].get())
            except ValueError:
                messagebox.showerror("错误", "发动率和距离必须是整数")
                return
            target_type = fields["target_type"].get()
            troop_type = fields["troop_type"].get()
            description = fields["description"].get()

            db = SessionLocal()
            if skill_id:
                skill = db.query(Skill).get(skill_id)
                if skill:
                    skill.name = name
                    skill.quality = quality
                    skill.skill_type = skill_type
                    skill.activation_rate = activation_rate
                    skill.range = range_val
                    skill.target_type = target_type
                    skill.troop_type = troop_type
                    skill.description = description
            else:
                new_skill = Skill(
                    name=name, level=1, quality=quality, skill_type=skill_type,
                    activation_rate=activation_rate, range=range_val,
                    target_type=target_type, troop_type=troop_type,
                    description=description, effect="",
                    effect_config={
                        "nodes": [
                            {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
                            {"id": 1, "type": "GetEnemy", "x": 350, "y": 200,
                             "params": {"数量": "全体"}},
                            {"id": 2, "type": "ApplyDamage", "x": 600, "y": 200,
                             "params": {"伤害类型": "攻击", "伤害率": 100.0}},
                        ],
                        "links": [
                            {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
                            {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
                            {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
                        ]
                    }
                )
                db.add(new_skill)
            db.commit()
            db.close()
            win.destroy()
            self.refresh_skill_tree()
            messagebox.showinfo("成功", "战法已保存")

        ttk.Button(win, text="保存", command=save).grid(row=row, column=0, columnspan=2, pady=20)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=row+1, column=0, columnspan=2)

    def config_skill_effect(self):
        selected = self.skill_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个战法")
            return
        item = self.skill_tree.item(selected[0])
        skill_id = item['values'][0]
        db = SessionLocal()
        skill = db.query(Skill).get(skill_id)
        if not skill:
            db.close()
            messagebox.showerror("错误", "战法不存在")
            return
        skill_name = skill.name
        effect_config = skill.effect_config

        editor = NodeEditor(self, skill_name, effect_config)

        def on_save(skill_name, config):
            new_db = SessionLocal()
            skill = new_db.query(Skill).get(skill_id)
            if skill:
                skill.effect_config = config
                new_db.commit()
                new_db.close()
                self.refresh_skill_tree()
                messagebox.showinfo("成功", f"战法【{skill_name}】效果已保存")
            else:
                new_db.close()
                messagebox.showerror("错误", f"未找到战法（ID={skill_id}），保存失败")

        editor.on_node_editor_save = on_save
        db.close()

    # -------------------- 武将管理标签页 --------------------
    def create_tab_hero(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="⚔️ 武将管理")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        btn_add = ttk.Button(toolbar, text="新增武将", command=self.add_hero_template)
        btn_add.pack(side=tk.LEFT, padx=2)
        btn_edit = ttk.Button(toolbar, text="编辑武将", command=self.edit_hero_template)
        btn_edit.pack(side=tk.LEFT, padx=2)
        btn_del = ttk.Button(toolbar, text="删除武将", command=self.del_hero_template)
        btn_del.pack(side=tk.LEFT, padx=2)
        btn_refresh = ttk.Button(toolbar, text="刷新", command=self.refresh_hero_tree)
        btn_refresh.pack(side=tk.LEFT, padx=2)

        columns = ("ID", "名称", "星级", "阵营", "兵种", "统率", "自带战法", "攻击成长", "防御成长", "速度成长")
        self.hero_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)
        for col in columns:
            self.hero_tree.heading(col, text=col)
            self.hero_tree.column(col, width=80, anchor="center")
        self.hero_tree.column("名称", width=100)
        self.hero_tree.column("自带战法", width=120)
        self.hero_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.refresh_hero_tree()

    def refresh_hero_tree(self):
        for item in self.hero_tree.get_children():
            self.hero_tree.delete(item)
        db = SessionLocal()
        heroes = db.query(HeroTemplate).all()
        for h in heroes:
            skill_name = ""
            if h.innate_skill_id:
                skill = db.query(Skill).get(h.innate_skill_id)
                if skill:
                    skill_name = skill.name
            self.hero_tree.insert("", tk.END, values=(
                h.id, h.name, h.stars, h.faction, h.troop_type,
                h.cost, skill_name, h.atk_g, h.def_g, h.spd_g
            ))
        db.close()

    def add_hero_template(self):
        self._hero_template_dialog("新增武将")

    def edit_hero_template(self):
        selected = self.hero_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个武将")
            return
        item = self.hero_tree.item(selected[0])
        hero_id = item['values'][0]
        self._hero_template_dialog("编辑武将", hero_id)

    def del_hero_template(self):
        selected = self.hero_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个武将")
            return
        if messagebox.askyesno("确认", "删除武将模板将影响已存在的武将实体，确定删除吗？"):
            item = self.hero_tree.item(selected[0])
            hero_id = item['values'][0]
            db = SessionLocal()
            db.query(HeroTemplate).filter(HeroTemplate.id == hero_id).delete()
            db.commit()
            db.close()
            self.refresh_hero_tree()
            messagebox.showinfo("成功", "武将已删除")

    def _hero_template_dialog(self, title, hero_id=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("700x600")
        win.resizable(False, False)

        fields = {}
        labels = [
            ("名称", "name"),
            ("星级(1-5)", "stars"),
            ("统率Cost", "cost"),
            ("攻击距离", "attack_range"),
            ("阵营", "faction"),
            ("兵种", "troop_type"),
            ("初始攻击", "atk"),
            ("初始防御", "defs"),
            ("初始谋略", "strg"),
            ("初始攻城", "sie"),
            ("初始速度", "spd"),
            ("攻击成长", "atk_g"),
            ("防御成长", "def_g"),
            ("谋略成长", "strg_g"),
            ("攻城成长", "sie_g"),
            ("速度成长", "spd_g"),
            ("自带战法", "innate_skill_id"),
        ]
        row = 0
        for text, key in labels:
            ttk.Label(win, text=text).grid(row=row, column=0, padx=5, pady=5, sticky="e")
            if key == "innate_skill_id":
                frame = ttk.Frame(win)
                frame.grid(row=row, column=1, padx=5, pady=5, sticky="w")
                skill_var = tk.StringVar()
                skill_combo = ttk.Combobox(frame, textvariable=skill_var, state="readonly", width=25)
                skill_combo.pack(side=tk.LEFT)
                btn_new_skill = ttk.Button(frame, text="新建战法",
                                           command=lambda: self._create_skill_and_refresh(skill_combo))
                btn_new_skill.pack(side=tk.LEFT, padx=5)
                fields[key] = (skill_combo, skill_var)
            elif key in ["faction", "troop_type"]:
                opts = {
                    "faction": ["魏", "蜀", "吴", "群", "汉"],
                    "troop_type": ["步兵", "骑兵", "弓兵"]
                }[key]
                combo = ttk.Combobox(win, values=opts, state="readonly", width=20)
                combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
                fields[key] = combo
            else:
                entry = ttk.Entry(win, width=20)
                entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
                fields[key] = entry
            row += 1

        self._refresh_skill_combo(fields["innate_skill_id"][0])

        if hero_id:
            db = SessionLocal()
            hero = db.query(HeroTemplate).get(hero_id)
            if hero:
                fields["name"].insert(0, hero.name)
                fields["stars"].insert(0, str(hero.stars))
                fields["cost"].insert(0, str(hero.cost))
                fields["attack_range"].insert(0, str(hero.attack_range))
                fields["faction"].set(hero.faction)
                fields["troop_type"].set(hero.troop_type)
                fields["atk"].insert(0, str(hero.atk))
                fields["defs"].insert(0, str(hero.defs))
                fields["strg"].insert(0, str(hero.strg))
                fields["sie"].insert(0, str(hero.sie))
                fields["spd"].insert(0, str(hero.spd))
                fields["atk_g"].insert(0, str(hero.atk_g))
                fields["def_g"].insert(0, str(hero.def_g))
                fields["strg_g"].insert(0, str(hero.strg_g))
                fields["sie_g"].insert(0, str(hero.sie_g))
                fields["spd_g"].insert(0, str(hero.spd_g))
                if hero.innate_skill_id:
                    skill = db.query(Skill).get(hero.innate_skill_id)
                    if skill:
                        fields["innate_skill_id"][1].set(skill.name)
            db.close()

        def save():
            try:
                name = fields["name"].get()
                stars = int(fields["stars"].get())
                cost = float(fields["cost"].get())
                attack_range = int(fields["attack_range"].get())
                faction = fields["faction"].get()
                troop_type = fields["troop_type"].get()
                atk = float(fields["atk"].get())
                defs = float(fields["defs"].get())
                strg = float(fields["strg"].get())
                sie = float(fields["sie"].get())
                spd = float(fields["spd"].get())
                atk_g = float(fields["atk_g"].get())
                def_g = float(fields["def_g"].get())
                strg_g = float(fields["strg_g"].get())
                sie_g = float(fields["sie_g"].get())
                spd_g = float(fields["spd_g"].get())
                skill_name = fields["innate_skill_id"][1].get()
                skill_id = None
                if skill_name:
                    db = SessionLocal()
                    skill = db.query(Skill).filter(Skill.name == skill_name).first()
                    if skill:
                        skill_id = skill.id
                    db.close()
            except ValueError as e:
                messagebox.showerror("错误", f"数值格式错误: {e}")
                return

            db = SessionLocal()
            if hero_id:
                hero = db.query(HeroTemplate).get(hero_id)
                if hero:
                    hero.name = name
                    hero.stars = stars
                    hero.cost = cost
                    hero.attack_range = attack_range
                    hero.faction = faction
                    hero.troop_type = troop_type
                    hero.atk = atk
                    hero.defs = defs
                    hero.strg = strg
                    hero.sie = sie
                    hero.spd = spd
                    hero.atk_g = atk_g
                    hero.def_g = def_g
                    hero.strg_g = strg_g
                    hero.sie_g = sie_g
                    hero.spd_g = spd_g
                    hero.innate_skill_id = skill_id
            else:
                new_hero = HeroTemplate(
                    name=name, stars=stars, cost=cost, attack_range=attack_range,
                    faction=faction, troop_type=troop_type,
                    atk=atk, defs=defs, strg=strg, sie=sie, spd=spd,
                    atk_g=atk_g, def_g=def_g, strg_g=strg_g, sie_g=sie_g, spd_g=spd_g,
                    innate_skill_id=skill_id
                )
                db.add(new_hero)
            db.commit()
            db.close()
            win.destroy()
            self.refresh_hero_tree()
            messagebox.showinfo("成功", "武将已保存")

        ttk.Button(win, text="保存", command=save).grid(row=row, column=0, columnspan=2, pady=20)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=row+1, column=0, columnspan=2)

    def _refresh_skill_combo(self, combo):
        db = SessionLocal()
        skills = db.query(Skill).all()
        skill_names = [s.name for s in skills]
        combo['values'] = skill_names
        if skill_names:
            combo.set(skill_names[0])
        db.close()

    def _create_skill_and_refresh(self, combo):
        self._skill_dialog("新增战法")
        self._refresh_skill_combo(combo)

    # -------------------- 卡包管理标签页 --------------------
    def create_tab_pack(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📦 卡包管理")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        btn_add = ttk.Button(toolbar, text="新增卡包", command=self.add_pack)
        btn_add.pack(side=tk.LEFT, padx=2)
        btn_edit = ttk.Button(toolbar, text="编辑卡包", command=self.edit_pack)
        btn_edit.pack(side=tk.LEFT, padx=2)
        btn_del = ttk.Button(toolbar, text="删除卡包", command=self.del_pack)
        btn_del.pack(side=tk.LEFT, padx=2)
        btn_refresh = ttk.Button(toolbar, text="刷新", command=self.refresh_pack_tree)
        btn_refresh.pack(side=tk.LEFT, padx=2)

        columns = ("ID", "名称", "消耗类型", "消耗数量")
        self.pack_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)
        for col in columns:
            self.pack_tree.heading(col, text=col)
            self.pack_tree.column(col, width=100, anchor="center")
        self.pack_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.refresh_pack_tree()

    def refresh_pack_tree(self):
        for item in self.pack_tree.get_children():
            self.pack_tree.delete(item)
        db = SessionLocal()
        packs = db.query(CardPack).all()
        for p in packs:
            self.pack_tree.insert("", tk.END, values=(p.id, p.name, p.cost_type, p.cost_amount))
        db.close()

    def add_pack(self):
        self._pack_dialog("新增卡包")

    def edit_pack(self):
        selected = self.pack_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个卡包")
            return
        item = self.pack_tree.item(selected[0])
        pack_id = item['values'][0]
        self._pack_dialog("编辑卡包", pack_id)

    def del_pack(self):
        selected = self.pack_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个卡包")
            return
        if messagebox.askyesno("确认", "删除卡包将同时删除其掉落配置，确定删除吗？"):
            item = self.pack_tree.item(selected[0])
            pack_id = item['values'][0]
            db = SessionLocal()
            db.query(CardPackDrop).filter(CardPackDrop.pack_id == pack_id).delete()
            db.query(CardPack).filter(CardPack.id == pack_id).delete()
            db.commit()
            db.close()
            self.refresh_pack_tree()
            messagebox.showinfo("成功", "卡包已删除")

    def _pack_dialog(self, title, pack_id=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("300x200")

        ttk.Label(win, text="卡包名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        name_entry = ttk.Entry(win, width=20)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(win, text="消耗类型:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        cost_type_combo = ttk.Combobox(win, values=["tiger", "copper"], state="readonly", width=15)
        cost_type_combo.set("tiger")
        cost_type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(win, text="消耗数量:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        cost_amount_entry = ttk.Entry(win, width=10)
        cost_amount_entry.insert(0, "200")
        cost_amount_entry.grid(row=2, column=1, padx=5, pady=5)

        if pack_id:
            db = SessionLocal()
            pack = db.query(CardPack).get(pack_id)
            if pack:
                name_entry.insert(0, pack.name)
                cost_type_combo.set(pack.cost_type)
                cost_amount_entry.delete(0, tk.END)
                cost_amount_entry.insert(0, str(pack.cost_amount))
            db.close()

        def save():
            name = name_entry.get()
            cost_type = cost_type_combo.get()
            try:
                cost_amount = int(cost_amount_entry.get())
            except ValueError:
                messagebox.showerror("错误", "消耗数量必须是整数")
                return
            db = SessionLocal()
            if pack_id:
                pack = db.query(CardPack).get(pack_id)
                if pack:
                    pack.name = name
                    pack.cost_type = cost_type
                    pack.cost_amount = cost_amount
            else:
                new_pack = CardPack(name=name, cost_type=cost_type, cost_amount=cost_amount)
                db.add(new_pack)
            db.commit()
            db.close()
            win.destroy()
            self.refresh_pack_tree()
            messagebox.showinfo("成功", "卡包已保存")

        ttk.Button(win, text="保存", command=save).grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=4, column=0, columnspan=2)

    # -------------------- 卡包掉落配置标签页 --------------------
    def create_tab_pack_drop(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🎲 卡包掉落")

        left_frame = ttk.Frame(tab)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(left_frame, text="选择卡包:").pack(anchor=tk.W)
        self.pack_combo = ttk.Combobox(left_frame, state="readonly")
        self.pack_combo.pack(fill=tk.X, pady=5)
        self.pack_combo.bind("<<ComboboxSelected>>", self.on_pack_selected)

        btn_refresh_packs = ttk.Button(left_frame, text="刷新卡包列表", command=self.refresh_pack_combo)
        btn_refresh_packs.pack(pady=5)

        right_frame = ttk.Frame(tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("武将ID", "武将名称", "权重")
        self.drop_tree = ttk.Treeview(right_frame, columns=columns, show="headings", height=20)
        for col in columns:
            self.drop_tree.heading(col, text=col)
            self.drop_tree.column(col, width=100, anchor="center")
        self.drop_tree.pack(fill=tk.BOTH, expand=True)

        btn_add_drop = ttk.Button(right_frame, text="添加掉落", command=self.add_drop)
        btn_add_drop.pack(side=tk.LEFT, padx=5, pady=5)
        btn_edit_drop = ttk.Button(right_frame, text="编辑掉落", command=self.edit_drop)
        btn_edit_drop.pack(side=tk.LEFT, padx=5, pady=5)
        btn_del_drop = ttk.Button(right_frame, text="删除掉落", command=self.del_drop)
        btn_del_drop.pack(side=tk.LEFT, padx=5, pady=5)

        self.refresh_pack_combo()

    def refresh_pack_combo(self):
        db = SessionLocal()
        packs = db.query(CardPack).all()
        pack_names = [f"{p.id}: {p.name}" for p in packs]
        self.pack_combo['values'] = pack_names
        if pack_names:
            self.pack_combo.set(pack_names[0])
            self.on_pack_selected()
        db.close()

    def on_pack_selected(self, event=None):
        selected = self.pack_combo.get()
        if not selected:
            return
        pack_id = int(selected.split(":")[0])
        db = SessionLocal()
        drops = db.query(CardPackDrop).filter(CardPackDrop.pack_id == pack_id).all()
        self.drop_tree.delete(*self.drop_tree.get_children())
        for d in drops:
            hero = db.query(HeroTemplate).get(d.template_id)
            hero_name = hero.name if hero else "未知"
            self.drop_tree.insert("", tk.END, values=(d.template_id, hero_name, d.weight))
        db.close()

    def add_drop(self):
        selected = self.pack_combo.get()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个卡包")
            return
        pack_id = int(selected.split(":")[0])
        self._drop_dialog(pack_id)

    def edit_drop(self):
        selected = self.drop_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个掉落")
            return
        item = self.drop_tree.item(selected[0])
        hero_id = item['values'][0]
        weight = item['values'][2]
        pack_id = int(self.pack_combo.get().split(":")[0])
        self._drop_dialog(pack_id, hero_id, weight)

    def del_drop(self):
        selected = self.drop_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个掉落")
            return
        if messagebox.askyesno("确认", "确定删除该掉落吗？"):
            item = self.drop_tree.item(selected[0])
            hero_id = item['values'][0]
            pack_id = int(self.pack_combo.get().split(":")[0])
            db = SessionLocal()
            drop = db.query(CardPackDrop).filter(
                CardPackDrop.pack_id == pack_id,
                CardPackDrop.template_id == hero_id
            ).first()
            if drop:
                db.delete(drop)
                db.commit()
            db.close()
            self.on_pack_selected()
            messagebox.showinfo("成功", "掉落已删除")

    def _drop_dialog(self, pack_id, hero_id=None, weight=None):
        win = tk.Toplevel(self)
        win.title("配置掉落")
        win.geometry("300x200")

        ttk.Label(win, text="武将:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        hero_combo = ttk.Combobox(win, state="readonly", width=20)
        hero_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(win, text="权重:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        weight_entry = ttk.Entry(win, width=10)
        weight_entry.grid(row=1, column=1, padx=5, pady=5)

        db = SessionLocal()
        heroes = db.query(HeroTemplate).all()
        hero_items = [f"{h.id}: {h.name}" for h in heroes]
        hero_combo['values'] = hero_items
        if hero_id:
            hero_combo.set(f"{hero_id}: {next(h.name for h in heroes if h.id == hero_id)}")
        if weight:
            weight_entry.insert(0, str(weight))
        db.close()

        def save():
            try:
                hero_str = hero_combo.get()
                if not hero_str:
                    return
                hero_id_val = int(hero_str.split(":")[0])
                weight_val = float(weight_entry.get())
            except:
                messagebox.showerror("错误", "权重必须是数字")
                return

            db = SessionLocal()
            existing = db.query(CardPackDrop).filter(
                CardPackDrop.pack_id == pack_id,
                CardPackDrop.template_id == hero_id_val
            ).first()
            if existing and hero_id is None:
                messagebox.showerror("错误", "该武将已在此卡包中，请编辑或删除")
                db.close()
                return
            if existing and hero_id:
                existing.weight = weight_val
            else:
                new_drop = CardPackDrop(pack_id=pack_id, template_id=hero_id_val, weight=weight_val)
                db.add(new_drop)
            db.commit()
            db.close()
            win.destroy()
            self.on_pack_selected()
            messagebox.showinfo("成功", "掉落配置已保存")

        ttk.Button(win, text="保存", command=save).grid(row=2, column=0, columnspan=2, pady=20)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=3, column=0, columnspan=2)

    # -------------------- 启动服务器 --------------------
    def start_server(self):
        self.btn_start.config(state=tk.DISABLED, text="服务器运行中...")
        self.status_lbl.config(text="当前状态: 🟢 运行中 (端口: 8000)", fg="green")
        threading.Thread(target=start_server_thread, daemon=True).start()


if __name__ == "__main__":
    ServerGMConsole().mainloop()
# core/connection_manager.py
# WebSocket 连接管理、玩家在线状态、资源产出计算
import json
from fastapi import WebSocket
from sqlalchemy.orm import Session

from shared.protocol import MsgType, build_packet
from models.schema import (
    Player, Tile, PlayerBuilding, BuildingLevelConfig
)
from hex_utils import get_neighbors
from config import RES_MAP


class ConnectionManager:
    """管理所有 WebSocket 连接和玩家在线状态。"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.online_players: dict = {}

    async def connect(self, websocket: WebSocket, username: str, db: Session):
        """第一步：接受连接并验证玩家存在。返回 Player 对象或 None。"""
        try:
            await websocket.accept()
        except Exception as e:
            print(f"WebSocket 接受连接失败: {e}")
            return None

        self.active_connections[username] = websocket
        db_player = db.query(Player).filter(Player.username == username).first()
        if not db_player:
            try:
                await websocket.send_text(json.dumps(build_packet(MsgType.ERROR, "玩家不存在，请先注册！")))
                await websocket.close()
            except:
                pass
            del self.active_connections[username]
            return None

        return db_player

    async def complete_login(self, username: str, db: Session):
        """第二步：密码验证通过后完成登录，设置在线状态并发送 res_login。"""
        db_player = db.query(Player).filter(Player.username == username).first()
        if not db_player:
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
            # 建筑效果汇总（登录/升级时重算）
            "building_effects": self._default_building_effects(),
        }
        self.recalculate_production(username, db)
        self.recalculate_building_effects(username, db)

        try:
            # 登录响应（轻量：不含地图，地图数据通过 req_map 单独请求）
            await self.active_connections[username].send_text(
                json.dumps(
                    build_packet(
                        MsgType.RES_LOGIN,
                        {
                            "player_id": db_player.id,
                            "username": db_player.username,
                            "spawn": {"x": db_player.spawn_x, "y": db_player.spawn_y},
                            "resources": self.online_players[username]["resources"],
                            "currencies": self.online_players[username]["currencies"],
                        },
                    )
                )
            )
        except Exception as e:
            print(f"发送登录数据失败: {e}")
            try:
                await self.active_connections[username].close()
            except:
                pass
            return

    def _default_building_effects(self) -> dict:
        """返回建筑效果的默认值（未建任何建筑时的基础状态）。"""
        return {
            # 资源上限（仓库）
            "storage_cap": 50000,           # 默认5万
            # 部队相关（校场/兵营）
            "troop_slots": 1,               # 可出征队伍数（校场）
            "troop_capacity": 200,          # 部队单队最大兵力（兵营）
            "vanguard_slots": 0,            # 前锋营武将槽
            "reserve_cap": 0,               # 预备役上限
            # 招募速度（募兵所）
            "recruit_speed_bonus": 0,       # 百分比加速
            # 战斗属性加成（各战营）
            "attack_bonus": 0,              # 全军攻击加成（固定值，尚武营+武将巨像）
            "defense_bonus": 0,             # 全军防御加成（铁壁营+城墙）
            "speed_bonus": 0,               # 全军速度加成（疾风营）
            "strategy_bonus": 0,            # 全军谋略加成（军机营+沙盘阵图）
            # 点将台：阵营属性加成（汉/魏/蜀/吴/群）
            "faction_bonus": {
                "汉": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
                "魏": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
                "蜀": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
                "吴": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
                "群": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
            },
            # 防御类
            "wall_durability": 0,           # 城墙额外耐久
            "damage_reduction": 0.0,        # 守城伤害减免%（女墙）
            "physical_damage_reduction": 0.0,   # 物理伤害减免%（武将巨像）
            "strategy_damage_reduction": 0.0,   # 策略伤害减免%（沙盘阵图）
            # COST上限（城主府/封禅台）
            "cost_cap": 8.0,
            "cost_cap_bonus": 0.0,
            # 名望上限（社稷坛）
            "fame_cap": 0,
            # 铜币每小时产出（民居）
            "copper_per_hour": 0,
        }

    def recalculate_building_effects(self, username: str, db: Session):
        """
        汇总玩家所有建筑的效果，写入 state["building_effects"]。
        在登录、升级建筑后调用。
        """
        if username not in self.online_players:
            return
        p_id = self.online_players[username]["id"]
        effects = self._default_building_effects()

        try:
            player_buildings = db.query(PlayerBuilding).filter(
                PlayerBuilding.player_id == p_id,
                PlayerBuilding.level > 0,
            ).all()

            # 点将台 key → 阵营映射
            altar_faction_map = {
                "altar_han": "汉",
                "altar_wei": "魏",
                "altar_shu": "蜀",
                "altar_wu":  "吴",
                "altar_meng": "群",
            }

            for pb in player_buildings:
                blc = db.query(BuildingLevelConfig).filter(
                    BuildingLevelConfig.building_key == pb.building_key,
                    BuildingLevelConfig.level == pb.level,
                ).first()
                if not blc or not blc.effects:
                    continue
                eff = blc.effects

                # 仓库：资源上限
                if "storage_cap" in eff:
                    effects["storage_cap"] = max(effects["storage_cap"], eff["storage_cap"])

                # 校场：可出征队伍数
                if "troop_slots" in eff:
                    effects["troop_slots"] = max(effects["troop_slots"], eff["troop_slots"])

                # 兵营：单队最大兵力
                if "troop_capacity" in eff:
                    effects["troop_capacity"] = max(effects["troop_capacity"], eff["troop_capacity"])

                # 前锋营：前锋武将槽
                if "vanguard_slots" in eff:
                    effects["vanguard_slots"] = max(effects["vanguard_slots"], eff["vanguard_slots"])

                # 预备役所：预备兵上限
                if "reserve_cap" in eff:
                    effects["reserve_cap"] = max(effects["reserve_cap"], eff["reserve_cap"])

                # 募兵所：招募速度加成（累加）
                if "recruit_speed_bonus" in eff:
                    effects["recruit_speed_bonus"] += eff["recruit_speed_bonus"]

                # 尚武营+武将巨像：攻击加成（累加）
                if "attack_bonus" in eff:
                    effects["attack_bonus"] += eff["attack_bonus"]

                # 铁壁营+城墙：防御加成（累加）
                if "defense_bonus" in eff:
                    effects["defense_bonus"] += eff["defense_bonus"]

                # 疾风营：速度加成（累加）
                if "speed_bonus" in eff:
                    effects["speed_bonus"] += eff["speed_bonus"]

                # 军机营+沙盘阵图：谋略加成（累加）
                if "strategy_bonus" in eff:
                    effects["strategy_bonus"] += eff["strategy_bonus"]

                # 点将台：阵营加成
                if pb.building_key in altar_faction_map:
                    faction = altar_faction_map[pb.building_key]
                    effects["faction_bonus"][faction]["atk"] += eff.get("faction_bonus_atk", 0)
                    effects["faction_bonus"][faction]["def"] += eff.get("faction_bonus_def", 0)
                    effects["faction_bonus"][faction]["spd"] += eff.get("faction_bonus_spd", 0)
                    effects["faction_bonus"][faction]["strg"] += eff.get("faction_bonus_strg", 0)

                # 城墙：城墙耐久（累加）
                if "wall_durability" in eff:
                    effects["wall_durability"] += eff["wall_durability"]

                # 女墙：伤害减免（累加）
                if "damage_reduction" in eff:
                    effects["damage_reduction"] += eff["damage_reduction"]

                # 武将巨像：物理伤害减免（累加）
                if "physical_damage_reduction" in eff:
                    effects["physical_damage_reduction"] += eff["physical_damage_reduction"]

                # 沙盘阵图：策略伤害减免（累加）
                if "strategy_damage_reduction" in eff:
                    effects["strategy_damage_reduction"] += eff["strategy_damage_reduction"]

                # 城主府：COST上限（取最大值）
                if "cost_cap" in eff:
                    effects["cost_cap"] = max(effects["cost_cap"], eff["cost_cap"])

                # 封禅台：COST上限加成（累加）
                if "cost_cap_bonus" in eff:
                    effects["cost_cap_bonus"] += eff["cost_cap_bonus"]

                # 社稷坛：名望上限（取最大值）
                if "fame_cap" in eff:
                    effects["fame_cap"] = max(effects["fame_cap"], eff["fame_cap"])

                # 民居：铜币产出（累加）
                if "copper_per_hour" in eff:
                    effects["copper_per_hour"] += eff["copper_per_hour"]

        except Exception as e:
            print(f"[建筑效果计算警告] {username}: {e}")

        self.online_players[username]["building_effects"] = effects

    def get_building_effects(self, username: str) -> dict:
        """获取玩家当前建筑效果（外部调用入口）。"""
        if username not in self.online_players:
            return self._default_building_effects()
        return self.online_players[username].get("building_effects", self._default_building_effects())

    def recalculate_production(self, username: str, db: Session):
        """重算玩家每秒资源产出（领地格子 + 建筑产出）。"""
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
        """检查目标格子是否与玩家领地相连。"""
        for nq, nr in get_neighbors(target_q, target_r):
            neighbor = db.query(Tile).filter(Tile.x == nq, Tile.y == nr, Tile.owner_id == player_id).first()
            if neighbor:
                return True
        return False

    def get_territory_border(self, player_id: int, db: Session) -> set:
        """获取玩家领地的边界格子集合。"""
        owned_tiles = {(t.x, t.y) for t in db.query(Tile).filter(Tile.owner_id == player_id).all()}
        border = set()
        for q, r in owned_tiles:
            for nq, nr in get_neighbors(q, r):
                if (nq, nr) not in owned_tiles:
                    border.add((q, r))
                    break
        return border

    def disconnect(self, username: str, db: Session = None):
        """断线处理：资源写回数据库、清理连接。"""
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
        """向指定玩家发送 WebSocket 消息。"""
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_text(json.dumps(packet))
            except Exception as e:
                print(f"发送消息给 {username} 失败: {e}")


# 全局单例
manager = ConnectionManager()

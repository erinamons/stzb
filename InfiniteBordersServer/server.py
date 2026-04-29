# server.py - InfiniteBorders 服务器入口
# 从 server_gui.py 拆分出的新入口文件
import asyncio
import os
import sys

# 确保父目录在 sys.path 中（用于导入 shared 协议模块）
_server_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_server_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import *
from shared.protocol import MsgType, build_packet
from models.database import SessionLocal, engine
from models.schema import Player, Tile, Base

from core.connection_manager import manager
from core.game_loop import setup_startup_event
from ws_handlers import websocket_endpoint
from data_editor_api import router as snapshot_router


# 创建 FastAPI 应用
app = FastAPI(title="InfiniteBorders Server")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册启动事件（建表 + 加载配置 + 启动 game_loop）
setup_startup_event(app)

# 注册数据编辑器快照 API
app.include_router(snapshot_router)


@app.websocket("/ws/{username}")
async def ws_endpoint(websocket: WebSocket, username: str):
    """WebSocket 连接入口。"""
    await websocket_endpoint(websocket, username)


@app.get("/")
async def root():
    return {"message": "InfiniteBorders Server is running"}


@app.get("/api/health")
async def health_check():
    """健康检查，客户端用来判断服务器是否在线。"""
    # 启动时自动迁移：为旧数据库添加 permissions 列
    _migrate_db_columns()
    return {"status": "ok"}


def _migrate_db_columns():
    """数据库列迁移（幂等，每次启动检查一次）。"""
    if hasattr(_migrate_db_columns, "_done"):
        return
    _migrate_db_columns._done = True
    try:
        import sqlite3, json
        from models.database import SessionLocal
        from models.schema import DEFAULT_GM_PERMISSIONS, GmAdmin, GmOperationLog
        # 确保 gm_operation_logs 表存在
        GmOperationLog.__table__.create(bind=engine, checkfirst=True)
        # 检查 gm_admins 是否有 permissions 列
        conn = sqlite3.connect("infinite_borders.sqlite3")
        cursor = conn.execute("PRAGMA table_info(gm_admins)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        if "permissions" not in columns:
            conn = sqlite3.connect("infinite_borders.sqlite3")
            conn.execute("ALTER TABLE gm_admins ADD COLUMN permissions TEXT")
            conn.commit()
            conn.close()
            print("[迁移] gm_admins 表已添加 permissions 列")
        # 为没有权限的管理员设置默认值
        db = SessionLocal()
        try:
            admins = db.query(GmAdmin).filter(GmAdmin.permissions.is_(None)).all()
            for admin in admins:
                admin.permissions = json.dumps(DEFAULT_GM_PERMISSIONS, ensure_ascii=False)
            if admins:
                db.commit()
                print(f"[迁移] 已为 {len(admins)} 个管理员设置默认权限")
        finally:
            db.close()
    except Exception as e:
        print(f"[迁移] 警告: {e}")


@app.post("/api/register")
async def register_player(data: dict):
    """注册新玩家：创建账号、分配出生点、初始化资源和建筑。"""
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or len(username) < 2 or len(username) > 16:
        return {"ok": False, "message": "用户名需要 2-16 个字符"}
    if any(c in username for c in " \t\n/\\{}[]()<>"):
        return {"ok": False, "message": "用户名包含非法字符"}
    if password and len(password) < 3:
        return {"ok": False, "message": "密码至少 3 个字符"}

    db = SessionLocal()
    try:
        # 检查用户名是否已存在
        existing = db.query(Player).filter(Player.username == username).first()
        if existing:
            return {"ok": False, "message": "用户名已被注册"}

        # 查找可用的出生点（PLAINS 且无 owner）
        spawn = db.query(Player).order_by(Player.id.desc()).first()
        # 获取所有已被占用的出生点
        taken_spawns = {(p.spawn_x, p.spawn_y) for p in db.query(Player).all()}

        # 在凉州附近区域寻找空闲的 PLAINS 格子（优先原点附近）
        spawn_point = None
        # 搜索范围从小到大
        for radius in range(1, 20):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    sx, sy = 15 + dx, 22 + dy
                    if (sx, sy) in taken_spawns:
                        continue
                    if sx < 0 or sy < 0 or sx >= MAP_COLS or sy >= MAP_ROWS:
                        continue
                    tile = db.query(Tile).filter(
                        Tile.x == sx, Tile.y == sy,
                        Tile.terrain != "MOUNTAIN",
                        Tile.owner_id.is_(None)
                    ).first()
                    if tile:
                        spawn_point = (sx, sy)
                        tile.terrain = "PLAINS"
                        tile.level = 3
                        tile.owner_id = None  # 先不设 owner，等 Player 创建后设
                        break
                if spawn_point:
                    break
            if spawn_point:
                break

        if not spawn_point:
            return {"ok": False, "message": "服务器已满，无法分配出生点"}

        # 创建玩家
        p = Player(
            username=username,
            password=password,
            spawn_x=spawn_point[0],
            spawn_y=spawn_point[1],
            copper=10000,
            jade=0,
            tiger_tally=0,
            main_city_level=1,
        )
        db.add(p)
        db.commit()

        # 将出生点归属给玩家
        tile = db.query(Tile).filter(
            Tile.x == spawn_point[0], Tile.y == spawn_point[1]
        ).first()
        if tile:
            tile.owner_id = p.id
            db.commit()

        # 初始化建筑
        from building_configs import init_player_buildings
        init_player_buildings(db, p.id, palace_level=1)

        # 初始部队槽位
        from models.schema import Troop
        for i in range(3):
            db.add(Troop(owner_id=p.id, name=f"部队{i+1}"))
        db.commit()

        print(f"[注册] 新玩家: {username}, 出生点: ({spawn_point[0]}, {spawn_point[1]})")
        return {"ok": True, "message": "注册成功", "username": username}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"注册失败: {e}"}
    finally:
        db.close()


@app.put("/api/account/password")
async def change_password(data: dict):
    """修改密码（需要验证旧密码）。"""
    username = data.get("username", "").strip()
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "").strip()

    if not username:
        return {"ok": False, "message": "缺少用户名"}
    if not new_password or len(new_password) < 3:
        return {"ok": False, "message": "新密码至少 3 个字符"}

    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.username == username).first()
        if not player:
            return {"ok": False, "message": "用户不存在"}

        # 验证旧密码
        if player.password:
            if old_password != player.password:
                return {"ok": False, "message": "旧密码错误"}
        else:
            # 无密码账号，设置密码不需要验证旧密码
            pass

        player.password = new_password
        db.commit()
        print(f"[账号] {username} 修改密码成功")
        return {"ok": True, "message": "密码修改成功"}
    except Exception as e:
        db.rollback()
        print(f"[账号] 修改密码失败: {e}")
        return {"ok": False, "message": f"修改失败: {e}"}
    finally:
        db.close()


# ============================================================
# GM 管理员认证与管理 API
# ============================================================

@app.post("/api/gm/login")
async def gm_login(data: dict):
    """GM 后台登录验证。"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"ok": False, "message": "用户名和密码不能为空"}
    db = SessionLocal()
    try:
        from models.schema import GmAdmin
        admin = db.query(GmAdmin).filter(GmAdmin.username == username).first()
        if not admin or admin.password != password:
            return {"ok": False, "message": "用户名或密码错误"}
        # 解析权限
        import json
        from models.schema import DEFAULT_GM_PERMISSIONS
        try:
            perms = json.loads(admin.permissions) if admin.permissions else DEFAULT_GM_PERMISSIONS
        except (json.JSONDecodeError, TypeError):
            perms = DEFAULT_GM_PERMISSIONS
        # 超管始终拥有全部权限
        if admin.role == "super_admin":
            perms = DEFAULT_GM_PERMISSIONS
        gm_log(admin.username, "login", "gm_admin", admin.id,
                f"GM 登录 (角色: {admin.role})")
        return {"ok": True, "data": {"id": admin.id, "username": admin.username, "role": admin.role, "permissions": perms}}
    finally:
        db.close()


@app.get("/api/gm/admins")
async def get_gm_admins():
    """获取所有 GM 管理员列表。"""
    db = SessionLocal()
    try:
        from models.schema import GmAdmin
        admins = db.query(GmAdmin).all()
        import json
        result = []
        for a in admins:
            try:
                perms = json.loads(a.permissions) if a.permissions else None
            except (json.JSONDecodeError, TypeError):
                perms = None
            result.append({"id": a.id, "username": a.username, "password": a.password,
                           "role": a.role, "created_at": a.created_at, "permissions": perms})
        return {"ok": True, "admins": result}
    finally:
        db.close()


@app.post("/api/gm/admins")
async def create_gm_admin(data: dict):
    """创建新 GM 管理员。"""
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "admin")
    if not username or not password:
        return {"ok": False, "message": "用户名和密码不能为空"}
    if len(password) < 3:
        return {"ok": False, "message": "密码至少 3 个字符"}
    if role not in ("admin", "super_admin"):
        return {"ok": False, "message": "无效的角色"}
    db = SessionLocal()
    try:
        from models.schema import GmAdmin, DEFAULT_GM_PERMISSIONS
        import json
        existing = db.query(GmAdmin).filter(GmAdmin.username == username).first()
        if existing:
            return {"ok": False, "message": "该用户名已存在"}
        permissions = data.get("permissions", DEFAULT_GM_PERMISSIONS)
        admin = GmAdmin(username=username, password=password, role=role,
                        permissions=json.dumps(permissions, ensure_ascii=False))
        db.add(admin)
        db.commit()
        operator = data.get("operator", "")
        gm_log(operator, "create", "admin", admin.id, f"创建管理员 {username} (角色: {role})")
        return {"ok": True, "message": f"已创建管理员: {username}"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": f"创建失败: {e}"}
    finally:
        db.close()


@app.put("/api/gm/admins/{admin_id}")
async def update_gm_admin(admin_id: int, data: dict):
    """修改 GM 管理员信息。"""
    db = SessionLocal()
    try:
        from models.schema import GmAdmin
        admin = db.query(GmAdmin).filter(GmAdmin.id == admin_id).first()
        if not admin:
            return {"ok": False, "message": "管理员不存在"}
        # 记录修改详情
        detail_parts = []
        if "password" in data and data["password"].strip():
            if len(data["password"].strip()) < 3:
                return {"ok": False, "message": "密码至少 3 个字符"}
            admin.password = data["password"].strip()
            detail_parts.append("修改密码")
        if "role" in data and data["role"] in ("admin", "super_admin"):
            if admin.role != data["role"]:
                detail_parts.append(f"角色: {admin.role} → {data['role']}")
            admin.role = data["role"]
        if "permissions" in data:
            import json
            admin.permissions = json.dumps(data["permissions"], ensure_ascii=False)
            detail_parts.append("修改权限")
        db.commit()
        operator = data.get("operator", "unknown")
        gm_log(operator, "update", "admin", admin_id,
               f"修改管理员 {admin.username}: {', '.join(detail_parts)}")
        return {"ok": True, "message": "修改成功"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": f"修改失败: {e}"}
    finally:
        db.close()


@app.delete("/api/gm/admins/{admin_id}")
async def delete_gm_admin(admin_id: int, data: dict = None):
    """删除 GM 管理员（不能删除自己）。"""
    db = SessionLocal()
    try:
        from models.schema import GmAdmin
        admin = db.query(GmAdmin).filter(GmAdmin.id == admin_id).first()
        if not admin:
            return {"ok": False, "message": "管理员不存在"}
        operator = (data or {}).get("operator", "unknown") if data else "unknown"
        username = admin.username
        db.delete(admin)
        db.commit()
        gm_log(operator, "delete", "admin", admin_id, f"删除管理员 {username}")
        return {"ok": True, "message": f"已删除管理员: {username}"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": f"删除失败: {e}"}
    finally:
        db.close()


# ===== GM 操作日志 =====

def gm_log(operator, action, target_type, target_id="", detail="", error_hash=""):
    """记录 GM 操作日志（供其他 API 调用）。"""
    try:
        import time as _time
        db = SessionLocal()
        try:
            from models.schema import GmOperationLog
            log = GmOperationLog(
                timestamp=_time.strftime('%Y-%m-%d %H:%M:%S'),
                operator=operator, action=action,
                target_type=target_type, target_id=str(target_id),
                detail=detail[:2000], error_hash=error_hash,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # 日志记录失败不应影响业务


@app.get("/api/gm/logs")
async def get_gm_logs(action: str = "", operator: str = "", target_type: str = "",
                      limit: int = 500, offset: int = 0):
    """查询 GM 操作日志，支持过滤。"""
    db = SessionLocal()
    try:
        from models.schema import GmOperationLog
        q = db.query(GmOperationLog)
        if action:
            q = q.filter(GmOperationLog.action == action)
        if operator:
            q = q.filter(GmOperationLog.operator == operator)
        if target_type:
            q = q.filter(GmOperationLog.target_type == target_type)
        total = q.count()
        logs = q.order_by(GmOperationLog.id.desc()).offset(offset).limit(limit).all()
        return {
            "ok": True, "total": total,
            "logs": [{"id": l.id, "timestamp": l.timestamp, "operator": l.operator,
                      "action": l.action, "target_type": l.target_type,
                      "target_id": l.target_id, "detail": l.detail} for l in logs],
        }
    finally:
        db.close()


@app.get("/api/gm/logs/export")
async def export_gm_logs(action: str = "", operator: str = "", target_type: str = ""):
    """导出 GM 操作日志为 CSV。"""
    import csv, io
    db = SessionLocal()
    try:
        from models.schema import GmOperationLog
        q = db.query(GmOperationLog)
        if action:
            q = q.filter(GmOperationLog.action == action)
        if operator:
            q = q.filter(GmOperationLog.operator == operator)
        if target_type:
            q = q.filter(GmOperationLog.target_type == target_type)
        logs = q.order_by(GmOperationLog.id.desc()).limit(5000).all()
        output = io.StringIO()
        writer = csv.writer(output, encoding='utf-8-sig')
        writer.writerow(["ID", "时间", "操作人", "操作类型", "目标类型", "目标ID", "详情"])
        for l in logs:
            writer.writerow([l.id, l.timestamp, l.operator, l.action,
                             l.target_type, l.target_id, l.detail])
        output.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8-sig')]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=gm_operation_logs.csv"},
        )
    finally:
        db.close()


@app.post("/api/gm/logs/clear")
async def clear_gm_logs():
    """清空所有 GM 操作日志。"""
    db = SessionLocal()
    try:
        from models.schema import GmOperationLog
        count = db.query(GmOperationLog).count()
        db.query(GmOperationLog).delete()
        db.commit()
        return {"ok": True, "message": f"已清空 {count} 条日志"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": f"清空失败: {e}"}
    finally:
        db.close()


@app.get("/api/players")
async def get_players():
    """获取所有玩家列表（含详细数据）。"""
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        result = []
        for p in players:
            # 统计领地格数
            from models.schema import Tile, Hero, Troop
            tile_count = db.query(Tile).filter(Tile.owner_id == p.id).count()
            hero_count = db.query(Hero).filter(Hero.owner_id == p.id).count()
            troop_count = db.query(Troop).filter(Troop.owner_id == p.id).count()
            online = p.username in manager.active_connections

            result.append({
                "id": p.id,
                "username": p.username,
                "password": p.password or "",
                "has_password": bool(p.password),
                "spawn": f"({p.spawn_x}, {p.spawn_y})",
                "resources": {
                    "wood": p.wood, "iron": p.iron,
                    "stone": p.stone, "grain": p.grain,
                },
                "currencies": {
                    "copper": int(p.copper), "jade": int(p.jade),
                    "tiger_tally": int(p.tiger_tally),
                },
                "main_city_level": int(p.main_city_level),
                "territory": tile_count,
                "heroes": hero_count,
                "troops": troop_count,
                "online": online,
            })
        return result
    finally:
        db.close()


@app.delete("/api/players/{player_id}")
async def delete_player(player_id: int, data: dict = None):
    """删除指定玩家及其所有关联数据。"""
    db = SessionLocal()
    try:
        from models.schema import Tile, Hero, Troop, BattleReport, PlayerBuilding
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        username = player.username

        # 如果在线，先踢下线
        if username in manager.active_connections:
            del manager.active_connections[username]
        if username in manager.online_players:
            del manager.online_players[username]

        # 释放领地
        db.query(Tile).filter(Tile.owner_id == player_id).update({"owner_id": None})
        # 删除关联数据（按外键顺序）
        for Model in (BattleReport, Troop, Hero, PlayerBuilding, Player):
            if Model == Player:
                db.query(Player).filter(Player.id == player_id).delete()
            else:
                db.query(Model).filter(
                    getattr(Model, "owner_id") == player_id
                ).delete()
        db.commit()

        print(f"[删除玩家] {username} (ID:{player_id})")
        operator = (data or {}).get("operator", "unknown") if data else "unknown"
        gm_log(operator, "delete", "player", player_id, f"删除玩家 {username} (ID:{player_id})")
        return {"ok": True, "message": f"已删除玩家 {username}"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"删除失败: {e}"}
    finally:
        db.close()


# ============================================================
# 玩家武将管理 API
# ============================================================

@app.get("/api/hero_templates")
async def get_hero_templates():
    """获取所有武将模板列表（GM添加武将用）。"""
    db = SessionLocal()
    try:
        from models.schema import HeroTemplate
        templates = db.query(HeroTemplate).order_by(HeroTemplate.stars.desc(), HeroTemplate.name).all()
        result = []
        for t in templates:
            skill_name = t.innate_skill.name if t.innate_skill else "无"
            result.append({
                "id": t.id,
                "name": t.name,
                "stars": t.stars,
                "faction": t.faction,
                "troop_type": t.troop_type,
                "cost": t.cost,
                "innate_skill": skill_name,
            })
        return result
    finally:
        db.close()


@app.get("/api/players/{player_id}/heroes")
async def get_player_heroes(player_id: int):
    """获取指定玩家的所有武将。"""
    db = SessionLocal()
    try:
        from models.schema import Hero
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        heroes = db.query(Hero).filter(Hero.owner_id == player_id).all()
        result = []
        for h in heroes:
            # 获取战法名称
            skill_names = []
            if h.template and h.template.innate_skill:
                skill_names.append(h.template.innate_skill.name)
            if h.skill_2:
                skill_names.append(h.skill_2.name)
            if h.skill_3:
                skill_names.append(h.skill_3.name)

            result.append({
                "id": h.id,
                "template_id": h.template_id,
                "name": h.name,
                "stars": h.stars,
                "level": h.level,
                "exp": h.exp,
                "attack": h.attack,
                "defense": h.defense,
                "strategy": h.strategy,
                "speed": h.speed,
                "faction": h.faction,
                "troop_type": h.troop_type,
                "cost": h.cost,
                "troops": h.troops,
                "max_troops": h.max_troops,
                "rank": h.rank,
                "stamina": h.stamina,
                "skills": " / ".join(skill_names) if skill_names else "无",
            })
        return result
    finally:
        db.close()


@app.post("/api/players/{player_id}/heroes")
async def add_hero_to_player(player_id: int, data: dict):
    """给玩家添加一个武将（从模板创建）。"""
    db = SessionLocal()
    try:
        from models.schema import Hero, HeroTemplate

        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        template_id = data.get("template_id")
        if not template_id:
            return {"ok": False, "message": "缺少 template_id"}

        template = db.query(HeroTemplate).filter(HeroTemplate.id == template_id).first()
        if not template:
            return {"ok": False, "message": f"武将模板 ID:{template_id} 不存在"}

        hero = Hero(
            owner_id=player_id,
            template_id=template.id,
            name=template.name,
            stars=template.stars,
            attack=int(template.atk),
            defense=int(template.defs),
            strategy=int(template.strg),
            speed=int(template.spd),
            faction=template.faction,
            troop_type=template.troop_type,
            cost=template.cost,
            rank=1,
            duplicates=0,
            bonus_points=0,
            stamina=100,
            max_stamina=100,
        )
        db.add(hero)
        db.commit()

        print(f"[GM] 玩家 ID:{player_id} 添加武将: {template.name} (Hero ID:{hero.id})")
        operator = data.get("operator", "unknown")
        gm_log(operator, "create", "hero", hero.id,
               f"为玩家 {player.username} (ID:{player_id}) 添加武将 {template.name}")
        return {"ok": True, "message": f"已添加武将 {template.name}", "hero_id": hero.id}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"添加失败: {e}"}
    finally:
        db.close()


@app.delete("/api/players/{player_id}/heroes/{hero_id}")
async def remove_hero_from_player(player_id: int, hero_id: int, data: dict = None):
    """从玩家移除指定武将。"""
    db = SessionLocal()
    try:
        from models.schema import Hero, Troop

        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        hero = db.query(Hero).filter(Hero.id == hero_id, Hero.owner_id == player_id).first()
        if not hero:
            return {"ok": False, "message": f"武将 ID:{hero_id} 不属于该玩家或不存在"}

        hero_name = hero.name

        # 从部队中卸下（清空 slot 引用）
        troops = db.query(Troop).filter(Troop.owner_id == player_id).all()
        for troop in troops:
            if troop.slot1_hero_id == hero_id:
                troop.slot1_hero_id = None
            if troop.slot2_hero_id == hero_id:
                troop.slot2_hero_id = None
            if troop.slot3_hero_id == hero_id:
                troop.slot3_hero_id = None

        db.delete(hero)
        db.commit()

        print(f"[GM] 玩家 ID:{player_id} 移除武将: {hero_name} (Hero ID:{hero_id})")
        operator = (data or {}).get("operator", "unknown") if data else "unknown"
        gm_log(operator, "delete", "hero", hero_id,
               f"从玩家 {player.username} (ID:{player_id}) 移除武将 {hero_name}")
        return {"ok": True, "message": f"已移除武将 {hero_name}"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"移除失败: {e}"}
    finally:
        db.close()


# ============================================================
# 玩家建筑管理 API
# ============================================================

@app.get("/api/players/{player_id}/buildings")
async def get_player_buildings(player_id: int):
    """获取指定玩家的所有建筑及配置信息。"""
    db = SessionLocal()
    try:
        from models.schema import PlayerBuilding, BuildingConfig

        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        # 获取建筑配置名称映射
        configs = db.query(BuildingConfig).all()
        config_map = {bc.building_key: bc for bc in configs}

        buildings = db.query(PlayerBuilding).filter(
            PlayerBuilding.player_id == player_id
        ).order_by(PlayerBuilding.building_key).all()

        result = []
        for pb in buildings:
            bc = config_map.get(pb.building_key)
            result.append({
                "id": pb.id,
                "building_key": pb.building_key,
                "building_name": bc.building_name if bc else pb.building_key,
                "level": pb.level,
                "max_level": bc.max_level if bc else 1,
                "category": bc.category if bc else "",
                "description": bc.description if bc else "",
            })
        return result
    finally:
        db.close()


@app.put("/api/players/{player_id}/buildings/{building_id}")
async def update_player_building(player_id: int, building_id: int, data: dict):
    """修改玩家建筑等级。"""
    db = SessionLocal()
    try:
        from models.schema import PlayerBuilding, BuildingConfig

        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        pb = db.query(PlayerBuilding).filter(
            PlayerBuilding.id == building_id,
            PlayerBuilding.player_id == player_id,
        ).first()
        if not pb:
            return {"ok": False, "message": f"建筑 ID:{building_id} 不属于该玩家或不存在"}

        new_level = data.get("level")
        if new_level is None:
            return {"ok": False, "message": "缺少 level 参数"}

        new_level = int(new_level)

        # 获取最大等级限制
        bc = db.query(BuildingConfig).filter(
            BuildingConfig.building_key == pb.building_key
        ).first()
        max_level = bc.max_level if bc else 1

        if new_level < 0:
            return {"ok": False, "message": "等级不能小于 0"}
        if new_level > max_level:
            return {"ok": False, "message": f"该建筑最高 {max_level} 级"}

        old_level = pb.level
        pb.level = new_level

        # 如果修改了城主府等级，需要同步玩家表
        if pb.building_key == "palace":
            player.main_city_level = new_level

        db.commit()

        # 如果玩家在线，重新计算建筑效果
        if player.username in manager.online_players:
            try:
                manager.recalculate_building_effects(player.username, db)
            except Exception:
                pass

        print(f"[GM] 玩家 ID:{player_id} 建筑 {pb.building_key}: Lv{old_level} → Lv{new_level}")
        operator = data.get("operator", "unknown")
        gm_log(operator, "update", "building", building_id,
               f"修改玩家 {player.username} (ID:{player_id}) 建筑 {pb.building_key}: Lv{old_level} → Lv{new_level}")
        return {"ok": True, "message": f"{pb.building_key} Lv{old_level} → Lv{new_level}"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"修改失败: {e}"}
    finally:
        db.close()


@app.put("/api/players/{player_id}")
async def update_player(player_id: int, data: dict):
    """修改指定玩家的任意字段（GM后台编辑用）。"""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"ok": False, "message": "玩家不存在"}

        # 可编辑字段白名单
        editable_fields = {
            "username": str,
            "password": str,
            "wood": int,
            "iron": int,
            "stone": int,
            "grain": int,
            "copper": int,
            "jade": int,
            "tiger_tally": int,
            "spawn_x": int,
            "spawn_y": int,
            "main_city_level": int,
            "max_troops": int,
        }

        changes = []
        for field, field_type in editable_fields.items():
            if field in data:
                new_val = data[field]
                # 类型转换
                try:
                    new_val = field_type(new_val)
                except (ValueError, TypeError):
                    return {"ok": False, "message": f"字段 {field} 类型错误"}

                # 特殊处理：用户名修改需检查唯一性
                if field == "username":
                    if not new_val or len(new_val.strip()) < 2:
                        return {"ok": False, "message": "用户名需要 2-16 个字符"}
                    new_val = new_val.strip()
                    if new_val != player.username:
                        exists = db.query(Player).filter(Player.username == new_val).first()
                        if exists:
                            return {"ok": False, "message": f"用户名 {new_val} 已被占用"}

                # 特殊处理：修改用户名时更新在线连接的 key
                if field == "username" and new_val != player.username:
                    old_username = player.username
                    # 转移在线状态
                    if old_username in manager.active_connections:
                        ws = manager.active_connections.pop(old_username)
                        manager.active_connections[new_val] = ws
                    if old_username in manager.online_players:
                        state = manager.online_players.pop(old_username)
                        manager.online_players[new_val] = state

                old_val = getattr(player, field)
                setattr(player, field, new_val)
                changes.append(f"{field}: {old_val} → {new_val}")

        if not changes:
            return {"ok": False, "message": "没有需要修改的字段"}

        db.commit()

        # 如果修改了资源且玩家在线，同步到内存状态
        if player.username in manager.online_players:
            state = manager.online_players[player.username]
            state["resources"]["wood"] = player.wood
            state["resources"]["iron"] = player.iron
            state["resources"]["stone"] = player.stone
            state["resources"]["grain"] = player.grain
            state["currencies"]["copper"] = player.copper
            state["currencies"]["jade"] = player.jade
            state["currencies"]["tiger_tally"] = player.tiger_tally

        print(f"[GM编辑] 玩家 ID:{player_id} 修改: {', '.join(changes)}")
        operator = data.get("operator", "unknown")
        gm_log(operator, "update", "player", player_id,
               f"修改玩家 {player.username} (ID:{player_id}): {', '.join(changes)}")
        return {"ok": True, "message": f"已修改 {len(changes)} 个字段", "changes": changes}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"修改失败: {e}"}
    finally:
        db.close()


# ============================================================
# 战报管理 API（GM后台用）
# ============================================================

@app.get("/api/battle_reports")
async def get_battle_reports(player_id: int = None, page: int = 1, page_size: int = 50):
    """获取战报列表（可按玩家筛选，支持分页）。"""
    from models.schema import BattleReport
    db = SessionLocal()
    try:
        query = db.query(BattleReport)
        if player_id:
            query = query.filter(BattleReport.player_id == player_id)
        query = query.order_by(BattleReport.id.desc())
        total = query.count()
        reports = query.offset((page - 1) * page_size).limit(page_size).all()
        result = []
        for r in reports:
            rpt = r.report or {}
            hdr = rpt.get("header", {})
            result.append({
                "id": r.id,
                "player_id": r.player_id,
                "attacker_id": r.attacker_id,
                "tile_x": r.tile_x,
                "tile_y": r.tile_y,
                "is_victory": r.is_victory,
                "created_at": r.created_at,
                # 摘要信息
                "attacker_name": hdr.get("attacker_name", "?"),
                "defender_name": hdr.get("defender_name", "?"),
                "total_rounds": hdr.get("total_rounds", "?"),
                "total_battles": hdr.get("total_battles"),
                "result_text": hdr.get("result_text", ""),
            })
        return {"ok": True, "reports": result, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"查询失败: {e}"}
    finally:
        db.close()


@app.get("/api/battle_reports/{report_id}")
async def get_battle_report_detail(report_id: int):
    """获取单条战报的完整详情。"""
    from models.schema import BattleReport
    db = SessionLocal()
    try:
        r = db.query(BattleReport).filter(BattleReport.id == report_id).first()
        if not r:
            return {"ok": False, "message": "战报不存在"}
        return {
            "ok": True,
            "id": r.id,
            "player_id": r.player_id,
            "attacker_id": r.attacker_id,
            "tile_x": r.tile_x,
            "tile_y": r.tile_y,
            "is_victory": r.is_victory,
            "created_at": r.created_at,
            "report": r.report,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"查询失败: {e}"}
    finally:
        db.close()


@app.delete("/api/battle_reports")
async def delete_battle_reports(player_id: int = None, report_id: int = None):
    """删除战报。可按 player_id 批量删除某玩家的全部战报，或按 report_id 删除单条。"""
    from models.schema import BattleReport
    db = SessionLocal()
    try:
        count = 0
        if report_id:
            count = db.query(BattleReport).filter(BattleReport.id == report_id).delete()
        elif player_id:
            count = db.query(BattleReport).filter(BattleReport.player_id == player_id).delete()
        else:
            return {"ok": False, "message": "请指定 player_id 或 report_id"}
        db.commit()
        return {"ok": True, "message": f"已删除 {count} 条战报"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": f"删除失败: {e}"}
    finally:
        db.close()


if __name__ == "__main__":
    import threading
    import time

    # 1. 后台启动服务器
    from server_runner import start_server_thread
    threading.Thread(target=start_server_thread, daemon=True).start()

    # 2. 等待服务器就绪
    print("[GM] 服务器启动中，请稍候...")
    import urllib.request
    for _ in range(15):  # 最多等 7.5 秒
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1)
            print("[GM] 服务器已就绪")
            break
        except Exception:
            continue
    else:
        print("[GM] 警告：服务器可能未成功启动，GM 功能可能受限")

    # 3. 弹登录框（走 HTTP API 验证）
    from gm_console import gm_login_dialog, ServerGMConsole
    ok, role, permissions, gm_username = gm_login_dialog()
    if ok:
        ServerGMConsole(gm_role=role, server_auto_started=True, permissions=permissions,
                         gm_username=gm_username).mainloop()

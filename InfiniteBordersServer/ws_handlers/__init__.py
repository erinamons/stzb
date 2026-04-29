# ws_handlers/__init__.py
# WebSocket 消息路由分发
import json
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from shared.protocol import MsgType, build_packet
from models.database import SessionLocal
from models.schema import Player
from core.connection_manager import manager

from ws_handlers.hero_handlers import send_heroes, handle_add_point, handle_sub_point, handle_max_point, handle_rank_up, handle_cheat_level
from ws_handlers.march_handler import handle_march
from ws_handlers.recruit_handler import handle_recruit
from ws_handlers.troop_handlers import handle_req_troops, handle_edit_troop, handle_recruit_troops
from ws_handlers.building_handlers import handle_req_buildings, handle_upgrade_building, handle_req_building_detail
from ws_handlers.report_handler import handle_req_report_history
from ws_handlers.shop_handlers import handle_req_packs, handle_recharge, handle_exchange


async def websocket_endpoint(websocket: WebSocket, username: str):
    """WebSocket 消息路由主入口：密码验证 → 分发消息。"""
    # 第一步：接受连接，验证玩家存在
    db = SessionLocal()
    try:
        print(f"尝试连接用户 {username}")
        db_player = await manager.connect(websocket, username, db)
        if not db_player:
            db.close()
            return
        # 在 session 关闭前缓存密码（避免 DetachedInstanceError）
        stored_password = db_player.password or ""
        print(f"用户 {username} 连接建立，等待密码验证... (有密码: {bool(stored_password)})")
    except Exception as e:
        print(f"连接建立失败: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close()
        db.close()
        return
    finally:
        db.close()

    # 第二步：等待密码验证消息
    try:
        first_packet = json.loads(await websocket.receive_text())
    except WebSocketDisconnect:
        print(f"客户端 {username} 在密码验证前断开")
        if username in manager.active_connections:
            del manager.active_connections[username]
        return
    except Exception as e:
        print(f"接收验证消息错误: {e}")
        try:
            await manager.send_to(username, build_packet(MsgType.ERROR, "消息格式错误"))
            await websocket.close()
        except:
            pass
        if username in manager.active_connections:
            del manager.active_connections[username]
        return

    # 判断是否为 auth 消息（向后兼容旧客户端：旧客户端不发 auth，直接发业务消息）
    is_auth_packet = first_packet.get("type") in ("auth", "login", "verify")
    pending_business_packet = None  # 如果首条不是 auth，保存为待处理业务消息

    if is_auth_packet:
        # 验证密码
        auth_data = first_packet.get("data", {})
        input_password = auth_data.get("password", "")
        print(f"[验证] 用户={username}, 输入密码={'***' if input_password else '(空)'}, 存储密码={'有' if stored_password else '无'}")
        if stored_password and input_password != stored_password:
            print(f"用户 {username} 密码错误")
            try:
                await manager.send_to(username, build_packet(MsgType.ERROR, "密码错误"))
                await websocket.close()
            except:
                pass
            if username in manager.active_connections:
                del manager.active_connections[username]
            return
    else:
        # 旧客户端兼容：首条消息不是 auth，直接当作业务消息，跳过密码验证
        # 但如果玩家有密码，仍然要求验证
        if stored_password:
            print(f"用户 {username} 有密码但客户端未发送验证消息，拒绝登录")
            try:
                await manager.send_to(username, build_packet(MsgType.ERROR, "此账号已设密码，请使用新版客户端登录"))
                await websocket.close()
            except:
                pass
            if username in manager.active_connections:
                del manager.active_connections[username]
            return
        pending_business_packet = first_packet

    # 第三步：密码验证通过（或跳过），完成登录
    db = SessionLocal()
    try:
        await manager.complete_login(username, db)
        print(f"用户 {username} 登录成功")
    except Exception as e:
        print(f"完成登录失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close()
        except:
            pass
        return
    finally:
        db.close()

    # 第四步：进入消息循环
    # 如果有旧客户端的待处理业务消息，先处理它
    if pending_business_packet:
        _db = SessionLocal()
        try:
            msg_type = pending_business_packet.get("type")
            msg_data = pending_business_packet.get("data", {})
            if username in manager.online_players:
                state = manager.online_players[username]
                _db_player = _db.query(Player).filter(Player.id == state["id"]).first()
                if _db_player:
                    await _dispatch_message(username, state, _db, _db_player, msg_type, msg_data)
        except Exception as e:
            print(f"处理旧客户端首条消息异常: {e}")
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

            # 每次消息处理使用独立 Session
            db = SessionLocal()
            try:
                db_player = db.query(Player).filter(Player.id == state["id"]).first()
                if not db_player:
                    await manager.send_to(username, build_packet(MsgType.ERROR, "玩家数据丢失"))
                    continue

                await _dispatch_message(username, state, db, db_player, msg_type, msg_data)

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


async def _send_map_data(username: str, db: Session):
    """分批发送全量地图数据（每批 500 tile，避免 WebSocket 单包超出 buffer 限制）。"""
    from models.schema import Tile
    BATCH_SIZE = 500
    all_tiles = db.query(Tile).all()
    total = len(all_tiles)
    batches = [all_tiles[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    print(f"[地图] 开始发送地图数据: {total} 格, 共 {len(batches)} 批")
    for idx, batch in enumerate(batches):
        is_last = (idx == len(batches) - 1)
        tile_list = [
            {
                "x": t.x, "y": t.y,
                "terrain": t.terrain, "level": t.level,
                "owner": t.owner_id,
                "region": t.region or "",
                "city_type": t.city_type,
                "city_name": t.city_name,
            }
            for t in batch
        ]
        await manager.send_to(username, build_packet(MsgType.RES_MAP, {
            "tiles": tile_list,
            "batch": idx,
            "total_batches": len(batches),
            "done": is_last,
        }))
    print(f"[地图] 地图数据发送完毕")


async def _dispatch_message(username, state, db, db_player, msg_type, msg_data):
    """根据消息类型分发到对应的 handler。"""
    if msg_type == MsgType.CMD_MARCH:
        await handle_march(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_RECHARGE:
        await handle_recharge(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_EXCHANGE:
        await handle_exchange(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.REQ_PACKS:
        await handle_req_packs(username, db, msg_data)
    elif msg_type == MsgType.REQ_HEROES:
        await send_heroes(username)
    elif msg_type == MsgType.CMD_ADD_POINT:
        await handle_add_point(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_CHEAT_LVL:
        await handle_cheat_level(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_RANK_UP:
        await handle_rank_up(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_SUB_POINT:
        await handle_sub_point(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_MAX_POINT:
        await handle_max_point(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_RECRUIT:
        await handle_recruit(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.REQ_TROOPS:
        await handle_req_troops(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_EDIT_TROOP:
        await handle_edit_troop(username, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_RECRUIT_TROOPS:
        await handle_recruit_troops(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.REQ_REPORT_HISTORY:
        await handle_req_report_history(username, state, db, msg_data)
    elif msg_type == MsgType.REQ_BUILDINGS:
        await handle_req_buildings(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.CMD_UPGRADE_BUILDING:
        await handle_upgrade_building(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.REQ_BUILDING_DETAIL:
        await handle_req_building_detail(username, state, db, db_player, msg_data)
    elif msg_type == MsgType.REQ_MAP:
        await _send_map_data(username, db)

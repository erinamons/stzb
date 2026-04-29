# ws_handlers/report_handler.py
# 战报历史查询
from shared.protocol import MsgType, build_packet
from models.schema import BattleReport
from core.connection_manager import manager


async def handle_req_report_history(username, state, db, msg_data):
    """查询战报历史（分页）。"""
    try:
        page = msg_data.get("page", 1)
        page_size = msg_data.get("page_size", 50)
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

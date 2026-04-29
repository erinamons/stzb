# data_editor_api.py
# 数据编辑器专用 REST API：数据库快照管理（上传/列表/恢复/导出）
import os
import sys
import json
import time
import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from sqlalchemy import create_engine, inspect, text
from models.database import engine, SessionLocal, Base
from models.schema import (
    HeroTemplate, Skill, CardPack, CardPackDrop,
    BuildingConfig, BuildingLevelConfig
)

router = APIRouter(prefix="/api/snapshots", tags=["快照管理"])

# 快照存储目录（服务端根目录下，使用绝对路径避免 CWD 问题）
_SERVER_ROOT = os.path.dirname(os.path.abspath(__file__))
SNAPSHOTS_DIR = os.path.join(_SERVER_ROOT, "db_snapshots")


def _ensure_snapshots_dir():
    """确保快照目录存在。"""
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def _snapshot_path(snapshot_id: str) -> str:
    """返回指定快照的 SQLite 文件路径。"""
    return os.path.join(SNAPSHOTS_DIR, f"{snapshot_id}.sqlite3")


def _metadata_path(snapshot_id: str) -> str:
    """返回指定快照的元数据 JSON 路径。"""
    return os.path.join(SNAPSHOTS_DIR, f"{snapshot_id}.json")


def _generate_snapshot_id() -> str:
    """生成唯一快照 ID：时间戳 + 短随机数。"""
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{int(time.time() % 10000)}"


def _get_all_metadata() -> list:
    """读取所有快照的元数据，按时间倒序排列。"""
    _ensure_snapshots_dir()
    snapshots = []
    for fname in os.listdir(SNAPSHOTS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(SNAPSHOTS_DIR, fname), "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    snapshots.append(meta)
            except Exception:
                continue
    # 按创建时间倒序
    snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return snapshots


def _copy_gm_tables(src_engine, dst_engine):
    """将所有数据表从 src_engine 复制到 dst_engine（自动检测所有表）。
    
    默认复制所有表，排除 gm_operation_logs（操作日志无需备份）。
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import sessionmaker

    src_session = sessionmaker(bind=src_engine)()
    dst_session = sessionmaker(bind=dst_engine)()

    # 自动检测源库所有表，排除操作日志
    inspector = inspect(src_engine)
    all_tables = inspector.get_table_names()
    exclude_tables = {"gm_operation_logs"}
    tables = [t for t in all_tables if t not in exclude_tables]

    try:
        for table_name in tables:
            # 清空目标表
            dst_session.execute(text(f"DELETE FROM {table_name}"))

            # 从源表读取全部数据并插入目标表
            result = src_session.execute(text(f"SELECT * FROM {table_name}"))
            columns = result.keys()
            placeholders = ", ".join([":{}".format(col) for col in columns])
            insert_sql = text(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})")
            for row in result.fetchall():
                # 将 Row 转为 dict（兼容 SA 1.x 和 2.x）
                dst_session.execute(insert_sql, dict(row._mapping))

            dst_session.commit()

        dst_session.commit()
    finally:
        src_session.close()
        dst_session.close()


def _get_current_stats() -> dict:
    """获取当前数据库全量统计信息（自动检测所有表）。"""
    from sqlalchemy import inspect
    db = SessionLocal()
    try:
        # 自动检测所有表并统计行数
        inspector = inspect(db.bind)
        all_tables = inspector.get_table_names()
        stats = {}
        for table_name in all_tables:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                stats[table_name] = count or 0
            except Exception:
                stats[table_name] = -1  # 查询失败标记
        # 计算文件大小
        db_path = os.path.join(_SERVER_ROOT, "infinite_borders.sqlite3")
        stats["db_size_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2) \
            if os.path.exists(db_path) else 0
        return stats
    finally:
        db.close()


# ============================================================
# 请求模型
# ============================================================

class UploadRequest(BaseModel):
    description: str = ""   # 快照描述（可选）


# ============================================================
# API 接口
# ============================================================

@router.post("/upload")
async def upload_snapshot(req: UploadRequest = UploadRequest()):
    """
    上传当前数据库快照：
    1. 创建一个新的 SQLite 文件，复制所有 GM 表数据
    2. 保存元数据 JSON
    3. 返回 snapshot_id
    """
    _ensure_snapshots_dir()

    snapshot_id = _generate_snapshot_id()

    # 统计当前数据
    stats = _get_current_stats()

    # 使用 SQLAlchemy 创建新的 SQLite 文件并复制数据
    from sqlalchemy import create_engine
    db_file = _snapshot_path(snapshot_id)
    new_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    # 在新数据库中建表
    Base.metadata.create_all(new_engine)

    # 复制 GM 表数据
    _copy_gm_tables(engine, new_engine)

    new_engine.dispose()

    # 获取文件大小
    file_size = os.path.getsize(db_file) if os.path.exists(db_file) else 0

    # 保存元数据
    metadata = {
        "id": snapshot_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": req.description or f"手动备份 - {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "stats": stats,
    }

    meta_file = _metadata_path(snapshot_id)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "message": f"快照已上传: {snapshot_id}",
        "metadata": metadata,
    }


@router.get("/list")
async def list_snapshots():
    """列出所有已保存的数据库快照（含统计信息）。"""
    snapshots = _get_all_metadata()
    return {
        "success": True,
        "total": len(snapshots),
        "snapshots": snapshots,
    }


@router.get("/stats")
async def get_current_stats():
    """获取当前数据库的数据统计（在线模式仪表盘用）。"""
    stats = _get_current_stats()
    return {"success": True, **stats}


@router.post("/restore/{snapshot_id}")
async def restore_snapshot(snapshot_id: str):
    """
    将指定快照恢复到当前数据库。
    ⚠️ 危险操作：会覆盖当前的 GM 配置数据！
    """
    db_file = _snapshot_path(snapshot_id)
    if not os.path.exists(db_file):
        raise HTTPException(status_code=404, detail=f"快照不存在: {snapshot_id}")

    # 从快照文件读取数据并覆盖到主数据库
    from sqlalchemy import create_engine
    snap_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    _copy_gm_tables(snap_engine, engine)
    snap_engine.dispose()

    # 返回恢复后的统计
    stats = _get_current_stats()
    return {
        "success": True,
        "message": f"已从快照 {snapshot_id} 恢复数据库",
        "restored_stats": stats,
    }


@router.get("/export/{snapshot_id}")
async def export_snapshot(snapshot_id: str):
    """
    导出指定快照为 SQLite 文件下载。
    """
    db_file = _snapshot_path(snapshot_id)
    if not os.path.exists(db_file):
        raise HTTPException(status_code=404, detail=f"快照不存在: {snapshot_id}")

    meta_file = _metadata_path(snapshot_id)
    download_name = f"infiniteborders_snapshot_{snapshot_id}.sqlite3"

    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        desc = meta.get("description", snapshot_id)[:50]
        safe_desc = "".join(c if c.isalnum() or c in "_-" else "_" for c in desc)
        download_name = f"IB_backup_{safe_desc}.sqlite3"

    return FileResponse(
        path=db_file,
        filename=download_name,
        media_type="application/vnd.sqlite3",
    )


@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str):
    """删除指定快照（SQLite 文件 + 元数据 JSON）。"""
    db_file = _snapshot_path(snapshot_id)
    meta_file = _metadata_path(snapshot_id)

    deleted_files = []
    if os.path.exists(db_file):
        os.remove(db_file)
        deleted_files.append(db_file)
    if os.path.exists(meta_file):
        os.remove(meta_file)
        deleted_files.append(meta_file)

    if not deleted_files:
        raise HTTPException(status_code=404, detail=f"快照不存在: {snapshot_id}")

    return {"success": True, "message": f"已删除快照 {snapshot_id}", "deleted": deleted_files}

# gm_console/tabs/snapshot_tab.py
# 服务端 GM Console 专用：数据库快照管理标签页（本地模式，直接操作文件系统）
#
# 功能：
#   📤 创建快照 — 将当前数据库 GM 表数据存档为快照
#   📋 浏览快照 — 查看所有历史快照列表（时间/描述/大小/统计）
#   ⬇️ 恢复快照 — 选择历史版本覆盖回当前数据库
#   📂 导出快照 — 将快照复制为 .sqlite3 文件（可备份/分享）
#   🗑️ 删除快照 — 清理不需要的历史版本
#
# 注意：此 Tab 运行在服务器进程内，直接调用 data_editor_api 的底层函数，
#       不经过 HTTP API，因此不需要网络连接。

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import shutil
from datetime import datetime

# 复用 data_editor_api 的核心函数（同进程，直接导入）
from data_editor_api import (
    _ensure_snapshots_dir,
    _snapshot_path,
    _metadata_path,
    _generate_snapshot_id,
    _get_all_metadata,
    _copy_gm_tables,
    _get_current_stats,
)
from models.database import engine

from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER, BG_SURFACE,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_INFO,
    BTN_SUCCESS, BTN_DANGER, BTN_PRIMARY, BTN_ACCENT,
    FONT_FAMILY, FONT_MONO,
)


class SnapshotTab:
    """数据库版本管理标签页（服务端本地模式）。"""

    def __init__(self, notebook):
        self.notebook = notebook
        self.db = None  # 延迟初始化

        # 创建标签页容器（手动注册到 notebook）
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="💾 数据库版本")

        # ==================== 顶部：操作按钮栏 ====================
        top_bar = tk.Frame(tab, bg=BG_DARK)
        top_bar.pack(fill=tk.X, padx=5, pady=5)

        # 左侧标题
        tk.Label(top_bar, text="📦 数据库版本管理",
                 font=("微软雅黑", 12, "bold"), fg="white", bg=BG_DARK).pack(side=tk.LEFT, padx=5)

        # 右侧操作按钮
        btn_frame = tk.Frame(top_bar, bg=BG_DARK)
        btn_frame.pack(side=tk.RIGHT)

        tk.Button(btn_frame, text="📤 创建快照", command=self._create_snapshot,
                  bg=BTN_SUCCESS, fg="white", font=("微软雅黑", 10, "bold"),
                  padx=12, pady=4).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🔄 刷新", command=self._refresh_list,
                  bg=BTN_ACCENT, fg="white", font=("微软雅黑", 9),
                  padx=10, pady=4).pack(side=tk.LEFT, padx=3)

        # ==================== 中部：当前统计信息 ====================
        stats_frame = tk.LabelFrame(tab, text="当前数据库统计", font=("微软雅黑", 10, "bold"),
                                    fg="white", bg=BG_DARK, padx=10, pady=6)
        stats_frame.pack(fill=tk.X, padx=5, pady=3)

        self.stats_labels = {}
        stats_items = [
            ("heroes", "武将模板"), ("skills", "战法"),
            ("card_packs", "卡包"), ("card_pack_drops", "掉落配置"),
            ("building_configs", "建筑配置"), ("building_levels", "建筑等级"),
            ("db_size_mb", "DB大小(MB)"),
        ]
        for i, (key, cn) in enumerate(stats_items):
            r, c = divmod(i, 4)
            lbl = tk.Label(stats_frame, text=f"{cn}: --",
                          font=("微软雅黑", 9), fg=FG_SECONDARY, bg=BG_DARK, anchor="w")
            lbl.grid(row=r, column=c, padx=15, pady=4, sticky="w")
            self.stats_labels[key] = lbl

        # ==================== 主区域：快照列表 ====================
        list_frame = tk.Frame(tab, bg=BG_DARK)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 列表标题 + 操作栏
        header_frame = tk.Frame(list_frame, bg=BG_DARK)
        header_frame.pack(fill=tk.X, pady=(0, 3))

        tk.Label(header_frame, text="📋 历史快照列表",
                 font=("微软雅黑", 11, "bold"), fg="white", bg=BG_DARK).pack(side=tk.LEFT)

        # 选中快照的操作按钮
        sel_frame = tk.Frame(header_frame, bg=BG_DARK)
        sel_frame.pack(side=tk.RIGHT)
        tk.Label(sel_frame, text="选中操作:", fg=FG_SECONDARY, bg=BG_DARK,
                font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 5))

        for text, cmd, color in [
            ("⬇️ 恢复", self._restore, "#e68a00"),
            ("📂 导出", self._export, BTN_SUCCESS),
            ("🗑️ 删除", self._delete, BTN_DANGER),
        ]:
            tk.Button(sel_frame, text=text, command=cmd, bg=color, fg="white",
                     font=("微软雅黑", 9), padx=8, pady=2).pack(side=tk.LEFT, padx=2)

        # 快照 Treeview
        cols = ("id", "time", "desc", "size_mb", "heroes", "skills", "buildings")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)

        headers = {
            "id": "快照ID",
            "time": "创建时间",
            "desc": "描述",
            "size_mb": "大小(MB)",
            "heroes": "武将",
            "skills": "战法",
            "buildings": "建筑",
        }
        widths = {"id": 220, "time": 150, "desc": 280, "size_mb": 70,
                  "heroes": 55, "skills": 55, "buildings": 55}
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="center" if c != "desc" else "w")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(3, 0))

        # 双击查看详情
        self.tree.bind("<Double-1>", self._show_detail)

        # 滚动条
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        # （scrollbar 需要和 tree 配合 pack，这里简化处理）

        # 底部状态栏
        self.status_label = tk.Label(tab, text="", font=(FONT_MONO, 9),
                                     fg=FG_MUTED, bg=BG_DARK)
        self.status_label.pack(fill=tk.X, padx=5, pady=(0, 3))

        # 初始化：加载统计数据和快照列表
        self._update_stats()
        self._refresh_list()

    # ==================== 工具方法 ====================

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_label.config(text=f"[{ts}] {msg}")

    def _get_selected_id(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][0]

    # ==================== 数据加载 ====================

    def _update_stats(self):
        """刷新当前数据库统计显示。"""
        try:
            stats = _get_current_stats()
            cn_map = {
                "heroes": "武将模板", "skills": "战法",
                "card_packs": "卡包", "card_pack_drops": "掉落",
                "building_configs": "建筑", "building_levels": "等级",
                "db_size_mb": "MB",
            }
            for key, lbl in self.stats_labels.items():
                val = stats.get(key, "--")
                cn = cn_map.get(key, key)
                lbl.config(text=f"{cn}: {val}", fg="white")
        except Exception as e:
            self._log(f"读取统计失败: {e}")

    def _refresh_list(self):
        """刷新快照列表。"""
        self.tree.delete(*self.tree.get_children())
        try:
            snapshots = _get_all_metadata()
            if not snapshots:
                self.tree.insert("", "end", values=(
                    "(暂无快照)", "", "点击「创建快照」开始备份", "", "", "", ""
                ), tags=("all_rows",))
                return

            for snap in snapshots:
                s = snap.get("stats", {})
                size_str = str(snap.get("file_size_mb", "?"))
                self.tree.insert("", "end", iid=snap["id"], values=(
                    snap["id"],
                    snap.get("created_at", ""),
                    snap.get("description", "")[:50],
                    size_str,
                    s.get("heroes", "--"),
                    s.get("skills", "--"),
                    s.get("building_configs", "--"),
                ), tags=("all_rows",))
            self._log(f"共 {len(snapshots)} 个快照")
        except Exception as e:
            self._log(f"加载快照列表失败: {e}")

    # ==================== 快照操作 ====================

    def _create_snapshot(self):
        """创建新的数据库快照。"""
        # 弹出描述输入对话框
        d = tk.Toplevel(self.notebook.winfo_toplevel())
        d.title("创建数据库快照")
        d.geometry("420x160")
        d.resizable(False, False)
        d.configure(bg=BG_DARK)
        d.transient(self.notebook.winfo_toplevel())
        d.grab_set()

        tk.Label(d, text="📤 创建新快照", font=("微软雅黑", 13, "bold"),
                 fg="white", bg=BG_DARK).pack(pady=(15, 8))
        tk.Label(d, text="描述（可选，方便以后识别）：", fg=FG_SECONDARY,
                bg=BG_DARK, font=("微软雅黑", 10)).pack()
        desc_var = tk.StringVar(value=f"手动备份 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        entry = tk.Entry(d, textvariable=desc_var, width=45, bg=BG_ELEVATED, fg="white",
                        insertbackground="white", font=("微软雅黑", 10))
        entry.pack(padx=20, pady=8)
        entry.focus_set()
        entry.select_range(0, tk.END)

        result = [None]

        def do_create():
            try:
                result[0] = self._do_create(desc_var.get().strip())
            except Exception as e:
                result[0] = {"success": False, "message": str(e)}
            d.destroy()

        btn_row = tk.Frame(d, bg=BG_DARK)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="✅ 创建", command=do_create, bg=BTN_SUCCESS, fg="white",
                 font=("微软雅黑", 10, "bold"), padx=20).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_row, text="取消", command=lambda: d.destroy(), bg=BTN_PRIMARY, fg="white",
                 font=("微软雅黑", 10), padx=15).pack(side=tk.LEFT, padx=5)
        d.bind("<Return>", lambda e: do_create())

        self._wait_window(d)
        if result[0]:
            res = result[0]
            if res.get("success"):
                self._log(f'✅ 创建成功: {res["snapshot_id"]}')
                messagebox.showinfo("创建成功", res.get("message", ""))
                self._refresh_list()
                self._update_stats()
            else:
                messagebox.showerror("创建失败", res.get("message", "未知错误"))

    def _do_create(self, description: str) -> dict:
        """执行创建快照的核心逻辑（与 data_editor_api.upload_snapshot 相同）。"""
        _ensure_snapshots_dir()
        snapshot_id = _generate_snapshot_id()
        stats = _get_current_stats()

        from sqlalchemy import create_engine
        db_file = _snapshot_path(snapshot_id)
        new_engine = create_engine(f"sqlite:///{db_file}",
                                   connect_args={"check_same_thread": False})
        from models.database import Base
        Base.metadata.create_all(new_engine)
        _copy_gm_tables(engine, new_engine)
        new_engine.dispose()

        file_size = os.path.getsize(db_file) if os.path.exists(db_file) else 0

        metadata = {
            "id": snapshot_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": description or f"手动备份 - {datetime.now().strftime('%Y/%m/%d %H:%M')}",
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "stats": stats,
        }

        meta_file = _metadata_path(snapshot_id)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {"success": True, "snapshot_id": snapshot_id,
                "message": f"快照已创建: {snapshot_id}"}

    def _restore(self):
        """恢复选中的快照到当前数据库。"""
        sid = self._get_selected_id()
        if not sid:
            messagebox.showwarning("提示", "请先选择一个快照"); return

        db_file = _snapshot_path(sid)
        if not os.path.exists(db_file):
            messagebox.showerror("错误", f"快照文件不存在:\n{db_file}"); return

        # 二次确认
        item_data = self.tree.item(sid)["values"]
        desc = item_data[2] if len(item_data) > 2 else sid
        if not messagebox.askyesno(
            "⚠️ 确认恢复",
            f"即将用以下快照覆盖当前数据库的 GM 数据：\n\n"
            f"  ID: {sid}\n"
            f"  描述: {desc}\n\n"
            f"⚠️ 当前数据将被替换！建议先创建一个快照备份。\n\n"
            f"确定要继续吗？",
            icon="warning"
        ):
            return

        try:
            self._log(f"正在从 {sid} 恢复...")
            from sqlalchemy import create_engine
            snap_engine = create_engine(f"sqlite:///{db_file}",
                                        connect_args={"check_same_thread": False})
            _copy_gm_tables(snap_engine, engine)
            snap_engine.dispose()
            self._log(f"✅ 已恢复: {sid}")
            messagebox.showinfo("恢复成功", f"数据库已从快照恢复！\n{sid}")
            self._update_stats()
            # 恢复后通知各 Tab 刷新数据
            self._notify_refresh()
        except Exception as e:
            self._log(f"❌ 恢复失败: {e}")
            messagebox.showerror("恢复失败", f"恢复过程中出错:\n{e}")

    def _export(self):
        """导出选中的快照为 SQLite 文件。"""
        sid = self._get_selected_id()
        if not sid:
            messagebox.showwarning("提示", "请先选择一个快照"); return

        db_file = _snapshot_path(sid)
        if not os.path.exists(db_file):
            messagebox.showerror("错误", f"快照文件不存在:\n{db_file}"); return

        # 选择保存位置
        dest = filedialog.asksaveasfilename(
            title="导出快照",
            defaultextension=".sqlite3",
            initialfile=f"IB_backup_{sid[:19]}.sqlite3",
            filetypes=[("SQLite 数据库", "*.sqlite3"), ("所有文件", "*.*")]
        )
        if not dest:
            return

        try:
            shutil.copy2(db_file, dest)
            size_mb = round(os.path.getsize(dest) / (1024*1024), 2)
            self._log(f'✅ 已导出到: {dest}')
            messagebox.showinfo("导出成功", f"快照已导出至:\n{dest}\n({size_mb} MB)")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出失败:\n{e}")

    def _delete(self):
        """删除选中的快照。"""
        sid = self._get_selected_id()
        if not sid:
            messagebox.showwarning("提示", "请先选择一个快照"); return

        item_data = self.tree.item(sid)["values"]
        desc = item_data[2] if len(item_data) > 2 else sid

        if not messagebox.askyesno(
            "⚠️ 确认删除",
            f"确定要删除以下快照吗？\n\n"
            f"  ID: {sid}\n"
            f"  描述: {desc}\n\n"
            f"此操作不可撤销！",
            icon="warning"
        ):
            return

        db_file = _snapshot_path(sid)
        meta_file = _metadata_path(sid)
        deleted = []
        for f in [db_file, meta_file]:
            if os.path.exists(f):
                os.remove(f)
                deleted.append(os.path.basename(f))

        if deleted:
            self._log(f"🗑️ 已删除: {sid}")
            self._refresh_list()
        else:
            messagebox.showerror("错误", "快照文件不存在，可能已被删除")

    def _show_detail(self, event=None):
        """双击查看快照详情。"""
        sid = self._get_selected_id()
        if not sid:
            return

        meta_file = _metadata_path(sid)
        if not os.path.exists(meta_file):
            return

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # 详情弹窗
        d = tk.Toplevel(self.notebook.winfo_toplevel())
        d.title("快照详情")
        d.geometry("500x400")
        d.resizable(False, False)
        d.configure(bg=BG_DARK)
        d.transient(self.notebook.winfo_toplevel())

        tk.Label(d, text="📋 快照详情", font=("微软雅黑", 14, "bold"),
                 fg="white", bg=BG_DARK).pack(pady=(15, 10))

        info_frame = tk.Frame(d, bg=BG_DARK)
        info_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # 基本信息
        basic_info = [
            ("快照ID", meta.get("id", "")),
            ("创建时间", meta.get("created_at", "")),
            ("描述", meta.get("description", "")),
            ("文件大小", f'{meta.get("file_size_mb", "?")} MB'),
        ]
        for label, value in basic_info:
            row = tk.Frame(info_frame, bg=BG_DARK)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label + ":", fg=FG_SECONDARY, bg=BG_DARK,
                     font=("微软雅黑", 10), width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=str(value), fg="white", bg=BG_DARK,
                     font=("微软雅黑", 10), anchor="w").pack(side=tk.LEFT)

        # 统计信息
        sep = tk.Frame(info_frame, bg=BTN_PRIMARY, height=1)
        sep.pack(fill="x", pady=8)

        tk.Label(info_frame, text="数据统计:", fg=ACCENT_INFO, bg=BG_DARK,
                 font=("微软雅黑", 11, "bold")).pack(anchor="w")
        stats = meta.get("stats", {})
        for key, cn in [("heroes", "武将模板"), ("skills", "战法"),
                         ("card_packs", "卡包"), ("card_pack_drops", "掉落项"),
                         ("building_configs", "建筑配置"), ("building_levels", "建筑等级")]:
            val = stats.get(key, "--")
            tk.Label(info_frame, text=f"  {cn}: {val}", fg=FG_PRIMARY, bg=BG_DARK,
                     font=(FONT_MONO, 10)).pack(anchor="w")

        tk.Button(d, text="关闭", command=d.destroy, bg=BTN_PRIMARY, fg="white",
                 font=("微软雅黑", 10), padx=30, pady=6).pack(pady=15)

    @staticmethod
    def _wait_window(win):
        """阻塞等待窗口关闭（用于模态对话框）。"""
        win.wait_window()

    def _notify_refresh(self):
        """通知其他 Tab 刷新数据（恢复快照后调用）。"""
        # 通过 notebook 的父级找到 ServerGMConsole，触发各 Tab 的刷新方法
        try:
            console = self.notebook.master
            if hasattr(console, 'hero_tab'):
                tab = console.hero_tab
                if hasattr(tab, '_refresh_hero_list'):
                    tab._refresh_hero_list()
            if hasattr(console, 'skill_tab'):
                tab = console.skill_tab
                if hasattr(tab, '_refresh_skill_list'):
                    tab._refresh_skill_list()
            if hasattr(console, 'building_tab'):
                tab = console.building_tab
                if hasattr(tab, '_refresh_building_list'):
                    tab._refresh_building_list()
        except Exception:
            pass

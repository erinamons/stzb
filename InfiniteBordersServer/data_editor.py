# data_editor.py
# InfiniteBorders 独立数据编辑器
# 功能：连接服务器/本地数据库 + 武将/战法/卡包/建筑编辑 + 数据库快照管理  
#
# 用法：
#   python data_editor.py              # 本地模式（直接操作 SQLite）
#   python data_editor.py --online     # 连接服务器模式
#
# 也可从 GM Console 或 server.py 中作为模块导入使用：
#   from data_editor import DataEditor; DataEditor().mainloop()
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import threading
import time

# ============================================================
# 路径设置：确保能导入服务端模块
# ============================================================
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SERVER_DIR)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from models.database import SessionLocal, engine
    from models.schema import (
        HeroTemplate, Skill, CardPack, CardPackDrop,
        BuildingConfig, BuildingLevelConfig
    )
    HAS_LOCAL_DB = True
except Exception as e:
    print(f"[警告] 无法加载本地数据库模块: {e}")
    print("       将仅支持在线模式")
    HAS_LOCAL_DB = False

try:
    from node_editor import NodeEditor
    HAS_NODE_EDITOR = True
except ImportError:
    HAS_NODE_EDITOR = False
    print("[警告] NodeEditor 模块不可用，战法效果配置功能将被禁用")

import urllib.request
import urllib.error
from datetime import datetime


# ============================================================
# 使用统一主题模块（主题常量和 apply_dark_theme 从 theme.py 导入）
# ============================================================
from theme import (
    apply_dark_theme,
    BG_DARK, BG_SURFACE, BG_ELEVATED, BG_HOVER,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING, ACCENT_INFO,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED, FG_SELECTED,
    BG_SELECTED, BORDER_SUBTLE, BORDER_MUTED,
    BTN_PRIMARY, BTN_PRIMARY_HOVER, BTN_ACCENT, BTN_ACCENT_HOVER,
    BTN_SUCCESS, BTN_SUCCESS_HOVER, BTN_DANGER, BTN_DANGER_HOVER,
    FONT_FAMILY, FONT_MONO,
)






# ============================================================
# GM 操作日志辅助函数（data_editor 直连数据库版）
# ============================================================

def _log_operation(action, target_type, target_id="", detail="", operator="data_editor"):
    """记录操作日志到 gm_operation_logs 表。"""
    if not HAS_LOCAL_DB:
        return
    try:
        import time as _time
        db = SessionLocal()
        try:
            from models.schema import GmOperationLog
            log = GmOperationLog(
                timestamp=_time.strftime('%Y-%m-%d %H:%M:%S'),
                operator=operator, action=action,
                target_type=target_type, target_id=str(target_id),
                detail=detail[:2000], error_hash="",
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # 日志记录失败不影响业务


# ============================================================
# API 客户端：与服务器通信
# ============================================================

class APIClient:
    """轻量 HTTP 客户端，用于与服务器快照 API 通信。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.connected = False
        self._last_error = ""

    def test_connection(self) -> tuple:
        """测试连接是否可用，返回 (成功, 消息)。"""
        try:
            url = f"{self.base_url}/api/snapshots/stats"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return True, json.dumps(data.get("stats", {}), ensure_ascii=False, indent=2)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            return False, f"HTTP {e.code}: {body[:200]}"
        except Exception as e:
            return False, str(e)

    def upload_snapshot(self, description: str = "") -> dict:
        """上传快照。"""
        url = f"{self.base_url}/api/snapshots/upload"
        payload = json.dumps({"description": description}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def list_snapshots(self) -> dict:
        """列出所有快照。"""
        url = f"{self.base_url}/api/snapshots/list"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def restore_snapshot(self, snapshot_id: str) -> dict:
        """恢复快照。"""
        url = f"{self.base_url}/api/snapshots/restore/{snapshot_id}"
        req = urllib.request.Request(url, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())

    def delete_snapshot(self, snapshot_id: str) -> dict:
        """删除快照。"""
        url = f"{self.base_url}/api/snapshots/{snapshot_id}"
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_stats(self) -> dict:
        """获取当前数据库统计。"""
        url = f"{self.base_url}/api/snapshots/stats"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def export_snapshot(self, snapshot_id: str, save_path: str) -> bool:
        """导出快照文件到指定路径。"""
        url = f"{self.base_url}/api/snapshots/export/{snapshot_id}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(save_path, "wb") as f:
                f.write(resp.read())
            return True





# ============================================================
# 编辑器标签页基类
# ============================================================

class EditorTab:
    """标签页基类：提供通用 CRUD 操作框架。"""

    def __init__(self, notebook, tab_name: str, tab_emoji: str, register_tab: bool = True):
        self.notebook = notebook
        self.tab_name = tab_name
        self.master_root = notebook.master  # Toplevel/Tk 根窗口

        tab = tk.Frame(notebook, bg=BG_DARK)
        if register_tab:
            notebook.add(tab, text=f"{tab_emoji} {tab_name}")
        self.tab_frame = tab


# ============================================================
# 武将管理标签页
# ============================================================

class HeroEditorTab(EditorTab):
    """武将模板编辑标签页（左右分割布局，类似建筑管理风格）。"""

    def __init__(self, notebook, skill_tab=None):
        super().__init__(notebook, "武将管理", "⚔️")
        self.skill_tab = skill_tab
        self.db = SessionLocal()
        self.current_hero = None
        tab = self.tab_frame

        # ==================== 顶部：工具栏 ====================
        top_frame = tk.Frame(tab, bg=BG_SURFACE)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        # 左侧标题 + 搜索
        tk.Label(top_frame, text="⚔️ 武将列表", font=("微软雅黑", 11, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY
                 ).pack(side=tk.LEFT, padx=(8, 12))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_heroes())
        search_entry = tk.Entry(top_frame, textvariable=self.search_var, width=18,
                                font=("微软雅黑", 10),
                                bg=BG_ELEVATED, fg=FG_PRIMARY,
                                insertbackground=FG_PRIMARY,
                                relief="flat", borderwidth=1)
        search_entry.pack(side=tk.LEFT, padx=4)

        # 右侧操作按钮
        btn_frame = tk.Frame(top_frame, bg=BG_SURFACE)
        btn_frame.pack(side=tk.RIGHT)

        tk.Button(btn_frame, text="+ 新增武将", command=self._add_new_hero,
                  bg=BTN_SUCCESS, fg="white", font=(FONT_FAMILY, 9, "bold"),
                  relief="flat", borderwidth=0, padx=14, pady=4,
                  activebackground=BTN_SUCCESS_HOVER).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🗑 删除选中", command=self._delete_hero,
                  bg=BTN_DANGER, fg="white", font=(FONT_FAMILY, 9, "bold"),
                  relief="flat", borderwidth=0, padx=12, pady=4,
                  activebackground=BTN_DANGER_HOVER).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🔄 刷新", command=self.refresh_hero_tree,
                  bg=BTN_PRIMARY, fg=FG_PRIMARY, font=("微软雅黑", 9),
                  relief="flat", borderwidth=0, padx=10, pady=4,
                  activebackground=BTN_PRIMARY_HOVER).pack(side=tk.LEFT, padx=3)

        # ==================== 主区域：PanedWindow 左右分割 ====================
        main_pane = tk.PanedWindow(tab, orient="horizontal",
                                    sashwidth=4, sashrelief="raised")
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        # ---- 左侧面板：武将列表 ----
        left_panel = tk.Frame(main_pane)
        main_pane.add(left_panel, width=420)

        cols = ("id", "name", "stars", "faction", "troop_type", "cost", "skill")
        self.hero_tree = ttk.Treeview(left_panel, columns=cols, show="headings")

        headers = {"id": "ID", "name": "名称", "stars": "★", "faction": "阵营",
                    "troop_type": "兵种", "cost": "统率", "skill": "自带战法"}
        widths = {"id": 40, "name": 90, "stars": 30, "faction": 40,
                   "troop_type": 50, "cost": 45, "skill": 120}
        for c in cols:
            self.hero_tree.heading(c, text=headers[c])
            self.hero_tree.column(c, width=widths[c], anchor="center" if c not in ("name", "skill") else "w")

        scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.hero_tree.yview)
        self.hero_tree.configure(yscrollcommand=scroll.set)
        self.hero_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.hero_tree.bind("<<TreeviewSelect>>", self._on_hero_select)

        # ---- 右侧面板：武将详情编辑 ----
        right_panel = tk.Frame(main_pane, bg=BG_SURFACE)
        main_pane.add(right_panel, width=600)

        detail_header = tk.Frame(right_panel, bg=BG_SURFACE)
        detail_header.pack(fill=tk.X, pady=(0, 8))
        tk.Label(detail_header, text="⚔️ 武将详情", font=(FONT_FAMILY, 12, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY
                 ).pack(side=tk.LEFT, padx=8)
        self.detail_hint = tk.Label(detail_header, text="← 请从左侧选择一个武将",
                                     fg=FG_MUTED, font=(FONT_FAMILY, 9),
                                     bg=BG_SURFACE)
        self.detail_hint.pack(side=tk.RIGHT, padx=10)

        # 基础信息区域
        info_frame = tk.LabelFrame(right_panel, text=" 基础信息 ", 
                                    font=(FONT_FAMILY, 9, "bold"), fg=ACCENT_PRIMARY,
                                    bg=BG_SURFACE, padx=10, pady=8,
                                    relief="solid", borderwidth=1)
        info_frame.pack(fill=tk.X, padx=5, pady=3)

        self.fields = {}
        basic_fields = [
            ("name", "名称"), ("stars", "星级(1-5)"), ("cost", "统率Cost"),
            ("attack_range", "攻击距离"), ("faction", "阵营"), ("troop_type", "兵种"),
            ("innate_skill_id", "自带战法"),
        ]
        for i, (key, label) in enumerate(basic_fields):
            r, c = divmod(i, 2)
            tk.Label(info_frame, text=label,
                     font=(FONT_FAMILY, 9), bg=BG_SURFACE, fg=FG_PRIMARY
                     ).grid(row=r, column=c*2, sticky="w", padx=5, pady=3)

            if key == "innate_skill_id":
                skill_frame = tk.Frame(info_frame)
                skill_frame.grid(row=r, column=c*2+1, sticky="w", padx=5, pady=3)
                skill_var = tk.StringVar()
                skill_combo = ttk.Combobox(skill_frame, textvariable=skill_var,
                                            state="readonly", width=20)
                skill_combo.pack(side=tk.LEFT)
                new_btn = tk.Button(skill_frame, text="+ 新建", bg=BTN_ACCENT, fg="white",
                                    font=(FONT_FAMILY, 8, "bold"), relief="flat",
                                    command=lambda s=skill_combo: self._create_skill_and_refresh(s),
                                    activebackground=BTN_ACCENT_HOVER)
                new_btn.pack(side=tk.LEFT, padx=3)
                self.fields[key] = (skill_combo, skill_var)
            elif key in ("faction", "troop_type"):
                opts = {"faction": ["魏", "蜀", "吴", "群", "汉"],
                        "troop_type": ["步兵", "骑兵", "弓兵"]}[key]
                combo = ttk.Combobox(info_frame, values=opts, state="readonly", width=16)
                combo.grid(row=r, column=c*2+1, sticky="w", padx=5, pady=3)
                self.fields[key] = combo
            else:
                entry = tk.Entry(info_frame, width=18,
                                bg=BG_ELEVATED, fg=FG_PRIMARY,
                                insertbackground=FG_PRIMARY,
                                font=(FONT_FAMILY, 9),
                                relief="flat", borderwidth=1)
                entry.grid(row=r, column=c*2+1, sticky="w", padx=5, pady=3)
                self.fields[key] = entry

        # 属性成长区
        growth_frame = tk.LabelFrame(right_panel, text=" 属性 / 成长值 ",
                                      font=(FONT_FAMILY, 9, "bold"), fg=ACCENT_PRIMARY,
                                      bg=BG_SURFACE, padx=10, pady=8,
                                      relief="solid", borderwidth=1)
        growth_frame.pack(fill=tk.X, padx=5, pady=3)

        attr_fields = [
            ("atk", "初始攻击"), ("defs", "初始防御"), ("strg", "初始谋略"),
            ("sie", "初始攻城"), ("spd", "初始速度"),
            ("atk_g", "攻击成长"), ("def_g", "防御成长"), ("strg_g", "谋略成长"),
            ("sie_g", "攻城成长"), ("spd_g", "速度成长"),
        ]
        for i, (key, label) in enumerate(attr_fields):
            r, c = divmod(i, 5)
            tk.Label(growth_frame, text=label,
                     font=(FONT_FAMILY, 9), bg=BG_SURFACE, fg=FG_PRIMARY
                     ).grid(row=r, column=c*2, sticky="w", padx=3, pady=2)
            entry = tk.Entry(growth_frame, width=9,
                             bg=BG_ELEVATED, fg=FG_PRIMARY,
                             insertbackground=FG_PRIMARY,
                             font=(FONT_MONO, 9),
                             relief="flat", borderwidth=1)
            entry.grid(row=r, column=c*2+1, sticky="w", padx=3, pady=2)
            self.fields[key] = entry

        # 保存按钮
        btn_row = tk.Frame(right_panel, bg=BG_SURFACE)
        btn_row.pack(fill=tk.X, padx=5, pady=10)
        tk.Button(btn_row, text="💾 保存修改", command=self._save_current_hero,
                  bg=BTN_SUCCESS, fg="white", font=(FONT_FAMILY, 10, "bold"),
                  relief="flat", borderwidth=0, padx=28, pady=7,
                  activebackground=BTN_SUCCESS_HOVER).pack(side=tk.LEFT, padx=8)

        # 底部状态栏
        self.status_label = tk.Label(tab, text="", font=(FONT_FAMILY, 9),
                                     fg=FG_MUTED, bg=BG_DARK)
        self.status_label.pack(fill=tk.X, padx=8, pady=(0, 4))

        # 初始化数据
        self.refresh_hero_tree()

    # ================================================================
    #   列表操作
    # ================================================================

    def refresh_hero_tree(self):
        """刷新武将列表。"""
        self.hero_tree.delete(*self.hero_tree.get_children())
        if not HAS_LOCAL_DB:
            return
        db = SessionLocal()
        heroes = db.query(HeroTemplate).order_by(HeroTemplate.id).all()
        for h in heroes:
            skill_name = ""
            if h.innate_skill_id:
                skill = db.get(Skill, h.innate_skill_id)
                if skill:
                    skill_name = skill.name[:15]
            star_str = "★" * h.stars if h.stars else ""
            self.hero_tree.insert("", "end", iid=str(h.id), values=(
                h.id, h.name, star_str, h.faction, h.troop_type,
                h.cost, skill_name
            ), tags=("all_rows",))
        db.close()
        self._update_status()

    def _filter_heroes(self):
        """搜索过滤。"""
        search = self.search_var.get().lower().strip()
        for item in self.hero_tree.get_children():
            vals = self.hero_tree.item(item, "values")
            text = " ".join(str(v).lower() for v in vals)
            if search in text:
                self.hero_tree.reattach(item, "", "end")
            else:
                self.hero_tree.detach(item)

    def _update_status(self):
        """更新底部状态栏。"""
        total = len(self.hero_tree.get_children())
        hint = f"共 {total} 个武将"
        if self.current_hero:
            hint += f"  |  当前编辑: {self.current_hero.name} (ID:{self.current_hero.id})"
        self.status_label.config(text=hint)

    # ================================================================
    #   选中武将 → 加载右侧详情
    # ================================================================

    def _on_hero_select(self, event=None):
        sel = self.hero_tree.selection()
        if not sel:
            return
        hero_id = int(sel[0])
        db = SessionLocal()
        hero = db.get(HeroTemplate, hero_id)
        db.close()
        if not hero:
            return

        self.current_hero = hero
        self.detail_hint.config(text=f"{hero.name} ★{'★' * (hero.stars-1) if hero.stars else ''}")

        # 填充基本字段
        self.fields["name"].delete(0, tk.END)
        self.fields["name"].insert(0, hero.name or "")
        self.fields["stars"].delete(0, tk.END)
        self.fields["stars"].insert(0, str(hero.stars))
        self.fields["cost"].delete(0, tk.END)
        self.fields["cost"].insert(0, str(hero.cost))
        self.fields["attack_range"].delete(0, tk.END)
        self.fields["attack_range"].insert(0, str(hero.attack_range))

        self.fields["faction"].set(hero.faction or "")
        self.fields["troop_type"].set(hero.troop_type or "")

        # 战法
        combo, var = self.fields["innate_skill_id"]
        if hero.innate_skill_id:
            skill_db = SessionLocal()
            sk = skill_db.get(Skill, hero.innate_skill_id)
            if sk:
                var.set(sk.name)
            else:
                var.set("")
            skill_db.close()
        else:
            var.set("")
        self._refresh_skill_combo(combo)

        # 属性和成长
        for key in ["atk", "defs", "strg", "sie", "spd",
                     "atk_g", "def_g", "strg_g", "sie_g", "spd_g"]:
            val = getattr(hero, key, 0)
            self.fields[key].delete(0, tk.END)
            self.fields[key].insert(0, str(val) if val is not None else "0")

        self._update_status()

    # ================================================================
    #   CRUD 操作
    # ================================================================

    def _add_new_hero(self):
        """新增武将 → 清空右侧表单让用户填写。"""
        self.current_hero = None
        self.detail_hint.config(text="正在新增武将 — 填写后点击保存")
        for key, widget in self.fields.items():
            if key == "innate_skill_id":
                combo, var = widget
                var.set("")
                self._refresh_skill_combo(combo)
            elif key in ("faction", "troop_type"):
                widget.set("")
            else:
                widget.delete(0, tk.END)

    def _save_current_hero(self):
        """保存当前编辑的武将（新增或更新）。"""
        if not HAS_LOCAL_DB:
            messagebox.showerror("错误", "本地数据库不可用"); return
        try:
            name = self.fields["name"].get().strip()
            if not name:
                messagebox.showwarning("提示", "名称不能为空"); return

            stars = int(self.fields["stars"].get() or "1")
            cost = float(self.fields["cost"].get() or "1")
            attack_range = int(self.fields["attack_range"].get() or "1")
            faction = self.fields["faction"].get() or ""
            troop_type = self.fields["troop_type"].get() or ""

            atk = float(self.fields["atk"].get() or "0")
            defs_val = float(self.fields["defs"].get() or "0")
            strg = float(self.fields["strg"].get() or "0")
            sie = float(self.fields["sie"].get() or "0")
            spd = float(self.fields["spd"].get() or "0")
            atk_g = float(self.fields["atk_g"].get() or "0")
            def_g = float(self.fields["def_g"].get() or "0")
            strg_g = float(self.fields["strg_g"].get() or "0")
            sie_g = float(self.fields["sie_g"].get() or "0")
            spd_g = float(self.fields["spd_g"].get() or "0")

            # 战法
            skill_name = self.fields["innate_skill_id"][1].get()
            skill_id = None
            if skill_name.strip():
                sdb = SessionLocal()
                sk = sdb.query(Skill).filter(Skill.name == skill_name.strip()).first()
                if sk:
                    skill_id = sk.id
                sdb.close()

        except ValueError as e:
            messagebox.showerror("格式错误", f"数值字段格式错误:\n{e}")
            return

        db = SessionLocal()
        try:
            if self.current_hero:
                # 更新现有
                h = db.get(HeroTemplate, self.current_hero.id)
                if not h:
                    messagebox.showerror("错误", "武将已被删除"); return
                h.name = name; h.stars = stars; h.cost = cost
                h.attack_range = attack_range; h.faction = faction
                h.troop_type = troop_type; h.innate_skill_id = skill_id
                h.atk = atk; h.defs = defs_val; h.strg = strg; h.sie = sie; h.spd = spd
                h.atk_g = atk_g; h.def_g = def_g; h.strg_g = strg_g
                h.sie_g = sie_g; h.spd = spd_g
                msg = f'已更新: {name}'
            else:
                # 新增
                h = HeroTemplate(
                    name=name, stars=stars, cost=cost, attack_range=attack_range,
                    faction=faction, troop_type=troop_type,
                    atk=atk, defs=defs_val, strg=strg, sie=sie, spd=spd,
                    atk_g=atk_g, def_g=def_g, strg_g=strg_g, sie_g=sie_g, spd_g=spd_g,
                    innate_skill_id=skill_id
                )
                db.add(h)
                db.flush()  # 获取 ID
                self.current_hero = h
                msg = f'已创建: {name} (ID:{h.id})'
            db.commit()
        except Exception as e:
            db.rollback()
            messagebox.showerror("保存失败", str(e))
            return
        finally:
            db.close()

        self.refresh_hero_tree()
        if self.current_hero:
            self.hero_tree.selection_set(str(self.current_hero.id))
        self.detail_hint.config(text=msg)
        messagebox.showinfo("成功", msg)

    def _delete_hero(self):
        """删除选中武将。"""
        sel = self.hero_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先从左侧选择要删除的武将"); return

        hero_id = int(sel[0])
        item_data = self.hero_tree.item(sel[0])["values"]
        name = item_data[1]

        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除以下武将吗？\n\n  {name} (ID: {hero_id})\n\n此操作不可撤销！",
            icon="warning"
        ):
            return

        db = SessionLocal()
        db.query(HeroTemplate).filter(HeroTemplate.id == hero_id).delete()
        db.commit()
        db.close()

        self.current_hero = None
        self.detail_hint.config(text="← 请从左侧选择一个武将")
        self.refresh_hero_tree()
        messagebox.showinfo("已删除", f'{name} 已删除')

    # ================================================================
    #   战法相关辅助
    # ================================================================

    def _refresh_skill_combo(self, combo):
        """刷新战法下拉列表。"""
        if not HAS_LOCAL_DB: return
        db = SessionLocal()
        skills = db.query(Skill).order_by(Skill.id).all()
        names = [s.name for s in skills]
        combo['values'] = names
        db.close()

    def _create_skill_and_refresh(self, combo):
        """快速新建战法并刷新下拉框。"""
        if self.skill_tab:
            self.skill_tab._add_skill_dialog()
        self._refresh_skill_combo(combo)


# ============================================================
# 战法管理标签页
# ============================================================

class SkillEditorTab(EditorTab):
    """战法编辑标签页（左右分栏布局 + 嵌入式节点编辑器）。

    布局：
      - 左侧面板：战法列表 Treeview + 选中后的属性编辑区 + 操作按钮
      - 右侧面板：嵌入式 NodeEditor 节点画布（可切换为独立窗口模式）
    """

    # 属性字段定义: (数据库字段key, 显示名称, 是否下拉, 下拉选项)
    SKILL_FIELDS = [
        ("name",           "名称",         False, None),
        ("quality",        "品质",         True,  ["S", "A", "B", "C"]),
        ("skill_type",     "类型",         True,  ["主动", "被动", "指挥", "追击"]),
        ("activation_rate","发动率(%)",    False, None),
        ("range",          "有效距离",     False, None),
        ("target_type",    "目标类型",     True,  ["自己", "敌军单体", "敌军群体", "友军单体", "友军群体", "全体"]),
        ("troop_type",     "兵种限制",     True,  ["通用", "步兵", "骑兵", "弓兵"]),
        ("description",    "描述",         False, None),
    ]

    def __init__(self, notebook):
        super().__init__(notebook, "战法管理", "📜")
        tab = self.tab_frame

        self.current_skill_id = None          # 当前选中的战法ID
        self.current_skill_obj = None         # 当前选中的 Skill ORM 对象
        self.node_editor = None               # 嵌入式 NodeEditor 实例
        self.node_editor_window = None        # 独立窗口 NodeEditor 实例
        self.embed_var = tk.BooleanVar(value=True)  # 是否嵌入模式

        # ===== 主区域：PanedWindow 左右分割 =====
        paned = tk.PanedWindow(tab, orient="horizontal", bg=BG_DARK, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # ========== 左侧面板 ==========
        left = tk.Frame(paned, bg=BG_SURFACE)
        paned.add(left, width=360)

        # --- 左侧标题栏 ---
        left_header = tk.Frame(left, bg=BG_SURFACE)
        left_header.pack(fill="x", padx=6, pady=(6, 4))

        tk.Label(left_header, text="📜 战法列表", font=("微软雅黑", 11, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY).pack(side="left")

        # 搜索框
        self.skill_search_var = tk.StringVar()
        self.skill_search_var.trace_add("write", lambda *_: self._filter_skills())
        search_entry = tk.Entry(left_header, textvariable=self.skill_search_var, width=14,
                                font=("微软雅黑", 9), bg=BG_ELEVATED, fg=FG_PRIMARY,
                                insertbackground=FG_PRIMARY, relief="flat")
        search_entry.pack(side="right", padx=(10, 0))

        # --- 工具按钮行 ---
        tbar = tk.Frame(left, bg=BG_SURFACE)
        tbar.pack(fill="x", padx=5, pady=(0, 4))
        for text, cmd, color in [
            ("新增", self._add_skill_dialog, "#238636"),
            ("删除", self._delete_skill, "#da3633"),
            ("刷新", self.refresh_skill_tree, BTN_PRIMARY),
        ]:
            tk.Button(tbar, text=text, command=cmd,
                     bg=color if "新增" in text or "删除" in text else BTN_PRIMARY,
                     fg="white" if "新增" in text or "删除" in text else FG_PRIMARY,
                     font=("微软雅黑", 9, "bold") if "新增" in text or "删除" in text else ("微软雅黑", 9),
                     relief="flat", borderwidth=0, padx=10, pady=3,
                     activebackground=BG_HOVER).pack(side=tk.LEFT, padx=2)

        # --- 战法列表 Treeview ---
        columns = ("ID", "名称", "品质", "类型", "发动率")
        self.skill_tree = ttk.Treeview(left, columns=columns, show="headings", height=12)
        for col in columns:
            self.skill_tree.heading(col, text=col)
            self.skill_tree.column(col, width=65 if col != "名称" else 120, anchor="center")
        self.skill_tree.pack(fill="both", expand=True, padx=5, pady=3)
        self.skill_tree.bind("<<TreeviewSelect>>", self._on_skill_select)
        self.skill_tree.bind("<Double-1>", self._on_skill_double_click)
        self.refresh_skill_tree()

        # --- 左侧：属性编辑区 (选中战法后显示) ---
        detail_frame = tk.LabelFrame(left, text=" 属性编辑 ", font=("微软雅黑", 9, "bold"),
                                     fg=FG_SECONDARY, bg=BG_SURFACE,
                                     relief="solid", bd=1)
        detail_frame.pack(fill="x", padx=5, pady=5)

        self.skill_vars = {}   # 字段 -> tk变量
        for i, (key, label, is_combo, opts) in enumerate(self.SKILL_FIELDS):
            tk.Label(detail_frame, text=label, font=("微软雅黑", 9),
                     fg=FG_SECONDARY, bg=BG_SURFACE
                     ).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            if is_combo:
                var = tk.StringVar()
                combo = ttk.Combobox(detail_frame, textvariable=var, values=opts,
                                     state="readonly", width=16)
                combo.grid(row=i, column=1, padx=4, pady=2, sticky="ew")
            else:
                var = tk.StringVar()
                entry = tk.Entry(detail_frame, textvariable=var, width=18,
                                 font=("微软雅黑", 9), bg=BG_ELEVATED, fg=FG_PRIMARY,
                                 insertbackground=FG_PRIMARY, relief="flat")
                entry.grid(row=i, column=1, padx=4, pady=2, sticky="ew")
            self.skill_vars[key] = var
        detail_frame.columnconfigure(1, weight=1)

        # 保存属性按钮
        save_btn_row = len(self.SKILL_FIELDS)
        tk.Button(detail_frame, text="💾 保存属性", command=self._save_skill_info,
                  bg=BTN_SUCCESS, fg="white", font=(FONT_FAMILY, 9, "bold"),
                  relief="flat", padx=12, pady=4).grid(
                      row=save_btn_row, column=0, columnspan=2, pady=(8, 6), sticky="ew", padx=6)

        # 提示文字
        self.skill_hint = tk.Label(detail_frame, text="← 请先选择左侧一条战法",
                                   fg=FG_MUTED, bg=BG_SURFACE, font=("微软雅黑", 8))
        self.skill_hint.grid(row=save_btn_row+1, column=0, columnspan=2, pady=(0, 4))

        # ========== 右侧面板：节点编辑器区域 ==========
        right = tk.Frame(paned, bg=BG_DARK)
        paned.add(right)

        # 右侧顶部工具栏
        right_toolbar = tk.Frame(right, bg=BG_SURFACE)
        right_toolbar.pack(fill="x", padx=4, pady=(4, 0))

        tk.Label(right_toolbar, text="⚡ 节点效果配置", font=("微软雅黑", 11, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY).pack(side="left", padx=6)

        # 嵌入/独立窗口切换
        embed_cb = tk.Checkbutton(right_toolbar, text="嵌入右侧面板", variable=self.embed_var,
                                  command=self._toggle_node_editor_mode,
                                  bg=BG_SURFACE, fg=FG_PRIMARY, selectcolor=BG_ELEVATED,
                                  activebackground=BG_SURFACE, activeforeground=FG_PRIMARY,
                                  font=("微软雅黑", 9))
        embed_cb.pack(side="right", padx=6)

        # 右侧：NodeEditor 容器
        self.editor_container = tk.Frame(right, bg=BG_DARK)
        self.editor_container.pack(fill="both", expand=True, padx=4, pady=4)

        # 占位提示（未选择战法时显示）
        self.editor_placeholder = tk.Label(self.editor_container,
                                           text="📋 选择左侧战法后在此编辑节点效果\n\n"
                                                "支持拖拽连线、双击编辑参数\n\n"
                                                "可切换上方「嵌入右侧面板」改为独立窗口",
                                           fg=FG_MUTED, bg=BG_DARK, font=("微软雅黑", 11),
                                           justify="center")
        self.editor_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    # ================================================================
    #  战法列表操作
    # ================================================================

    def refresh_skill_tree(self):
        for item in self.skill_tree.get_children():
            self.skill_tree.delete(item)
        if not HAS_LOCAL_DB:
            return
        db = SessionLocal()
        skills = db.query(Skill).all()
        for s in skills:
            self.skill_tree.insert("", tk.END, values=(
                s.id, s.name, s.quality, s.skill_type, s.activation_rate
            ), tags=("all_rows",))
        db.close()

    def _filter_skills(self):
        search = self.skill_search_var.get().lower().strip()
        for item in self.skill_tree.get_children():
            vals = self.skill_tree.item(item, "values")
            text = " ".join(str(v).lower() for v in vals)
            if search in text:
                self.skill_tree.reattach(item, "", "end")
            else:
                self.skill_tree.detach(item)

    def _kill_all_node_editor_windows(self, skill_name=None):
        """暴力销毁所有已存在的 NodeEditor Toplevel 窗口，返回销毁数量。"""
        if not hasattr(self, 'master_root'):
            return 0
        to_destroy = []
        for widget in self.master_root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                try:
                    title = widget.title()
                    if skill_name:
                        if title == f"节点编辑器 - {skill_name}":
                            to_destroy.append(widget)
                    else:
                        if "节点编辑器" in title:
                            to_destroy.append(widget)
                except tk.TclError:
                    pass
        count = 0
        for w in to_destroy:
            try:
                w.destroy()
                count += 1
            except Exception:
                pass
        return count

    def _on_skill_select(self, event=None):
        """左侧战法单击选中 → 填充属性编辑区。"""
        sel = self.skill_tree.selection()
        if not sel:
            return
        item = self.skill_tree.item(sel[0])
        skill_id = item['values'][0]

        if not HAS_LOCAL_DB:
            return

        # skill_id 去重：跳过重复选中
        if skill_id == getattr(self, 'current_skill_id', None):
            return

        db = SessionLocal()
        skill = db.get(Skill, skill_id)
        if not skill:
            db.close()
            return

        self.current_skill_id = skill_id
        self.current_skill_obj = skill

        # 填充左侧属性编辑区
        self.skill_vars["name"].set(skill.name or "")
        self.skill_vars["quality"].set(skill.quality or "")
        self.skill_vars["skill_type"].set(skill.skill_type or "")
        self.skill_vars["activation_rate"].set(str(skill.activation_rate) if skill.activation_rate is not None else "")
        self.skill_vars["range"].set(str(skill.range) if skill.range is not None else "")
        self.skill_vars["target_type"].set(skill.target_type or "")
        self.skill_vars["troop_type"].set(skill.troop_type or "")
        self.skill_vars["description"].set(skill.description or "")
        self.skill_hint.configure(text=f"当前: 【{skill.name}】 ID={skill_id}")

        db.close()

    def _on_skill_double_click(self, event=None):
        """左侧战法双击 → 打开独立节点编辑器窗口（单例模式，已存在则提升前台）。"""
        if not HAS_LOCAL_DB or not HAS_NODE_EDITOR:
            return
        if self.current_skill_id is None or self.current_skill_obj is None:
            return
        # NodeEditor.__new__ 内部通过 _active_instances 实现单例
        self.node_editor_window = NodeEditor(self.master_root, self.current_skill_obj.name,
                                            self.current_skill_obj.effect_config)
        self.node_editor_window.on_node_editor_save = self._on_node_editor_save_window

    # ================================================================
    #  属性 CRUD
    # ================================================================

    def _add_skill_dialog(self):
        """弹出新增战法对话框。"""
        self._skill_form_dialog(title="新增战法", skill_id=None)

    def _delete_skill(self):
        """删除选中的战法。"""
        if self.current_skill_id is None:
            messagebox.showwarning("提示", "请先选择一条战法"); return
        if not messagebox.askyesno("确认删除", "删除战法将同时影响使用它的武将，确定删除吗？"):
            return
        if HAS_LOCAL_DB:
            db = SessionLocal()
            db.query(Skill).filter(Skill.id == self.current_skill_id).delete()
            db.commit(); db.close()
        self.current_skill_id = None
        self.current_skill_obj = None
        self._clear_editor()
        self.refresh_skill_tree()
        messagebox.showinfo("成功", "战法已删除")

    def _save_skill_info(self):
        """保存左侧属性编辑区的修改到数据库。"""
        if self.current_skill_id is None or not HAS_LOCAL_DB:
            messagebox.showwarning("提示", "请先选择一条战法"); return
        try:
            ar = int(self.skill_vars["activation_rate"].get().strip() or "0")
            rv = int(self.skill_vars["range"].get().strip() or "0")
        except ValueError:
            messagebox.showerror("错误", "发动率和距离必须是整数"); return

        name = self.skill_vars["name"].get().strip()
        if not name:
            messagebox.showerror("错误", "战法名称不能为空"); return

        db = SessionLocal()
        sk = db.get(Skill, self.current_skill_id)
        if sk:
            sk.name = name
            sk.quality = self.skill_vars["quality"].get()
            sk.skill_type = self.skill_vars["skill_type"].get()
            sk.activation_rate = ar
            sk.range = rv
            sk.target_type = self.skill_vars["target_type"].get()
            sk.troop_type = self.skill_vars["troop_type"].get()
            sk.description = self.skill_vars["description"].get().strip()
            db.commit()
            self.refresh_skill_tree()
            # 重新选中当前项
            for iid in self.skill_tree.get_children():
                if self.skill_tree.item(iid, "values")[0] == self.current_skill_id:
                    self.skill_tree.selection_set(iid)
                    break
            messagebox.showinfo("成功", f"战法【{name}】属性已保存")
        else:
            messagebox.showerror("错误", f"未找到战法(ID={self.current_skill_id})")
        db.close()

    def _skill_form_dialog(self, title, skill_id=None):
        """通用的战法表单弹窗（新增/复用编辑）。"""
        win = tk.Toplevel(self.master_root)
        win.title(title)
        win.geometry("480x480")
        win.resizable(False, False)

        fields = {}
        row = 0
        for key, label, is_combo, opts in self.SKILL_FIELDS:
            tk.Label(win, text=label, font=("微软雅黑", 9)).grid(row=row, column=0, padx=8, pady=4, sticky="e")
            if is_combo:
                var = tk.StringVar()
                cb = ttk.Combobox(win, textvariable=var, values=opts, state="readonly", width=26)
                cb.grid(row=row, column=1, padx=6, pady=4, sticky="w")
                fields[key] = var
            else:
                var = tk.StringVar()
                entry = tk.Entry(win, textvariable=var, width=28, font=("微软雅黑", 9))
                entry.grid(row=row, column=1, padx=6, pady=4, sticky="w")
                fields[key] = var
            row += 1

        # 编辑模式填充数据
        if skill_id and HAS_LOCAL_DB:
            db = SessionLocal()
            sk = db.get(Skill, skill_id)
            if sk:
                fields["name"].set(sk.name or "")
                fields["quality"].set(sk.quality or "")
                fields["skill_type"].set(sk.skill_type or "")
                fields["activation_rate"].set(str(sk.activation_rate) if sk.activation_rate is not None else "")
                fields["range"].set(str(sk.range) if sk.range is not None else "")
                fields["target_type"].set(sk.target_type or "")
                fields["troop_type"].set(sk.troop_type or "")
                fields["description"].set(sk.description or "")
            db.close()

        def save():
            if not HAS_LOCAL_DB:
                messagebox.showerror("错误", "本地数据库不可用"); return
            name = fields["name"].get().strip()
            if not name:
                messagebox.showerror("错误", "战法名称不能为空"); return
            try:
                ar = int(fields["activation_rate"].get().strip() or "0")
                rv = int(fields["range"].get().strip() or "0")
            except ValueError:
                messagebox.showerror("错误", "发动率和距离必须是整数"); return

            db = SessionLocal()
            if skill_id:
                sk = db.get(Skill, skill_id)
                if sk:
                    sk.name = name
                    sk.quality = fields["quality"].get()
                    sk.skill_type = fields["skill_type"].get()
                    sk.activation_rate = ar
                    sk.range = rv
                    sk.target_type = fields["target_type"].get()
                    sk.troop_type = fields["troop_type"].get()
                    sk.description = fields["description"].get().strip()
            else:
                db.add(Skill(name=name, level=1, quality=fields["quality"].get(),
                             skill_type=fields["skill_type"].get(),
                             activation_rate=ar, range=rv,
                             target_type=fields["target_type"].get(),
                             troop_type=fields["troop_type"].get(),
                             description=fields["description"].get().strip(),
                             effect="", effect_config={
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
                             }))
            db.commit(); db.close()
            win.destroy()
            self.refresh_skill_tree()
            messagebox.showinfo("成功", "战法已保存")

        btn_frame = tk.Frame(win, bg=BG_DARK)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=18)
        tk.Button(btn_frame, text="✅ 保存", command=save,
                  bg=BTN_SUCCESS, fg="white", font=(FONT_FAMILY, 9, "bold"),
                  relief="flat", padx=24, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="取消", command=win.destroy,
                  bg=BG_ELEVATED, fg=FG_SECONDARY, font=("微软雅黑", 9),
                  relief="flat", padx=16, pady=4).pack(side=tk.LEFT, padx=4)

    # ================================================================
    #  节点编辑器管理（嵌入 / 独立窗口 切换）
    # ================================================================

    def _destroy_editors(self):
        """销毁所有已有的 NodeEditor 实例（嵌入+独立窗口）。"""
        if self.node_editor:
            try:
                self.node_editor.destroy()
            except Exception:
                pass
            self.node_editor = None
        if self.node_editor_window:
            try:
                self.node_editor_window.destroy()
            except Exception:
                pass
            self.node_editor_window = None

    def _load_node_for_skill(self, skill_name, effect_config):
        """根据当前模式加载/创建节点编辑器。"""
        if not HAS_NODE_EDITOR:
            return

        # 读取当前模式
        mode_embed = self.embed_var.get()

        # 通过 _active_instances 销毁旧的 Toplevel 窗口
        from node_editor import _NodeEditorBase
        old = _NodeEditorBase._active_instances.get(skill_name)
        if old:
            try:
                if old.winfo_exists():
                    old.destroy()
            except Exception:
                pass
        self._destroy_editors()

        # 根据模式创建新的编辑器
        try:
            if mode_embed:
                if hasattr(self, 'editor_placeholder') and self.editor_placeholder:
                    self.editor_placeholder.place_forget()
                self.node_editor = NodeEditor(self.editor_container, skill_name, effect_config, embed_mode=True)
                self.node_editor.on_node_editor_save = self._on_node_editor_save_embedded
                self.node_editor.pack(fill="both", expand=True)
            else:
                if hasattr(self, 'editor_placeholder') and self.editor_placeholder:
                    self.editor_placeholder.place(relx=0.5, rely=0.5, anchor="center")
                self.node_editor_window = NodeEditor(self.master_root, skill_name, effect_config)
                self.node_editor_window.on_node_editor_save = self._on_node_editor_save_window
        except Exception:
            import traceback
            traceback.print_exc()

    def _toggle_node_editor_mode(self):
        """Checkbutton 回调：勾选=嵌入面板，取消勾选=关闭嵌入（不弹窗）。"""
        if self.embed_var.get():
            # 切换到嵌入模式：如果有选中战法则加载
            if self.current_skill_id is not None and self.current_skill_obj is not None:
                self._load_node_for_skill(self.current_skill_obj.name, self.current_skill_obj.effect_config)
        else:
            # 取消嵌入模式：只关闭嵌入式编辑器，不弹窗口
            self._destroy_editors()
            if hasattr(self, 'editor_placeholder') and self.editor_placeholder:
                self.editor_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _clear_editor(self):
        """清除右侧编辑器（取消选择或删除时调用）。"""
        self._destroy_editors()
        # 清空属性
        for var in self.skill_vars.values():
            if isinstance(var, tk.StringVar):
                var.set("")
        self.skill_hint.configure(text="← 请先选择左侧一条战法")
        # 显示占位符
        if hasattr(self, 'editor_placeholder') and self.editor_placeholder:
            self.editor_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    # ---- 节点编辑器保存回调 ----

    def _on_node_editor_save_embedded(self, skill_name, config):
        """嵌入式 NodeEditor 保存回调。"""
        self._do_node_save(config)

    def _on_node_editor_save_window(self, skill_name, config):
        """独立窗口 NodeEditor 保存回调。"""
        self._do_node_save(config)

    def _do_node_save(self, config):
        """统一执行节点图保存逻辑。"""
        if self.current_skill_id is None or not HAS_LOCAL_DB:
            return
        db = SessionLocal()
        s = db.get(Skill, self.current_skill_id)
        if s:
            s.effect_config = config
            db.commit()
            self.refresh_skill_tree()
            # 保持选中状态
            for iid in self.skill_tree.get_children():
                if self.skill_tree.item(iid, "values")[0] == self.current_skill_id:
                    self.skill_tree.selection_set(iid)
                    break
            messagebox.showinfo("成功", f"战法【{s.name}】节点效果已保存")
        else:
            messagebox.showerror("错误", f"未找到战法(ID={self.current_skill_id})")
        db.close()


# ============================================================
# 卡包管理标签页（合并 PackTab + PackDropTab）
# ============================================================

class PackEditorTab(EditorTab):
    """卡包 + 掉落配置标签页（左右分割布局）。"""

    def __init__(self, notebook):
        super().__init__(notebook, "卡包管理", "📦")
        tab = self.tab_frame
        self.current_pack_id = None

        paned = tk.PanedWindow(tab, orient="horizontal", sashwidth=4)
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # === 左侧：卡包列表 ===
        left = tk.Frame(paned, bg=BG_SURFACE); paned.add(left, width=350)
        tk.Label(left, text="📦 卡包列表", font=("微软雅黑", 11, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY
                 ).pack(anchor="w", padx=6, pady=(0, 4))

        tbar = tk.Frame(left, bg=BG_SURFACE)
        tbar.pack(fill="x", padx=5, pady=(0, 4))
        for text, cmd, color in [("新增卡包", self._add_pack, "#238636"), ("刷新", self._refresh_packs, BTN_PRIMARY)]:
            tk.Button(tbar, text=text, command=cmd,
                     bg=color if "新增" in text else BTN_PRIMARY,
                     fg="white" if "新增" in text else FG_PRIMARY,
                     font=("微软雅黑", 9, "bold") if "新增" in text else ("微软雅黑", 9),
                     relief="flat", borderwidth=0,
                     padx=10, pady=3).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "名称", "消耗类型", "消耗数量")
        self.pack_tree = ttk.Treeview(left, columns=cols, show="headings", height=18)
        for c in cols:
            self.pack_tree.heading(c, text=c); self.pack_tree.column(c, width=80, anchor="center")
        self.pack_tree.column("名称", width=120)
        self.pack_tree.pack(fill="both", expand=True, padx=5, pady=3)
        self.pack_tree.bind("<<TreeviewSelect>>", self._on_pack_select)
        self._refresh_packs()

        # === 右侧：掉落配置 ===
        right = tk.Frame(paned, bg=BG_SURFACE); paned.add(right)
        r_header = tk.Frame(right, bg=BG_SURFACE)
        r_header.pack(fill="x", padx=5, pady=(0, 4))
        tk.Label(r_header, text="⚡ 掉落配置", font=("微软雅黑", 11, "bold"),
                 bg=BG_SURFACE, fg=ACCENT_PRIMARY
                 ).pack(side="left")
        tk.Button(r_header, text="+ 添加掉落", command=self._add_drop, 
                  bg=BTN_ACCENT, fg="white",
                  font=("微软雅黑", 9, "bold"), relief="flat",
                  padx=10, pady=3).pack(side="right", padx=2)
        tk.Button(r_header, text="- 删除选中", command=self._del_drop, 
                  bg=BTN_DANGER, fg="white",
                  font=(FONT_FAMILY, 9, "bold"), relief="flat",
                  padx=8, pady=3).pack(side="right", padx=2)
        self.drop_hint = tk.Label(r_header, text="← 选择左侧卡包", fg=FG_MUTED,
                                   font=("微软雅黑", 9), bg=BG_SURFACE)
        self.drop_hint.pack(side="right", padx=10)

        dcols = ("ID", "武将名", "权重")
        self.drop_tree = ttk.Treeview(right, columns=dcols, show="headings", height=22)
        for c in dcols:
            self.drop_tree.heading(c, text=c); self.drop_tree.column(c, width=100, anchor="center")
        self.drop_tree.column("武将名", width=150)
        self.drop_tree.pack(fill="both", expand=True, padx=5)

        # 掉落列表右键菜单
        self.drop_menu = tk.Menu(self.drop_tree, tearoff=0)
        self.drop_menu.add_command(label="✏️ 修改权重", command=self._edit_drop_weight)
        self.drop_menu.add_separator()
        self.drop_menu.add_command(label="🗑️ 删除选中", command=self._del_drop)
        self.drop_tree.bind("<Button-3>", self._show_drop_menu)
        self.drop_tree.bind("<Double-1>", lambda e: self._edit_drop_weight())

    def _refresh_packs(self):
        self.pack_tree.delete(*self.pack_tree.get_children())
        if not HAS_LOCAL_DB: return
        db = SessionLocal()
        packs = db.query(CardPack).all()
        for p in packs:
            self.pack_tree.insert("", tk.END, values=(
                p.id, p.name, p.cost_type, p.cost_amount
            ), tags=("all_rows",))
        db.close()

    def _on_pack_select(self, event=None):
        sel = self.pack_tree.selection()
        if not sel:
            self.current_pack_id = None; return
        item = self.pack_tree.item(sel[0]); pid = item['values'][0]
        self.current_pack_id = pid
        self._load_drops(pid)

    def _load_drops(self, pack_id):
        self.drop_tree.delete(*self.drop_tree.get_children())
        if not HAS_LOCAL_DB: return
        db = SessionLocal()
        drops = db.query(CardPackDrop).filter(CardPackDrop.pack_id == pack_id).all()
        total_w = sum(d.weight for d in drops) if drops else 0
        for d in drops:
            ht = db.get(HeroTemplate, d.template_id)
            hname = ht.name if ht else f"(未知:{d.template_id})"
            pct = (d.weight / total_w * 100) if total_w > 0 else 0
            self.drop_tree.insert("", tk.END, values=(
                d.id, hname, f"{d.weight} ({pct:.1f}%)"
            ), tags=("all_rows",))
        db.close()
        self.drop_hint.config(text=f"总权重: {total_w}")

    def _add_pack(self):
        if not HAS_LOCAL_DB: return
        win = tk.Toplevel(self.master_root); win.title("新增卡包")
        win.geometry("300x180"); fields = {}
        for i, (text, key) in enumerate([("名称", "name"), ("消耗类型", "cost_type"), ("消耗数量", "cost_amount")]):
            tk.Label(win, text=text,
                     font=("微软雅黑", 9)).grid(row=i, column=0, padx=5, pady=8, sticky="e")
            if key == "cost_type":
                cb = ttk.Combobox(win, values=["tiger_tally", "copper"], state="readonly", width=15)
                cb.grid(row=i, column=1, padx=5, pady=8); fields[key] = cb
            else:
                e = tk.Entry(win, width=15,
                             font=("微软雅黑", 9))
                e.grid(row=i, column=1, padx=5, pady=8); fields[key] = e
        def save():
            db = SessionLocal()
            pack = CardPack(name=fields["name"].get(),
                           cost_type=fields["cost_type"].get(),
                           cost_amount=int(fields["cost_amount"].get() or 0))
            db.add(pack)
            db.commit()
            _log_operation("create", "card_pack", pack.id,
                           f"新增卡包 {pack.name} ({pack.cost_type}×{pack.cost_amount})")
            db.close(); win.destroy(); self._refresh_packs()
        tk.Button(win, text="保存", command=save, bg=BTN_SUCCESS, fg="white",
                 font=(FONT_FAMILY, 9, "bold"), relief="flat",
                 padx=20, pady=5).grid(row=3, column=0, columnspan=2, pady=15)

    def _add_drop(self):
        if not self.current_pack_id or not HAS_LOCAL_DB:
            messagebox.showwarning("提示", "请先选择一个卡包"); return
        db = SessionLocal()
        heroes = db.query(HeroTemplate).all()
        if not heroes:
            db.close(); messagebox.showwarning("提示", "没有武将模板，请先添加武将"); return
        win = tk.Toplevel(self.master_root); win.title("添加掉落项")
        win.geometry("300x160")
        tk.Label(win, text="武将:",
                 font=("微软雅黑", 9)).grid(row=0, column=0, padx=5, pady=10, sticky="e")
        hv = tk.StringVar()
        hc = ttk.Combobox(win, textvariable=hv, state="readonly", width=25,
                          values=[f"{h.id}:{h.name}" for h in heroes])
        hc.grid(row=0, column=1, padx=5, pady=10)
        if heroes: hc.set(f"{heroes[0].id}:{heroes[0].name}")
        tk.Label(win, text="权重:",
                 font=("微软雅黑", 9)).grid(row=1, column=0, padx=5, pady=10, sticky="e")
        we = tk.Entry(win, width=15,
                      font=("微软雅黑", 9))
        we.insert(0, "100"); we.grid(row=1, column=1, padx=5, pady=10)
        def save_d():
            hid = int(hv.get().split(":")[0])
            w = float(we.get())
            db2 = SessionLocal()
            drop = CardPackDrop(pack_id=self.current_pack_id, template_id=hid, weight=w)
            db2.add(drop)
            db2.commit()
            _log_operation("create", "card_pack_drop", drop.id,
                           f"卡包 {self.current_pack_id} 新增掉落 (武将模板ID:{hid}, 权重:{w})")
            db2.close(); win.destroy(); self._load_drops(self.current_pack_id)
        tk.Button(win, text="保存", command=save_d, bg=BTN_SUCCESS, fg="white",
                 font=(FONT_FAMILY, 9, "bold"), relief="flat",
                 padx=20, pady=5).grid(row=2, column=0, columnspan=2, pady=15)
        db.close()

    def _del_drop(self):
        sel = self.drop_tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", "删除此掉落项？"): return
        did = self.drop_tree.item(sel[0])['values'][0]
        if HAS_LOCAL_DB:
            db = SessionLocal()
            try:
                drop = db.query(CardPackDrop).filter(CardPackDrop.id == did).first()
                if drop:
                    _log_operation("delete", "card_pack_drop", did,
                                   f"删除卡包 {self.current_pack_id} 掉落项 (武将模板ID:{drop.template_id}, 权重:{drop.weight})")
                db.query(CardPackDrop).filter(CardPackDrop.id == did).delete()
                db.commit()
            finally:
                db.close()
        self._load_drops(self.current_pack_id)

    def _show_drop_menu(self, event):
        item = self.drop_tree.identify_row(event.y)
        if item:
            self.drop_tree.selection_set(item)
            self.drop_menu.post(event.x_root, event.y_root)

    def _edit_drop_weight(self):
        """右键/双击修改掉落权重。"""
        sel = self.drop_tree.selection()
        if not sel: return
        item = self.drop_tree.item(sel[0])
        did = item['values'][0]
        hname = item['values'][1]
        weight_str = str(item['values'][2]).split(" ")[0]  # "100 (33.3%)" → "100"
        try:
            current_weight = float(weight_str)
        except ValueError:
            current_weight = 100

        win = tk.Toplevel(self.master_root)
        win.title(f"修改权重 - {hname}")
        win.resizable(False, False)
        win.configure(bg=BG_DARK)
        win.transient(self.master_root)
        win.grab_set()

        tk.Label(win, text=f"修改 {hname} 的权重",
                 font=("微软雅黑", 12, "bold"), fg=FG_PRIMARY, bg=BG_DARK).pack(pady=(20, 15))

        row = tk.Frame(win, bg=BG_DARK)
        row.pack(padx=30, anchor="w")
        tk.Label(row, text="当前权重:", font=("微软雅黑", 10), fg=FG_SECONDARY, bg=BG_DARK).pack(side=tk.LEFT)
        tk.Label(row, text=str(current_weight), font=("微软雅黑", 10, "bold"), fg=ACCENT_PRIMARY, bg=BG_DARK).pack(side=tk.LEFT, padx=(5, 0))

        row2 = tk.Frame(win, bg=BG_DARK)
        row2.pack(padx=30, pady=(10, 15), anchor="w")
        tk.Label(row2, text="新权重:", font=("微软雅黑", 10), fg=FG_SECONDARY, bg=BG_DARK).pack(side=tk.LEFT)
        weight_entry = tk.Entry(row2, font=("微软雅黑", 11), width=15,
                                bg=BG_ELEVATED, fg=FG_PRIMARY, insertbackground=FG_PRIMARY,
                                relief=tk.FLAT, highlightthickness=1,
                                highlightcolor=ACCENT_PRIMARY, highlightbackground=BG_HOVER)
        weight_entry.pack(side=tk.LEFT, padx=(5, 0))
        weight_entry.insert(0, str(int(current_weight)))
        weight_entry.select_range(0, tk.END)
        weight_entry.focus_set()

        def do_save():
            try:
                new_weight = float(weight_entry.get().strip())
                if new_weight <= 0:
                    messagebox.showwarning("提示", "权重必须大于 0", parent=win)
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效数字", parent=win)
                return
            if HAS_LOCAL_DB:
                db = SessionLocal()
                try:
                    drop = db.query(CardPackDrop).filter(CardPackDrop.id == did).first()
                    if drop:
                        old_weight = drop.weight
                        drop.weight = new_weight
                        db.commit()
                        _log_operation("update", "card_pack_drop", did,
                                       f"修改卡包 {self.current_pack_id} 掉落项 {hname} 权重: {old_weight} → {new_weight}")
                finally:
                    db.close()
            win.destroy()
            self._load_drops(self.current_pack_id)

        btn_frame = tk.Frame(win, bg=BG_DARK)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="保存", command=do_save, bg=BTN_SUCCESS, fg="white",
                 font=("微软雅黑", 10, "bold"), relief="flat",
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=win.destroy, bg=BG_HOVER, fg=FG_PRIMARY,
                 font=("微软雅黑", 10), relief="flat",
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        weight_entry.bind("<Return>", lambda e: do_save())
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")


# ============================================================
# 建筑管理标签页（复用 BuildingTab 核心逻辑）
# ============================================================

class BuildingEditorTab(EditorTab):
    """建筑配置编辑标签页——精简版 BuildingTab。"""

    def __init__(self, notebook):
        super().__init__(notebook, "建筑管理", "🏗️", register_tab=False)
        # 复用 building_tab 的完整实现
        from gm_console.tabs.building_tab import (
            BuildingTab, EFFECT_CN_NAMES, EFFECT_FIELD_DEFS, _effects_to_cn_text
        )
        # 创建一个虚拟 notebook 让 BuildingTab 正确初始化
        self.building_tab = BuildingTab(self.notebook)


# ============================================================
# 快照管理标签页（核心新功能！）
# ============================================================

class SnapshotManagerTab(EditorTab):
    """
    数据库快照管理标签页：
    - 上传当前数据库为快照
    - 列出所有历史快照（含统计信息）
    - 恢复某个快照到当前数据库
    - 导出快照为文件
    - 删除快照
    """

    def __init__(self, notebook, api_client: APIClient = None):
        super().__init__(notebook, "数据库版本", "💾")
        self.api_client = api_client  # 可能为 None（纯离线模式）
        tab = self.tab_frame

        # ---- 顶部：连接状态 + 操作按钮 ----
        top_bar = tk.Frame(tab, bg=BG_SURFACE)
        top_bar.pack(fill=tk.X, padx=5, pady=5)

        # 左侧状态区
        status_frame = tk.LabelFrame(top_bar, text=" 连接状态 ",
                                     font=("微软雅黑", 9, "bold"), fg=ACCENT_PRIMARY,
                                     bg=BG_SURFACE, padx=10, pady=6,
                                     relief="solid", borderwidth=1)
        status_frame.pack(side=tk.LEFT, fill="y", padx=(0, 12))

        self.conn_status_var = tk.StringVar(value="🔴 未连接")
        self.conn_status_label = tk.Label(status_frame, textvariable=self.conn_status_var,
                                          font=(FONT_FAMILY, 10, "bold"), fg=ACCENT_DANGER,
                                          bg=BG_SURFACE)
        self.conn_status_label.pack(anchor="w")

        # URL 输入
        url_row = tk.Frame(status_frame, bg=BG_SURFACE)
        url_row.pack(fill="x", pady=(4, 0))
        tk.Label(url_row, text="地址:", font=("微软雅黑", 9),
                bg=BG_SURFACE, fg=FG_SECONDARY).pack(side="left")
        self.url_var = tk.StringVar(value="http://127.0.0.1:8000")
        self.url_entry = tk.Entry(url_row, textvariable=self.url_var, width=22,
                                  font=("Consolas", 9),
                                  bg=BG_ELEVATED, fg=FG_PRIMARY,
                                  insertbackground=FG_PRIMARY,
                                  relief="flat", borderwidth=1)
        self.url_entry.pack(side="left", padx=4)

        btn_conn = tk.Button(url_row, text="连接", command=self._connect,
                            bg=BTN_SUCCESS, fg="white",
                            font=(FONT_FAMILY, 9), relief="flat",
                            padx=8, pady=2)
        btn_conn.pack(side="left", padx=2)
        btn_disconn = tk.Button(url_row, text="断开", command=self._disconnect,
                               bg=BG_ELEVATED, fg=FG_SECONDARY,
                               font=("微软雅黑", 9), relief="flat",
                               padx=8, pady=2)
        btn_disconn.pack(side="left", padx=2)

        # 右侧操作按钮区
        action_frame = tk.LabelFrame(top_bar, text=" 操作 ",
                                     font=("微软雅黑", 9, "bold"), fg=ACCENT_PRIMARY,
                                     bg=BG_SURFACE, padx=10, pady=6,
                                     relief="solid", borderwidth=1)
        action_frame.pack(side=tk.RIGHT, fill="y")

        for text, cmd, color in [
            ("📤 上传快照", self._upload, "#238636"),
            ("🔄 刷新列表", self._list_snapshots, BTN_ACCENT),
        ]:
            tk.Button(action_frame, text=text, command=cmd, 
                     bg=color, fg="white",
                     font=("微软雅黑", 9, "bold"),
                     relief="flat", borderwidth=0,
                     padx=10, pady=4).pack(side="left", padx=3)

        # ---- 中部：当前统计信息 ----
        stats_frame = tk.LabelFrame(tab, text=" 当前数据库统计 ",
                                     font=("微软雅黑", 9, "bold"), fg=ACCENT_PRIMARY,
                                     bg=BG_SURFACE, padx=10, pady=6,
                                     relief="solid", borderwidth=1)
        stats_frame.pack(fill=tk.X, padx=5, pady=3)

        self.stats_labels = {}
        stats_keys = [
            ("heroes", "武将模板"), ("skills", "战法"),
            ("card_packs", "卡包"), ("card_pack_drops", "掉落项"),
            ("building_configs", "建筑"), ("building_levels", "建筑等级"),
            ("db_size_mb", "DB大小(MB)")
        ]
        for i, (key, cn) in enumerate(stats_keys):
            r, c = divmod(i, 4)
            lbl = tk.Label(stats_frame, text=f"{cn}: --", font=("微软雅黑", 9),
                           anchor="w")
            lbl.grid(row=r, column=c, padx=10, pady=3, sticky="w")
            self.stats_labels[key] = lbl

        # ---- 主区域：快照列表 ----
        list_frame = tk.Frame(tab, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        tk.Label(list_frame, text="📋 历史快照列表", font=("微软雅黑", 11, "bold"),
                 bg=BG_DARK, fg=ACCENT_PRIMARY
                 ).pack(anchor="w", pady=(0, 4))

        # 快照操作栏
        snap_toolbar = tk.Frame(list_frame, bg=BG_DARK)
        snap_toolbar.pack(fill="x")
        tk.Label(snap_toolbar, text="选中快照操作:", font=("微软雅黑", 9),
                bg=BG_DARK, fg=FG_SECONDARY).pack(side="left")
        for text, cmd, color, tip in [
            ("⬇️ 恢复", self._restore, ACCENT_WARNING, "覆盖当前数据库为此快照"),
            ("📂 导出", self._export, "#238636", "下载为SQLite文件"),
            ("🗑️ 删除", self._delete_snap, "#da3633", "永久删除此快照"),
        ]:
            b = tk.Button(snap_toolbar, text=text, command=cmd, bg=color,
                         fg="white" if color in (ACCENT_WARNING, "#238636", "#da3633") else FG_PRIMARY,
                         font=("微软雅黑", 9), relief="flat",
                         borderwidth=0, padx=8, pady=3)
            b.pack(side="left", padx=3)
            # 鼠标悬停提示
            self._bind_tooltip(b, tip)

        # 快照 Treeview
        snap_cols = ("id", "time", "desc", "size", "heroes", "skills", "buildings")
        self.snap_tree = ttk.Treeview(list_frame, columns=snap_cols, show="headings", height=14)
        headers = {
            "id": "快照ID", "time": "创建时间", "desc": "描述", "size": "大小",
            "heroes": "武将", "skills": "战法", "buildings": "建筑"
        }
        widths = {"id": 220, "time": 145, "desc": 260, "size": 70,
                  "heroes": 55, "skills": 55, "buildings": 55}
        for c in snap_cols:
            self.snap_tree.heading(c, text=headers[c])
            self.snap_tree.column(c, width=widths[c], anchor="center")
        self.snap_tree.column("desc", anchor="w")
        self.snap_tree.pack(fill="both", expand=True, pady=(3, 0))

        # 双击查看详情
        self.snap_tree.bind("<Double-1>", self._show_detail)

        # 底部信息栏
        self.bottom_info = tk.Label(tab, text="", font=("微软雅黑", 9),
                                    fg=FG_MUTED, bg=BG_DARK)
        self.bottom_info.pack(fill="x", padx=8, pady=(0, 4))

        # 自动加载本地统计
        self._update_local_stats()

    # ---- 工具方法 ----

    @staticmethod
    def _bind_tooltip(widget, text):
        """简单的 tooltip 绑定。"""
        def show(e):
            tw = tk.Toplevel(widget); tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root+10}+{e.y_root+20}")
            tk.Label(tw, text=text, bg="#ffffdd", fg="black", font=("微软雅黑", 9),
                    relief="solid", borderwidth=1, padx=4, pady=2).pack()
            widget._tooltip = tw
            tw.after(3000, lambda: tw.destroy() if tw.winfo_exists() else None)
        def hide(e):
            if hasattr(widget, '_tooltip') and widget._tooltip.winfo_exists():
                widget._tooltip.destroy()
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _log(self, msg: str):
        """在底部信息栏显示消息。"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.bottom_info.config(text=f"[{ts}] {msg}")

    def _set_connected(self, connected: bool, msg: str = ""):
        """更新连接状态显示。"""
        if connected:
            self.conn_status_var.set("🟢 已连接")
            self.conn_status_label.config(fg=ACCENT_SUCCESS)
            self.api_client.connected = True
        else:
            self.conn_status_var.set(f"🔴 {msg or '未连接'}")
            self.conn_status_label.config(fg=ACCENT_DANGER)
            self.api_client.connected = False

    def _update_local_stats(self):
        """更新本地数据库统计显示。"""
        if HAS_LOCAL_DB:
            try:
                db = SessionLocal()
                stats = {
                    "heroes": db.query(HeroTemplate).count(),
                    "skills": db.query(Skill).count(),
                    "card_packs": db.query(CardPack).count(),
                    "card_pack_drops": db.query(CardPackDrop).count(),
                    "building_configs": db.query(BuildingConfig).count(),
                    "building_levels": db.query(BuildingLevelConfig).count(),
                }
                db.close()
                db_path = os.path.join(_SERVER_DIR, "infinite_borders.sqlite3")
                stats["db_size_mb"] = round(os.path.getsize(db_path)/(1024*1024), 2) \
                                       if os.path.exists(db_path) else 0
                for key, label in self.stats_labels.items():
                    val = stats.get(key, "--")
                    cn_map = {"heroes": "武将", "skills": "战法", "card_packs": "卡包",
                              "card_pack_drops": "掉落", "building_configs": "建筑",
                              "building_levels": "等级", "db_size_mb": "MB"}
                    label.config(text=f"{cn_map.get(key,key)}: {val}")
            except Exception as e:
                self._log(f"读取统计失败: {e}")

    # ---- 连接管理 ----

    def _connect(self):
        """连接到服务器。"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入服务器地址"); return
        self.api_client = APIClient(base_url=url)
        self._log(f"正在连接 {url} ...")
        self.conn_status_var.set("🟡 连接中...")

        ok, info = self.api_client.test_connection()
        if ok:
            self._set_connected(True)
            self._log(f"✅ 连接成功")
            # 显示远程统计
            try:
                data = json.loads(info)
                for key in ["heroes", "skills", "card_packs", "building_configs",
                            "building_levels", "db_size_mb"]:
                    if key in self.stats_labels:
                        self.stats_labels[key].config(text=f"{data.get(key,'--')}", fg=ACCENT_INFO)
            except Exception:
                pass
            # 自动加载快照列表
            self._list_snapshots()
        else:
            self._set_connected(False, "连接失败")
            self._log(f"❌ 连接失败: {info}")
            messagebox.showerror("连接失败", f"无法连接到服务器:\n{info}")

    def _disconnect(self):
        """断开连接。"""
        self._set_connected(False, "已断开")
        self._log("已断开连接")
        self._update_local_stats()

    # ---- 快照操作 ----

    def _upload(self):
        """上传当前数据库快照。"""
        if not self.api_client or not self.api_client.connected:
            messagebox.showwarning("未连接", "请先连接到服务器"); return

        # 弹出输入描述对话框
        d = tk.Toplevel(self.master_root)
        d.title("上传快照"); d.geometry("400x140"); d.resizable(False, False)
        tk.Label(d, text="输入快照描述（可选）:",
                font=("微软雅黑", 10)).pack(pady=(15, 5))
        desc_var = tk.StringVar()
        de = tk.Entry(d, textvariable=desc_var, width=40,
                      font=("微软雅黑", 10))
        de.pack(padx=20, pady=5); de.focus_set()
        result = [None]

        def do_upload():
            try:
                result[0] = self.api_client.upload_snapshot(desc_var.get())
            except Exception as e:
                result[0] = {"success": False, "message": str(e)}
            d.destroy()

        tk.Button(d, text="上传", command=do_upload, bg=BTN_SUCCESS, fg="white",
                 font=(FONT_FAMILY, 10, "bold"), relief="flat",
                 padx=25, pady=6).pack(pady=15)
        d.bind("<Return>", lambda e: do_upload())

        # 等待对话框关闭后处理结果
        self._wait_window(d)
        if result[0]:
            res = result[0]
            if res.get("success"):
                self._log(f"✅ 上传成功: {res.get('snapshot_id', '')}")
                messagebox.showinfo("上传成功", res.get("message", ""))
                self._list_snapshots()
            else:
                messagebox.showerror("上传失败", res.get("message", "未知错误"))

    def _list_snapshots(self):
        """从服务器获取快照列表。"""
        if not self.api_client or not self.api_client.connected:
            messagebox.showwarning("未连接", "请先连接到服务器"); return
        try:
            data = self.api_client.list_snapshots()
            self.snap_tree.delete(*self.snap_tree.get_children())
            for snap in data.get("snapshots", []):
                stats = snap.get("stats", {})
                self.snap_tree.insert("", "end", iid=snap["id"], values=(
                    snap["id"],
                    snap.get("created_at", ""),
                    (snap.get("description", ""))[:40],
                    f"{snap.get('file_size_mb', '?')} MB",
                    stats.get("heroes", "-"),
                    stats.get("skills", "-"),
                    stats.get("building_configs", "-"),
                ), tags=("all_rows",))
            self._log(f"📋 共 {len(data.get('snapshots', []))} 个快照")
        except Exception as e:
            self._log(f"❌ 获取列表失败: {e}")
            messagebox.showerror("失败", f"获取快照列表失败:\n{e}")

    def _restore(self):
        """恢复选中的快照。"""
        sel = self.snap_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个快照"); return
        sid = sel[0]
        desc = self.snap_tree.item(sid)["values"][2] or sid
        if not messagebox.askyesno(
            "⚠️ 危险操作",
            f"确定要恢复快照到当前数据库吗？\n\n"
            f"快照: {sid}\n描述: {desc}\n\n"
            f"⚠️ 当前 GM 配置数据将被覆盖！（玩家数据不受影响）"):
            return

        if not self.api_client or not self.api_client.connected:
            messagebox.showwarning("未连接", "请先连接"); return

        try:
            self._log(f"正在恢复快照 {sid}...")
            result = self.api_client.restore_snapshot(sid)
            if result.get("success"):
                self._log(f"✅ 恢复成功: {sid}")
                messagebox.showinfo("恢复成功", f"已从快照恢复数据库\n\n{result.get('message','')}")
                self._update_local_stats()
            else:
                messagebox.showerror("恢复失败", result.get("message", ""))
        except Exception as e:
            messagebox.showerror("恢复失败", str(e))

    def _export(self):
        """导出选中的快照为 SQLite 文件。"""
        sel = self.snap_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个快照"); return
        sid = sel[0]

        if self.api_client and self.api_client.connected:
            # 在线导出
            path = filedialog.asksaveasfilename(
                defaultextension=".sqlite3",
                filetypes=[("SQLite", "*.sqlite3"), ("所有文件", "*.*")],
                initialfile=f"IB_snapshot_{sid}.sqlite3")
            if not path: return
            try:
                self._log(f"正在导出 {sid}...")
                self.api_client.export_snapshot(sid, path)
                size_mb = round(os.path.getsize(path) / (1024*1024), 2)
                self._log(f"✅ 导出完成: {path} ({size_mb} MB)")
                messagebox.showinfo("导出成功", f"已导出到:\n{path}\n({size_mb} MB)")
            except Exception as e:
                messagebox.showerror("导出失败", str(e))
        else:
            messagebox.showwarning("未连接", "导出需要在线连接")

    def _delete_snap(self):
        """删除选中的快照。"""
        sel = self.snap_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个快照"); return
        sid = sel[0]
        if not messagebox.askyesno("⚠️ 删除确认", f"确定要删除快照\n{sid}\n\n此操作不可撤销！"):
            return
        if not self.api_client or not self.api_client.connected:
            return
        try:
            result = self.api_client.delete_snapshot(sid)
            if result.get("success"):
                self._log(f"🗑️ 已删除: {sid}")
                self._list_snapshots()
            else:
                messagebox.showerror("删除失败", result.get("message", ""))
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def _show_detail(self, event=None):
        """双击查看快照详细信息。"""
        sel = self.snap_tree.selection()
        if not sel: return
        sid = sel[0]
        vals = self.snap_tree.item(sid, "values")

        detail_win = tk.Toplevel(self.master_root)
        detail_win.title(f"快照详情: {sid}")
        detail_win.geometry("450x380")
        detail_win.resizable(False, False)
        detail_win.configure(bg=BG_DARK)

        frame = tk.Frame(detail_win, bg=BG_SURFACE)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        info = [
            ("快照 ID", vals[0]),
            ("创建时间", vals[1]),
            ("描述", vals[2]),
            ("文件大小", vals[3]),
            ("武将数", vals[4]),
            ("战法数", vals[5]),
            ("建筑数", vals[6]),
        ]
        for i, (label, value) in enumerate(info):
            tk.Label(frame, text=label + ":",
                    font=("微软雅黑", 10, "bold")).grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(frame, text=str(value),
                    font=("微软雅黑", 10)).grid(row=i, column=1, sticky="w", padx=15, pady=4)

        # 关闭按钮
        tk.Button(frame, text="关闭", command=detail_win.destroy,
                 bg=BG_ELEVATED, fg=FG_SECONDARY,
                 font=("微软雅黑", 9), relief="flat",
                 padx=15, pady=4).grid(
                 row=len(info)+1, column=0, columnspan=2, pady=15)

    @staticmethod
    def _wait_window(window):
        """阻塞等待窗口关闭（模拟 wait_window 行为，兼容性更好）。"""
        window.grab_set()
        window.transient(window.master)
        window.wait_window()


# ============================================================
# 主编辑器窗口
# ============================================================

class DataEditor(tk.Tk):
    """
    InfiniteBorders 独立数据编辑器。

    功能：
    1. 🔗 连接管理 — 连接到服务器或使用本地数据库
    2. ⚔️ 武将管理 — 武增模板 CRUD
    3. 📜 战法管理 — 战法 CRUD + 节点编辑器
    4. 📦 卡包管理 — 卡包和掉落配置
    5. 🏗️ 建筑管理 — 建筑配置和等级效果
    6. 💾 数据库版本管理 — 快照上传/列表/恢复/导出/删除
    """

    def __init__(self, start_online: bool = False):
        super().__init__()
        self.title("InfiniteBorders 数据编辑器")
        self.geometry("1300x850")
        self.minsize(1100, 700)

        self.api_client = APIClient()

        # Notebook 主容器
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 先创建战法 Tab（因为武将 Tab 引用它）
        self.skill_tab = SkillEditorTab(self.notebook)

        # 创建各标签页
        self.hero_tab = HeroEditorTab(self.notebook, skill_tab=self.skill_tab)
        self.pack_tab = PackEditorTab(self.notebook)
        self.building_tab = BuildingEditorTab(self.notebook)
        self.snapshot_tab = SnapshotManagerTab(self.notebook, api_client=self.api_client)

        # 应用暗色主题（必须在所有标签页创建之后，才能遍历到所有子控件）
        apply_dark_theme(self)

        # 如果启动时指定了 online 模式，自动尝试连接
        if start_online:
            self.after(500, lambda: self.snapshot_tab._connect())


def main():
    """命令行入口。"""
    import argparse
    parser = argparse.ArgumentParser(description="InfiniteBorders 数据编辑器")
    parser.add_argument("--online", action="store_true", help="启动时自动尝试连接服务器")
    args = parser.parse_args()

    editor = DataEditor(start_online=args.online)
    editor.mainloop()


if __name__ == "__main__":
    main()

# gm_console/tabs/building_tab.py
# 建筑管理标签页：建筑基础配置 + 等级消耗/效果表格视图
# 从 gm_building_editor.py 迁移为 Notebook 标签页形式

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import copy

from sqlalchemy.orm.attributes import flag_modified
from theme import BG_DARK, BG_ELEVATED, FG_PRIMARY, FG_SECONDARY, FG_MUTED, FONT_FAMILY, BTN_ACCENT, BTN_DANGER, BTN_SUCCESS, ACCENT_WARNING
from models.database import SessionLocal
from models.schema import BuildingConfig, BuildingLevelConfig

# 效果字段中文映射
EFFECT_CN_NAMES = {
    "durability": "城池耐久", "cost_cap": "COST上限",
    "troop_slots": "出征队伍数", "troop_capacity": "部队容量",
    "vanguard_slots": "前锋武将槽", "garrison_bonus": "守军加成%",
    "vision_range": "视野范围", "alliance_share": "同盟共享",
    "exchange_enabled": "资源兑换",
    "physical_damage_reduction": "物理减伤%", "attack_bonus": "攻击加成",
    "strategy_damage_reduction": "策略减伤%", "strategy_bonus": "谋略加成",
    "cost_cap_bonus": "COST上限+", "fame_cap": "名望上限",
    "faction_bonus_atk": "攻击加成", "faction_bonus_def": "防御加成",
    "faction_bonus_strg": "谋略加成", "faction_bonus_spd": "速度加成",
    "recruit_speed": "招募速度", "train_speed": "练兵速度",
    "march_speed": "行军速度", "resource_output": "资源产出",
    "wood_output": "木材产出", "iron_output": "铁矿产出",
    "grain_output": "粮食产出", "stone_output": "石料产出",
    "storage_bonus": "仓库容量", "defense_bonus": "城防加成",
}


def _effects_to_cn_text(effects):
    """将效果 JSON 翻译为中文描述文本"""
    if not effects or not isinstance(effects, dict):
        return "{}"
    parts = []
    for k, v in effects.items():
        cn = EFFECT_CN_NAMES.get(k, k)
        if isinstance(v, bool):
            parts.append(f"{cn}:{'✅' if v else '❌'}")
        else:
            parts.append(f"{cn}:{v}")
    return " ".join(parts)


# ============================================================
# 效果字段定义：根据 building_key 决定显示哪些效果字段
# ============================================================
# 格式: (效果JSON的key, 显示名称, 类型, 默认值)
# 类型: "int", "float", "bool"
EFFECT_FIELD_DEFS = {
    "palace": [
        ("durability", "城池耐久", "int", 500),
        ("cost_cap", "COST上限", "float", 8.0),
    ],
    "training_ground": [
        ("troop_slots", "出征队伍数", "int", 1),
    ],
    "vanguard_camp": [
        ("vanguard_slots", "前锋武将槽", "int", 1),
    ],
    "barracks": [
        ("troop_capacity", "带兵上限", "int", 200),
    ],
    "camp_speed": [
        ("speed_bonus", "速度加成", "int", 3),
    ],
    "camp_defense": [
        ("defense_bonus", "防御加成", "int", 3),
    ],
    "camp_strategy": [
        ("strategy_bonus", "谋略加成", "int", 3),
    ],
    "martial_hall": [
        ("attack_bonus", "攻击加成", "int", 3),
    ],
    "residence": [
        ("copper_per_hour", "铜币/小时", "int", 50),
    ],
    "lumber_mill": [
        ("wood_per_hour", "木材/小时", "int", 80),
    ],
    "iron_smelter": [
        ("iron_per_hour", "铁矿/小时", "int", 60),
    ],
    "flour_mill": [
        ("grain_per_hour", "粮草/小时", "int", 100),
    ],
    "quarry": [
        ("stone_per_hour", "石料/小时", "int", 70),
    ],
    "warehouse": [
        ("storage_cap", "资源上限", "int", 50000),
    ],
    "recruitment": [
        ("recruit_speed_bonus", "征兵加速%", "int", 5),
    ],
    "reserve_camp": [
        ("reserve_cap", "预备兵上限", "int", 500),
    ],
    "city_wall": [
        ("wall_durability", "城墙耐久", "int", 2000),
        ("defense_bonus", "防御加成", "int", 5),
    ],
    "parapet": [
        ("damage_reduction", "伤害减免%", "float", 3.0),
    ],
    "watchtower": [
        ("vision_range", "视野范围", "int", 2),
    ],
    "beacon_tower": [
        ("vision_range", "视野范围", "int", 5),
        ("alliance_share", "同盟共享", "bool", False),
    ],
    "garrison_hall": [
        ("garrison_bonus", "守军加成%", "int", 10),
    ],
    "market": [
        ("exchange_enabled", "资源兑换", "bool", True),
    ],
    "hero_statue": [
        ("physical_damage_reduction", "物理减伤%", "float", 4.0),
        ("attack_bonus", "攻击加成", "int", 2),
    ],
    "sandbox_map": [
        ("strategy_damage_reduction", "策略减伤%", "float", 4.0),
        ("strategy_bonus", "谋略加成", "int", 2),
    ],
    "fengshan_altar": [
        ("cost_cap_bonus", "COST上限+", "float", 0.5),
    ],
    "altar_state": [
        ("fame_cap", "名望上限", "int", 600),
    ],
    # 点将台系列
    "altar_han": [
        ("faction_bonus_atk", "攻击加成", "int", 2),
        ("faction_bonus_def", "防御加成", "int", 2),
        ("faction_bonus_strg", "谋略加成", "int", 1),
        ("faction_bonus_spd", "速度加成", "int", 1),
    ],
    "altar_wei": [
        ("faction_bonus_atk", "攻击加成", "int", 2),
        ("faction_bonus_def", "防御加成", "int", 2),
        ("faction_bonus_strg", "谋略加成", "int", 1),
        ("faction_bonus_spd", "速度加成", "int", 1),
    ],
    "altar_shu": [
        ("faction_bonus_atk", "攻击加成", "int", 2),
        ("faction_bonus_def", "防御加成", "int", 2),
        ("faction_bonus_strg", "谋略加成", "int", 1),
        ("faction_bonus_spd", "速度加成", "int", 1),
    ],
    "altar_wu": [
        ("faction_bonus_atk", "攻击加成", "int", 2),
        ("faction_bonus_def", "防御加成", "int", 2),
        ("faction_bonus_strg", "谋略加成", "int", 1),
        ("faction_bonus_spd", "速度加成", "int", 1),
    ],
    "altar_meng": [
        ("faction_bonus_atk", "攻击加成", "int", 2),
        ("faction_bonus_def", "防御加成", "int", 2),
        ("faction_bonus_strg", "谋略加成", "int", 1),
        ("faction_bonus_spd", "速度加成", "int", 1),
    ],
}

DEFAULT_EFFECT_FIELDS = [
    ("effect_value_1", "效果1", "int", 0),
]


class BuildingTab:
    """建筑管理标签页：建筑基础配置 + 等级消耗/效果表格视图。"""

    def __init__(self, notebook):
        self.notebook = notebook
        self.db = SessionLocal()
        self.current_building = None
        self.current_level_configs = {}
        self.effect_fields = []
        self._edit_popup = None

        # 创建标签页容器
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="🏗️ 建筑管理")

        # ---- 顶部：建筑列表 ----
        top_frame = tk.Frame(tab, bg=BG_DARK)
        top_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(top_frame, text="建筑列表", font=("微软雅黑", 11, "bold"),
                 fg="white", bg=BG_DARK).pack(side="left", padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_buildings())
        search_entry = tk.Entry(top_frame, textvariable=self.search_var, width=20,
                                font=("微软雅黑", 10), bg=BG_ELEVATED, fg="white",
                                insertbackground="white")
        search_entry.pack(side="left", padx=10)

        btn_frame = tk.Frame(top_frame, bg=BG_DARK)
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text="重新加载默认", command=self._reload_defaults,
                  bg=ACCENT_WARNING, fg="white", font=(FONT_FAMILY, 9)).pack(side="left", padx=2)
        tk.Button(btn_frame, text="导出JSON", command=self._export_json,
                  bg=BTN_SUCCESS, fg="white", font=(FONT_FAMILY, 9)).pack(side="left", padx=2)
        tk.Button(btn_frame, text="导入JSON", command=self._import_json,
                  bg=BTN_ACCENT, fg="white", font=("微软雅黑", 9)).pack(side="left", padx=2)

        # ---- 建筑列表 Treeview ----
        list_frame = tk.Frame(tab, bg=BG_DARK)
        list_frame.pack(fill="x", padx=5, pady=(0, 3))

        cols = ("key", "name", "unlock", "max_lv", "category")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=6)
        self.tree.heading("key", text="标识")
        self.tree.heading("name", text="名称")
        self.tree.heading("unlock", text="解锁城主府")
        self.tree.heading("max_lv", text="满级")
        self.tree.heading("category", text="分类")
        self.tree.column("key", width=140)
        self.tree.column("name", width=140)
        self.tree.column("unlock", width=80)
        self.tree.column("max_lv", width=50)
        self.tree.column("category", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_building_select)

        # ---- 下方主区域：PanedWindow 左右分割 ----
        main_pane = tk.PanedWindow(tab, orient="horizontal", bg=BG_DARK,
                                    sashwidth=4, sashrelief="raised")
        main_pane.pack(fill="both", expand=True, padx=5, pady=3)

        # === 左侧面板：基础配置 ===
        left_panel = tk.Frame(main_pane, bg=BG_DARK)
        main_pane.add(left_panel, width=280)

        info_frame = tk.LabelFrame(left_panel, text="基础配置", font=("微软雅黑", 10, "bold"),
                                    fg="white", bg=BG_DARK, padx=5, pady=5)
        info_frame.pack(fill="both", expand=True)

        self.info_vars = {}
        info_fields = [
            ("building_key", "建筑标识"),
            ("building_name", "建筑名称"),
            ("category", "分类"),
            ("unlock_palace_level", "解锁城主府等级"),
            ("max_level", "最高等级"),
            ("sort_order", "显示排序"),
            ("description", "功能描述"),
        ]
        for i, (key, label) in enumerate(info_fields):
            tk.Label(info_frame, text=label, fg=FG_SECONDARY, bg=BG_DARK,
                     font=("微软雅黑", 9)).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            var = tk.StringVar()
            self.info_vars[key] = var
            entry = tk.Entry(info_frame, textvariable=var, width=22, font=("微软雅黑", 9),
                             bg=BG_ELEVATED, fg="white", insertbackground="white")
            entry.grid(row=i, column=1, padx=5, pady=2)
            if key == "building_key":
                entry.configure(state="readonly")

        row = len(info_fields)
        tk.Label(info_frame, text="前置条件", fg=FG_SECONDARY, bg=BG_DARK,
                 font=("微软雅黑", 9)).grid(row=row, column=0, sticky="nw", padx=5, pady=2)
        self.prereq_text = tk.Text(info_frame, width=22, height=3, font=("微软雅黑", 9),
                                    bg=BG_ELEVATED, fg="white", insertbackground="white")
        self.prereq_text.grid(row=row, column=1, padx=5, pady=2)
        tk.Label(info_frame, text="(格式: key LvN)", fg=FG_MUTED, bg=BG_DARK,
                 font=("微软雅黑", 8)).grid(row=row + 1, column=1, sticky="w", padx=5)

        tk.Button(info_frame, text="保存基础配置", command=self._save_building_info,
                  bg=BTN_SUCCESS, fg="white", font=("微软雅黑", 9, "bold"),
                  relief="flat", padx=10, pady=4).grid(
            row=row + 2, column=0, columnspan=2, pady=10, padx=5, sticky="ew")

        # === 右侧面板：等级配置表格 ===
        right_panel = tk.Frame(main_pane, bg=BG_DARK)
        main_pane.add(right_panel, width=1100)

        level_header = tk.Frame(right_panel, bg=BG_DARK)
        level_header.pack(fill="x", pady=(0, 3))

        tk.Label(level_header, text="等级配置", font=("微软雅黑", 11, "bold"),
                 fg="white", bg=BG_DARK).pack(side="left", padx=5)

        tk.Button(level_header, text="+ 新增等级", command=self._add_level,
                  bg=BTN_ACCENT, fg="white", font=("微软雅黑", 9), relief="flat"
                  ).pack(side="right", padx=2)
        tk.Button(level_header, text="删除选中等级", command=self._delete_level,
                  bg=BTN_DANGER, fg="white", font=("微软雅黑", 9), relief="flat"
                  ).pack(side="right", padx=2)
        tk.Button(level_header, text="批量保存所有等级", command=self._save_all_levels,
                  bg=BTN_SUCCESS, fg="white", font=("微软雅黑", 9, "bold"), relief="flat"
                  ).pack(side="right", padx=2)

        self.level_hint = tk.Label(level_header, text="← 请先选择左侧建筑",
                                    fg=FG_MUTED, bg=BG_DARK, font=("微软雅黑", 9))
        self.level_hint.pack(side="right", padx=10)

        table_container = tk.Frame(right_panel, bg=BG_DARK)
        table_container.pack(fill="both", expand=True)

        self.table_canvas = tk.Canvas(table_container, bg=BG_DARK, highlightthickness=0)
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.table_canvas.xview)
        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.table_canvas.yview)

        self.table_inner_frame = tk.Frame(self.table_canvas, bg=BG_DARK)
        self.table_inner_frame.bind("<Configure>",
                                     lambda e: self.table_canvas.configure(
                                         scrollregion=self.table_canvas.bbox("all")))
        self.table_canvas.create_window((0, 0), window=self.table_inner_frame, anchor="nw")
        self.table_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        self.table_canvas.pack(side="left", fill="both", expand=True)
        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")

        self.table_canvas.bind("<MouseWheel>",
                                lambda e: self.table_canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.table_inner_frame.bind("<MouseWheel>",
                                     lambda e: self.table_canvas.yview_scroll(-int(e.delta / 120), "units"))

        self.level_tree = None
        self.table_cols = []

        self._refresh_building_list()

    # ============================================================
    # 建筑列表
    # ============================================================

    def _refresh_building_list(self):
        self.tree.delete(*self.tree.get_children())
        buildings = self.db.query(BuildingConfig).order_by(
            BuildingConfig.layout_row, BuildingConfig.sort_order
        ).all()
        for bc in buildings:
            self.tree.insert("", "end", iid=bc.building_key, values=(
                bc.building_key, bc.building_name,
                bc.unlock_palace_level, bc.max_level, bc.category
            ), tags=("all_rows",))

    def _filter_buildings(self):
        search = self.search_var.get().lower()
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            text = " ".join(str(v).lower() for v in values)
            if search in text:
                self.tree.reattach(item, "", "end")
            else:
                self.tree.detach(item)

    # ============================================================
    # 选中建筑 → 加载详情
    # ============================================================

    def _on_building_select(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        key = selected[0]
        bc = self.db.query(BuildingConfig).filter(BuildingConfig.building_key == key).first()
        if not bc:
            return

        self.current_building = bc
        self.info_vars["building_key"].set(bc.building_key)
        self.info_vars["building_name"].set(bc.building_name)
        self.info_vars["category"].set(bc.category)
        self.info_vars["unlock_palace_level"].set(str(bc.unlock_palace_level))
        self.info_vars["max_level"].set(str(bc.max_level))
        self.info_vars["sort_order"].set(str(bc.sort_order))
        self.info_vars["description"].set(bc.description or "")

        self.prereq_text.delete("1.0", "end")
        if bc.prerequisites:
            for p in bc.prerequisites:
                self.prereq_text.insert("end", f"{p['key']} Lv{p['level']}\n")

        self._load_level_table()

    # ============================================================
    # 等级配置表格
    # ============================================================

    def _get_effect_fields(self, building_key: str) -> list:
        return EFFECT_FIELD_DEFS.get(building_key, DEFAULT_EFFECT_FIELDS)

    def _load_level_table(self):
        if not self.current_building:
            return
        bc = self.current_building
        self.effect_fields = self._get_effect_fields(bc.building_key)

        levels = self.db.query(BuildingLevelConfig).filter(
            BuildingLevelConfig.building_key == bc.building_key
        ).order_by(BuildingLevelConfig.level).all()
        self.current_level_configs = {lc.level: lc for lc in levels}

        for w in self.table_inner_frame.winfo_children():
            w.destroy()

        cost_cols = [
            ("level", "等级", 50),
            ("cost_wood", "木材", 90),
            ("cost_iron", "铁矿", 90),
            ("cost_stone", "石料", 90),
            ("cost_grain", "粮草", 90),
            ("cost_copper", "铜币", 90),
        ]
        effect_cols = [(f"eff_{ef[0]}", ef[1], 120) for ef in self.effect_fields]
        all_cols = cost_cols + effect_cols + [("raw_json", "效果描述(中文)", 260)]
        self.table_cols = all_cols

        self.level_tree = ttk.Treeview(
            self.table_inner_frame, columns=[c[0] for c in all_cols],
            show="headings", selectmode="browse",
            height=min(bc.max_level + 1, 25),
        )
        self.level_tree.tag_configure("all_rows", foreground="white", background=BG_ELEVATED)
        for cid, name, width in all_cols:
            self.level_tree.heading(cid, text=name)
            self.level_tree.column(cid, width=width, minwidth=40, anchor="center")

        for lv in range(1, bc.max_level + 1):
            lc = self.current_level_configs.get(lv)
            if lc:
                values = [lc.level, lc.cost_wood, lc.cost_iron, lc.cost_stone,
                          lc.cost_grain, lc.cost_copper]
                for ef in self.effect_fields:
                    val = lc.effects.get(ef[0], "") if lc.effects else ""
                    values.append("✅" if isinstance(val, bool) and val else
                                  ("❌" if isinstance(val, bool) else val if val else ""))
                raw = _effects_to_cn_text(lc.effects)
                values.append(raw if len(raw) <= 80 else raw[:78] + "..")
            else:
                values = [lv, 0, 0, 0, 0, 0] + [""] * len(self.effect_fields) + ["(未配置)"]
            self.level_tree.insert("", "end", iid=str(lv), values=values, tags=("all_rows",))

        self.level_tree.bind("<Double-1>", self._on_cell_double_click)

        tree_y = ttk.Scrollbar(self.table_inner_frame, orient="vertical", command=self.level_tree.yview)
        tree_x = ttk.Scrollbar(self.table_inner_frame, orient="horizontal", command=self.level_tree.xview)
        self.level_tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.level_tree.pack(side="left", fill="both", expand=True)
        tree_y.pack(side="right", fill="y")
        tree_x.pack(side="bottom", fill="x")
        self.level_hint.configure(text=f"{bc.building_name} Lv1~{bc.max_level} — 双击单元格编辑")

    def _on_cell_double_click(self, event):
        if not self.level_tree:
            return
        if self._edit_popup:
            self._edit_popup.destroy()

        region = self.level_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.level_tree.identify_column(event.x)
        row_id = self.level_tree.identify_row(event.y)
        if not col_id or not row_id:
            return

        col_idx = int(col_id.replace("#", "")) - 1
        if col_idx < 0 or col_idx >= len(self.table_cols):
            return
        col_key = self.table_cols[col_idx][0]
        if col_key in ("level", "raw_json"):
            return

        bbox = self.level_tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current_values = self.level_tree.item(row_id, "values")
        current_val = current_values[col_idx]

        self._edit_popup = popup = tk.Toplevel(self.notebook.master)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        abs_x = self.level_tree.winfo_rootx() + x
        abs_y = self.level_tree.winfo_rooty() + y
        popup.geometry(f"{w}x{h}+{abs_x}+{abs_y}")

        entry_var = tk.StringVar()
        is_bool = False
        if col_key.startswith("eff_"):
            ef_key = col_key[4:]
            for ef in self.effect_fields:
                if ef[0] == ef_key and ef[2] == "bool":
                    is_bool = True
                    new_val = not ("✅" in str(current_val))
                    entry_var.set("✅" if new_val else "❌")
                    break
        if not is_bool:
            edit_val = str(current_val) if current_val else "0"
            if edit_val in ("✅", "❌"):
                edit_val = "1" if edit_val == "✅" else "0"
            entry_var.set(edit_val)

        entry = tk.Entry(popup, textvariable=entry_var, font=("微软雅黑", 10),
                          bg="#ffffcc", fg="black", relief="solid", borderwidth=1)
        entry.pack(fill="both", expand=True)
        entry.select_range(0, "end")
        entry.focus_set()

        def _confirm(e=None):
            new_val_str = entry_var.get().strip()
            new_val = new_val_str
            if col_key.startswith("cost_"):
                try:
                    new_val = int(new_val_str or "0")
                except ValueError:
                    popup.destroy()
                    return
            elif col_key.startswith("eff_"):
                ef_key = col_key[4:]
                for ef in self.effect_fields:
                    if ef[0] == ef_key:
                        if ef[2] == "int":
                            try: new_val = int(new_val_str or "0")
                            except ValueError: popup.destroy(); return
                        elif ef[2] == "float":
                            try: new_val = float(new_val_str or "0")
                            except ValueError: popup.destroy(); return
                        elif ef[2] == "bool":
                            new_val = new_val_str in ("✅", "1", "True", "true")
                        break
            lv = int(row_id)
            values = list(self.level_tree.item(row_id, "values"))
            display_val = "✅" if isinstance(new_val, bool) and new_val else (
                "❌" if isinstance(new_val, bool) else new_val)
            values[col_idx] = display_val
            self.level_tree.item(row_id, values=values)
            self._update_cached_level(lv, col_key, new_val)
            self._update_raw_json_column(lv)
            popup.destroy()

        entry.bind("<Return>", _confirm)
        entry.bind("<Escape>", lambda e: popup.destroy())
        entry.bind("<FocusOut>", _confirm)

    def _update_cached_level(self, level, col_key, value):
        lc = self.current_level_configs.get(level)
        if not lc:
            lc = BuildingLevelConfig(
                building_key=self.current_building.building_key, level=level,
                cost_wood=0, cost_iron=0, cost_stone=0, cost_grain=0, cost_copper=0, effects={})
            self.current_level_configs[level] = lc
        if col_key.startswith("cost_"):
            setattr(lc, col_key, value)
        elif col_key.startswith("eff_"):
            if not lc.effects:
                lc.effects = {}
            lc.effects[col_key[4:]] = value

    def _update_raw_json_column(self, level):
        lc = self.current_level_configs.get(level)
        if not lc:
            return
        values = list(self.level_tree.item(str(level), "values"))
        raw = _effects_to_cn_text(lc.effects)
        values[-1] = raw if len(raw) <= 80 else raw[:78] + ".."
        self.level_tree.item(str(level), values=values)

    # ============================================================
    # 等级操作
    # ============================================================

    def _add_level(self):
        if not self.current_building:
            return
        bc = self.current_building
        new_level = bc.max_level + 1
        if not messagebox.askyesno("新增等级", f"将 {bc.building_name} 最高等级提升到 {new_level}？"):
            return
        bc.max_level = new_level
        self.info_vars["max_level"].set(str(new_level))
        self.db.commit()
        self._load_level_table()

    def _delete_level(self):
        if not self.current_building:
            return
        bc = self.current_building
        if bc.max_level <= 1:
            messagebox.showwarning("警告", "建筑至少需要1级！")
            return
        sel = self.level_tree.selection() if self.level_tree else []
        if not sel:
            return
        del_level = int(sel[0])
        if del_level != bc.max_level:
            messagebox.showwarning("警告", f"只能删除最高等级 (当前: Lv{bc.max_level})")
            return
        if not messagebox.askyesno("删除等级", f"删除 {bc.building_name} Lv{del_level}？"):
            return
        lc = self.db.query(BuildingLevelConfig).filter(
            BuildingLevelConfig.building_key == bc.building_key,
            BuildingLevelConfig.level == del_level).first()
        if lc:
            self.db.delete(lc)
            self.db.commit()
        bc.max_level = del_level - 1
        self.info_vars["max_level"].set(str(bc.max_level))
        self.db.commit()
        self.current_level_configs.pop(del_level, None)
        self._load_level_table()

    # ============================================================
    # 批量保存
    # ============================================================

    def _save_all_levels(self):
        if not self.current_building:
            return
        bc = self.current_building
        saved = created = 0
        for level, lc in self.current_level_configs.items():
            existing = self.db.query(BuildingLevelConfig).filter(
                BuildingLevelConfig.building_key == bc.building_key,
                BuildingLevelConfig.level == level).first()
            if existing:
                existing.cost_wood = lc.cost_wood
                existing.cost_iron = lc.cost_iron
                existing.cost_stone = lc.cost_stone
                existing.cost_grain = lc.cost_grain
                existing.cost_copper = lc.cost_copper
                existing.effects = copy.deepcopy(lc.effects) if lc.effects else {}
                flag_modified(existing, "effects")
                saved += 1
            else:
                self.db.add(BuildingLevelConfig(
                    building_key=bc.building_key, level=level,
                    cost_wood=lc.cost_wood, cost_iron=lc.cost_iron,
                    cost_stone=lc.cost_stone, cost_grain=lc.cost_grain,
                    cost_copper=lc.cost_copper,
                    effects=copy.deepcopy(lc.effects) if lc.effects else {}))
                created += 1
        try:
            self.db.commit()
            messagebox.showinfo("成功", f"批量保存完成: 更新 {saved} 条, 新增 {created} 条")
        except Exception as e:
            self.db.rollback()
            messagebox.showerror("保存失败", str(e))

    # ============================================================
    # 基础配置保存
    # ============================================================

    def _save_building_info(self):
        if not self.current_building:
            return
        bc = self.current_building
        bc.building_name = self.info_vars["building_name"].get()
        bc.category = self.info_vars["category"].get()
        try:
            bc.unlock_palace_level = int(self.info_vars["unlock_palace_level"].get())
            bc.max_level = int(self.info_vars["max_level"].get())
            bc.sort_order = int(self.info_vars["sort_order"].get())
        except ValueError:
            messagebox.showerror("错误", "等级和排序必须是整数")
            return
        bc.description = self.info_vars["description"].get()

        prereq_text = self.prereq_text.get("1.0", "end").strip()
        prereqs = []
        if prereq_text:
            for line in prereq_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit("Lv", 1)
                if len(parts) == 2:
                    prereqs.append({"key": parts[0].strip(), "level": int(parts[1].strip())})
                else:
                    messagebox.showerror("错误", f"前置条件格式错误: {line}\n正确: key LvN")
                    return
        bc.prerequisites = prereqs
        flag_modified(bc, "prerequisites")
        self.db.commit()
        self._refresh_building_list()
        self.tree.selection_set(bc.building_key)
        messagebox.showinfo("成功", f"已保存 {bc.building_name} 基础配置")

    # ============================================================
    # 导入/导出/重新加载
    # ============================================================

    def _reload_defaults(self):
        if not messagebox.askyesno("确认", "⚠️ 清空所有建筑配置并重新加载默认值！\nGM修改将丢失！"):
            return
        self.db.query(BuildingLevelConfig).delete()
        self.db.query(BuildingConfig).delete()
        self.db.commit()
        from building_configs import load_building_configs
        load_building_configs(self.db)
        self.current_building = None
        self.current_level_configs = {}
        self._refresh_building_list()
        self._clear_level_table()
        messagebox.showinfo("成功", "已重新加载默认配置")

    def _clear_level_table(self):
        for w in self.table_inner_frame.winfo_children():
            w.destroy()
        self.level_tree = None
        self.level_hint.configure(text="← 请先选择左侧建筑")

    def _export_json(self):
        buildings = self.db.query(BuildingConfig).all()
        export_data = []
        for bc in buildings:
            levels = self.db.query(BuildingLevelConfig).filter(
                BuildingLevelConfig.building_key == bc.building_key
            ).order_by(BuildingLevelConfig.level).all()
            export_data.append({
                "building_key": bc.building_key, "building_name": bc.building_name,
                "category": bc.category, "unlock_palace_level": bc.unlock_palace_level,
                "max_level": bc.max_level, "sort_order": bc.sort_order,
                "description": bc.description, "prerequisites": bc.prerequisites,
                "layout_row": bc.layout_row, "layout_col": bc.layout_col,
                "levels": [{"level": l.level, "cost_wood": l.cost_wood, "cost_iron": l.cost_iron,
                           "cost_stone": l.cost_stone, "cost_grain": l.cost_grain,
                           "cost_copper": l.cost_copper, "effects": l.effects} for l in levels],
            })
        filepath = filedialog.asksaveasfilename(defaultextension=".json",
                                                  filetypes=[("JSON", "*.json")],
                                                  initialfile="building_configs_backup.json")
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"已导出到 {filepath}")

    def _import_json(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not filepath:
            return
        if not messagebox.askyesno("确认", "⚠️ 导入将覆盖现有配置！"):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")
            return
        self.db.query(BuildingLevelConfig).delete()
        self.db.query(BuildingConfig).delete()
        self.db.commit()
        for bdata in data:
            self.db.add(BuildingConfig(
                building_key=bdata["building_key"], building_name=bdata["building_name"],
                category=bdata.get("category", "military"),
                unlock_palace_level=bdata.get("unlock_palace_level", 0),
                max_level=bdata.get("max_level", 1), sort_order=bdata.get("sort_order", 0),
                description=bdata.get("description", ""), prerequisites=bdata.get("prerequisites", []),
                layout_row=bdata.get("layout_row", 0), layout_col=bdata.get("layout_col", 0)))
            for ldata in bdata.get("levels", []):
                self.db.add(BuildingLevelConfig(
                    building_key=bdata["building_key"], level=ldata["level"],
                    cost_wood=ldata.get("cost_wood", 0), cost_iron=ldata.get("cost_iron", 0),
                    cost_stone=ldata.get("cost_stone", 0), cost_grain=ldata.get("cost_grain", 0),
                    cost_copper=ldata.get("cost_copper", 0), effects=ldata.get("effects", {})))
        self.db.commit()
        self.current_building = None
        self.current_level_configs = {}
        self._refresh_building_list()
        self._clear_level_table()
        messagebox.showinfo("成功", f"已从 {filepath} 导入配置")

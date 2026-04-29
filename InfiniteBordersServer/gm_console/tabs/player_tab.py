# gm_console/tabs/player_tab.py
# 用户管理标签页：查看所有玩家数据、在线状态、编辑玩家、删除玩家
# 支持：基本属性编辑、武将管理（增删）、建筑管理（升降级）
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests

from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING,
    BTN_DANGER, BTN_DANGER_HOVER, BTN_ACCENT, BTN_ACCENT_HOVER,
    FONT_FAMILY, FONT_MONO,
)

SERVER_URL = "http://127.0.0.1:8000"


class PlayerTab:
    """用户管理标签页。"""

    COLUMNS = [
        ("id", "ID", 40), ("username", "用户名", 100), ("password", "密码", 80),
        ("spawn", "出生点", 80), ("level", "主城", 50), ("territory", "领地", 55),
        ("heroes", "武将", 50), ("troops", "部队", 50),
        ("copper", "铜币", 70), ("jade", "玉符", 60), ("tiger_tally", "虎符", 60),
        ("wood", "木材", 60), ("iron", "铁矿", 60), ("stone", "石料", 60),
        ("grain", "粮草", 60), ("online", "在线", 50),
    ]

    def __init__(self, notebook, is_super_admin=False, readonly=False, player_detail_perms=None, gm_username=""):
        self.notebook = notebook
        self.is_super_admin = is_super_admin
        self.readonly = readonly
        self.player_detail_perms = player_detail_perms or {}
        self.gm_username = gm_username
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="👥 用户管理")

        toolbar = tk.Frame(tab, bg=BG_DARK)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Button(toolbar, text="🔄 刷新列表", font=(FONT_FAMILY, 10),
                  bg=BTN_ACCENT, fg=FG_PRIMARY, activebackground=BTN_ACCENT_HOVER,
                  relief=tk.FLAT, padx=12, pady=4, command=self.refresh_players).pack(side=tk.LEFT, padx=(0, 10))
        self.count_lbl = tk.Label(toolbar, text="共 0 个玩家", fg=FG_SECONDARY, bg=BG_DARK, font=(FONT_FAMILY, 10))
        self.count_lbl.pack(side=tk.LEFT)

        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        col_ids = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")
        for cid, heading, width in self.COLUMNS:
            self.tree.heading(cid, text=heading)
            self.tree.column(cid, width=width, minwidth=40, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.context_menu = tk.Menu(tab, tearoff=0, bg=BG_ELEVATED, fg=FG_PRIMARY)
        self.context_menu.add_command(label="✏️ 编辑此玩家", command=self.edit_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ 删除此玩家", command=self.delete_selected)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        detail_frame = tk.Frame(tab, bg=BG_DARK)
        detail_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.detail_lbl = tk.Label(detail_frame, text="", fg=FG_SECONDARY, bg=BG_DARK,
                                   font=(FONT_FAMILY, 9), anchor="w", justify=tk.LEFT)
        self.detail_lbl.pack(fill=tk.X)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._players_data = []
        self._auto_refresh()

    def _auto_refresh(self):
        # 检查窗口是否还存在（防止关闭后 after 回调报错）
        try:
            if not self.notebook.winfo_exists():
                return
        except tk.TclError:
            return
        self.refresh_players()
        self.notebook.after(5000, self._auto_refresh)

    def refresh_players(self):
        try:
            resp = requests.get(f"{SERVER_URL}/api/players", timeout=3)
            if resp.status_code == 200:
                self._players_data = resp.json()
                self._update_tree(self._players_data)
            else:
                self.count_lbl.config(text=f"请求失败: HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            self.count_lbl.config(text="服务器未启动")
        except Exception as e:
            self.count_lbl.config(text=f"刷新失败: {e}")

    def _update_tree(self, players):
        for item in self.tree.get_children():
            self.tree.delete(item)
        online_count = 0
        for p in players:
            online_str = "🟢 在线" if p.get("online") else "⚪ 离线"
            if p.get("online"):
                online_count += 1
            res = p.get("resources", {})
            cur = p.get("currencies", {})
            values = (
                p.get("id", ""), p.get("username", ""),
                p.get("password", "") or "无" if self.is_super_admin else ("●●●●" if p.get("has_password") else "无"), p.get("spawn", ""),
                p.get("main_city_level", 1), p.get("territory", 0),
                p.get("heroes", 0), p.get("troops", 0),
                f"{int(cur.get('copper', 0)):,}", f"{int(cur.get('jade', 0)):,}",
                f"{cur.get('tiger_tally', 0):,}",
                f"{res.get('wood', 0):,}", f"{res.get('iron', 0):,}",
                f"{res.get('stone', 0):,}", f"{res.get('grain', 0):,}", online_str,
            )
            tag = "online" if p.get("online") else "offline"
            self.tree.insert("", tk.END, iid=str(p["id"]), values=values, tags=(tag,))
        self.tree.tag_configure("online", foreground=ACCENT_SUCCESS)
        self.tree.tag_configure("offline", foreground=FG_MUTED)
        self.count_lbl.config(text=f"共 {len(players)} 个玩家 | 🟢 在线 {online_count} | ⚪ 离线 {len(players) - online_count}")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        pid, values = sel[0], self.tree.item(sel[0], "values")
        self.detail_lbl.config(text=f"已选中: {values[1]} (ID:{pid})  出生点: {values[3]}  |  双击编辑  |  右键菜单")

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _find_player_data(self, player_id):
        for p in self._players_data:
            if p.get("id") == player_id:
                return p
        return None

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        player_data = self._find_player_data(pid)
        if not player_data:
            messagebox.showerror("❌ 错误", "找不到玩家数据")
            return
        PlayerDetailDialog(self.notebook, player_data, on_refresh=self.refresh_players,
                            player_detail_perms=self.player_detail_perms,
                            gm_username=self.gm_username)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        username = self.tree.item(pid, "values")[1]
        if not messagebox.askyesno("⚠️ 删除玩家",
            f"确定要删除玩家 [{username}] (ID:{pid}) 吗？\n\n此操作不可撤销！"):
            return
        try:
            resp = requests.delete(f"{SERVER_URL}/api/players/{pid}",
                                   json={"operator": self.gm_username}, timeout=5)
            result = resp.json()
            if result.get("ok"):
                messagebox.showinfo("✅ 删除成功", result.get("message", ""))
                self.refresh_players()
            else:
                messagebox.showerror("❌ 删除失败", result.get("message", "未知错误"))
        except Exception as e:
            messagebox.showerror("❌ 删除失败", str(e))


class PlayerDetailDialog:
    """玩家综合管理对话框（三个标签页：基本信息 / 武将管理 / 建筑管理）。"""

    def __init__(self, parent, player_data, on_refresh=None, player_detail_perms=None, gm_username=""):
        self.player_data = player_data
        self.on_refresh = on_refresh
        self.player_id = player_data.get("id")
        self.username = player_data.get("username", "")
        self.gm_username = gm_username
        self.entries = {}
        self.perms = player_detail_perms or {}

        self.win = tk.Toplevel(parent)
        self.win.title(f"玩家管理 - {self.username} (ID:{self.player_id})")
        self.win.geometry("720x560")
        self.win.configure(bg=BG_DARK)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.update_idletasks()
        x = (self.win.winfo_screenwidth() - 720) // 2
        y = (self.win.winfo_screenheight() - 560) // 2
        self.win.geometry(f"+{x}+{y}")

        tk.Label(self.win, text=f"👤 {self.username} (ID:{self.player_id})",
                 font=(FONT_FAMILY, 14, "bold"), fg=ACCENT_PRIMARY, bg=BG_DARK).pack(pady=(10, 5))

        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._build_basic_tab()
        self._build_hero_tab()
        self._build_building_tab()

        tk.Button(self.win, text="关闭", font=(FONT_FAMILY, 10),
                  bg=BG_HOVER, fg=FG_SECONDARY, relief=tk.FLAT, padx=20, pady=5,
                  command=self.win.destroy).pack(pady=(0, 10))

    # ---- 标签页1：基本信息 ----
    def _build_basic_tab(self):
        tab = tk.Frame(self.nb, bg=BG_DARK)
        self.nb.add(tab, text="  📋 基本信息  ")
        container = tk.Frame(tab, bg=BG_DARK)
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        left = tk.Frame(container, bg=BG_DARK)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._add_field_group(left, "账号信息", [("username", "用户名", "str"), ("password", "新密码", "str")])
        self._add_field_group(left, "位置信息", [("spawn_x", "出生点 X", "int"), ("spawn_y", "出生点 Y", "int"), ("main_city_level", "主城等级", "int")])

        right = tk.Frame(container, bg=BG_DARK)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))
        self._add_field_group(right, "资源", [("wood", "木材", "int"), ("iron", "铁矿", "int"), ("stone", "石料", "int"), ("grain", "粮草", "int")])
        self._add_field_group(right, "货币", [("copper", "铜币", "int"), ("jade", "玉符", "int"), ("tiger_tally", "虎符", "int")])

        self._fill_basic_data()
        tk.Button(left, text="💾 保存修改", font=(FONT_FAMILY, 10, "bold"),
                  bg=BTN_ACCENT, fg=FG_PRIMARY, activebackground=BTN_ACCENT_HOVER,
                  relief=tk.FLAT, padx=15, pady=4, command=self._save_basic).pack(anchor="w", pady=(15, 0))

    def _add_field_group(self, parent, group_name, fields):
        tk.Label(parent, text=group_name, font=(FONT_FAMILY, 11, "bold"),
                 fg=ACCENT_PRIMARY, bg=BG_DARK, anchor="w").pack(anchor="w", pady=(10, 4), padx=5)
        for field_key, label_text, field_type in fields:
            row = tk.Frame(parent, bg=BG_DARK)
            row.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row, text=label_text, font=(FONT_FAMILY, 10), fg=FG_SECONDARY, bg=BG_DARK,
                     width=10, anchor="e").pack(side=tk.LEFT)
            entry = tk.Entry(row, font=(FONT_FAMILY, 10), width=18, bg=BG_ELEVATED, fg=FG_PRIMARY,
                             insertbackground=FG_PRIMARY, relief=tk.FLAT, highlightthickness=1,
                             highlightcolor=ACCENT_PRIMARY, highlightbackground=BG_HOVER)
            entry.pack(side=tk.LEFT, padx=(5, 0))
            if field_key == "password":
                entry.configure(show="*")
            # 根据权限控制只读
            if not self._is_field_editable(field_key):
                entry.config(state=tk.DISABLED)
            self.entries[field_key] = (entry, field_type)

    def _is_field_editable(self, field_key):
        """根据权限判断字段是否可编辑。"""
        perm_map = {
            "username": "edit_username",
            "password": "edit_password",
            "spawn_x": "edit_position",
            "spawn_y": "edit_position",
            "main_city_level": "edit_position",
            "wood": "edit_resources", "iron": "edit_resources",
            "stone": "edit_resources", "grain": "edit_resources",
            "copper": "edit_currencies", "jade": "edit_currencies",
            "tiger_tally": "edit_currencies",
        }
        perm_key = perm_map.get(field_key)
        if perm_key is None:
            return True  # 没有定义权限的字段默认可编辑
        return bool(self.perms.get(perm_key, True))

    def _fill_basic_data(self):
        res = self.player_data.get("resources", {})
        cur = self.player_data.get("currencies", {})
        spawn = self.player_data.get("spawn", "(0, 0)")
        try:
            sx, sy = spawn.strip("()").split(",")
            spawn_x, spawn_y = int(sx.strip()), int(sy.strip())
        except:
            spawn_x, spawn_y = 0, 0
        defaults = {
            "username": self.username, "password": "",
            "spawn_x": spawn_x, "spawn_y": spawn_y,
            "main_city_level": self.player_data.get("main_city_level", 1),
            "wood": res.get("wood", 0), "iron": res.get("iron", 0),
            "stone": res.get("stone", 0), "grain": res.get("grain", 0),
            "copper": int(cur.get("copper", 0)), "jade": int(cur.get("jade", 0)),
            "tiger_tally": int(cur.get("tiger_tally", 0)),
        }
        for field_key, (entry, _) in self.entries.items():
            if field_key == "password":
                entry.insert(0, "")
                entry.configure(fg=FG_MUTED)
                ph = "（留空不修改）"
                entry.bind("<FocusIn>", lambda e, ent=entry: self._clr_ph(ent, ph))
                entry.bind("<FocusOut>", lambda e, ent=entry, p=ph: self._set_ph(ent, p))
            else:
                entry.insert(0, str(defaults.get(field_key, "")))

    def _clr_ph(self, entry, ph):
        if entry.get() == ph:
            entry.delete(0, tk.END)
            entry.configure(fg=FG_PRIMARY)

    def _set_ph(self, entry, ph):
        if not entry.get().strip():
            entry.insert(0, ph)
            entry.configure(fg=FG_MUTED)

    def _save_basic(self):
        changes = {}
        for field_key, (entry, field_type) in self.entries.items():
            # 跳过无权限的字段
            if not self._is_field_editable(field_key):
                continue
            val = entry.get().strip()
            if field_key == "password":
                if not val or val == "（留空不修改）":
                    continue
            elif not val:
                continue
            try:
                if field_type == "int":
                    val = int(val)
            except ValueError:
                messagebox.showerror("❌ 输入错误", f"字段 {field_key} 需要整数")
                return
            changes[field_key] = val
        if not changes:
            messagebox.showinfo("提示", "没有修改任何字段")
            return
        if not messagebox.askyesno("确认修改", f"确认保存以下修改？\n\n" + "\n".join(f"{k} = {v}" for k, v in changes.items())):
            return
        try:
            changes["operator"] = self.gm_username
            resp = requests.put(f"{SERVER_URL}/api/players/{self.player_id}", json=changes, timeout=5)
            result = resp.json()
            if result.get("ok"):
                messagebox.showinfo("✅ 成功", result.get("message", ""))
                if self.on_refresh:
                    self.on_refresh()
            else:
                messagebox.showerror("❌ 失败", result.get("message", "未知错误"))
        except Exception as e:
            messagebox.showerror("❌ 失败", str(e))

    # ---- 标签页2：武将管理 ----
    def _build_hero_tab(self):
        tab = tk.Frame(self.nb, bg=BG_DARK)
        self.nb.add(tab, text="  ⚔️ 武将管理  ")

        hero_editable = self.perms.get("edit_heroes", True)

        toolbar = tk.Frame(tab, bg=BG_DARK)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))
        self._btn_add_hero = tk.Button(toolbar, text="➕ 添加武将", font=(FONT_FAMILY, 10), bg=BTN_ACCENT, fg=FG_PRIMARY,
                  activebackground=BTN_ACCENT_HOVER, relief=tk.FLAT, padx=10, pady=3,
                  command=self._add_hero)
        self._btn_add_hero.pack(side=tk.LEFT, padx=(0, 5))
        self._btn_remove_hero = tk.Button(toolbar, text="🗑️ 移除选中", font=(FONT_FAMILY, 10), bg=BTN_DANGER, fg=FG_PRIMARY,
                  activebackground=BTN_DANGER_HOVER, relief=tk.FLAT, padx=10, pady=3,
                  command=self._remove_hero)
        self._btn_remove_hero.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(toolbar, text="🔄 刷新", font=(FONT_FAMILY, 10), bg=BG_HOVER, fg=FG_SECONDARY,
                  relief=tk.FLAT, padx=10, pady=3, command=self._load_heroes).pack(side=tk.LEFT)
        self.hero_count_lbl = tk.Label(toolbar, text="", fg=FG_SECONDARY, bg=BG_DARK, font=(FONT_FAMILY, 10))
        self.hero_count_lbl.pack(side=tk.RIGHT)

        if not hero_editable:
            self._btn_add_hero.config(state=tk.DISABLED)
            self._btn_remove_hero.config(state=tk.DISABLED)

        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        hero_cols = [("id", "ID", 40), ("name", "武将", 75), ("stars", "星级", 45), ("level", "等级", 40),
                     ("faction", "阵营", 40), ("troop_type", "兵种", 50), ("attack", "攻击", 50),
                     ("defense", "防御", 50), ("strategy", "谋略", 50), ("speed", "速度", 50),
                     ("troops", "兵力", 70), ("rank", "阶", 30), ("stamina", "体力", 45), ("skills", "战法", 100)]
        col_ids = [c[0] for c in hero_cols]
        self.hero_tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="extended")
        for cid, heading, width in hero_cols:
            self.hero_tree.heading(cid, text=heading)
            self.hero_tree.column(cid, width=width, minwidth=30, anchor="center")
        self.hero_tree.column("skills", anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.hero_tree.yview)
        self.hero_tree.configure(yscrollcommand=vsb.set)
        self.hero_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._load_heroes()

    def _load_heroes(self):
        try:
            resp = requests.get(f"{SERVER_URL}/api/players/{self.player_id}/heroes", timeout=5)
            if resp.status_code == 200:
                self._render_heroes(resp.json())
            else:
                self.hero_count_lbl.config(text="加载失败")
        except Exception as e:
            self.hero_count_lbl.config(text=f"加载失败: {e}")

    def _render_heroes(self, heroes):
        for item in self.hero_tree.get_children():
            self.hero_tree.delete(item)
        for h in heroes:
            self.hero_tree.insert("", tk.END, iid=str(h["id"]), values=(
                h.get("id", ""), h.get("name", ""), "★" * h.get("stars", 0),
                h.get("level", 1), h.get("faction", ""), h.get("troop_type", ""),
                h.get("attack", 0), h.get("defense", 0), h.get("strategy", 0),
                h.get("speed", 0), f"{h.get('troops', 0)}/{h.get('max_troops', 0)}",
                h.get("rank", 1), h.get("stamina", 100), h.get("skills", "")))
        self.hero_count_lbl.config(text=f"共 {len(heroes)} 个武将")

    def _add_hero(self):
        try:
            resp = requests.get(f"{SERVER_URL}/api/hero_templates", timeout=5)
            if resp.status_code != 200:
                messagebox.showerror("❌ 错误", "无法加载武将模板列表")
                return
            templates = resp.json()
        except Exception as e:
            messagebox.showerror("❌ 错误", f"加载武将模板失败: {e}")
            return
        if not templates:
            messagebox.showinfo("提示", "没有可用的武将模板")
            return

        dlg = tk.Toplevel(self.win)
        dlg.title("选择武将模板")
        dlg.resizable(False, False)
        dlg.configure(bg=BG_DARK)
        dlg.transient(self.win)
        dlg.grab_set()

        tk.Label(dlg, text="选择要添加的武将模板", font=(FONT_FAMILY, 12, "bold"),
                 fg=ACCENT_PRIMARY, bg=BG_DARK).pack(pady=(10, 5))

        search_var = tk.StringVar()
        search_entry = tk.Entry(dlg, textvariable=search_var, font=(FONT_FAMILY, 10),
                                bg=BG_ELEVATED, fg=FG_PRIMARY, insertbackground=FG_PRIMARY,
                                relief=tk.FLAT, highlightthickness=1, highlightcolor=ACCENT_PRIMARY,
                                highlightbackground=BG_HOVER)
        search_entry.pack(fill=tk.X, padx=15, pady=5)
        search_entry.insert(0, "搜索武将名...")
        search_entry.configure(fg=FG_MUTED)
        search_entry.select_range(0, tk.END)

        def _focus_in(e):
            if search_entry.get() == "搜索武将名...":
                search_entry.delete(0, tk.END); search_entry.configure(fg=FG_PRIMARY)
        def _focus_out(e):
            if not search_entry.get().strip():
                search_entry.insert(0, "搜索武将名..."); search_entry.configure(fg=FG_MUTED)
        search_entry.bind("<FocusIn>", _focus_in)
        search_entry.bind("<FocusOut>", _focus_out)

        tree_frame = tk.Frame(dlg, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, padx=15, pady=5)
        tpl_cols = [("id", "ID", 40), ("name", "武将", 80), ("stars", "星级", 50),
                    ("faction", "阵营", 50), ("troop_type", "兵种", 55), ("cost", "统御", 50),
                    ("innate_skill", "自带战法", 110)]
        col_ids = [c[0] for c in tpl_cols]
        tpl_tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse", height=12)
        for cid, heading, width in tpl_cols:
            tpl_tree.heading(cid, text=heading)
            tpl_tree.column(cid, width=width, minwidth=35, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tpl_tree.yview)
        tpl_tree.configure(yscrollcommand=vsb.set)
        tpl_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _populate(filt=""):
            for item in tpl_tree.get_children():
                tpl_tree.delete(item)
            for t in templates:
                if filt and filt not in t.get("name", ""):
                    continue
                tpl_tree.insert("", tk.END, iid=str(t["id"]), values=(
                    t.get("id", ""), t.get("name", ""), "★" * t.get("stars", 0),
                    t.get("faction", ""), t.get("troop_type", ""), t.get("cost", 0),
                    t.get("innate_skill", "无")))
        _populate()
        search_var.trace_add("write", lambda *a: _populate(
            search_var.get().strip() if search_var.get().strip() != "搜索武将名..." else ""))

        def _confirm():
            sel = tpl_tree.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择一个武将模板", parent=dlg)
                return
            dlg._result = int(sel[0])
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=15, pady=12)
        tk.Button(btn_frame, text="✅ 确认添加", font=(FONT_FAMILY, 10, "bold"),
                  bg=BTN_ACCENT, fg=FG_PRIMARY, activebackground=BTN_ACCENT_HOVER,
                  relief=tk.FLAT, padx=20, pady=6, command=_confirm).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="取消", font=(FONT_FAMILY, 10), bg=BG_HOVER, fg=FG_SECONDARY,
                  relief=tk.FLAT, padx=20, pady=6, command=dlg.destroy).pack(side=tk.LEFT)
        tpl_tree.bind("<Double-1>", lambda e: _confirm())

        # 所有控件创建完后居中
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        x = (dlg.winfo_screenwidth() - w) // 2
        y = (dlg.winfo_screenheight() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        self.win.wait_window(dlg)
        if hasattr(dlg, "_result"):
            try:
                resp = requests.post(f"{SERVER_URL}/api/players/{self.player_id}/heroes",
                                     json={"template_id": dlg._result, "operator": self.gm_username}, timeout=5)
                result = resp.json()
                if result.get("ok"):
                    messagebox.showinfo("✅ 成功", result.get("message", ""))
                    self._load_heroes()
                    if self.on_refresh:
                        self.on_refresh()
                else:
                    messagebox.showerror("❌ 失败", result.get("message", "未知错误"))
            except Exception as e:
                messagebox.showerror("❌ 失败", str(e))

    def _remove_hero(self):
        sel = self.hero_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要移除的武将")
            return

        # 收集选中武将信息
        names = []
        for s in sel:
            hid = int(s)
            hname = self.hero_tree.item(s, "values")[1]
            names.append(f"{hname}(ID:{hid})")

        count = len(names)
        if count == 1:
            msg = f"确定要移除武将 [{names[0]}] 吗？\n该武将从部队中卸下后将被删除，不可撤销！"
        else:
            msg = (f"确定要移除以下 {count} 个武将吗？\n\n"
                   + "\n".join(f"  · {n}" for n in names)
                   + "\n\n这些武将从部队中卸下后将被删除，不可撤销！")

        if not messagebox.askyesno("⚠️ 确认移除", msg):
            return

        success, failed = 0, 0
        for s in sel:
            try:
                resp = requests.delete(
                    f"{SERVER_URL}/api/players/{self.player_id}/heroes/{int(s)}",
                    json={"operator": self.gm_username}, timeout=5)
                if resp.json().get("ok"):
                    success += 1
                else:
                    failed += 1
            except:
                failed += 1

        if failed == 0:
            messagebox.showinfo("✅ 成功", f"已移除 {success} 个武将")
        else:
            messagebox.showwarning("⚠️ 部分失败", f"成功 {success} 个，失败 {failed} 个")

        self._load_heroes()
        if self.on_refresh:
            self.on_refresh()

    # ---- 标签页3：建筑管理 ----
    def _build_building_tab(self):
        tab = tk.Frame(self.nb, bg=BG_DARK)
        self.nb.add(tab, text="  🏰 建筑管理  ")

        building_editable = self.perms.get("edit_buildings", True)

        toolbar = tk.Frame(tab, bg=BG_DARK)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))
        self._btn_building_up = tk.Button(toolbar, text="⬆️ 升级", font=(FONT_FAMILY, 10), bg=BTN_ACCENT, fg=FG_PRIMARY,
                  activebackground=BTN_ACCENT_HOVER, relief=tk.FLAT, padx=10, pady=3,
                  command=lambda: self._change_building_level(1))
        self._btn_building_up.pack(side=tk.LEFT, padx=(0, 5))
        self._btn_building_down = tk.Button(toolbar, text="⬇️ 降级", font=(FONT_FAMILY, 10), bg=BTN_DANGER, fg=FG_PRIMARY,
                  activebackground=BTN_DANGER_HOVER, relief=tk.FLAT, padx=10, pady=3,
                  command=lambda: self._change_building_level(-1))
        self._btn_building_down.pack(side=tk.LEFT, padx=(0, 5))
        self._btn_building_custom = tk.Button(toolbar, text="📝 自定义等级", font=(FONT_FAMILY, 10), bg=BG_HOVER, fg=FG_SECONDARY,
                  relief=tk.FLAT, padx=10, pady=3, command=self._set_building_level_custom)
        self._btn_building_custom.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(toolbar, text="🔄 刷新", font=(FONT_FAMILY, 10), bg=BG_HOVER, fg=FG_SECONDARY,
                  relief=tk.FLAT, padx=10, pady=3, command=self._load_buildings).pack(side=tk.LEFT)

        if not building_editable:
            self._btn_building_up.config(state=tk.DISABLED)
            self._btn_building_down.config(state=tk.DISABLED)
            self._btn_building_custom.config(state=tk.DISABLED)
        self.bld_count_lbl = tk.Label(toolbar, text="", fg=FG_SECONDARY, bg=BG_DARK, font=(FONT_FAMILY, 10))
        self.bld_count_lbl.pack(side=tk.RIGHT)

        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        bld_cols = [("id", "ID", 40), ("building_name", "建筑", 90), ("level", "等级", 75),
                    ("max_level", "上限", 50), ("category", "分类", 65), ("description", "描述", 250)]
        col_ids = [c[0] for c in bld_cols]
        self.bld_tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")
        for cid, heading, width in bld_cols:
            self.bld_tree.heading(cid, text=heading)
            self.bld_tree.column(cid, width=width, minwidth=35, anchor="center")
        self.bld_tree.column("description", anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.bld_tree.yview)
        self.bld_tree.configure(yscrollcommand=vsb.set)
        self.bld_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- 底部：资源编辑区 ----
        res_frame = tk.LabelFrame(tab, text="📦 资源编辑", font=(FONT_FAMILY, 10, "bold"),
                                  fg=ACCENT_PRIMARY, bg=BG_DARK, padx=10, pady=8)
        res_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.res_entries = {}
        res_fields = [("wood", "🪵 木材"), ("iron", "⛏️ 铁矿"), ("stone", "🪨 石料"), ("grain", "🌾 粮草")]
        for i, (key, label) in enumerate(res_fields):
            tk.Label(res_frame, text=label, font=(FONT_FAMILY, 10), fg=FG_SECONDARY,
                     bg=BG_DARK, width=8, anchor="e").grid(row=0, column=i * 2, padx=(10 if i > 0 else 0, 3))
            entry = tk.Entry(res_frame, font=(FONT_FAMILY, 10), width=10,
                             bg=BG_ELEVATED, fg=FG_PRIMARY, insertbackground=FG_PRIMARY,
                             relief=tk.FLAT, highlightthickness=1, highlightcolor=ACCENT_PRIMARY,
                             highlightbackground=BG_HOVER)
            entry.grid(row=0, column=i * 2 + 1, padx=(0, 10), pady=3)
            self.res_entries[key] = entry

        tk.Button(res_frame, text="💾 保存资源", font=(FONT_FAMILY, 10, "bold"),
                  bg=BTN_ACCENT, fg=FG_PRIMARY, activebackground=BTN_ACCENT_HOVER,
                  relief=tk.FLAT, padx=15, pady=4, command=self._save_resources
                  ).grid(row=0, column=len(res_fields) * 2, padx=(10, 0))

        # 填充当前资源值
        res = self.player_data.get("resources", {})
        for key, entry in self.res_entries.items():
            entry.insert(0, str(int(res.get(key, 0))))

        self._load_buildings()

    def _load_buildings(self):
        try:
            resp = requests.get(f"{SERVER_URL}/api/players/{self.player_id}/buildings", timeout=5)
            if resp.status_code == 200:
                self._render_buildings(resp.json())
            else:
                self.bld_count_lbl.config(text="加载失败")
        except Exception as e:
            self.bld_count_lbl.config(text=f"加载失败: {e}")

    def _render_buildings(self, buildings):
        for item in self.bld_tree.get_children():
            self.bld_tree.delete(item)
        cat_map = {"core": "🏛 核心", "resource": "📦 资源", "military": "⚔ 军事",
                   "defense": "🛡 防御", "special": "✨ 特殊"}
        for b in buildings:
            lv = b.get("level", 0)
            ml = b.get("max_level", 1)
            lv_str = f"Lv {lv}/{ml}" if lv > 0 else "未建造"
            cat = cat_map.get(b.get("category", ""), b.get("category", ""))
            self.bld_tree.insert("", tk.END, iid=str(b["id"]), values=(
                b.get("id", ""), b.get("building_name", ""), lv_str, ml, cat,
                b.get("description", "")))
        self.bld_count_lbl.config(text=f"共 {len(buildings)} 个建筑")

    def _get_selected_building_info(self):
        """获取选中建筑的当前等级和上限。"""
        sel = self.bld_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个建筑")
            return None
        bid = int(sel[0])
        values = self.bld_tree.item(bid, "values")
        # 解析等级字符串 "Lv 3/5" 或 "未建造"
        lv_str = str(values[2])
        try:
            if lv_str == "未建造":
                current = 0
            else:
                current = int(lv_str.split("/")[0].replace("Lv ", ""))
        except:
            current = 0
        max_lv = int(values[3])
        return bid, values[1], current, max_lv

    def _change_building_level(self, delta):
        info = self._get_selected_building_info()
        if not info:
            return
        bid, name, current, max_lv = info
        new_lv = current + delta
        if new_lv < 0:
            messagebox.showinfo("提示", "等级不能低于 0")
            return
        if new_lv > max_lv:
            messagebox.showinfo("提示", f"该建筑最高 {max_lv} 级")
            return
        action = "升级" if delta > 0 else "降级"
        if not messagebox.askyesno("确认", f"将 {name} 从 Lv{current} {action}到 Lv{new_lv}？"):
            return
        self._do_update_building(bid, new_lv)

    def _set_building_level_custom(self):
        info = self._get_selected_building_info()
        if not info:
            return
        bid, name, current, max_lv = info
        val = simpledialog.askinteger("自定义等级",
            f"设置 {name} 的等级 (0~{max_lv})：\n0=未建造",
            initialvalue=current, minvalue=0, maxvalue=max_lv, parent=self.win)
        if val is None:
            return
        if val == current:
            return
        self._do_update_building(bid, val)

    def _do_update_building(self, building_id, new_level):
        try:
            resp = requests.put(
                f"{SERVER_URL}/api/players/{self.player_id}/buildings/{building_id}",
                json={"level": new_level, "operator": self.gm_username}, timeout=5)
            result = resp.json()
            if result.get("ok"):
                messagebox.showinfo("✅ 成功", result.get("message", ""))
                self._load_buildings()
                if self.on_refresh:
                    self.on_refresh()
            else:
                messagebox.showerror("❌ 失败", result.get("message", "未知错误"))
        except Exception as e:
            messagebox.showerror("❌ 失败", str(e))

    def _save_resources(self):
        """保存资源修改。"""
        changes = {}
        cn_map = {"wood": "木材", "iron": "铁矿", "stone": "石料", "grain": "粮草"}
        for key, entry in self.res_entries.items():
            val = entry.get().strip()
            if not val:
                continue
            try:
                changes[key] = int(val)
            except ValueError:
                messagebox.showerror("❌ 输入错误", f"{cn_map[key]}需要整数")
                return
        if not changes:
            messagebox.showinfo("提示", "没有修改任何资源")
            return
        if not messagebox.askyesno("确认修改",
            f"确认保存以下资源修改？\n\n" + "\n".join(f"{cn_map[k]} = {v:,}" for k, v in changes.items())):
            return
        try:
            changes["operator"] = self.gm_username
            resp = requests.put(f"{SERVER_URL}/api/players/{self.player_id}", json=changes, timeout=5)
            result = resp.json()
            if result.get("ok"):
                messagebox.showinfo("✅ 成功", "资源已保存")
                if self.on_refresh:
                    self.on_refresh()
            else:
                messagebox.showerror("❌ 失败", result.get("message", "未知错误"))
        except Exception as e:
            messagebox.showerror("❌ 失败", str(e))

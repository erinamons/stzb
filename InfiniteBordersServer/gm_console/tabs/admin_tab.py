# gm_console/tabs/admin_tab.py
# GM 管理员管理标签页（超级管理员专属）
# 功能：查看所有管理员、添加新管理员、修改密码/角色/权限、删除管理员
# 通过 HTTP API 操作，需要服务器运行
import tkinter as tk
from tkinter import ttk, messagebox
import requests

from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING,
    BTN_PRIMARY, BTN_SUCCESS, BTN_DANGER,
    FONT_FAMILY,
)

SERVER_URL = "http://127.0.0.1:8000"

# 标签页定义（名称 → 显示名）
TAB_DEFINITIONS = [
    ("dashboard", "🎮 运行状态"),
    ("player", "👥 用户管理"),
    ("skill", "📜 战法管理"),
    ("hero", "⚔️ 武将管理"),
    ("pack", "📦 卡包管理"),
    ("building", "🏗️ 建筑管理"),
    ("report", "📋 战报管理"),
    ("snapshot", "📸 快照管理"),
]

# 用户管理子权限定义（键 → 显示名）
PLAYER_PERM_DEFINITIONS = [
    ("edit_username", "修改用户名"),
    ("edit_password", "修改密码"),
    ("edit_position", "修改出生点"),
    ("edit_resources", "修改资源（木材/铁矿/石料/粮草）"),
    ("edit_currencies", "修改货币（铜币/玉符/虎符）"),
    ("edit_heroes", "管理武将（添加/移除）"),
    ("edit_buildings", "管理建筑（升级/降级）"),
]


class AdminTab:
    """GM 管理员管理标签页（仅超级管理员可见）。"""

    COLUMNS = [
        ("id", "ID", 40), ("username", "用户名", 120), ("password", "密码", 100),
        ("role", "角色", 100), ("created_at", "创建时间", 160),
    ]

    def __init__(self, notebook, is_super_admin=True, gm_username=""):
        self.notebook = notebook
        self.is_super_admin = is_super_admin
        self.gm_username = gm_username
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="🛡️ 管理员管理")

        # 工具栏
        toolbar = tk.Frame(tab, bg=BG_DARK)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(toolbar, text="➕ 添加管理员", command=self._add_admin).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="🔄 刷新", command=self._load_admins_safe).pack(side=tk.LEFT, padx=(5, 0))

        # 状态提示
        self.count_label = tk.Label(toolbar, text="", font=(FONT_FAMILY, 9),
                                    fg=FG_MUTED, bg=BG_DARK)
        self.count_label.pack(side=tk.RIGHT, padx=5)

        # 提示
        tk.Label(toolbar, text="（仅超级管理员可操作此页面）", font=(FONT_FAMILY, 9),
                 fg=FG_MUTED, bg=BG_DARK).pack(side=tk.RIGHT)

        # Treeview
        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        columns = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
        for col_id, col_name, col_width in self.COLUMNS:
            self.tree.heading(col_id, text=col_name)
            self.tree.column(col_id, width=col_width, minwidth=col_width, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击编辑
        self.tree.bind("<Double-1>", self._on_double_click)

        # 右键菜单
        self.context_menu = tk.Menu(self.tree, tearoff=0, bg=BG_ELEVATED, fg=FG_PRIMARY,
                                     activebackground=ACCENT_PRIMARY, activeforeground="white")
        self.context_menu.add_command(label="编辑", command=self._on_double_click)
        self.context_menu.add_command(label="权限设置", command=self._on_permission_edit)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_admin)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # 保存管理员列表数据（含权限信息，用于权限编辑）
        self.admin_data_list = []

        # 初始加载
        self.notebook.after(200, self._load_admins_safe)

    def _widget_exists(self):
        """检查窗口是否还存在。"""
        try:
            return self.notebook.winfo_exists()
        except tk.TclError:
            return False

    def _load_admins_safe(self):
        """安全的加载方法，带窗口检查。"""
        if not self._widget_exists():
            return
        self._load_admins()

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _load_admins(self):
        """从服务器 API 加载管理员列表。"""
        try:
            resp = requests.get(f"{SERVER_URL}/api/gm/admins", timeout=5)
            data = resp.json()
            if not data.get("ok"):
                self.count_label.config(text="加载失败")
                return

            admins = data.get("admins", [])
            if not self._widget_exists():
                return

            # 保存完整数据
            self.admin_data_list = admins

            # 清空
            for item in self.tree.get_children():
                self.tree.delete(item)

            for a in admins:
                role_text = "超级管理员" if a.get("role") == "super_admin" else "普通管理员"
                # 超管看明文密码，普通管理员看掩码（当前页面仅超管可见，这里预留）
                password = a.get("password", "") or ""
                password_text = password if self.is_super_admin else ("●●●●" if password else "无")
                self.tree.insert("", tk.END, values=(
                    a.get("id"), a.get("username"), password_text, role_text, a.get("created_at", "")
                ))
            self.count_label.config(text=f"共 {len(admins)} 个管理员")
        except requests.ConnectionError:
            if self._widget_exists():
                self.count_label.config(text="服务器未连接")
        except Exception as e:
            if self._widget_exists():
                self.count_label.config(text=f"加载失败: {e}")

    def _get_selected_admin(self):
        """获取选中的管理员数据（从完整数据列表中取）。"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个管理员")
            return None
        item = self.tree.item(selection[0])
        values = item["values"]
        admin_id = int(values[0])
        # 从 admin_data_list 找到完整数据
        for a in self.admin_data_list:
            if a.get("id") == admin_id:
                return a
        # fallback
        return {
            "id": admin_id,
            "username": str(values[1]),
            "role": "super_admin" if "超级" in str(values[3]) else "admin",
            "permissions": None,
        }

    def _on_double_click(self, event=None):
        """双击编辑管理员基本信息。"""
        admin = self._get_selected_admin()
        if not admin:
            return
        self._edit_admin_dialog(admin)

    def _on_permission_edit(self):
        """右键菜单：编辑权限。"""
        admin = self._get_selected_admin()
        if not admin:
            return
        if admin.get("role") == "super_admin":
            messagebox.showinfo("提示", "超级管理员拥有全部权限，无需单独设置")
            return
        self._permission_dialog(admin)

    def _add_admin(self):
        """添加新管理员对话框。"""
        self._edit_admin_dialog(None)

    def _edit_admin_dialog(self, admin):
        """编辑/添加管理员基本信息对话框。"""
        is_edit = admin is not None

        win = tk.Toplevel(self.notebook)
        win.title(f"编辑管理员 - {admin['username']}" if is_edit else "添加管理员")
        win.resizable(False, False)
        win.configure(bg=BG_DARK)
        win.transient(self.notebook)
        win.grab_set()

        tk.Label(win, text=f"编辑管理员" if is_edit else "添加新管理员",
                 font=(FONT_FAMILY, 14, "bold"), fg=FG_PRIMARY, bg=BG_DARK).pack(pady=(20, 15))

        # 用户名
        tk.Label(win, text="用户名", font=(FONT_FAMILY, 9), fg=FG_SECONDARY, bg=BG_DARK).pack(anchor="w", padx=60)
        user_entry = tk.Entry(win, font=(FONT_FAMILY, 11), width=25, bg=BG_ELEVATED, fg=FG_PRIMARY,
                              insertbackground=FG_PRIMARY, relief=tk.FLAT, highlightthickness=1,
                              highlightcolor=ACCENT_PRIMARY, highlightbackground=BG_HOVER)
        user_entry.pack(padx=60, pady=(3, 10))
        if is_edit:
            user_entry.insert(0, admin["username"])
            user_entry.config(state=tk.DISABLED)

        # 密码
        tk.Label(win, text="新密码（留空不修改）" if is_edit else "密码", font=(FONT_FAMILY, 9),
                 fg=FG_SECONDARY, bg=BG_DARK).pack(anchor="w", padx=60)
        pass_entry = tk.Entry(win, font=(FONT_FAMILY, 11), width=25, bg=BG_ELEVATED, fg=FG_PRIMARY,
                              insertbackground=FG_PRIMARY, relief=tk.FLAT, highlightthickness=1,
                              highlightcolor=ACCENT_PRIMARY, highlightbackground=BG_HOVER, show="●")
        pass_entry.pack(padx=60, pady=(3, 10))

        # 角色
        tk.Label(win, text="角色", font=(FONT_FAMILY, 9), fg=FG_SECONDARY, bg=BG_DARK).pack(anchor="w", padx=60)
        role_var = tk.StringVar(value=admin["role"] if is_edit else "admin")
        role_frame = tk.Frame(win, bg=BG_DARK)
        role_frame.pack(padx=60, anchor="w", pady=(3, 15))
        tk.Radiobutton(role_frame, text="普通管理员", variable=role_var, value="admin",
                       bg=BG_DARK, fg=FG_PRIMARY, selectcolor=BG_ELEVATED,
                       activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                       font=(FONT_FAMILY, 10)).pack(side=tk.LEFT)
        tk.Radiobutton(role_frame, text="超级管理员", variable=role_var, value="super_admin",
                       bg=BG_DARK, fg=FG_PRIMARY, selectcolor=BG_ELEVATED,
                       activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                       font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(20, 0))

        def do_save():
            password = pass_entry.get().strip()
            role = role_var.get()

            if is_edit:
                # 编辑模式 - 调用 PUT API
                payload = {"role": role, "operator": self.gm_username}
                if password:
                    payload["password"] = password
                try:
                    resp = requests.put(f"{SERVER_URL}/api/gm/admins/{admin['id']}",
                                        json=payload, timeout=5)
                    data = resp.json()
                    if data.get("ok"):
                        win.destroy()
                        self._load_admins()
                    else:
                        messagebox.showerror("失败", data.get("message", "修改失败"))
                except Exception as e:
                    messagebox.showerror("请求失败", str(e))
            else:
                # 新增模式 - 调用 POST API
                username = user_entry.get().strip()
                if not username:
                    messagebox.showwarning("提示", "请输入用户名")
                    return
                if not password:
                    messagebox.showwarning("提示", "请输入密码")
                    return
                try:
                    resp = requests.post(f"{SERVER_URL}/api/gm/admins",
                                         json={"username": username, "password": password, "role": role,
                                               "operator": self.gm_username},
                                         timeout=5)
                    data = resp.json()
                    if data.get("ok"):
                        win.destroy()
                        self._load_admins()
                    else:
                        messagebox.showerror("失败", data.get("message", "创建失败"))
                except Exception as e:
                    messagebox.showerror("请求失败", str(e))

        # 按钮栏
        btn_frame = tk.Frame(win, bg=BG_DARK)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="保存", font=(FONT_FAMILY, 10, "bold"),
                  bg=BTN_PRIMARY, fg="white", relief=tk.FLAT, padx=25, pady=5,
                  command=do_save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=(FONT_FAMILY, 10),
                  bg=BG_HOVER, fg=FG_PRIMARY, relief=tk.FLAT, padx=25, pady=5,
                  command=win.destroy).pack(side=tk.LEFT, padx=5)

        # 所有控件创建完后居中显示
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _permission_dialog(self, admin):
        """权限设置对话框。"""
        from models.schema import DEFAULT_GM_PERMISSIONS
        import copy
        import json

        # 当前权限
        current_perms = admin.get("permissions") or copy.deepcopy(DEFAULT_GM_PERMISSIONS)
        tab_perms = current_perms.get("tabs", {})
        player_perms = current_perms.get("player_detail", {})

        win = tk.Toplevel(self.notebook)
        win.title(f"权限设置 - {admin['username']}")
        win.resizable(False, False)
        win.configure(bg=BG_DARK)
        win.transient(self.notebook)
        win.grab_set()

        tk.Label(win, text=f"🔐 权限设置 - {admin['username']}",
                 font=(FONT_FAMILY, 14, "bold"), fg=ACCENT_PRIMARY, bg=BG_DARK).pack(pady=(20, 15))

        # Notebook 两个区域
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # ===== 标签页1：管理界面权限 =====
        tab_perm_frame = tk.Frame(nb, bg=BG_DARK)
        nb.add(tab_perm_frame, text="  📑 管理界面  ")

        # 表头
        header = tk.Frame(tab_perm_frame, bg=BG_DARK)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(header, text="界面", font=(FONT_FAMILY, 10, "bold"), fg=FG_PRIMARY, bg=BG_DARK,
                 width=20, anchor="w").pack(side=tk.LEFT)
        for text, w in [("可编辑", 8), ("只读", 6), ("隐藏", 6)]:
            tk.Label(header, text=text, font=(FONT_FAMILY, 9), fg=FG_MUTED, bg=BG_DARK,
                     width=w, anchor="center").pack(side=tk.LEFT, padx=(15, 0))

        # 每个标签页一行
        tab_vars = {}
        for tab_key, tab_name in TAB_DEFINITIONS:
            row = tk.Frame(tab_perm_frame, bg=BG_DARK)
            row.pack(fill=tk.X, padx=10, pady=2)

            tk.Label(row, text=tab_name, font=(FONT_FAMILY, 10), fg=FG_SECONDARY, bg=BG_DARK,
                     width=20, anchor="w").pack(side=tk.LEFT)

            current_val = tab_perms.get(tab_key, "editable")
            var = tk.StringVar(value=current_val)
            tab_vars[tab_key] = var

            for val, text in [("editable", "可编辑"), ("readonly", "只读"), ("hidden", "隐藏")]:
                tk.Radiobutton(row, text=text, variable=var, value=val,
                               bg=BG_DARK, fg=FG_PRIMARY, selectcolor=BG_ELEVATED,
                               activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                               font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(15, 0))

        # 快捷操作
        shortcut_frame = tk.Frame(tab_perm_frame, bg=BG_DARK)
        shortcut_frame.pack(fill=tk.X, padx=10, pady=(15, 5))
        tk.Label(shortcut_frame, text="快捷操作：", font=(FONT_FAMILY, 9, "bold"),
                 fg=FG_MUTED, bg=BG_DARK).pack(side=tk.LEFT)

        def set_all_tabs(val):
            for v in tab_vars.values():
                v.set(val)

        tk.Button(shortcut_frame, text="全部可编辑", font=(FONT_FAMILY, 9),
                  bg=BTN_SUCCESS, fg="white", relief=tk.FLAT, padx=8, pady=2,
                  command=lambda: set_all_tabs("editable")).pack(side=tk.LEFT, padx=3)
        tk.Button(shortcut_frame, text="全部只读", font=(FONT_FAMILY, 9),
                  bg=ACCENT_WARNING, fg="white", relief=tk.FLAT, padx=8, pady=2,
                  command=lambda: set_all_tabs("readonly")).pack(side=tk.LEFT, padx=3)
        tk.Button(shortcut_frame, text="全部隐藏", font=(FONT_FAMILY, 9),
                  bg=BTN_DANGER, fg="white", relief=tk.FLAT, padx=8, pady=2,
                  command=lambda: set_all_tabs("hidden")).pack(side=tk.LEFT, padx=3)

        # ===== 标签页2：用户管理细粒度权限 =====
        player_perm_frame = tk.Frame(nb, bg=BG_DARK)
        nb.add(player_perm_frame, text="  👥 用户管理  ")

        tk.Label(player_perm_frame, text="控制用户管理对话框中各字段的只读/可编辑状态",
                 font=(FONT_FAMILY, 9), fg=FG_MUTED, bg=BG_DARK).pack(anchor="w", padx=15, pady=(10, 5))

        player_vars = {}
        for perm_key, perm_name in PLAYER_PERM_DEFINITIONS:
            row = tk.Frame(player_perm_frame, bg=BG_DARK)
            row.pack(fill=tk.X, padx=15, pady=3)

            current_val = player_perms.get(perm_key, True)
            var = tk.BooleanVar(value=bool(current_val))
            player_vars[perm_key] = var

            tk.Checkbutton(row, text=perm_name, variable=var,
                           bg=BG_DARK, fg=FG_SECONDARY, selectcolor=BG_ELEVATED,
                           activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                           font=(FONT_FAMILY, 10)).pack(anchor="w")

        # ===== 保存按钮 =====
        def do_save():
            # 构建权限
            new_perms = {
                "tabs": {k: v.get() for k, v in tab_vars.items()},
                "player_detail": {k: v.get() for k, v in player_vars.items()},
            }
            try:
                resp = requests.put(f"{SERVER_URL}/api/gm/admins/{admin['id']}",
                                    json={"permissions": new_perms, "operator": self.gm_username}, timeout=5)
                data = resp.json()
                if data.get("ok"):
                    messagebox.showinfo("成功", f"已更新 {admin['username']} 的权限")
                    win.destroy()
                    self._load_admins()
                else:
                    messagebox.showerror("失败", data.get("message", "保存失败"))
            except Exception as e:
                messagebox.showerror("请求失败", str(e))

        def do_reset():
            """重置为默认权限。"""
            for k, v in DEFAULT_GM_PERMISSIONS["tabs"].items():
                if k in tab_vars:
                    tab_vars[k].set(v)
            for k, v in DEFAULT_GM_PERMISSIONS["player_detail"].items():
                if k in player_vars:
                    player_vars[k].set(v)

        btn_frame = tk.Frame(win, bg=BG_DARK)
        btn_frame.pack(pady=(5, 15))
        tk.Button(btn_frame, text="💾 保存权限", font=(FONT_FAMILY, 10, "bold"),
                  bg=BTN_PRIMARY, fg="white", relief=tk.FLAT, padx=20, pady=5,
                  command=do_save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 恢复默认", font=(FONT_FAMILY, 10),
                  bg=BG_HOVER, fg=FG_PRIMARY, relief=tk.FLAT, padx=20, pady=5,
                  command=do_reset).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=(FONT_FAMILY, 10),
                  bg=BG_HOVER, fg=FG_PRIMARY, relief=tk.FLAT, padx=20, pady=5,
                  command=win.destroy).pack(side=tk.LEFT, padx=5)

        # 居中
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _delete_admin(self):
        """删除选中的管理员（通过 API）。"""
        admin = self._get_selected_admin()
        if not admin:
            return
        if not messagebox.askyesno("确认删除", f"确定要删除管理员【{admin['username']}】吗？"):
            return
        try:
            resp = requests.delete(f"{SERVER_URL}/api/gm/admins/{admin['id']}",
                                   json={"operator": self.gm_username}, timeout=5)
            data = resp.json()
            if data.get("ok"):
                messagebox.showinfo("成功", f"已删除管理员: {admin['username']}")
                self._load_admins()
            else:
                messagebox.showerror("失败", data.get("message", "删除失败"))
        except Exception as e:
            messagebox.showerror("请求失败", str(e))

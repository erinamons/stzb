# gm_console/__init__.py
# GM 管理控制台：tkinter 统一后台（暗色主题）
# 包含：仪表盘、武将管理、战法管理、卡包管理(含掉落)、建筑管理、数据库版本、管理员管理
import tkinter as tk
from tkinter import ttk
import threading

from theme import apply_dark_theme  # 统一主题模块

from gm_console.tabs.dashboard import DashboardTab
from gm_console.tabs.building_tab import BuildingTab
from gm_console.tabs.snapshot_tab import SnapshotTab
from gm_console.tabs.report_tab import ReportTab
from gm_console.tabs.player_tab import PlayerTab
from gm_console.tabs.admin_tab import AdminTab
from gm_console.tabs.log_tab import LogTab

# 复用 data_editor 的标签页（统一 UI 风格和功能）
from data_editor import HeroEditorTab, SkillEditorTab, PackEditorTab

SERVER_URL = "http://127.0.0.1:8000"


def _disable_all_widgets(widget):
    """递归禁用 widget 下所有可交互组件（Button、Entry），保留 Treeview 和 Label 只读可见。"""
    try:
        wtype = widget.winfo_class()
    except tk.TclError:
        return
    # 禁用按钮和输入框
    if wtype in ("Button", "TButton", "Entry", "TEntry", "TCombobox", "Checkbutton", "TCheckbutton",
                  "Radiobutton", "TRadiobutton", "Scale", "TScale", "Spinbox"):
        try:
            widget.config(state=tk.DISABLED)
        except (tk.TclError, AttributeError):
            try:
                widget.configure(state="disabled")
            except (tk.TclError, AttributeError):
                pass
    # 递归子组件（跳过 Notebook 自身，否则 tab 切换也禁了）
    if wtype not in ("TNotebook", "Notebook"):
        for child in widget.winfo_children():
            _disable_all_widgets(child)


def gm_login_dialog(parent=None):
    """GM 登录对话框，通过 HTTP API 验证（需要服务器已启动）。"""
    import requests

    dialog = tk.Toplevel(parent) if parent else tk.Tk()
    dialog.title("GM 管理后台 - 登录")
    dialog.geometry("400x340")
    dialog.resizable(False, False)
    if parent:
        dialog.transient(parent)
        dialog.grab_set()

    # 暗色主题
    dialog.configure(bg="#1e1e2a")

    # 居中
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - 400) // 2
    y = (dialog.winfo_screenheight() - 340) // 2
    dialog.geometry(f"400x340+{x}+{y}")

    result = {"ok": False, "role": None, "permissions": None, "username": ""}

    # 标题
    tk.Label(dialog, text="InfiniteBorders GM", font=("微软雅黑", 16, "bold"),
             fg="#7082ff", bg="#1e1e2a").pack(pady=(30, 5))
    tk.Label(dialog, text="管理后台登录", font=("微软雅黑", 10),
             fg="#8c919b", bg="#1e1e2a").pack(pady=(0, 20))

    # 用户名
    tk.Label(dialog, text="用户名", font=("微软雅黑", 9), fg="#b0b4c0", bg="#1e1e2a").pack(anchor="w", padx=70)
    user_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=24, bg="#282a36", fg="white",
                          insertbackground="white", relief=tk.FLAT, highlightthickness=1,
                          highlightcolor="#7082ff", highlightbackground="#373a4a")
    user_entry.pack(padx=70, pady=(3, 10))

    # 密码
    tk.Label(dialog, text="密码", font=("微软雅黑", 9), fg="#b0b4c0", bg="#1e1e2a").pack(anchor="w", padx=70)
    pass_entry = tk.Entry(dialog, font=("微软雅黑", 11), width=24, bg="#282a36", fg="white",
                          insertbackground="white", relief=tk.FLAT, highlightthickness=1,
                          highlightcolor="#7082ff", highlightbackground="#373a4a", show="●")
    pass_entry.pack(padx=70, pady=(3, 12))

    # 错误提示
    err_label = tk.Label(dialog, text="", font=("微软雅黑", 9), fg="#dc5050", bg="#1e1e2a")
    err_label.pack(pady=(0, 8))

    def do_login():
        username = user_entry.get().strip()
        password = pass_entry.get().strip()
        if not username or not password:
            err_label.config(text="请输入用户名和密码")
            return
        # 通过 HTTP API 验证
        try:
            resp = requests.post(f"{SERVER_URL}/api/gm/login",
                                 json={"username": username, "password": password},
                                 timeout=5)
            data = resp.json()
            if data.get("ok"):
                result["ok"] = True
                login_data = data.get("data", {})
                result["role"] = login_data.get("role", "admin")
                result["permissions"] = login_data.get("permissions")
                result["username"] = login_data.get("username", "")
                dialog.destroy()
            else:
                err_label.config(text=data.get("message", "登录失败"))
        except requests.ConnectionError:
            err_label.config(text="无法连接服务器，请确认服务器已启动")
        except Exception as e:
            err_label.config(text=f"请求失败: {e}")

    def on_enter(event):
        do_login()

    # 登录按钮
    login_btn = tk.Button(dialog, text="登 录", font=("微软雅黑", 12, "bold"),
                          bg="#4670e6", fg="white", activebackground="#5a82ff",
                          activeforeground="white", relief=tk.FLAT, cursor="hand2",
                          width=18, height=1, command=do_login)
    login_btn.pack(pady=8)

    pass_entry.bind("<Return>", on_enter)
    user_entry.bind("<Return>", lambda e: pass_entry.focus_set())

    user_entry.focus_set()

    # 如果是独立窗口（无 parent），关闭窗口退出程序
    def on_close():
        if parent:
            dialog.destroy()
        else:
            dialog.destroy()
            import sys as _sys
            _sys.exit()

    dialog.protocol("WM_DELETE_WINDOW", on_close)

    if not parent:
        dialog.mainloop()

    return result["ok"], result["role"], result["permissions"], result["username"]


class ServerGMConsole(tk.Tk):
    """InfiniteBorders 统一 GM 管理后台。"""

    def __init__(self, gm_role="admin", server_auto_started=False, permissions=None, gm_username=""):
        super().__init__()
        self.gm_role = gm_role  # "super_admin" 或 "admin"
        self.server_auto_started = server_auto_started  # 服务器是否由入口自动启动
        self.permissions = permissions  # 权限配置字典
        self.gm_username = gm_username  # 当前登录的管理员用户名
        self.title(f"InfiniteBorders GM 管理后台 ({'超级管理员' if gm_role == 'super_admin' else '管理员'})")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # 应用统一暗色主题
        apply_dark_theme(self)

        # Notebook 主标签页
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 超管始终拥有全部权限
        from models.schema import DEFAULT_GM_PERMISSIONS
        tab_perms = DEFAULT_GM_PERMISSIONS["tabs"] if gm_role == "super_admin" else \
                    (permissions or {}).get("tabs", DEFAULT_GM_PERMISSIONS["tabs"])

        # 创建各标签页（根据权限决定 hidden/readonly/editable）
        self.tabs = {}  # tab_name -> (tab_instance, access_level)
        # 记录 notebook 中各 tab 的创建顺序 index，用于获取实际的 tk Frame
        _tab_widget_map = {}  # tab_name -> notebook index
        _idx = 0

        if tab_perms.get("dashboard", "editable") != "hidden":
            self.dashboard_tab = DashboardTab(self.notebook, server_auto_started=server_auto_started)
            self.tabs["dashboard"] = (self.dashboard_tab, tab_perms.get("dashboard", "editable"))
            _tab_widget_map["dashboard"] = _idx; _idx += 1
            if tab_perms.get("dashboard") == "readonly":
                # 只读模式下禁用所有操作按钮
                self.dashboard_tab.btn_start.config(state=tk.DISABLED)
                self.dashboard_tab.btn_stop.config(state=tk.DISABLED)
                self.dashboard_tab.btn_restart.config(state=tk.DISABLED)
                self.dashboard_tab.btn_reset_db.config(state=tk.DISABLED)
        else:
            self.dashboard_tab = None

        if tab_perms.get("player", "editable") != "hidden":
            pd_perms = DEFAULT_GM_PERMISSIONS["player_detail"] if gm_role == "super_admin" else \
                       (permissions or {}).get("player_detail", DEFAULT_GM_PERMISSIONS["player_detail"])
            self.player_tab = PlayerTab(self.notebook, is_super_admin=(gm_role == "super_admin"),
                                        readonly=(tab_perms.get("player") == "readonly"),
                                        player_detail_perms=pd_perms,
                                        gm_username=self.gm_username)
            self.tabs["player"] = (self.player_tab, tab_perms.get("player", "editable"))
            _tab_widget_map["player"] = _idx; _idx += 1
        else:
            self.player_tab = None

        if tab_perms.get("skill", "editable") != "hidden":
            self.skill_tab = SkillEditorTab(self.notebook)
            self.tabs["skill"] = (self.skill_tab, tab_perms.get("skill", "editable"))
            _tab_widget_map["skill"] = _idx; _idx += 1
        else:
            self.skill_tab = None

        if tab_perms.get("hero", "editable") != "hidden":
            self.hero_tab = HeroEditorTab(self.notebook, skill_tab=self.skill_tab)
            self.tabs["hero"] = (self.hero_tab, tab_perms.get("hero", "editable"))
            _tab_widget_map["hero"] = _idx; _idx += 1
        else:
            self.hero_tab = None

        if tab_perms.get("pack", "editable") != "hidden":
            self.pack_tab = PackEditorTab(self.notebook)
            self.tabs["pack"] = (self.pack_tab, tab_perms.get("pack", "editable"))
            _tab_widget_map["pack"] = _idx; _idx += 1
        else:
            self.pack_tab = None

        if tab_perms.get("building", "editable") != "hidden":
            self.building_tab = BuildingTab(self.notebook)
            self.tabs["building"] = (self.building_tab, tab_perms.get("building", "editable"))
            _tab_widget_map["building"] = _idx; _idx += 1
        else:
            self.building_tab = None

        if tab_perms.get("report", "editable") != "hidden":
            self.report_tab = ReportTab(self.notebook)
            self.tabs["report"] = (self.report_tab, tab_perms.get("report", "editable"))
            _tab_widget_map["report"] = _idx; _idx += 1
        else:
            self.report_tab = None

        if tab_perms.get("snapshot", "editable") != "hidden":
            self.snapshot_tab = SnapshotTab(self.notebook)
            self.tabs["snapshot"] = (self.snapshot_tab, tab_perms.get("snapshot", "editable"))
            _tab_widget_map["snapshot"] = _idx; _idx += 1
        else:
            self.snapshot_tab = None

        # 操作日志标签页（所有管理员可见，不受权限隐藏控制）
        self.log_tab = LogTab(self.notebook)
        _tab_widget_map["log"] = _idx; _idx += 1

        # 超级管理员专属：管理员管理标签页
        if gm_role == "super_admin":
            self.admin_tab = AdminTab(self.notebook, is_super_admin=True, gm_username=self.gm_username)
            self.tabs["admin"] = (self.admin_tab, "editable")
            _tab_widget_map["admin"] = _idx; _idx += 1

        # 对 readonly 的标签页递归禁用所有按钮和输入框
        for tab_name, (tab_instance, access) in self.tabs.items():
            if access == "readonly" and tab_name in _tab_widget_map:
                nb_idx = _tab_widget_map[tab_name]
                nb_tabs = self.notebook.tabs()
                if nb_idx < len(nb_tabs):
                    # notebook.tabs() 返回字符串 ID，需转成 widget
                    actual_widget = self.notebook.nametowidget(nb_tabs[nb_idx])
                    _disable_all_widgets(actual_widget)

        # 绑定仪表盘按钮
        if self.dashboard_tab:
            self.dashboard_tab.btn_start.config(command=self.start_server)
            self.dashboard_tab.btn_stop.config(command=self.stop_server)
            self.dashboard_tab.btn_restart.config(command=self.restart_server)
            self.dashboard_tab.btn_reset_db.config(command=self.reset_database)

    def start_server(self):
        """启动服务器。"""
        from server_runner import start_server_thread
        if self.dashboard_tab:
            self.dashboard_tab.set_running()
        threading.Thread(target=start_server_thread, daemon=True).start()

    def stop_server(self):
        """停止服务器。"""
        from server_runner import stop_server
        from tkinter import messagebox
        result = messagebox.askyesno("⏹️ 停止服务器", "确定要停止服务器吗？\n所有在线玩家将被断开。")
        if not result:
            return
        if self.dashboard_tab:
            self.dashboard_tab.btn_stop.config(state=tk.DISABLED, text="停止中...")
            self.dashboard_tab.btn_restart.config(state=tk.DISABLED)
        self.update_idletasks()
        stop_server()
        if self.dashboard_tab:
            self.dashboard_tab.set_stopped()

    def restart_server(self):
        """重启服务器（停止 → 等待 → 重新启动）。"""
        from server_runner import stop_server
        from server_runner import start_server_thread
        if self.dashboard_tab:
            self.dashboard_tab.btn_stop.config(state=tk.DISABLED)
            self.dashboard_tab.btn_restart.config(state=tk.DISABLED, text="重启中...")
            self.dashboard_tab.btn_reset_db.config(state=tk.DISABLED)
        self.update_idletasks()
        stop_server()
        # 等待 uvicorn 完全退出后再启动
        self.after(2000, self._do_restart)

    def _do_restart(self):
        """重启的第二步：启动新服务器。"""
        from server_runner import start_server_thread
        if self.dashboard_tab:
            self.dashboard_tab.set_running()
        threading.Thread(target=start_server_thread, daemon=True).start()

    def reset_database(self):
        """运行时重置数据库，支持选择保留/不保留模板数据。"""
        from tkinter import messagebox

        # 先选择重置模式
        mode = messagebox.askyesnocancel(
            "🔄 重置数据库",
            "请选择重置模式：\n\n"
            "【是】= 轻量重置（保留武将/战法/卡包/建筑配置）\n"
            "       只清玩家数据和地图\n\n"
            "【否】= 全量重置（清空所有数据，包括GM配置）\n\n"
            "【取消】= 取消操作"
        )
        if mode is None:
            return  # 取消

        keep_templates = mode  # 是=轻量(保留模板)，否=全量(不保留)

        if not keep_templates:
            # 全量重置需要二次确认
            result = messagebox.askyesno(
                "⚠️ 全量重置确认",
                "全量重置将清空所有数据，包括：\n"
                "- GM 手动配置的武将模板\n"
                "- GM 手动配置的战法\n"
                "- 卡包和掉落配置\n"
                "- 建筑配置\n\n"
                "确定要全量重置吗？",
                icon="warning"
            )
            if not result:
                return

        if self.dashboard_tab:
            self.dashboard_tab.btn_reset_db.config(state=tk.DISABLED, text="重置中...")
        self.update_idletasks()

        try:
            # 1. 踢掉所有在线玩家
            from core.connection_manager import manager
            kicked = list(manager.active_connections.keys())
            manager.active_connections.clear()
            manager.online_players.clear()
            if kicked:
                print(f"[重置数据库] 已清空在线玩家列表: {kicked}")

            # 2. 调用 init_database()
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from init_db import init_database
            init_database(keep_templates=keep_templates)

            if keep_templates:
                mode_text = "轻量重置（已保留武将/战法/卡包/建筑配置）"
            else:
                mode_text = "全量重置"
                # 全量重置后需要重载建筑配置
                from models.database import SessionLocal
                _db = SessionLocal()
                try:
                    from building_configs import load_building_configs
                    load_building_configs(_db)
                except Exception as e:
                    print(f"[重置数据库] 建筑配置重载失败: {e}")
                finally:
                    _db.close()

            messagebox.showinfo("✅ 重置成功", f"数据库{mode_text}完成！\n请通知玩家重新登录。")
        except Exception as e:
            print(f"[重置数据库] 失败: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("❌ 重置失败", f"数据库重置失败：\n{e}")
        finally:
            if self.dashboard_tab:
                self.dashboard_tab.btn_reset_db.config(state=tk.NORMAL, text="⚠️ 重置数据库")

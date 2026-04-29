# gm_console/tabs/log_tab.py
# GM 操作日志标签页
# 功能：查看所有操作日志、按类型/操作人过滤、去重错误信息、导出 CSV
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from datetime import datetime

from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING,
    BTN_PRIMARY, BTN_DANGER,
    FONT_FAMILY,
)

SERVER_URL = "http://127.0.0.1:8000"

# 操作类型定义及颜色
ACTION_TYPES = {
    "create": ("新增", ACCENT_SUCCESS),
    "update": ("修改", ACCENT_PRIMARY),
    "delete": ("删除", ACCENT_DANGER),
    "error": ("错误", ACCENT_WARNING),
    "login": ("登录", "#7082ff"),
}

# 过滤用的目标类型
TARGET_TYPES = ["", "player", "hero", "skill", "pack", "building", "admin", "report"]


class LogTab:
    """GM 操作日志标签页。"""

    def __init__(self, notebook):
        self.notebook = notebook
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="📝 操作日志")

        # ===== 工具栏 =====
        toolbar = tk.Frame(tab, bg=BG_DARK)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(toolbar, text="🔄 刷新", command=self._load_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="📥 导出 CSV", command=self._export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="🗑️ 清空日志", command=self._clear_logs).pack(side=tk.LEFT, padx=(0, 5))

        self.count_label = tk.Label(toolbar, text="", font=(FONT_FAMILY, 9),
                                    fg=FG_MUTED, bg=BG_DARK)
        self.count_label.pack(side=tk.RIGHT, padx=5)

        # ===== 过滤栏 =====
        filter_frame = tk.Frame(tab, bg=BG_DARK)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(filter_frame, text="操作类型:", font=(FONT_FAMILY, 9),
                 fg=FG_SECONDARY, bg=BG_DARK).pack(side=tk.LEFT, padx=(0, 3))
        self.action_var = tk.StringVar(value="")
        action_combo = ttk.Combobox(filter_frame, textvariable=self.action_var, width=8,
                                    values=[""] + [f"{k} ({v[0]})" for k, v in ACTION_TYPES.items()],
                                    state="readonly")
        action_combo.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filter_frame, text="目标类型:", font=(FONT_FAMILY, 9),
                 fg=FG_SECONDARY, bg=BG_DARK).pack(side=tk.LEFT, padx=(0, 3))
        self.target_var = tk.StringVar(value="")
        target_combo = ttk.Combobox(filter_frame, textvariable=self.target_var, width=10,
                                    values=[""] + TARGET_TYPES, state="readonly")
        target_combo.pack(side=tk.LEFT, padx=(0, 10))

        # 去重错误开关
        self.dedup_var = tk.BooleanVar(value=False)
        tk.Checkbutton(filter_frame, text="错误去重", variable=self.dedup_var,
                       bg=BG_DARK, fg=FG_SECONDARY, selectcolor=BG_ELEVATED,
                       activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                       font=(FONT_FAMILY, 9),
                       command=self._load_logs).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Button(filter_frame, text="筛选", command=self._load_logs).pack(side=tk.LEFT, padx=(10, 0))

        # ===== 日志列表 =====
        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        columns = ("id", "timestamp", "operator", "action", "target_type", "target_id", "detail")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=25)
        headings = {"id": ("ID", 50), "timestamp": ("时间", 150), "operator": ("操作人", 90),
                     "action": ("类型", 60), "target_type": ("目标类型", 80),
                     "target_id": ("目标ID", 60), "detail": ("详情", 450)}
        for col, (heading, width) in headings.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=40, anchor="center" if col != "detail" else "w")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 统计信息
        self.stats_frame = tk.Frame(tab, bg=BG_DARK)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.stats_label = tk.Label(self.stats_frame, text="", font=(FONT_FAMILY, 9),
                                    fg=FG_MUTED, bg=BG_DARK, anchor="w")
        self.stats_label.pack(fill=tk.X)

        # 初始加载
        self.notebook.after(300, self._load_logs)

    def _widget_exists(self):
        try:
            return self.notebook.winfo_exists()
        except tk.TclError:
            return False

    def _parse_filter(self):
        """解析过滤条件的 combo 值。"""
        action = self.action_var.get()
        if action:
            action = action.split(" ")[0]  # "create (新增)" -> "create"
        target = self.target_var.get()
        return action, target

    def _load_logs(self):
        """从服务器加载日志。"""
        if not self._widget_exists():
            return
        action, target = self._parse_filter()
        try:
            params = {"limit": 500, "offset": 0}
            if action:
                params["action"] = action
            if target:
                params["target_type"] = target
            resp = requests.get(f"{SERVER_URL}/api/gm/logs", params=params, timeout=5)
            data = resp.json()
            if not data.get("ok"):
                self.count_label.config(text="加载失败")
                return

            logs = data.get("logs", [])
            total = data.get("total", 0)

            if not self._widget_exists():
                return

            # 去重错误
            if self.dedup_var.get() and action == "":
                seen_errors = set()
                deduped = []
                for l in logs:
                    if l["action"] == "error":
                        key = l["detail"][:100] if l["detail"] else ""
                        if key in seen_errors:
                            continue
                        seen_errors.add(key)
                    deduped.append(l)
                logs = deduped

            # 清空
            for item in self.tree.get_children():
                self.tree.delete(item)

            # 填充
            stats = {"create": 0, "update": 0, "delete": 0, "error": 0, "login": 0}
            for l in logs:
                act = l.get("action", "")
                stats[act] = stats.get(act, 0) + 1

                # 颜色标签
                tag = act
                if tag not in ("create", "update", "delete", "error", "login"):
                    tag = ""

                action_display = act
                if act in ACTION_TYPES:
                    action_display = ACTION_TYPES[act][0]

                self.tree.insert("", tk.END, values=(
                    l.get("id", ""),
                    l.get("timestamp", ""),
                    l.get("operator", ""),
                    action_display,
                    l.get("target_type", ""),
                    l.get("target_id", ""),
                    l.get("detail", ""),
                ), tags=(tag,))

            # 颜色配置
            self.tree.tag_configure("create", foreground=ACCENT_SUCCESS)
            self.tree.tag_configure("update", foreground=ACCENT_PRIMARY)
            self.tree.tag_configure("delete", foreground=ACCENT_DANGER)
            self.tree.tag_configure("error", foreground=ACCENT_WARNING)
            self.tree.tag_configure("login", foreground="#7082ff")

            # 统计信息
            stats_text = (f"新增 {stats['create']} | 修改 {stats['update']} | "
                          f"删除 {stats['delete']} | 错误 {stats['error']} | "
                          f"登录 {stats.get('login', 0)}")
            self.stats_label.config(text=stats_text)
            self.count_label.config(text=f"共 {total} 条日志" + (f"（去重后显示 {len(logs)} 条）" if self.dedup_var.get() else ""))

        except requests.ConnectionError:
            if self._widget_exists():
                self.count_label.config(text="服务器未连接")
        except Exception as e:
            if self._widget_exists():
                self.count_label.config(text=f"加载失败: {e}")

    def _export_csv(self):
        """导出日志为 CSV 文件。"""
        action, target = self._parse_filter()
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
                initialfile=f"gm_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            if not filepath:
                return
            # 直接下载
            params = {}
            if action:
                params["action"] = action
            if target:
                params["target_type"] = target
            resp = requests.get(f"{SERVER_URL}/api/gm/logs/export", params=params, timeout=10)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            messagebox.showinfo("导出成功", f"日志已导出至:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _clear_logs(self):
        """清空所有日志。"""
        if not messagebox.askyesno("⚠️ 清空日志", "确定要清空所有操作日志吗？\n此操作不可撤销！"):
            return
        try:
            resp = requests.post(f"{SERVER_URL}/api/gm/logs/clear", timeout=5)
            data = resp.json()
            if data.get("ok"):
                self._load_logs()
                messagebox.showinfo("成功", data.get("message", "已清空"))
            else:
                messagebox.showerror("失败", data.get("message", "清空失败"))
        except Exception as e:
            messagebox.showerror("请求失败", str(e))

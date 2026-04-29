# gm_console/tabs/dashboard.py
# 运行状态仪表盘标签页
import tkinter as tk
from tkinter import ttk

from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING,
    BTN_PRIMARY, BTN_SUCCESS, BTN_DANGER,
    BTN_SUCCESS_HOVER, BTN_DANGER_HOVER, BTN_PRIMARY_HOVER, BTN_ACCENT_HOVER,
    FONT_FAMILY,
)


class DashboardTab:
    """服务器运行状态仪表盘。"""

    def __init__(self, notebook, server_auto_started=False):
        self.notebook = notebook
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="🎮 运行状态")

        self.status_lbl = tk.Label(tab, text="当前状态: 🔴 已停止",
                                    fg=ACCENT_DANGER, bg=BG_DARK,
                                    font=(FONT_FAMILY, 14, "bold"))
        self.status_lbl.pack(pady=40)

        self.btn_start = tk.Button(
            tab, text="🚀 启动服务器",
            bg=BTN_SUCCESS, fg="white", activebackground=BTN_SUCCESS_HOVER,
            activeforeground="white",
            font=(FONT_FAMILY, 13, "bold"), width=24, height=2,
            relief="flat", cursor="hand2",
        )
        self.btn_start.pack(pady=10)

        # 按钮行：停止 + 重启
        btn_row = tk.Frame(tab, bg=BG_DARK)
        btn_row.pack(pady=(0, 10))

        self.btn_stop = tk.Button(
            btn_row, text="⏹️ 停止服务器",
            bg=ACCENT_WARNING, fg="white", activebackground="#cc7a00",
            activeforeground="white",
            font=(FONT_FAMILY, 11, "bold"), width=14, height=2,
            relief="flat", cursor="hand2",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_stop.config(state=tk.DISABLED)

        self.btn_restart = tk.Button(
            btn_row, text="🔄 重启服务器",
            bg=ACCENT_PRIMARY, fg="white", activebackground=BTN_ACCENT_HOVER,
            activeforeground="white",
            font=(FONT_FAMILY, 11, "bold"), width=14, height=2,
            relief="flat", cursor="hand2",
        )
        self.btn_restart.pack(side=tk.LEFT, padx=5)
        self.btn_restart.config(state=tk.DISABLED)

        # 重置数据库按钮
        self.btn_reset_db = tk.Button(
            tab, text="⚠️ 重置数据库",
            bg=BTN_DANGER, fg="white", activebackground=BTN_DANGER_HOVER,
            activeforeground="white",
            font=(FONT_FAMILY, 12, "bold"), width=24, height=2,
            relief="flat", cursor="hand2",
        )
        self.btn_reset_db.pack(pady=(5, 10))

        # 快捷信息
        info_frame = tk.Frame(tab, bg=BG_DARK)
        info_frame.pack(pady=20)
        tips = [
            "📌 武将管理 — 新增/编辑武将模板，配置属性和自带战法",
            "📜 战法管理 — CRUD 战法 + 节点编辑器配置效果",
            "📦 卡包管理 — 管理招募卡包的消耗和武将池",
            "🎲 卡包掉落 — 配置每个卡包的武将掉落权重",
            "🏗️ 建筑管理 — 30个建筑的基础配置和等级消耗/效果",
        ]
        for tip in tips:
            tk.Label(info_frame, text=tip, fg=FG_SECONDARY, bg=BG_DARK,
                     font=(FONT_FAMILY, 10), anchor="w").pack(fill="x", padx=40, pady=2)

        # 如果服务器由入口自动启动，仪表盘默认显示运行中
        if server_auto_started:
            self.set_running()

    def set_running(self):
        """更新状态为运行中。"""
        self.btn_start.config(state=tk.DISABLED, text="服务器运行中...", bg=BG_ELEVATED, fg=FG_MUTED)
        self.btn_stop.config(state=tk.NORMAL, bg=ACCENT_WARNING)
        self.btn_restart.config(state=tk.NORMAL)
        self.status_lbl.config(text="当前状态: 🟢 运行中 (端口: 8000)", fg=ACCENT_SUCCESS)

    def set_stopped(self):
        """更新状态为已停止。"""
        self.btn_start.config(state=tk.NORMAL, text="🚀 启动服务器", bg=BTN_SUCCESS, fg="white")
        self.btn_stop.config(state=tk.DISABLED, bg=BG_ELEVATED, fg=FG_MUTED)
        self.btn_restart.config(state=tk.DISABLED)
        self.status_lbl.config(text="当前状态: 🔴 已停止", fg=ACCENT_DANGER)

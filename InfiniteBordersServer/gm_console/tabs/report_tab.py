# gm_console/tabs/report_tab.py
# 战报管理标签页：查看所有用户的战报、筛选、查看详情、删除

import tkinter as tk
from tkinter import ttk, messagebox
import json

import requests
from theme import (
    BG_DARK, BG_ELEVATED, BG_HOVER, BG_SURFACE,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT_PRIMARY, ACCENT_SUCCESS, ACCENT_DANGER, ACCENT_WARNING,
    BTN_SUCCESS, BTN_DANGER, BTN_PRIMARY, BTN_ACCENT,
    FONT_FAMILY, FONT_MONO,
)

SERVER_URL = "http://127.0.0.1:8000"


class ReportTab:
    """战报管理标签页。"""

    def __init__(self, notebook):
        self.notebook = notebook
        self.all_reports = []       # 缓存当前列表
        self.player_map = {}        # {player_id: username}
        self._filter_player_id = None

        # 创建标签页容器
        tab = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab, text="📜 战报管理")

        # ==================== 顶部：操作按钮栏 ====================
        top_bar = tk.Frame(tab, bg=BG_DARK)
        top_bar.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(top_bar, text="📜 战报管理",
                 font=(FONT_FAMILY, 12, "bold"), fg="white", bg=BG_DARK).pack(side=tk.LEFT, padx=5)

        btn_frame = tk.Frame(top_bar, bg=BG_DARK)
        btn_frame.pack(side=tk.RIGHT)

        tk.Button(btn_frame, text="🔄 刷新", command=self._load_data,
                  bg=BTN_ACCENT, fg="white", font=(FONT_FAMILY, 9),
                  padx=10, pady=4).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🗑️ 删除选中", command=self._delete_selected,
                  bg=BTN_DANGER, fg="white", font=(FONT_FAMILY, 9, "bold"),
                  padx=10, pady=4).pack(side=tk.LEFT, padx=3)

        # ==================== 筛选栏 ====================
        filter_bar = tk.Frame(tab, bg=BG_DARK)
        filter_bar.pack(fill=tk.X, padx=5, pady=3)

        tk.Label(filter_bar, text="按玩家筛选：", fg=FG_SECONDARY, bg=BG_DARK,
                 font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=5)

        self.player_combo = ttk.Combobox(filter_bar, width=18, state="readonly",
                                         values=["全部玩家"])
        self.player_combo.set("全部玩家")
        self.player_combo.pack(side=tk.LEFT, padx=3)
        self.player_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        self.count_label = tk.Label(filter_bar, text="共 0 条战报", fg=FG_MUTED, bg=BG_DARK,
                                    font=(FONT_FAMILY, 9))
        self.count_label.pack(side=tk.RIGHT, padx=5)

        # ==================== 中部：战报列表 Treeview ====================
        tree_frame = tk.Frame(tab, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        columns = ("id", "player", "result", "coord", "attacker", "defender", "rounds", "time")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("id", text="ID")
        self.tree.heading("player", text="玩家")
        self.tree.heading("result", text="结果")
        self.tree.heading("coord", text="坐标")
        self.tree.heading("attacker", text="进攻方")
        self.tree.heading("defender", text="防守方")
        self.tree.heading("rounds", text="回合/场次")
        self.tree.heading("time", text="时间")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("player", width=80, anchor="center")
        self.tree.column("result", width=50, anchor="center")
        self.tree.column("coord", width=80, anchor="center")
        self.tree.column("attacker", width=80, anchor="center")
        self.tree.column("defender", width=80, anchor="center")
        self.tree.column("rounds", width=80, anchor="center")
        self.tree.column("time", width=150, anchor="center")

        # 滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 双击查看详情
        self.tree.bind("<Double-1>", lambda e: self._view_detail())

        # ==================== 底部：提示 ====================
        bottom = tk.Frame(tab, bg=BG_DARK)
        bottom.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(bottom, text="💡 双击战报查看详情 | Ctrl/Shift 多选后可批量删除",
                 fg=FG_MUTED, bg=BG_DARK, font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)

        # 自动加载
        self.notebook.after(100, self._load_data)

    # ==================== 数据加载 ====================

    def _load_data(self):
        """加载战报列表和玩家列表。"""
        # 检查窗口是否还存在（防止关闭后 after 回调触发报错）
        try:
            if not self.notebook.winfo_exists():
                return
        except tk.TclError:
            return
        self._load_players()
        self._load_reports()

    def _load_players(self):
        """加载玩家列表用于筛选下拉。"""
        try:
            resp = requests.get(f"{SERVER_URL}/api/players", timeout=5)
            data = resp.json()
            players = data if isinstance(data, list) else []
            self.player_map = {p["id"]: p["username"] for p in players}
            names = ["全部玩家"] + [p["username"] for p in players]
            self.player_combo["values"] = names
        except Exception as e:
            print(f"[战报Tab] 加载玩家列表失败: {e}")

    def _load_reports(self):
        """加载战报列表。"""
        try:
            params = {"page": 1, "page_size": 500}
            if self._filter_player_id:
                params["player_id"] = self._filter_player_id
            resp = requests.get(f"{SERVER_URL}/api/battle_reports", params=params, timeout=10)
            data = resp.json()
            self.all_reports = data.get("reports", [])
            total = data.get("total", 0)
            self.count_label.config(text=f"共 {total} 条战报")
            self._refresh_tree()
        except Exception:
            pass  # 服务器未连接时静默失败（如关闭窗口时）

    def _refresh_tree(self):
        """刷新 Treeview 显示。"""
        self.tree.delete(*self.tree.get_children())
        for r in self.all_reports:
            player_name = self.player_map.get(r.get("player_id"), f"P{r.get('player_id', '?')}")
            is_win = r.get("is_victory", 0) == 1
            result_text = "✅ 胜利" if is_win else "❌ 失败"
            total_battles = r.get("total_battles")
            rounds_text = f"{total_battles}场" if total_battles else f"{r.get('total_rounds', '?')}回合"
            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"],
                player_name,
                result_text,
                f"({r.get('tile_x', '?')}, {r.get('tile_y', '?')})",
                r.get("attacker_name", "?")[:8],
                r.get("defender_name", "?")[:8],
                rounds_text,
                r.get("created_at", ""),
            ))

    # ==================== 筛选 ====================

    def _on_filter_change(self, event=None):
        """玩家筛选切换。"""
        selected = self.player_combo.get()
        if selected == "全部玩家":
            self._filter_player_id = None
        else:
            # 反查 player_id
            for pid, name in self.player_map.items():
                if name == selected:
                    self._filter_player_id = pid
                    break
        self._load_reports()

    # ==================== 查看 ====================

    def _view_detail(self):
        """查看选中战报的详情。"""
        sel = self.tree.selection()
        if not sel:
            return
        report_id = int(sel[0])
        self._open_detail_window(report_id)

    def _open_detail_window(self, report_id):
        """打开战报详情弹窗（支持公式显示切换）。"""
        try:
            resp = requests.get(f"{SERVER_URL}/api/battle_reports/{report_id}", timeout=5)
            data = resp.json()
            if not data.get("ok"):
                messagebox.showwarning("提示", data.get("message", "获取战报失败"))
                return
        except Exception as e:
            messagebox.showerror("错误", f"获取战报失败: {e}")
            return

        report = data.get("report")
        if not report:
            messagebox.showinfo("提示", "该战报无详细数据")
            return

        is_victory = data.get("is_victory", 0) == 1
        player_name = self.player_map.get(data.get("player_id"), f"P{data.get('player_id', '?')}")

        # 创建弹窗
        win = tk.Toplevel(self.notebook)
        win.title(f"战报详情 #{report_id}")
        win.geometry("860x720")
        win.minsize(700, 500)

        # 顶部信息栏
        top = tk.Frame(win, bg=BG_DARK)
        top.pack(fill=tk.X, padx=10, pady=(10, 2))

        title_color = ACCENT_SUCCESS if is_victory else ACCENT_DANGER
        title_text = "大捷 ✅" if is_victory else "战败 ❌"
        tk.Label(top, text=title_text, font=(FONT_FAMILY, 14, "bold"),
                 fg=title_color, bg=BG_DARK).pack(side=tk.LEFT)

        # 公式开关状态
        show_formula = {"on": False}

        # 可滚动的文本区域（先创建，供重建函数引用）
        text_frame = tk.Frame(win, bg=BG_DARK)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(text_frame, wrap=tk.WORD, bg=BG_ELEVATED, fg=FG_PRIMARY,
                       font=(FONT_FAMILY, 9), insertbackground=FG_PRIMARY,
                       selectbackground="#384152", relief="flat", padx=10, pady=8,
                       yscrollcommand=scrollbar.set, spacing1=1, spacing3=1)
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        # 公式标签
        text.tag_configure("formula_title", font=(FONT_MONO, 8, "bold"), foreground="#e3b341")
        text.tag_configure("formula_step", font=(FONT_MONO, 8), foreground="#8b949e")

        def render_formula(formula):
            """在 text 中渲染公式详情。"""
            if not formula:
                return
            steps = formula.get("steps", [])
            if not steps:
                return
            text.insert(tk.END, f"      ┌─ {formula.get('type', '?')} 计算过程 ─\n", "formula_title")
            for step in steps:
                text.insert(tk.END, f"      │ {step}\n", "formula_step")
            text.insert(tk.END, f"      └{'─' * 40}\n", "formula_title")

        def build_content():
            """构建战报文本内容（根据 show_formula 状态决定是否包含公式）。"""
            text.config(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            show_f = show_formula["on"]

            # 配置文本标签
            text.tag_configure("header", font=(FONT_FAMILY, 11, "bold"), foreground=ACCENT_WARNING)
            text.tag_configure("section", font=(FONT_FAMILY, 10, "bold"), foreground=ACCENT_WARNING)
            text.tag_configure("round_header", font=(FONT_FAMILY, 9, "bold"), foreground=ACCENT_PRIMARY)
            text.tag_configure("damage", foreground="#ff8a8a")
            text.tag_configure("heal", foreground="#7ee787")
            text.tag_configure("control", foreground="#d2a8ff")
            text.tag_configure("status", foreground="#79c0ff")
            text.tag_configure("skill", foreground="#79c0ff")
            text.tag_configure("normal", foreground=FG_PRIMARY)
            text.tag_configure("muted", foreground=FG_MUTED)
            text.tag_configure("alive", foreground=ACCENT_SUCCESS)
            text.tag_configure("dead", foreground=ACCENT_DANGER)

            header = report.get("header", {})
            text.insert(tk.END, f"进攻方: {header.get('attacker_name', '?')}  vs  防守方: {header.get('defender_name', '?')}\n", "header")
            text.insert(tk.END, f"战斗时间: {header.get('time', '?')}  |  总回合: {header.get('total_rounds', '?')}\n", "muted")
            text.insert(tk.END, f"结果: {header.get('result_text', '?')}\n\n", "header")

            # 阵容
            text.insert(tk.END, "═══ 初始阵容 ═══\n", "section")
            for side_label, heroes_key in [("进攻方", "attacker_heroes"), ("防守方", "defender_heroes")]:
                text.insert(tk.END, f"\n【{side_label}】\n", "round_header")
                for h in report.get(heroes_key, []):
                    hp_pct = int(h["remaining_troops"] / max(h["initial_troops"], 1) * 100)
                    status = "存活" if h["is_alive"] else "阵亡"
                    tag = "alive" if h["is_alive"] else "dead"
                    text.insert(tk.END,
                                f"  {h['position']}  {h['name']}  兵力{h['initial_troops']}  "
                                f"攻{h['attack']} 防{h['defense']} 谋{h['strategy']} 速{h['speed']}  "
                                f"战法:{h.get('skill', '无')}\n", "normal")
                    text.insert(tk.END,
                                f"    → 剩余{h['remaining_troops']} ({hp_pct}%)  {status}\n", tag)
            text.insert(tk.END, "\n")

            # 指挥/被动战法
            prep = report.get("preparation", {})
            cmd_skills = prep.get("command_skills", [])
            passive_skills = prep.get("passive_skills", [])
            if cmd_skills or passive_skills:
                text.insert(tk.END, "═══ 战前战法 ═══\n", "section")
                for ps in passive_skills:
                    text.insert(tk.END, f"  [被动] {ps.get('caster', '?')} - {ps.get('skill', '?')}: {ps.get('effect', '')}\n", "status")
                for cs in cmd_skills:
                    text.insert(tk.END, f"  [指挥] {cs.get('caster', '?')} - {cs.get('skill', '?')}: {cs.get('effect', '')}\n", "status")
                text.insert(tk.END, "\n")

            # 回合详情
            for rd in report.get("rounds", []):
                rd_num = rd.get("round", 0)
                if rd_num < 0:
                    events = rd.get("events", [])
                    for ev in events:
                        if ev["type"] == "battle_break":
                            bd = ev["data"]
                            text.insert(tk.END, f"══════ 第{bd.get('battle_num', '?')}场战斗 ══════\n", "section")
                            text.insert(tk.END,
                                        f"  进攻方剩余兵力: {bd.get('attacker_troops', 0)}  "
                                        f"防守方剩余兵力: {bd.get('defender_troops', 0)}\n\n", "muted")
                    continue

                if rd_num == 0:
                    text.insert(tk.END, f"── 准备回合 ──\n", "round_header")
                else:
                    text.insert(tk.END, f"── 第{rd['round']}回合 ──\n", "round_header")

                events = rd.get("events", [])
                for ev in events:
                    ev_type = ev["type"]
                    ev_data = ev["data"]

                    if ev_type == "round_start":
                        continue
                    elif ev_type == "building_bonus":
                        buffs = ev_data.get("buffs", [])
                        if buffs:
                            buff_str = ", ".join(f"{b['attr']}+{b['value']}" for b in buffs)
                            text.insert(tk.END, f"  {ev_data.get('hero', '?')} 设施加成: {buff_str}\n", "status")
                    elif ev_type == "passive_summary":
                        for sk in ev_data.get("skills", []):
                            text.insert(tk.END, f"  [被动] {sk.get('caster', '?')} - {sk.get('skill', '?')}\n", "status")
                    elif ev_type == "command_summary":
                        for sk in ev_data.get("skills", []):
                            text.insert(tk.END, f"  [指挥] {sk.get('caster', '?')} - {sk.get('skill', '?')}\n", "status")
                    elif ev_type == "action_order":
                        order_str = " > ".join(ev_data.get("order", []))
                        text.insert(tk.END, f"  出手顺序: {order_str}\n", "muted")
                    elif ev_type == "dot_damage":
                        text.insert(tk.END,
                                    f"  {ev_data.get('target', '?')} 受到{ev_data.get('dot_type', '?')}伤害{ev_data.get('damage', 0)}点\n",
                                    "damage")
                    elif ev_type == "prepare_done":
                        text.insert(tk.END,
                                    f"  {ev_data.get('hero', '?')} 的战法【{ev_data.get('skill', '?')}】准备完成\n",
                                    "skill")
                    elif ev_type == "hero_action":
                        hero_name = ev_data.get("hero", "?")
                        actions = ev_data.get("actions", [])
                        for act in actions:
                            act_type = act.get("type", "")
                            if act_type == "active_skill":
                                text.insert(tk.END, f"  {hero_name} 发动战法【{act.get('skill', '?')}】\n", "skill")
                            elif act_type == "pending_skill":
                                text.insert(tk.END, f"  {hero_name} 释放准备完成的战法【{act.get('skill', '?')}】\n", "skill")
                            elif act_type == "start_prepare":
                                text.insert(tk.END,
                                            f"  {hero_name} 开始准备战法【{act.get('skill', '?')}】({act.get('turns', '?')}回合)\n",
                                            "muted")
                            elif act_type == "hesitation":
                                text.insert(tk.END, f"  {hero_name} 犹豫，无法发动【{act.get('skill', '?')}】\n", "muted")
                            elif act_type == "preparing":
                                text.insert(tk.END, f"  {hero_name} 战法【{act.get('skill', '?')}】准备中\n", "muted")
                            elif act_type == "active_fail":
                                text.insert(tk.END, f"  {hero_name} 发动【{act.get('skill', '?')}】失败\n", "muted")
                            elif act_type == "normal_attack":
                                remaining_str = f" (兵:{act.get('target_remaining', '?')})" if act.get('target_remaining') is not None else ""
                                text.insert(tk.END,
                                            f"  {hero_name} 对【{act.get('target', '?')}】普攻，造成{act.get('damage', 0)}伤害{remaining_str}\n",
                                            "damage")
                                if show_f and act.get("formula"):
                                    render_formula(act["formula"])
                            elif act_type == "no_target":
                                text.insert(tk.END, f"  {hero_name} 无有效攻击目标\n", "muted")
                    elif ev_type == "skill_effect":
                        eff = ev_data
                        eff_type = eff.get("effect_type", "")
                        if eff_type == "damage":
                            remaining_str = f" (兵:{eff.get('target_remaining', '?')})" if eff.get('target_remaining') is not None else ""
                            text.insert(tk.END,
                                        f"    → 对【{eff.get('target', '?')}】造成{eff.get('damage', 0)}伤害"
                                        f"({eff.get('damage_type', '?')}){remaining_str}\n", "damage")
                            if show_f and eff.get("formula"):
                                render_formula(eff["formula"])
                        elif eff_type == "heal":
                            remaining_str = f" (兵:{eff.get('target_remaining', '?')})" if eff.get('target_remaining') is not None else ""
                            text.insert(tk.END,
                                        f"    → 恢复【{eff.get('target', '?')}】{eff.get('amount', 0)}兵力{remaining_str}\n", "heal")
                            if show_f and eff.get("formula"):
                                render_formula(eff["formula"])
                        elif eff_type == "control":
                            text.insert(tk.END,
                                        f"    → {eff.get('target', '?')} 陷入{eff.get('control_type', '?')}状态"
                                        f"，持续{eff.get('duration', '?')}\n", "control")
                        elif eff_type == "status":
                            dur_text = eff.get('duration', '')
                            dur_str = f"，持续{dur_text}" if dur_text else ""
                            text.insert(tk.END,
                                        f"    → {eff.get('target', '?')} 获得{eff.get('status_type', '?')}状态{dur_str}\n",
                                        "status")
                        elif eff_type == "modify_attr":
                            remaining_str = f" → {eff.get('current_value', '?')}" if eff.get('current_value') is not None else ""
                            text.insert(tk.END,
                                        f"    → {eff.get('target', '?')} 的{eff.get('attr_name', '?')} "
                                        f"{eff.get('modify_type', '?')}{eff.get('value', '?')}"
                                        f"{remaining_str}"
                                        f"，持续{eff.get('duration', '?')}\n", "status")
                text.insert(tk.END, "\n")

            # 战损统计
            text.insert(tk.END, "═══ 战损统计 ═══\n", "section")
            for side_label, heroes_key in [("进攻方", "attacker_heroes"), ("防守方", "defender_heroes")]:
                heroes = report.get(heroes_key, [])
                if not heroes:
                    continue
                total_init = sum(h["initial_troops"] for h in heroes)
                total_remain = sum(h["remaining_troops"] for h in heroes)
                text.insert(tk.END,
                            f"\n【{side_label}】总兵: {total_init} → {total_remain} (损{total_init - total_remain})\n",
                            "round_header")
                for h in heroes:
                    loss = h["initial_troops"] - h["remaining_troops"]
                    cast_info = ""
                    if h.get("skill_cast_count"):
                        casts = " ".join(f"{sk}x{ct}" for sk, ct in h["skill_cast_count"].items())
                        cast_info = f"  战法: {casts}" if casts else ""
                    status = "存活" if h["is_alive"] else "阵亡"
                    tag = "alive" if h["is_alive"] else "dead"
                    text.insert(tk.END,
                                f"  {h['position']} {h['name']}: 初始{h['initial_troops']} "
                                f"剩{h['remaining_troops']} 损{loss} [{status}]{cast_info}\n", tag)

            text.config(state=tk.DISABLED)

        def toggle_formula():
            show_formula["on"] = not show_formula["on"]
            if show_formula["on"]:
                btn_formula.config(text="🔢 隐藏公式", bg=BTN_ACCENT)
            else:
                btn_formula.config(text="🔢 显示公式", bg=BTN_PRIMARY)
            build_content()

        # 按钮区（放在 text_frame 之上、info 之下）
        btn_bar = tk.Frame(win, bg=BG_DARK)
        btn_bar.pack(fill=tk.X, padx=10, pady=2)

        btn_formula = tk.Button(btn_bar, text="🔢 显示公式", command=toggle_formula,
                                bg=BTN_PRIMARY, fg=FG_PRIMARY,
                                font=(FONT_FAMILY, 9), padx=10, pady=3, relief="flat")
        btn_formula.pack(side=tk.LEFT, padx=3)

        # 复制编号按钮
        def copy_id():
            win.clipboard_clear()
            win.clipboard_append(str(report_id))

        tk.Button(btn_bar, text=f"📋 复制ID: {report_id}", command=copy_id,
                  bg=BG_ELEVATED, fg=FG_SECONDARY,
                  font=(FONT_FAMILY, 9), padx=8, pady=3, relief="flat").pack(side=tk.LEFT, padx=3)

        info_text = (f"玩家: {player_name}  |  坐标: ({data.get('tile_x')}, {data.get('tile_y')})  |  "
                     f"时间: {data.get('created_at', '')}")
        tk.Label(win, text=info_text, fg=FG_SECONDARY, bg=BG_DARK,
                 font=(FONT_FAMILY, 9)).pack(anchor="w", padx=10)

        # 首次构建内容（默认不带公式）
        build_content()

    # ==================== 删除 ====================

    def _delete_selected(self):
        """删除选中的战报（支持多选）。"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择要删除的战报")
            return

        count = len(sel)
        if not messagebox.askyesno("确认删除",
                                    f"确定要删除选中的 {count} 条战报吗？\n此操作不可撤销。"):
            return

        success = 0
        failed = 0
        for item_id in sel:
            try:
                resp = requests.delete(f"{SERVER_URL}/api/battle_reports",
                                       params={"report_id": int(item_id)}, timeout=5)
                result = resp.json()
                if result.get("ok"):
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        messagebox.showinfo("删除完成",
                            f"成功删除 {success} 条战报" +
                            (f"，{failed} 条失败" if failed else ""))
        self._load_reports()

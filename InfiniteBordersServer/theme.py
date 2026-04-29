# theme.py
# InfiniteBorders 统一暗色主题模块
# 所有 tkinter UI 文件应从此模块导入主题常量和 apply_dark_theme 函数
#
# 用法：
#   from theme import apply_dark_theme, BG_DARK, FG_PRIMARY, ...
#   apply_dark_theme(root)
#
# 按钮语义色快捷函数：
#   from theme import btn_success, btn_danger, btn_accent, btn_muted
#   tk.Button(parent, text="保存", **btn_success())

import tkinter as tk
from tkinter import ttk

# ============================================================
# 统一字体
# ============================================================
FONT_FAMILY = "微软雅黑"
FONT_MONO = "Consolas"

# ============================================================
# 主背景层次
# ============================================================
BG_DARK = "#1a1d23"          # 最深层（窗口底色）
BG_SURFACE = "#21252b"       # 次层表面（面板/卡片）
BG_ELEVATED = "#2c313a"      # 凸起控件（输入框/Treeview）
BG_HOVER = "#363c47"         # hover 状态

# ============================================================
# 功能色
# ============================================================
ACCENT_PRIMARY = "#5c7cfa"   # 主强调色（蓝）
ACCENT_SUCCESS = "#3fb950"   # 成功/保存（绿）
ACCENT_DANGER = "#f85149"    # 危险/删除（红）
ACCENT_WARNING = "#d29922"   # 警告（金橙）
ACCENT_INFO = "#58a6ff"      # 信息（亮蓝）

# ============================================================
# 文字色
# ============================================================
FG_PRIMARY = "#e6edf3"       # 主要文字
FG_SECONDARY = "#8b949e"     # 次要文字/提示
FG_MUTED = "#6e7681"         # 弱化文字
FG_SELECTED = "#c9dce8"      # 选中项文字
BG_SELECTED = "#384152"      # 选中项背景

# ============================================================
# 按钮梯度
# ============================================================
BTN_PRIMARY = "#2f4054"
BTN_PRIMARY_HOVER = "#3d5166"
BTN_ACCENT = "#1f6feb"
BTN_ACCENT_HOVER = "#388bfd"
BTN_SUCCESS = "#238636"
BTN_SUCCESS_HOVER = "#2ea043"
BTN_DANGER = "#da3633"
BTN_DANGER_HOVER = "#f85149"

# ============================================================
# 边框与分割线
# ============================================================
BORDER_SUBTLE = "#30363d"     # 微妙边框
BORDER_MUTED = "#21262d"      # 更弱的边框

# ============================================================
# Treeview 斑马纹
# ============================================================
BG_EVEN_ROW = BG_ELEVATED     # 偶数行
BG_ODD_ROW = "#2a2f38"        # 奇数行


# ============================================================
# 按钮语义色快捷函数（用于 tk.Button 的 ** 解包）
# ============================================================
def btn_success(text="保存"):
    """保存/确认按钮样式。"""
    return dict(
        bg=BTN_SUCCESS, fg="white",
        activebackground=BTN_SUCCESS_HOVER, activeforeground="white",
        relief="flat", borderwidth=0,
        font=(FONT_FAMILY, 9, "bold"), padx=15, pady=5,
    )

def btn_danger(text="删除"):
    """删除/危险按钮样式。"""
    return dict(
        bg=BTN_DANGER, fg="white",
        activebackground=BTN_DANGER_HOVER, activeforeground="white",
        relief="flat", borderwidth=0,
        font=(FONT_FAMILY, 9, "bold"), padx=12, pady=5,
    )

def btn_accent(text="新增"):
    """新增/强调按钮样式。"""
    return dict(
        bg=BTN_ACCENT, fg="white",
        activebackground=BTN_ACCENT_HOVER, activeforeground="white",
        relief="flat", borderwidth=0,
        font=(FONT_FAMILY, 9, "bold"), padx=12, pady=5,
    )

def btn_primary(text="操作"):
    """普通操作按钮样式（刷新/恢复/导出等）。"""
    return dict(
        bg=BTN_PRIMARY, fg=FG_PRIMARY,
        activebackground=BTN_PRIMARY_HOVER, activeforeground=FG_PRIMARY,
        relief="flat", borderwidth=0,
        font=(FONT_FAMILY, 9), padx=12, pady=5,
    )

def btn_muted(text="取消"):
    """取消/次要按钮样式。"""
    return dict(
        bg=BG_ELEVATED, fg=FG_SECONDARY,
        activebackground=BG_HOVER, activeforeground=FG_PRIMARY,
        relief="flat", borderwidth=0,
        font=(FONT_FAMILY, 9), padx=12, pady=5,
    )


def apply_dark_theme(root):
    """应用精致的蓝调暗色主题（设计升级版）。

    Args:
        root: tk.Tk 或 tk.Toplevel 实例
    """
    root.configure(bg=BG_DARK)

    style = ttk.Style()
    style.theme_use("clam")

    # ---- 全局基础样式 ----
    style.configure(".",
                    background=BG_DARK, foreground=FG_PRIMARY,
                    fieldbackground=BG_ELEVATED, borderwidth=1,
                    insertcolor=FG_PRIMARY,
                    selectbackground=BG_SELECTED, selectforeground=FG_PRIMARY,
                    relief="flat")

    # ---- Frame / 容器 ----
    style.configure("TFrame", background=BG_DARK)
    style.configure("TFrame.Card", background=BG_SURFACE)
    style.configure("TFrame.Elevated", background=BG_ELEVATED)

    # ---- Label ----
    style.configure("TLabel", background=BG_DARK, foreground=FG_PRIMARY,
                    font=(FONT_FAMILY, 9))
    style.configure("TLabel.Header", background=BG_DARK, foreground=FG_PRIMARY,
                    font=(FONT_FAMILY, 12, "bold"))
    style.configure("TLabel.SubHeader", background=BG_DARK, foreground=ACCENT_PRIMARY,
                    font=(FONT_FAMILY, 10, "bold"))
    style.configure("TLabel.Muted", background=BG_DARK, foreground=FG_SECONDARY,
                    font=(FONT_FAMILY, 9))
    style.configure("TLabelframe", background=BG_SURFACE, foreground=FG_PRIMARY,
                    font=(FONT_FAMILY, 9, "bold"), borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=BG_SURFACE, foreground=ACCENT_PRIMARY,
                    font=(FONT_FAMILY, 9, "bold"))

    # ---- Button（精致扁平 + hover）----
    style.configure("TButton",
                    background=BTN_PRIMARY, foreground=FG_PRIMARY,
                    font=(FONT_FAMILY, 9), padding=(12, 5),
                    borderwidth=0, relief="flat",
                    focuscolor="none")
    style.map("TButton",
              background=[("active", BTN_PRIMARY_HOVER), ("pressed", BG_ELEVATED), ("disabled", "#222")],
              foreground=[("disabled", FG_MUTED)])

    style.configure("Accent.TButton",
                    background=BTN_ACCENT, foreground="white",
                    font=(FONT_FAMILY, 9, "bold"), padding=(14, 6),
                    borderwidth=0, relief="flat")
    style.map("Accent.TButton",
              background=[("active", BTN_ACCENT_HOVER), ("pressed", "#1a5cad")])

    style.configure("Success.TButton",
                    background=BTN_SUCCESS, foreground="white",
                    font=(FONT_FAMILY, 9, "bold"), padding=(14, 6),
                    borderwidth=0, relief="flat")
    style.map("Success.TButton",
              background=[("active", BTN_SUCCESS_HOVER), ("pressed", "#196c2e")])

    style.configure("Danger.TButton",
                    background=BTN_DANGER, foreground="white",
                    font=(FONT_FAMILY, 9, "bold"), padding=(14, 6),
                    borderwidth=0, relief="flat")
    style.map("Danger.TButton",
              background=[("active", BTN_DANGER_HOVER), ("pressed", "#b91c1c")])

    style.configure("Muted.TButton",
                    background=BG_ELEVATED, foreground=FG_SECONDARY,
                    font=(FONT_FAMILY, 9), padding=(12, 5),
                    borderwidth=0, relief="flat")
    style.map("Muted.TButton",
              background=[("active", BG_HOVER)])

    # ---- Entry 输入框 ----
    style.configure("TEntry",
                    fieldbackground=BG_ELEVATED, foreground=FG_PRIMARY,
                    insertcolor=FG_PRIMARY,
                    selectbackground=BG_SELECTED, selectforeground=FG_PRIMARY,
                    borderwidth=1, relief="solid",
                    insertwidth=1)
    style.map("TEntry",
              fieldbackground=[("focus", "#3d4451"), ("!focus", BG_ELEVATED)],
              bordercolor=[("focus", ACCENT_PRIMARY), ("!focus", BORDER_SUBTLE)])

    # ---- Notebook 标签页 ----
    style.configure("TNotebook",
                    background=BG_DARK, borderwidth=0,
                    tabposition="n")
    style.map("TNotebook", background=[("selected", BG_DARK)])
    style.configure("TNotebook.Tab",
                    background=BG_SURFACE, foreground=FG_SECONDARY,
                    padding=[18, 8], font=(FONT_FAMILY, 10),
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", BG_DARK)],
              foreground=[("selected", FG_PRIMARY), ("!selected", FG_SECONDARY)])

    # 标签页布局
    style.layout("TNotebook.Tab", [
        ('Notebook.tab', {'sticky': 'nswe', 'children': [
            ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
                ('Notebook.label', {'side': 'top', 'sticky': ''})
            ]})
        ]})
    ])

    # ---- Treeview 表格 ----
    style.configure("Treeview",
                    background=BG_ELEVATED, foreground=FG_PRIMARY,
                    fieldbackground=BG_ELEVATED,
                    font=(FONT_FAMILY, 9), rowheight=28,
                    borderwidth=0, relief="flat")
    style.configure("Treeview.Heading",
                    font=(FONT_FAMILY, 9, "bold"),
                    background=BG_SURFACE, foreground=FG_SECONDARY,
                    borderwidth=1, relief="flat",
                    padding=(10, 6))
    style.map("Treeview.Heading",
              background=[("active", BTN_PRIMARY_HOVER)])
    style.map("Treeview",
              background=[("selected", BG_SELECTED), ("!selected", BG_ELEVATED)],
              foreground=[("selected", FG_SELECTED), ("!selected", FG_PRIMARY)])

    # ---- Combobox 下拉框 ----
    style.configure("TCombobox",
                    fieldbackground=BG_ELEVATED, foreground=FG_PRIMARY,
                    background=BTN_PRIMARY,
                    selectbackground=BG_SELECTED, selectforeground=FG_PRIMARY,
                    arrowcolor=FG_SECONDARY, borderwidth=1,
                    relief="solid", padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_ELEVATED), ("!readonly", BG_ELEVATED)],
              foreground=[("readonly", FG_PRIMARY)],
              bordercolor=[("focus", ACCENT_PRIMARY), ("!focus", BORDER_SUBTLE)])

    # ---- Scrollbar ----
    style.configure("TScrollbar",
                    background=BG_HOVER, troughcolor=BG_DARK,
                    arrowcolor=FG_SECONDARY, borderwidth=0,
                    width=10, relief="flat")
    style.map("TScrollbar",
              background=[("active", FG_MUTED), ("pressed", ACCENT_PRIMARY)])

    # ---- Separator 分割线 ----
    style.configure("TSeparator", background=BORDER_SUBTLE)

    # ---- PanedWindow 分割面板 ----
    style.configure("TPanedWindow", background=BORDER_SUBTLE, sashwidth=4)
    style.map("TPanedWindow", background=[("active", ACCENT_PRIMARY)])

    # ---- 兼容旧 Treeview 类名 ----
    style.configure("Treeview", foreground=FG_PRIMARY)

    # ============================================================
    #   动态修复：Treeview 行颜色 + Toplevel 弹窗
    # ============================================================

    def _fix_treeview_fg(event):
        """Treeview 映射时设置行颜色（斑马纹）。"""
        try:
            tv = event.widget
            if hasattr(tv, 'tag_configure'):
                tv.tag_configure("even_row", background=BG_EVEN_ROW, foreground=FG_PRIMARY)
                tv.tag_configure("odd_row", background=BG_ODD_ROW, foreground=FG_PRIMARY)
                tv.tag_configure("selected", background=BG_SELECTED, foreground=FG_SELECTED)
                children = tv.get_children()
                for idx, item in enumerate(children):
                    tag = "even_row" if idx % 2 == 0 else "odd_row"
                    tv.item(item, tags=(tag,))
        except Exception:
            pass

    root.bind_class("Treeview", "<Map>", _fix_treeview_fg)

    def _refresh_all_treeviews():
        """延迟刷新所有 Treeview 斑马纹。"""
        try:
            def _walk(widget):
                if isinstance(widget, ttk.Treeview):
                    widget.tag_configure("even_row", background=BG_EVEN_ROW, foreground=FG_PRIMARY)
                    widget.tag_configure("odd_row", background=BG_ODD_ROW, foreground=FG_PRIMARY)
                    widget.tag_configure("selected", background=BG_SELECTED, foreground=FG_SELECTED)
                    for idx, item in enumerate(widget.get_children()):
                        tag = "even_row" if idx % 2 == 0 else "odd_row"
                        widget.item(item, tags=(tag,))
                for child in widget.winfo_children():
                    _walk(child)
            _walk(root)
        except Exception:
            pass

    root.after(100, _refresh_all_treeviews)

    def _bind_toplevel(widget):
        """新弹窗打开时自动应用暗色。"""
        try:
            if isinstance(widget, tk.Toplevel):
                widget.configure(bg=BG_DARK)
                _apply_to_children(widget)
        except Exception:
            pass

    def _apply_to_children(parent):
        """递归遍历所有子控件，应用精致暗色。"""
        for child in parent.winfo_children():
            try:
                wtype = child.winfo_class()

                if wtype in ("Frame", "Labelframe"):
                    if isinstance(parent, tk.PanedWindow):
                        child.configure(bg=BG_SURFACE)
                    elif wtype == "Labelframe":
                        child.configure(bg=BG_SURFACE, fg=FG_PRIMARY,
                                       borderwidth=1, highlightthickness=0)
                    else:
                        child.configure(bg=BG_DARK)

                elif wtype == "Label":
                    try:
                        txt = child.cget("text") or ""
                        fnt = child.cget("font")
                        is_bold = "bold" in str(fnt).lower()
                        if is_bold and len(txt) > 3:
                            child.configure(bg=BG_DARK, fg=ACCENT_PRIMARY)
                        elif any(kw in txt for kw in ("←", "请从", "选择", "当前:")):
                            child.configure(bg=BG_DARK, fg=FG_MUTED)
                        else:
                            child.configure(bg=BG_DARK, fg=FG_PRIMARY)
                    except Exception:
                        child.configure(bg=BG_DARK, fg=FG_PRIMARY)

                elif wtype == "Entry":
                    child.configure(
                        bg=BG_ELEVATED, fg=FG_PRIMARY,
                        insertbackground=FG_PRIMARY,
                        selectbackground=BG_SELECTED, selectforeground=FG_PRIMARY,
                        relief="solid", borderwidth=1,
                        highlightthickness=0)

                elif wtype == "Text":
                    child.configure(
                        bg=BG_ELEVATED, fg=FG_PRIMARY,
                        insertbackground=FG_PRIMARY,
                        selectbackground=BG_SELECTED, selectforeground=FG_PRIMARY,
                        relief="flat", borderwidth=0)

                elif wtype == "Button":
                    try:
                        btn_text = child.cget("text") or ""
                        if any(kw in btn_text for kw in ("保存", "上传", "连接", "创建", "确认")):
                            child.configure(bg=BTN_SUCCESS, fg="white",
                                           activebackground=BTN_SUCCESS_HOVER, activeforeground="white",
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9, "bold"),
                                           padx=15, pady=5)
                        elif "删除" in btn_text or "重置" in btn_text:
                            child.configure(bg=BTN_DANGER, fg="white",
                                           activebackground=BTN_DANGER_HOVER, activeforeground="white",
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9, "bold"),
                                           padx=12, pady=5)
                        elif any(kw in btn_text for kw in ("取消", "断开", "关闭")):
                            child.configure(bg=BG_ELEVATED, fg=FG_SECONDARY,
                                           activebackground=BG_HOVER, activeforeground=FG_PRIMARY,
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9),
                                           padx=12, pady=5)
                        elif any(kw in btn_text for kw in ("新增", "添加", "+", "➕")):
                            child.configure(bg=BTN_ACCENT, fg="white",
                                           activebackground=BTN_ACCENT_HOVER, activeforeground="white",
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9, "bold"),
                                           padx=12, pady=5)
                        elif any(kw in btn_text for kw in ("刷新", "恢复", "导出", "重新加载")):
                            child.configure(bg=BTN_PRIMARY, fg=FG_PRIMARY,
                                           activebackground=BTN_PRIMARY_HOVER, activeforeground=FG_PRIMARY,
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9),
                                           padx=12, pady=5)
                        else:
                            child.configure(bg=BTN_PRIMARY, fg=FG_PRIMARY,
                                           activebackground=BTN_PRIMARY_HOVER, activeforeground=FG_PRIMARY,
                                           relief="flat", borderwidth=0,
                                           font=(FONT_FAMILY, 9),
                                           padx=10, pady=4)
                    except Exception:
                        child.configure(bg=BTN_PRIMARY, fg=FG_PRIMARY,
                                       activebackground=BTN_PRIMARY_HOVER,
                                       relief="flat")

                elif wtype == "Listbox":
                    child.configure(
                        bg=BG_ELEVATED, fg=FG_PRIMARY,
                        selectbackground=BG_SELECTED, selectforeground=FG_SELECTED,
                        relief="flat", borderwidth=0,
                        highlightthickness=0, highlightbackground=BG_DARK)

                elif wtype == "Checkbutton":
                    child.configure(
                        bg=BG_DARK, fg=FG_PRIMARY,
                        activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                        selectcolor=BG_ELEVATED,
                        relief="flat", borderwidth=0,
                        font=(FONT_FAMILY, 9))

                elif wtype == "Radiobutton":
                    child.configure(
                        bg=BG_DARK, fg=FG_PRIMARY,
                        activebackground=BG_DARK, activeforeground=FG_PRIMARY,
                        selectcolor=BG_ELEVATED,
                        relief="flat", borderwidth=0,
                        font=(FONT_FAMILY, 9))

                elif wtype == "PanedWindow":
                    child.configure(background=BORDER_SUBTLE, sashwidth=4,
                                    sashrelief="flat", bg=BORDER_SUBTLE)

                _apply_to_children(child)
            except (tk.TclError, Exception):
                pass

    root.bind_class("Toplevel", "<Map>", lambda e: _bind_toplevel(e.widget))

    # 立即对根窗口本身应用暗色
    _apply_to_children(root)

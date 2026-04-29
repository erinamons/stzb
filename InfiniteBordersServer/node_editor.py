import json
import copy
import time
import tkinter as tk
from tkinter import ttk, messagebox, Menu
import math

from theme import BG_DARK, BG_SURFACE, BG_ELEVATED, BG_HOVER, BG_SELECTED, FG_PRIMARY, FONT_FAMILY

class Node:
    # 节点类型 -> 颜色分类（用于卡片化外观）
    CATEGORY_COLORS = {
        "event":     {"header": "#c98a1e", "body": "#3d3425", "border": "#e6a82a", "header_text": "#ffffff"},   # 金色 - 事件入口
        "flow":      {"header": "#2d7d9a", "body": "#252d35", "border": "#3aa0c4", "header_text": "#ffffff"},   # 蓝色 - 流程控制
        "target":    {"header": "#2a9a4a", "body": "#25352d", "border": "#38c45a", "header_text": "#ffffff"},   # 绿色 - 目标选择
        "effect":    {"header": "#9a2d3a", "body": "#352528", "border": "#c43a4a", "header_text": "#ffffff"},   # 红色 - 效果节点
        "condition": {"header": "#8a4aca", "body": "#2d2535", "border": "#a86ae0", "header_text": "#ffffff"},   # 紫色 - 条件判断
        "value":     {"header": "#ca6a2a", "body": "#352e25", "border": "#e08840", "header_text": "#ffffff"},   # 橙色 - 数值操作
    }

    TYPE_CATEGORIES = {
        "Event_OnCast": "event", "Event_BeginCombat": "event", "Event_OnPursuit": "event", "Event_BeginRound": "event",
        "Sequence": "flow", "Branch": "flow", "ForEach": "flow", "Delay": "flow",
        "DoOnce": "flow", "Gate": "flow", "FlipFlop": "flow",
        "GetEnemy": "target", "GetAlly": "target", "GetSelf": "target",
        "ApplyDamage": "effect", "ApplyHeal": "effect", "ApplyControl": "effect",
        "ApplyStatus": "effect", "ModifyAttribute": "effect", "ApplyDamageBuff": "effect", "RemoveDebuff": "effect",
        "CompareAttribute": "condition", "CompareHPPercent": "condition", "HasStatus": "condition",
        "RandomChance": "condition", "CompareValues": "condition",
        "GetAttributeValue": "value", "CalculateDamage": "value", "SetVariable": "value",
        "GetVariable": "value", "AddToVariable": "value",
    }

    TYPE_ICONS = {
        "Event_OnCast": "\u2694\ufe0f", "Event_BeginCombat": "\u2694\ufe0f", "Event_OnPursuit": "\ud83d\udde1", "Event_BeginRound": "\ud83c\udf05",
        "Sequence": "\ud83d\udd04", "Branch": "\u27a4", "ForEach": "\ud83d\udd22", "Delay": "\u23f3",
        "DoOnce": "\u2713", "Gate": "\ud83d\udd12", "FlipFlop": "\u21c4",
        "GetEnemy": "\ud83d\udc80", "GetAlly": "\ud83d\udc81", "GetSelf": "\ud83d\udc64",
        "ApplyDamage": "\ud83d\udde1", "ApplyHeal": "\u2764\ufe0f", "ApplyControl": "\ud83d\udeab",
        "ApplyStatus": "\u2b50", "ModifyAttribute": "\ud83d\udcc8", "ApplyDamageBuff": "\ud83d\udcaa", "RemoveDebuff": "\u2728",
        "CompareAttribute": "\u2264", "CompareHPPercent": "\U0001f6e1", "HasStatus": "\ud83d\udd0d",
        "RandomChance": "\ud83c\udfb2", "CompareValues": "\u2264",
        "GetAttributeValue": "\ud83d\udccb", "CalculateDamage": "\ud83d\udde1", "SetVariable": "\ud83d\udddd",
        "GetVariable": "\ud83d\udccb", "AddToVariable": "\uff0b",
    }

    def __init__(self, node_id, node_type, x=100, y=100, params=None, inputs=None, outputs=None):
        self.id = node_id
        self.type = node_type
        self.x = x
        self.y = y
        self.params = params or {}
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.width = 190
        self.header_height = 30          # 标题栏高度
        # body_height = 参数预览区(20) + pin区域(max_pins * 24) + 底部padding(12)
        self.body_height = 20 + max(0, max(len(self.inputs), len(self.outputs)) * 24) + 12
        self.height = self.header_height + self.body_height
        self.selected = False
        self.radius = 6                  # 圆角半径

    @property
    def category(self):
        return self.TYPE_CATEGORIES.get(self.type, "flow")

    @property
    def colors(self):
        return self.CATEGORY_COLORS.get(self.category, self.CATEGORY_COLORS["flow"])

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.type, "")

    def update_port_positions(self):
        body_top = self.y + self.header_height
        # pin 从参数预览区（20px）下方开始，留 4px 间距
        pin_start_y = 24
        for i, pin in enumerate(self.inputs):
            y_offset = pin_start_y + i * 24
            pin['pos'] = (self.x, body_top + y_offset)
        for i, pin in enumerate(self.outputs):
            y_offset = pin_start_y + i * 24
            pin['pos'] = (self.x + self.width, body_top + y_offset)

    def contains(self, x, y):
        """判断相对坐标(x,y)是否在节点内（以节点左上角为原点）。"""
        return 0 <= x <= self.width and 0 <= y <= self.height
    def hit_pin(self, x, y):
        """判断相对坐标(x,y)是否命中pin（以节点左上角为原点）。"""
        body_top = self.header_height
        pin_start_y = 24  # 与 update_port_positions 一致：参数预览区下方
        for i, pin in enumerate(self.inputs):
            py = body_top + pin_start_y + i * 24
            px = 0
            if abs(x - px) < 12 and abs(y - py) < 12:
                return pin['id'], pin['type'], False
        for i, pin in enumerate(self.outputs):
            py = body_top + pin_start_y + i * 24
            px = self.width
            if abs(x - px) < 12 and abs(y - py) < 12:
                return pin['id'], pin['type'], True
        return None

class Connection:
    def __init__(self, from_node, from_pin_id, to_node, to_pin_id):
        self.from_node = from_node
        self.from_pin_id = from_pin_id
        self.to_node = to_node
        self.to_pin_id = to_pin_id

    def points(self):
        from_pin = next(p for p in self.from_node.outputs if p['id'] == self.from_pin_id)
        to_pin = next(p for p in self.to_node.inputs if p['id'] == self.to_pin_id)
        return from_pin['pos'], to_pin['pos']


class _NodeEditorBase:
    """节点编辑器核心逻辑（不继承任何 tkinter Widget）。

    所有业务方法（save/load/redraw/事件处理等）都定义在这里。
    子类 _NodeEditorToplevel 和 _NodeEditorFrame 分别继承 tk.Toplevel 和 tk.Frame，
    并在 __init__ 中调用 _init_core() 完成初始化。
    """

    NODE_TEMPLATES = {
        # 事件节点
        "Event_OnCast": {
            "title": "成功发动战法时",
            "inputs": [],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {},
            "doc": "成功发动战法时触发（主动战法入口）。"
        },
        "Event_BeginCombat": {
            "title": "战斗开始",
            "inputs": [],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {},
            "doc": "战斗开始时触发（指挥战法入口）。"
        },
        # 流程控制
        "Sequence": {
            "title": "顺序执行",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out_0", "name": "输出0", "type": "exec"},
                {"id": "exec_out_1", "name": "输出1", "type": "exec"},
                {"id": "exec_out_2", "name": "输出2", "type": "exec"}
            ],
            "params": {
                "输出数量": {
                    "type": "number",
                    "default": 3,
                    "min": 1,
                    "max": 10,
                    "description": "顺序执行引脚的数量"
                }
            },
            "doc": "依次执行所有输出引脚。"
        },
        "Delay": {
            "title": "延迟",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "延迟回合": {
                    "type": "number",
                    "default": 2,
                    "min": 1,
                    "max": 10,
                    "description": "延迟多少回合后执行后续节点"
                }
            },
            "doc": "延迟指定回合数后再执行后续节点。"
        },
        # 目标选择
        "GetEnemy": {
            "title": "获取敌军",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "params": {
                "数量": {
                    "type": "choice",
                    "options": ["全体", "群体(2)", "单体"],
                    "default": "全体",
                    "description": "选择目标的个数"
                },
                "状态过滤": {
                    "type": "multi_choice",
                    "options": ["混乱", "犹豫", "怯战", "暴走", "禁疗"],
                    "default": [],
                    "description": "只选择拥有这些状态的敌人（多选，不选=无过滤）"
                }
            },
            "doc": "获取敌军目标。"
        },
        "GetAlly": {
            "title": "获取友军",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "params": {
                "数量": {
                    "type": "choice",
                    "options": ["全体", "群体(2)", "单体"],
                    "default": "群体(2)",
                    "description": "选择目标的个数"
                },
                "状态过滤": {
                    "type": "multi_choice",
                    "options": ["混乱", "犹豫", "怯战", "暴走", "禁疗"],
                    "default": [],
                    "description": "只选择拥有这些状态的友军（多选，不选=无过滤）"
                }
            },
            "doc": "获取友军目标。"
        },
        "GetSelf": {
            "title": "获取自身",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "params": {},
            "doc": "获取自身作为目标。"
        },
        # 效果节点
        "ApplyDamage": {
            "title": "造成伤害",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "伤害类型": {
                    "type": "choice",
                    "options": ["攻击", "策略"],
                    "default": "攻击",
                    "description": "伤害类型：攻击伤害受攻击属性影响，策略伤害受谋略属性影响"
                },
                "伤害率": {
                    "type": "number",
                    "default": 100.0,
                    "min": 0,
                    "step": 1,
                    "description": "战法倍率，例如100表示100%的伤害率"
                },
                "受影响属性": {
                    "type": "choice",
                    "options": ["无", "攻击", "防御", "谋略", "速度"],
                    "default": "无",
                    "description": "伤害率额外受该属性影响：实际伤害率 = 伤害率 × 施法者属性/100"
                }
            },
            "doc": "对目标造成指定类型的伤害。"
        },
        "ApplyHeal": {
            "title": "恢复兵力",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "恢复率": {
                    "type": "number",
                    "default": 100.0,
                    "min": 0,
                    "description": "治疗倍率，例如100表示100%的恢复率"
                },
                "受影响属性": {
                    "type": "choice",
                    "options": ["无", "攻击", "防御", "谋略", "速度"],
                    "default": "无",
                    "description": "恢复率额外受该属性影响：实际恢复率 = 恢复率 × 施法者属性/100"
                }
            },
            "doc": "恢复目标兵力。"
        },
        "ApplyControl": {
            "title": "施加控制",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "控制类型": {
                    "type": "choice",
                    "options": ["混乱", "犹豫", "怯战", "暴走", "禁疗"],
                    "default": "混乱",
                    "description": "控制效果类型"
                },
                "持续时间": {
                    "type": "choice",
                    "options": ["1回合", "2回合", "3回合", "本场战斗"],
                    "default": "2回合",
                    "description": "控制持续时长"
                }
            },
            "doc": "对目标施加控制效果。"
        },
        "ApplyStatus": {
            "title": "施加增益",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "增益类型": {
                    "type": "choice",
                    "options": ["先手", "连击", "洞察", "规避", "援护"],
                    "default": "规避",
                    "description": "增益状态类型"
                },
                "持续时间": {
                    "type": "choice",
                    "options": ["1回合", "2回合", "3回合", "本场战斗"],
                    "default": "2回合",
                    "description": "增益持续时长"
                },
                "规避次数": {
                    "type": "number",
                    "default": 2,
                    "min": 1,
                    "max": 10,
                    "description": "当增益为“规避”时，可免疫的次数"
                }
            },
            "doc": "为目标施加增益状态。"
        },
        "ModifyAttribute": {
            "title": "修改属性",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "属性类型": {
                    "type": "multi_choice",
                    "options": ["攻击", "防御", "谋略", "速度", "攻击距离"],
                    "default": ["攻击", "防御", "谋略", "速度"],
                    "description": "要修改的属性（可多选，攻击距离独立于其他属性）"
                },
                "修改方式": {
                    "type": "choice",
                    "options": ["增加", "减少"],
                    "default": "增加",
                    "description": "增加或减少"
                },
                "计算方式": {
                    "type": "choice",
                    "options": ["固定值", "百分比"],
                    "default": "百分比",
                    "description": "固定值=直接加减数值，百分比=按基础属性百分比计算"
                },
                "修改值": {
                    "type": "number",
                    "default": 15.0,
                    "min": -100,
                    "max": 100,
                    "step": 0.1,
                    "description": "修改的数值（百分比时为如15表示15%，固定值时为具体点数）"
                },
                "持续时间": {
                    "type": "choice",
                    "options": ["1回合", "2回合", "3回合", "本场战斗"],
                    "default": "2回合",
                    "description": "属性修正持续时长"
                },
                "受影响属性": {
                    "type": "choice",
                    "options": ["无", "攻击", "防御", "谋略", "速度"],
                    "default": "无",
                    "description": "修改值额外受该属性影响：实际修改值 = 修改值 × 施法者属性/100（仅百分比模式生效）"
                }
            },
            "doc": "增加或减少目标的属性（支持固定值和百分比模式，支持多属性）。"
        },
        "ApplyDamageBuff": {
            "title": "伤害增减",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "Buff类型": {
                    "type": "choice",
                    "options": ["增伤", "减伤", "受创提升", "被伤害减少"],
                    "default": "增伤",
                    "description": "增伤=自身造成伤害提高; 减伤=自身受到伤害降低; 受创提升=目标受到伤害提高; 被伤害减少=目标受到伤害降低"
                },
                "数值": {
                    "type": "number",
                    "default": 120,
                    "min": -200,
                    "max": 500,
                    "step": 1,
                    "description": "增减百分比数值（如120表示120%）"
                },
                "持续时间": {
                    "type": "choice",
                    "options": ["1回合", "2回合", "3回合", "本场战斗"],
                    "default": "本场战斗",
                    "description": "效果持续时长"
                }
            },
            "doc": "为目标添加/减少伤害增减类buff（精确百分比增伤/减伤）。"
        },
        "RemoveDebuff": {
            "title": "移除负面",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "targets", "name": "目标", "type": "data", "data_type": "target_array"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "移除类型": {
                    "type": "multi_choice",
                    "options": ["混乱", "犹豫", "怯战", "暴走", "禁疗", "全部负面"],
                    "default": ["全部负面"],
                    "description": "要移除的负面状态（多选，\"全部负面\"=清除所有控制+持续伤害）"
                }
            },
            "doc": "移除目标身上的负面效果（控制状态和持续伤害）。"
        },

        # ---- 以下为补充节点类型（执行器已支持但编辑器缺失） ----

        # 流程控制补充
        "Branch": {
            "title": "条件分支",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "condition", "name": "条件", "type": "data", "data_type": "bool"}
            ],
            "outputs": [
                {"id": "exec_true", "name": "为真", "type": "exec"},
                {"id": "exec_false", "name": "为假", "type": "exec"}
            ],
            "params": {},
            "doc": "根据条件值走不同的分支（true/false）。"
        },
        "ForEach": {
            "title": "循环遍历",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "array", "name": "数组", "type": "data", "data_type": "array"}
            ],
            "outputs": [
                {"id": "exec_loop", "name": "循环体", "type": "exec"},
                {"id": "exec_out", "name": "完成", "type": "exec"}
            ],
            "params": {
                "循环变量名": {
                    "type": "string",
                    "default": "item",
                    "description": "当前循环元素的变量名"
                }
            },
            "doc": "遍历数组中的每个元素，执行循环体。"
        },
        "DoOnce": {
            "title": "仅执行一次",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {},
            "doc": "该节点在整个战斗中只执行一次。"
        },
        "Gate": {
            "title": "开关门",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "open", "name": "打开", "type": "data", "data_type": "bool"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "初始状态": {
                    "type": "choice",
                    "options": ["打开", "关闭"],
                    "default": "打开",
                    "description": "初始是否允许通过"
                }
            },
            "doc": "门打开时允许执行后续节点，关闭时跳过。"
        },
        "FlipFlop": {
            "title": "交替触发",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_a", "name": "输出A", "type": "exec"},
                {"id": "exec_b", "name": "输出B", "type": "exec"}
            ],
            "params": {},
            "doc": "每次执行时交替走A和B两个分支。"
        },

        # 条件判断补充
        "CompareAttribute": {
            "title": "比较属性",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "target", "name": "目标", "type": "data", "data_type": "target"},
                {"id": "compare_value", "name": "比较值", "type": "data", "data_type": "number"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "result", "name": "结果", "type": "data", "data_type": "bool"}
            ],
            "params": {
                "比较属性": {
                    "type": "choice",
                    "options": ["攻击", "防御", "谋略", "速度"],
                    "default": "攻击",
                    "description": "要比较的属性"
                },
                "比较类型": {
                    "type": "choice",
                    "options": ["大于", "小于", "等于", "大于等于", "小于等于"],
                    "default": "大于",
                    "description": "比较方式"
                }
            },
            "doc": "比较目标武将的某个属性与给定值，输出布尔结果。"
        },
        "CompareHPPercent": {
            "title": "比较兵力百分比",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "target", "name": "目标", "type": "data", "data_type": "target"},
                {"id": "threshold", "name": "阈值", "type": "data", "data_type": "number"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "result", "name": "结果", "type": "data", "data_type": "bool"}
            ],
            "params": {
                "比较类型": {
                    "type": "choice",
                    "options": ["大于", "小于", "等于", "大于等于", "小于等于"],
                    "default": "大于",
                    "description": "比较方式"
                }
            },
            "doc": "比较目标当前兵力百分比与给定阈值。"
        },
        "HasStatus": {
            "title": "检查状态",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "target", "name": "目标", "type": "data", "data_type": "target"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "result", "name": "结果", "type": "data", "data_type": "bool"}
            ],
            "params": {
                "状态类型": {
                    "type": "choice",
                    "options": ["混乱", "犹豫", "怯战", "暴走", "禁疗"],
                    "default": "混乱",
                    "description": "要检查的状态"
                }
            },
            "doc": "检查目标是否拥有指定状态。"
        },
        "RandomChance": {
            "title": "随机概率",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "result", "name": "结果", "type": "data", "data_type": "bool"}
            ],
            "params": {
                "几率": {
                    "type": "number",
                    "default": 0.3,
                    "min": 0,
                    "max": 1,
                    "step": 0.05,
                    "description": "触发概率（0.0-1.0）"
                }
            },
            "doc": "按照给定概率输出随机布尔结果。"
        },
        "CompareValues": {
            "title": "比较数值",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "a", "name": "值A", "type": "data", "data_type": "number"},
                {"id": "b", "name": "值B", "type": "data", "data_type": "number"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "result", "name": "结果", "type": "data", "data_type": "bool"}
            ],
            "params": {
                "比较类型": {
                    "type": "choice",
                    "options": ["大于", "小于", "等于", "大于等于", "小于等于"],
                    "default": "大于",
                    "description": "比较方式"
                }
            },
            "doc": "比较两个数值，输出布尔结果。"
        },

        # 数值操作补充
        "GetAttributeValue": {
            "title": "获取属性值",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "target", "name": "目标", "type": "data", "data_type": "target"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "value", "name": "属性值", "type": "data", "data_type": "number"}
            ],
            "params": {
                "属性": {
                    "type": "choice",
                    "options": ["攻击", "防御", "谋略", "速度"],
                    "default": "谋略",
                    "description": "要获取的属性"
                }
            },
            "doc": "获取目标武将的属性值。"
        },
        "CalculateDamage": {
            "title": "计算伤害",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "attribute", "name": "属性值", "type": "data", "data_type": "number"}
            ],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "damage", "name": "伤害", "type": "data", "data_type": "number"}
            ],
            "params": {
                "基础伤害率": {
                    "type": "number",
                    "default": 100,
                    "description": "基础伤害率百分比"
                },
                "属性系数": {
                    "type": "number",
                    "default": 1,
                    "description": "属性对伤害的影响系数"
                }
            },
            "doc": "根据属性值计算最终伤害数值。"
        },
        "SetVariable": {
            "title": "设置变量",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "value", "name": "值", "type": "data", "data_type": "any"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "变量名": {
                    "type": "string",
                    "default": "var",
                    "description": "变量名"
                }
            },
            "doc": "在武将的变量字典中设置一个变量。"
        },
        "GetVariable": {
            "title": "获取变量",
            "inputs": [{"id": "exec_in", "name": "执行", "type": "exec"}],
            "outputs": [
                {"id": "exec_out", "name": "执行", "type": "exec"},
                {"id": "value", "name": "值", "type": "data", "data_type": "any"}
            ],
            "params": {
                "变量名": {
                    "type": "string",
                    "default": "var",
                    "description": "要获取的变量名"
                }
            },
            "doc": "获取武将变量字典中的变量值。"
        },
        "AddToVariable": {
            "title": "变量累加",
            "inputs": [
                {"id": "exec_in", "name": "执行", "type": "exec"},
                {"id": "increment", "name": "增量", "type": "data", "data_type": "number"}
            ],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {
                "变量名": {
                    "type": "string",
                    "default": "var",
                    "description": "要累加的变量名"
                }
            },
            "doc": "将增量值累加到指定变量上。"
        },

        # 追击事件
        "Event_OnPursuit": {
            "title": "普通攻击后",
            "inputs": [],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {},
            "doc": "普通攻击后触发（追击战法入口）。"
        },

        # 被动事件（回合开始时自动触发，不受控制效果影响）
        "Event_BeginRound": {
            "title": "回合开始时",
            "inputs": [],
            "outputs": [{"id": "exec_out", "name": "执行", "type": "exec"}],
            "params": {},
            "doc": "每回合开始时自动触发（被动战法入口）。不受控制效果影响，优先级高于指挥战法。"
        },
    }

    # 类级别防重复：防止同一 skill 创建多个 Toplevel
    _active_instances = {}  # skill_name -> instance

    def __new__(cls, parent, skill_name, effect_config=None, embed_mode=False):
        """工厂方法：根据 embed_mode 返回正确的子类实例。"""
        if cls is not _NodeEditorBase:
            return super(_NodeEditorBase, cls).__new__(cls)

        # === 单例保护：同名 skill 只允许一个 Toplevel 窗口 ===
        if not embed_mode and skill_name in _NodeEditorBase._active_instances:
            old = _NodeEditorBase._active_instances[skill_name]
            try:
                if old.winfo_exists():
                    old.lift()  # 已存在就提升到前台，不重复创建
                    return old
            except Exception:
                pass
            del _NodeEditorBase._active_instances[skill_name]

        if embed_mode:
            return _NodeEditorFrame(parent, skill_name, effect_config)
        else:
            return _NodeEditorToplevel(parent, skill_name, effect_config)

    # ---- 核心初始化逻辑（由两个子类在 __init__ 中调用）----

    def _init_core(self, skill_name, effect_config=None):
        """共享的初始化逻辑：状态变量、快捷键绑定、画布、面板、节点库。"""
        self.skill_name = skill_name
        self.nodes = []
        self.connections = []
        self.next_node_id = 1
        self.drag_node = None
        self.drag_offset = (0, 0)
        self.temp_line = None
        self.drag_pin = None
        self.selected_node = None
        self.selected_connection = None
        self.selected_nodes = set()
        self.rubber_band_start = None
        self.rubber_band_rect = None
        self.clipboard = None

        # ---- 画布缩放/平移状态 ----
        self.canvas_zoom = 1.0          # 缩放比例（1.0=100%）
        self.canvas_pan_x = 0            # 平移偏移 X（世界坐标原点在画布上的像素位置）
        self.canvas_pan_y = 0            # 平移偏移 Y
        self._pan_dragging = False       # 是否正在中键/空格拖拽平移
        self._pan_start = (0, 0)         # 平拖拽起始画布坐标
        self._pan_start_offset = (0, 0)  # 平移起始时的 pan 偏移
        self._space_pressed = False      # 空格键是否按下（用于空格+左键平移）
        self._redraw_pending = False     # 延迟重绘待处理标志
        self._last_pan_dx = 0            # 上一帧平移增量 X（用于 canvas.move）
        self._last_pan_dy = 0            # 上一帧平移增量 Y
        self._zoom_dirty = False         # 标记缩放已改变，需要精细重绘
        self._last_dclick_time = 0        # 上次双击时间戳（防重复弹窗）

        # 通用快捷键
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-e>", lambda e: self.export_json())
        self.bind("<Control-i>", lambda e: self.import_json())
        self.bind("<Control-a>", self.select_all)
        self.bind("<Delete>", self.delete_selected_nodes)
        self.bind("<Control-c>", lambda e: self.copy_selected())
        self.bind("<Control-v>", lambda e: self.paste_clipboard())

        # 画布
        self.canvas = tk.Canvas(self, bg=BG_ELEVATED, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 画布鼠标事件绑定
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # 缩放（滚轮）
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)          # Windows
        self.canvas.bind("<Button-4>", lambda e: self._on_zoom(e, 1.1))   # Linux 上滚
        self.canvas.bind("<Button-5>", lambda e: self._on_zoom(e, 1/1.1)) # Linux 下滚

        # 平移（中键拖拽 / 空格+左键拖拽）
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        # 键盘事件：空格按下/释放（用于空格+左键平移模式）
        self.bind("<space>", self._on_space_press)
        self.bind("<KeyRelease-space>", self._on_space_release)

        # 缩放快捷键：Ctrl+= 放大，Ctrl+- 缩小，Ctrl+0 重置
        self.bind("<Control-equal>", lambda e: self._set_zoom(self.canvas_zoom * 1.2))
        self.bind("<Control-minus>", lambda e: self._set_zoom(self.canvas_zoom / 1.2))
        self.bind("<Control-0>", lambda e: self._reset_view())

        # 右侧面板 - 节点库（Treeview可折叠 + 彩色预览）
        self.panel = tk.Frame(self, width=280, bg=BG_SURFACE)
        self.panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0), pady=0)
        # 面板标题
        hdr = tk.Frame(self.panel, bg=BG_DARK)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="\U0001f4e6  \u8282\u70b9\u5e93", font=(FONT_FAMILY, 11, "bold"),
                 fg="#ddd", bg=BG_DARK, padx=12, pady=8).pack(side=tk.LEFT)
        # 搜索框
        sf = tk.Frame(self.panel, bg=BG_SURFACE)
        sf.pack(fill=tk.X, padx=6, pady=4)
        self.search_var = tk.StringVar()
        se = tk.Entry(sf, textvariable=self.search_var,
                      font=(FONT_FAMILY, 9), bg=BG_DARK,
                      fg="#ccc", insertbackground="white",
                      relief="flat", insertwidth=1)
        se.pack(fill=tk.X, ipady=4)
        self.search_var.trace_add("write", lambda *_: self._rebuild_node_tree())
        # Treeview
        tree_frame = tk.Frame(self.panel, bg=BG_SURFACE)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        style = ttk.Style()
        style.configure("NodeLib.Treeview",
                        background=BG_SURFACE, foreground=FG_PRIMARY,
                        fieldbackground=BG_SURFACE,
                        rowheight=26, font=(FONT_FAMILY, 9))
        style.configure("NodeLib.Treeview.Heading", background=BG_DARK)
        style.map("NodeLib.Treeview",
                  background=[("selected", BG_SELECTED)],
                  foreground=[("selected", "#000")])
        cols = ("type", "color_tag")
        self.node_tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings",
                                       style="NodeLib.Treeview",
                                       selectmode="browse")
        self.node_tree.column("#0", width=160, minwidth=120)
        self.node_tree.column("type", width=0, stretch=False, minwidth=0)
        self.node_tree.column("color_tag", width=16, stretch=False, minwidth=16)
        self.node_tree.heading("#0", text="")
        self.node_tree.heading("type", text="")
        self.node_tree.heading("color_tag", text="")
        ts = ttk.Scrollbar(tree_frame, orient="vertical", command=self.node_tree.yview)
        self.node_tree.configure(yscrollcommand=ts.set)
        self.node_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ts.pack(side=tk.RIGHT, fill=tk.Y)
        self.node_tree.bind("<Double-Button-1>", self._on_node_tree_double_click)
        # 分类图标
        self.cat_icons = {
            "\u4e8b\u4ef6": "\u26a1\ufe0f",
            "\u6d41\u7a0b\u63a7\u5236": "\u23f3\ufe0f",
            "\u76ee\u6807\u9009\u62e9": "\ud83d\udc41\ufe0f",
            "\u6548\u679c": "\ud83d\udca5",
            "\u6761\u4ef6\u5224\u65ad": "\u2733\ufe0f",
            "\u6570\u503c\u64cd\u4f5c": "\ud83d\udcc9",
        }
        # 分类定义（必须在 _rebuild_node_tree 之前）
        self.categories = {
            "事件": ["Event_OnCast", "Event_BeginCombat", "Event_OnPursuit", "Event_BeginRound"],
            "流程控制": ["Sequence", "Branch", "ForEach", "Delay", "DoOnce", "Gate", "FlipFlop"],
            "目标选择": ["GetEnemy", "GetAlly", "GetSelf"],
            "效果": ["ApplyDamage", "ApplyHeal", "ApplyControl", "ApplyStatus", "ModifyAttribute", "ApplyDamageBuff", "RemoveDebuff"],
            "条件判断": ["CompareAttribute", "CompareHPPercent", "HasStatus", "RandomChance", "CompareValues"],
            "数值操作": ["GetAttributeValue", "CalculateDamage", "SetVariable", "GetVariable", "AddToVariable"],
        }
        self._rebuild_node_tree()
        self.update_node_list()

        # 右键菜单
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="✂  复制节点", command=self.copy_selected)
        self.context_menu.add_command(label="📋 粘贴节点", command=self.paste_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑  删除选中", command=self.delete_selected_nodes)
        self.context_menu.add_command(label="🧹 清空画布", command=self.clear_canvas)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="💾 保存", command=self.save)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔍 重置视图", command=self._reset_view)

        # 初始加载配置
        if effect_config is not None:
            self.load_from_config(effect_config)

    # ==================== 文件操作 ====================

    def save(self):
        """保存当前节点图配置到 effect_config JSON。"""
        config = self.export_config()
        if not self._validate_graph(config, show_warning=True):
            return
        # 通过回调保存（支持两种回调格式）
        saved = False
        if hasattr(self, 'on_save') and self.on_save:
            self.on_save(config)
            saved = True
        if hasattr(self, 'on_node_editor_save') and self.on_node_editor_save:
            self.on_node_editor_save(self.skill_name, config)
            saved = True
        if not saved:
            # 无回调时打印到控制台
            print(f"[{self.skill_name}] 节点图已保存: {json.dumps(config, ensure_ascii=False, indent=2)}")

    def export_config(self):
        """导出当前画布为 effect_config 字典。"""
        nodes_data = []
        for n in self.nodes:
            nodes_data.append({
                "id": n.id,
                "type": n.type,
                "x": n.x,
                "y": n.y,
                "params": dict(n.params),
            })
        links_data = []
        for c in self.connections:
            links_data.append({
                "from_node": c.from_node.id,
                "from_pin": c.from_pin_id,
                "to_node": c.to_node.id,
                "to_pin": c.to_pin_id,
            })
        return {"nodes": nodes_data, "links": links_data}

    def load_from_config(self, effect_config):
        """从 effect_config JSON 加载节点图。"""
        if not effect_config or (not effect_config.get("nodes") and not effect_config.get("links")):
            self.create_default_graph()
            return

        self.nodes.clear()
        self.connections.clear()

        def _make_pins(pin_list):
            """统一 pin 格式（兼容字符串和字典两种输入）。"""
            pins = []
            for p in pin_list:
                if isinstance(p, dict):
                    pins.append({
                        "id": p["id"],
                        "name": p.get("name", p["id"]),
                        "type": p.get("type", "data"),
                    })
                else:
                    ptype = "exec" if p == "exec" else "data"
                    pins.append({"id": p, "name": p, "type": ptype})
            return pins

        node_map = {}
        for nd in effect_config.get("nodes", []):
            tmpl = self.NODE_TEMPLATES.get(nd["type"], {})
            n = Node(
                node_id=nd["id"],
                node_type=nd["type"],
                x=nd.get("x", 100),
                y=nd.get("y", 100),
                params=dict(nd.get("params", {})),
                inputs=_make_pins(tmpl.get("inputs", [])),
                outputs=_make_pins(tmpl.get("outputs", [])),
            )
            self.nodes.append(n)
            node_map[n.id] = n
            if n.id >= self.next_node_id:
                self.next_node_id = n.id + 1

        for ld in effect_config.get("links", []):
            from_id = ld.get("from_node") or ld.get("from")
            to_id = ld.get("to_node") or ld.get("to")
            from_pin = ld.get("from_pin") or ld.get("from_output")
            to_pin = ld.get("to_pin") or ld.get("to_input")
            fn = node_map.get(from_id)
            tn = node_map.get(to_id)
            if fn and tn:
                self.connections.append(Connection(fn, from_pin, tn, to_pin))

        for n in self.nodes:
            n.update_port_positions()

        # 自动选中第一个事件节点
        event_nodes = [n for n in self.nodes if n.type.startswith("Event_")]
        if event_nodes:
            self.selected_node = event_nodes[0]

        self.redraw()

    def create_default_graph(self):
        """创建默认空图：一个 Event_OnCast 入口节点。"""
        self.nodes.clear()
        self.connections.clear()
        tmpl = self.NODE_TEMPLATES.get("Event_OnCast", {})
        def _make_pins(pin_list):
            pins = []
            for p in pin_list:
                if isinstance(p, dict):
                    pins.append({"id": p["id"], "name": p.get("name", p["id"]), "type": p.get("type", "data")})
                else:
                    pins.append({"id": p, "name": p, "type": "exec" if p == "exec" else "data"})
            return pins
        event = Node(node_id=self.next_node_id, node_type="Event_OnCast", x=150, y=300,
                     inputs=_make_pins(tmpl.get("inputs", [])),
                     outputs=_make_pins(tmpl.get("outputs", [])))
        self.next_node_id += 1
        event.update_port_positions()
        self.nodes.append(event)
        self.selected_node = event
        self.redraw()

    def _validate_graph(self, config=None, show_warning=True):
        """验证节点图的合法性。"""
        if config is None:
            config = self.export_config()

        nodes = config.get("nodes", [])
        links = config.get("links", [])

        # 检查是否有入口节点
        has_entry = any(n["type"].startswith("Event_") for n in nodes)
        if not nodes:
            if show_warning:
                self._show_warning("画布为空\n请至少添加一个入口节点（事件类）")
            return False
        if not has_entry:
            if show_warning:
                self._show_warning("缺少入口节点\n请添加一个事件类节点（如「战斗发动」）作为起点")
            return False

        # 检查孤立节点
        linked_from = set(l.get("from_node") or l.get("from") for l in links)
        linked_to = set(l.get("to_node") or l.get("to") for l in links)
        all_linked = linked_from | linked_to
        isolated = [n["id"] for n in nodes if n["id"] not in all_linked and not n["type"].startswith("Event_")]
        if isolated and show_warning:
            names = ", ".join(
                next((self.NODE_TEMPLATES[n["type"]]["title"] for n in nodes if n["id"] == nid), str(nid))
                for nid in isolated[:5]
            )
            result = messagebox.askyesno(
                "验证警告",
                f"以下节点未连接任何连线，可能影响执行：\n{names}\n\n是否仍要保存？",
            )
            return result

        return True

    def _show_warning(self, message):
        """显示警告弹窗。"""
        try:
            from tkinter import messagebox as mb
            mb.showwarning("提示", message)
        except Exception:
            print(f"[WARNING] {message}")

    def import_json(self):
        """从JSON字符串导入节点图。"""
        from tkinter import simpledialog
        json_str = simpledialog.askstring("导入JSON", "粘贴effect_config JSON:")
        if not json_str:
            return
        import json
        try:
            config = json.loads(json_str)
            self.load_from_config(config)
        except json.JSONDecodeError as e:
            self._show_warning(f"JSON 解析错误:\n{e}")

    def export_json(self):
        """导出节点图为JSON字符串到剪贴板。"""
        import json
        config = self.export_config()
        json_str = json.dumps(config, ensure_ascii=False, indent=2)
        self.clipboard_clear()
        self.clipboard_append(json_str)
        self._show_warning("已复制到剪贴板")

    def clear_canvas(self):
        """清空画布。"""
        if messagebox.askyesno("确认清空", "确定要清空所有节点和连线吗？"):
            self.create_default_graph()

    # ==================== 节点库 ====================

    def update_node_list(self):
        """刷新右侧节点库列表（已改为 Treeview，由 _rebuild_node_tree 处理）。"""
        pass

    def _rebuild_node_tree(self):
        """重建节点库Treeview（带分类折叠 + 彩色标签）。"""
        if not hasattr(self, 'node_tree'):
            return
        expanded = set(self.node_tree.get_children())
        selected = self.node_tree.selection()
        search = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""
        for item in self.node_tree.get_children():
            self.node_tree.delete(item)

        cat_colors = {
            "事件": Node.CATEGORY_COLORS["event"]["header"],
            "流程控制": Node.CATEGORY_COLORS["flow"]["header"],
            "目标选择": Node.CATEGORY_COLORS["target"]["header"],
            "效果": Node.CATEGORY_COLORS["effect"]["header"],
            "条件判断": Node.CATEGORY_COLORS["condition"]["header"],
            "数值操作": Node.CATEGORY_COLORS["value"]["header"],
        }
        for cat_name, types in self.categories.items():
            icon = self.cat_icons.get(cat_name, "")
            color = cat_colors.get(cat_name, "#666")
            count_visible = sum(1 for t in types if not search or search in t.lower()
                                or search in self.NODE_TEMPLATES[t]["title"].lower())
            if search and count_visible == 0:
                continue
            cat_item = self.node_tree.insert("", "end", text=f" {icon} {cat_name} ({count_visible})", open=(not search), values=(cat_name, ""))
            tag = f"cat_{cat_name}"
            self.node_tree.tag_configure(tag, foreground=color)
            self.node_tree.item(cat_item, tags=(tag,))
            for nt in types:
                tmpl = self.NODE_TEMPLATES.get(nt)
                if not tmpl:
                    continue
                title = tmpl["title"]
                if search and search not in nt.lower() and search not in title.lower():
                    continue
                child_tag = f"node_{nt}"
                self.node_tree.tag_configure(child_tag, foreground="#cccccc")
                self.node_tree.insert(cat_item, "end", text=f"  {title}", values=(nt, ""), tags=(child_tag,))

        for item in self.node_tree.get_children():
            if item in expanded:
                self.node_tree.item(item, open=True)

    def _on_node_tree_double_click(self, event):
        """双击节点库项 → 在画布上添加节点。"""
        selection = self.node_tree.selection()
        if not selection:
            return
        item = selection[0]
        values = self.node_tree.item(item, "values")
        parent_id = self.node_tree.parent(item)
        if parent_id:  # 子项（具体节点类型）
            node_type = values[0] if values else None
            if node_type and node_type in self.NODE_TEMPLATES:
                cx = 200 + len([n for n in self.nodes if n.x < 400]) * 30
                cy = 150 + (len(self.nodes) % 6) * 80
                self.add_node(node_type, cx, cy)

    def add_node(self, node_type, x, y):
        """在画布指定位置添加新节点。"""
        template = self.NODE_TEMPLATES.get(node_type)
        if not template:
            return None
        # 统一 pin 格式：完整版模板已是字典列表，简化版是字符串列表
        def _normalize_pins(pin_list):
            pins = []
            for p in pin_list:
                if isinstance(p, dict):
                    # 已经是字典格式（完整版模板），保留 id/name/type
                    pins.append({
                        "id": p["id"],
                        "name": p.get("name", p["id"]),
                        "type": p.get("type", "data"),
                    })
                else:
                    # 字符串格式（简化版模板）
                    ptype = "exec" if p == "exec" else "data"
                    pins.append({"id": p, "name": p, "type": ptype})
            return pins

        node = Node(node_id=self.next_node_id, node_type=node_type, x=x, y=y,
                    inputs=_normalize_pins(template.get("inputs", [])),
                    outputs=_normalize_pins(template.get("outputs", [])))
        self.next_node_id += 1
        node.update_port_positions()
        self.nodes.append(node)
        self.selected_node = node
        self.redraw()
        return node

    def _schedule_redraw(self, delay_ms=30):
        """延迟调度重绘：合并短时间内多次请求，避免每帧全量重绘。

        平移拖拽期间只做 canvas.move() 位移，不触发全量 redraw。
        缩放操作用 canvas.scale() 即时预览，delay_ms 后再做精细重绘。
        """
        if self._redraw_pending:
            return
        self._redraw_pending = True
        self.after(delay_ms, self._do_pending_redraw)

    def _do_pending_redraw(self):
        """执行待处理的延迟重绘。"""
        self._redraw_pending = False
        # 安全检查：窗口/canvas 可能已销毁（after 调度的回调在关闭后仍可能触发）
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return
        # 如果当前正在平移拖拽中，不重绘（平移用 canvas.move 处理）
        if self._pan_dragging:
            return
        # 如果缩放脏了或需要正常重绘
        self.redraw()

    # ==================== 画布缩放/平移系统 ====================

    def _canvas_to_world(self, cx, cy):
        """画布坐标 → 世界坐标（节点使用的逻辑坐标）。"""
        wx = (cx - self.canvas_pan_x) / self.canvas_zoom
        wy = (cy - self.canvas_pan_y) / self.canvas_zoom
        return wx, wy

    def _world_to_canvas(self, wx, wy):
        """世界坐标 → 画布坐标（屏幕像素坐标）。"""
        cx = wx * self.canvas_zoom + self.canvas_pan_x
        cy = wy * self.canvas_zoom + self.canvas_pan_y
        return cx, cy

    def _set_zoom(self, new_zoom, center_cx=None, center_cy=None):
        """设置缩放比例：canvas.scale 即时预览 + 延迟精细重绘。

        Args:
            new_zoom: 新的缩放比例（限制在 0.1 ~ 5.0）
            center_cx: 缩放中心的画布 X 坐标（None=画布中心）
            center_cy: 缩放中心的画布 Y 坐标（None=画布中心）
        """
        # 限制缩放范围
        new_zoom = max(0.1, min(5.0, new_zoom))
        if abs(new_zoom - self.canvas_zoom) < 0.001:
            return

        # 以鼠标位置或画布中心为锚点
        if center_cx is None:
            center_cx = (self.canvas.winfo_width() or 1200) // 2
        if center_cy is None:
            center_cy = (self.canvas.winfo_height() or 750) // 2

        old_zoom = self.canvas_zoom
        scale_factor = new_zoom / old_zoom

        # 调整 pan 使锚点在世界空间中位置不变
        anchor_wx = (center_cx - self.canvas_pan_x) / old_zoom
        anchor_wy = (center_cy - self.canvas_pan_y) / old_zoom
        self.canvas_pan_x = center_cx - anchor_wx * new_zoom
        self.canvas_pan_y = center_cy - anchor_wy * new_zoom
        self.canvas_zoom = new_zoom
        self._zoom_dirty = True

        # ---- 快速路径：用 canvas.scale 即时预览（零 delete/all） ----
        try:
            # 以缩放中心为原点进行 scale
            self.canvas.scale("all", center_cx, center_cy, scale_factor, scale_factor)
        except tk.TclError:
            pass  # 画布还没就绪，忽略

        # 延迟精细重绘（30ms 后，合并连续滚轮事件）
        self._schedule_redraw(delay_ms=30)

    def _reset_view(self):
        """重置视图：zoom=1, pan=(0,0)，居中显示所有节点。"""
        self.canvas_zoom = 1.0
        if self.nodes:
            # 计算所有节点的包围盒，居中显示
            min_x = min(n.x for n in self.nodes)
            max_x = max(n.x + n.width for n in self.nodes)
            min_y = min(n.y for n in self.nodes)
            max_y = max(n.y + n.height for n in self.nodes)
            cw = self.canvas.winfo_width() or 1200
            ch = self.canvas.winfo_height() or 750
            node_cx = (min_x + max_x) / 2
            node_cy = (min_y + max_y) / 2
            self.canvas_pan_x = cw / 2 - node_cx
            self.canvas_pan_y = ch / 2 - node_cy
        else:
            self.canvas_pan_x = 0
            self.canvas_pan_y = 0
        self.redraw()

    def _on_mousewheel(self, event):
        """Windows 滚轮缩放（以鼠标位置为中心）。"""
        # 向上滚正数放大，向下负数缩小
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        self._set_zoom(self.canvas_zoom * factor, event.x, event.y)

    def _on_zoom(self, event, factor):
        """Linux 滚轮缩放。"""
        self._set_zoom(self.canvas_zoom * factor, event.x, event.y)

    def _on_pan_start(self, event):
        """中键按下：开始平移拖拽。"""
        self._pan_dragging = True
        self._pan_start = (event.x, event.y)
        self._pan_start_offset = (self.canvas_pan_x, self.canvas_pan_y)
        self._last_pan_dx = 0
        self._last_pan_dy = 0

    def _on_pan_drag(self, event):
        """中键/空格+左键 拖拽：用 canvas.move() 即时位移（零重绘）。"""
        if not self._pan_dragging:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]

        # 更新逻辑偏移
        self.canvas_pan_x = self._pan_start_offset[0] + dx
        self.canvas_pan_y = self._pan_start_offset[1] + dy

        # ---- 快速路径：canvas.move 整体位移，不触发全量 redraw ----
        actual_dx = dx - self._last_pan_dx
        actual_dy = dy - self._last_pan_dy
        if abs(actual_dx) > 0 or abs(actual_dy) > 0:
            try:
                self.canvas.move("all", actual_dx, actual_dy)
            except tk.TclError:
                pass
            self._last_pan_dx = dx
            self._last_pan_dy = dy

    def _on_pan_end(self, event=None):
        """中键释放：结束平移拖拽，安排一次精细重绘对齐坐标。"""
        was_dragging = self._pan_dragging
        self._pan_dragging = False
        self._last_pan_dx = 0
        self._last_pan_dy = 0
        # 平移结束后做一次精细重绘（消除 canvas.move 累积的浮点误差）
        if was_dragging:
            self.redraw()

    def _on_space_press(self, event):
        """空格键按下：标记空格已按（配合左键平移）。"""
        self._space_pressed = True
        # 改变光标样式提示用户
        if self.canvas.winfo_exists():
            self.canvas.configure(cursor="fleur")

    def _on_space_release(self, event):
        """空格键释放：恢复正常模式。"""
        self._space_pressed = False
        if self.canvas.winfo_exists():
            self.canvas.configure(cursor="")

    # ==================== 画布事件处理 ====================

    def on_click(self, event):
        """鼠标按下（画布坐标 → 世界坐标）。"""
        # 空格+左键 = 平移模式
        if self._space_pressed:
            self._pan_dragging = True
            self._pan_start = (event.x, event.y)
            self._pan_start_offset = (self.canvas_pan_x, self.canvas_pan_y)
            return

        # 画布坐标 → 世界坐标
        x, y = self._canvas_to_world(event.x, event.y)
        clicked_pin = None
        clicked_node = None
        for node in reversed(self.nodes):
            pin_result = node.hit_pin(x - node.x, y - node.y)
            if pin_result:
                clicked_pin = (node, pin_result)
                break
            if node.contains(x - node.x, y - node.y):
                clicked_node = node
                break

        if clicked_pin:
            node, pin_info = clicked_pin
            self.drag_pin = node, pin_info
            # 存储格式：(起点世界坐标x, 起点世界坐标y, 终点画布坐标x, 终点画布坐标y)
            pin_pos = None
            pl = node.outputs if pin_info[2] else node.inputs
            for p in pl:
                if p.get('id') == pin_info[0] and 'pos' in p:
                    pin_pos = p['pos']
                    break
            if pin_pos is None:
                # fallback: 用节点坐标估算
                body_top = node.y + node.header_height
                is_output = pin_info[2]
                base_x = node.x + (node.width if is_output else 0)
                idx = next((i for i, p in enumerate(pl) if p.get('id') == pin_info[0]), 0)
                pin_pos = (base_x, body_top + 24 + idx * 24)
            self.temp_line = (pin_pos[0], pin_pos[1], event.x, event.y)
            self.selected_connection = None  # 点pin时取消连线选中
        elif clicked_node:
            if event.state & 0x4:  # Ctrl 多选
                self.selected_nodes.add(clicked_node)
            else:
                self.selected_node = clicked_node
                self.selected_nodes = {clicked_node}
            self.drag_node = clicked_node
            self.drag_offset = (x - clicked_node.x, y - clicked_node.y)
            self.rubber_band_start = None
            self.selected_connection = None  # 点节点时取消连线选中
            self.redraw()
            return  # ⚠️ 必须提前 return：否则继续往下走 else 分支 + 再次 redraw，双击时会与 on_double_click 冲突弹出两窗口
        else:
            # 检查是否点击了连线
            conn = self.find_connection_at(x, y)
            if conn:
                self.selected_connection = conn
                self.selected_node = None
                self.selected_nodes.clear()
            else:
                self.selected_node = None
                self.selected_connection = None
                self.selected_nodes.clear()
                self.rubber_band_start = (x, y)
                self.rubber_band_rect = None
        self.redraw()

    def on_drag(self, event):
        """鼠标拖拽。"""
        # 如果是平移模式，走快速平移路径（canvas.move）
        if self._pan_dragging:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self.canvas_pan_x = self._pan_start_offset[0] + dx
            self.canvas_pan_y = self._pan_start_offset[1] + dy
            actual_dx = dx - self._last_pan_dx
            actual_dy = dy - self._last_pan_dy
            if abs(actual_dx) > 0 or abs(actual_dy) > 0:
                try:
                    self.canvas.move("all", actual_dx, actual_dy)
                except tk.TclError:
                    pass
                self._last_pan_dx = dx
                self._last_pan_dy = dy
            return

        # 画布坐标 → 世界坐标
        x, y = self._canvas_to_world(event.x, event.y)
        if self.drag_pin:
            node = self.drag_pin[0]
            # 从拖拽起始 pin 的实际 pos 坐标画线
            pin_info = self.drag_pin[1]   # (pin_id, pin_type, is_output)
            start_pos = None
            pin_list = node.outputs if pin_info[2] else node.inputs
            for p in pin_list:
                if p.get('id') == pin_info[0] and 'pos' in p:
                    start_pos = p['pos']
                    break
            # fallback: 用 update_port_positions 的公式计算
            if start_pos is None:
                body_top = node.y + node.header_height
                is_output = pin_info[2]
                base_x = node.x + (node.width if is_output else 0)
                # 在 pin_list 里找索引
                idx = next((i for i, p in enumerate(pin_list) if p.get('id') == pin_info[0]), 0)
                start_pos = (base_x, body_top + 24 + idx * 24)
            self.temp_line = (start_pos[0], start_pos[1], event.x, event.y)  # (世界起点, 画布终点)
            self.redraw()
        elif self.drag_node:
            # 计算主拖拽节点新位置
            new_x = x - self.drag_offset[0]
            new_y = y - self.drag_offset[1]
            offset_x = new_x - self.drag_node.x
            offset_y = new_y - self.drag_node.y
            # 同步移动所有选中节点
            for n in self.selected_nodes:
                n.x += offset_x
                n.y += offset_y
            for n in self.nodes:
                n.update_port_positions()
            self.redraw()
        elif self.rubber_band_start:
            x0, y0 = self.rubber_band_start  # 世界坐标
            self.rubber_band_rect = (min(x0, x), min(y0, y), max(x0, x), max(y0, y))
            self.redraw()

    def on_release(self, event):
        """鼠标释放 — 完成拖拽或创建连线。"""
        # 如果是平移模式，结束平移并精细重绘
        if self._pan_dragging:
            self._pan_dragging = False
            self._last_pan_dx = 0
            self._last_pan_dy = 0
            self.redraw()  # 精细重绘消除 canvas.move 累积误差
            return

        # 画布坐标 → 世界坐标
        x, y = self._canvas_to_world(event.x, event.y)
        if self.drag_pin:
            from_node, from_pin = self.drag_pin
            to_pin_hit = None
            to_node_hit = None
            for node in self.nodes:
                if node == from_node:
                    continue
                hit = node.hit_pin(x - node.x, y - node.y)
                if hit:
                    to_pin_hit = hit
                    to_node_hit = node
                    break
            if to_node_hit and to_pin_hit:
                can_connect = True
                from_pin_id = from_pin[0]
                from_pin_type = from_pin[1]
                to_pin_id = to_pin_hit[0]
                to_pin_type = to_pin_hit[1]
                is_exec_out = from_pin_type == "exec"
                is_exec_in = to_pin_type == "exec"
                # exec pin 只能连 exec pin
                if is_exec_out != is_exec_in:
                    can_connect = False
                # 数据 pin 不能连同一个输入两次
                if can_connect and not is_exec_in:
                    for c in self.connections:
                        if c.to_node == to_node_hit and c.to_pin_id == to_pin_id:
                            can_connect = False
                            break
                # 不允许反向连接已存在的边
                if can_connect:
                    for c in self.connections:
                        if c.from_node == from_node and c.from_pin_id == from_pin_id \
                           and c.to_node == to_node_hit and c.to_pin_id == to_pin_id:
                            can_connect = False
                            break
                if can_connect:
                    self.connections.append(Connection(from_node, from_pin_id, to_node_hit, to_pin_id))
            self.drag_pin = None
            self.temp_line = None
            self.redraw()
        elif self.rubber_band_start and self.rubber_band_rect:
            x0, y0, x1, y1 = self.rubber_band_rect
            for node in self.nodes:
                nx, ny = node.x, node.y
                nw, nh = node.width, node.height
                if x0 <= nx + nw / 2 <= x1 and y0 <= ny + nh / 2 <= y1:
                    self.selected_nodes.add(node)
            self.rubber_band_start = None
            self.rubber_band_rect = None
            self.redraw()
        self.drag_node = None

    def on_double_click(self, event):
        """双击节点 → 编辑参数（带防抖，防止重复弹出窗口）。"""
        # 防抖：500ms 内不重复弹窗
        now = time.time()
        if now - self._last_dclick_time < 0.5:
            return
        self._last_dclick_time = now

        x, y = self._canvas_to_world(event.x, event.y)
        for node in reversed(self.nodes):
            if node.contains(x - node.x, y - node.y):
                self.edit_node_params(node)
                return

    # ==================== 连线与选择 ====================

    def find_connection_at(self, x, y):
        """查找世界坐标处的连线（近似判断，容差随缩放调整）。"""
        tolerance = max(5, 8 / self.canvas_zoom)  # 世界坐标容差
        for conn in self.connections:
            pts = conn.points()
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                dist = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
                if dist < tolerance:
                    return conn
        return None

    def delete_selected_node(self):
        """删除选中节点及其连线。"""
        if self.selected_node:
            self.connections = [c for c in self.connections
                                if c.from_node != self.selected_node and c.to_node != self.selected_node]
            self.nodes.remove(self.selected_node)
            self.selected_node = None
            self.redraw()

    def delete_selected_nodes(self, event=None):
        """删除所有选中节点或选中连线。"""
        # 优先删除选中的连线
        if self.selected_connection and not self.selected_nodes:
            self.delete_selected_connection()
            return
        # 删除选中节点
        for n in list(self.selected_nodes):
            self.connections = [c for c in self.connections if c.from_node != n and c.to_node != n]
            if n in self.nodes:
                self.nodes.remove(n)
        self.selected_nodes.clear()
        self.selected_node = None
        self.redraw()

    def delete_selected_connection(self):
        """删除选中连线。"""
        if self.selected_connection:
            self.connections.remove(self.selected_connection)
            self.selected_connection = None
            self.redraw()

    def select_all(self, event=None):
        """全选所有节点。"""
        self.selected_nodes = set(self.nodes)
        self.redraw()

    def copy_selected(self, event=None):
        """复制选中节点到剪贴板。"""
        if not self.selected_nodes:
            return
        data = [(n.type, dict(n.params)) for n in self.selected_nodes]
        self.clipboard = data

    def paste_clipboard(self, event=None):
        """从剪贴板粘贴节点。"""
        if not self.clipboard:
            return
        offset = 50
        new_nodes = []
        for ntype, params in self.clipboard:
            tmpl = self.NODE_TEMPLATES.get(ntype, {})
            def _make_pins(pin_list):
                pins = []
                for p in pin_list:
                    if isinstance(p, dict):
                        pins.append({"id": p["id"], "name": p.get("name", p["id"]), "type": p.get("type", "data")})
                    else:
                        pins.append({"id": p, "name": p, "type": "exec" if p == "exec" else "data"})
                return pins
            n = Node(
                node_id=self.next_node_id, node_type=ntype,
                x=(self.selected_node.x + offset) if self.selected_node else 200,
                y=(self.selected_node.y + offset) if self.selected_node else 200,
                params=dict(params),
                inputs=_make_pins(tmpl.get("inputs", [])),
                outputs=_make_pins(tmpl.get("outputs", [])),
            )
            self.next_node_id += 1
            n.update_port_positions()
            self.nodes.append(n)
            new_nodes.append(n)
            offset += 30
        self.selected_nodes = set(new_nodes)
        self.selected_node = new_nodes[0] if new_nodes else None
        self.redraw()

    # ==================== 参数编辑对话框 ====================

    def edit_node_params(self, node):
        """打开节点参数编辑对话框——控件直接放在窗口上，零背景。"""
        dlg = tk.Toplevel(self)
        dlg.title(f"编辑参数 - {node.icon}")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.withdraw()

        colors = node.colors

        # --- 顶栏（唯一保留彩色的地方） ---
        hdr = tk.Frame(dlg, bg=colors["header"], height=32)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text=f"  {node.icon} {self.NODE_TEMPLATES.get(node.type, {}).get('title', node.type)}",
                 font=(FONT_FAMILY, 10, "bold"),
                 fg="white", bg=colors["header"]).pack(side=tk.LEFT, pady=5)

        # --- 对话框专属 ttk 样式（亮色系，不影响主窗口） ---
        dlg_style = ttk.Style(dlg)
        # Combobox: 白底黑字 + 下拉箭头正常
        dlg_style.configure("Dlg.TCombobox",
                            fieldbackground="white", background="white",
                            foreground="black")
        # Checkbutton: 正常前景色
        dlg_style.configure("Dlg.TCheckbutton", foreground="black", background=dlg.cget("bg"))
        dlg_style.map("Dlg.TCheckbutton", background=[("active", "SystemButtonFace")])

        # --- 控件区 ---
        content = tk.Frame(dlg)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        entries = {}

        template = self.NODE_TEMPLATES.get(node.type, {})
        param_defs = template.get("params", {})

        if not param_defs:
            tk.Label(content, text="此节点无可编辑参数",
                     font=(FONT_FAMILY, 9)).pack(pady=20)

        row = 0
        for pkey, pdef in param_defs.items():
            label_text = pkey
            desc = pdef.get("description", "")

            # 标签列
            lbl = tk.Label(content, text=label_text,
                           font=(FONT_FAMILY, 9, "bold"), anchor="w")
            lbl.grid(row=row, column=0, sticky="w", pady=(6, 2), padx=(0, 12))

            # 描述标签（如果有的话）
            if desc:
                desc_lbl = tk.Label(content, text=f"({desc})",
                                    font=(FONT_FAMILY, 8), fg="gray", anchor="w")
                desc_lbl.grid(row=row + 1, column=0, sticky="w", pady=(0, 4), padx=(0, 12))
                ctrl_row = row + 1
                row += 2
            else:
                ctrl_row = row
                row += 1

            ptype = pdef.get("type", "string")
            default_val = pdef.get("default", "")
            current_val = node.params.get(pkey, default_val)

            if ptype == "choice":
                # 使用 ttk.Combobox 替代 tk.OptionMenu（正常下拉箭头）
                options = pdef.get("options", [])
                var = tk.StringVar(value=str(current_val) if current_val is not None else str(default_val))
                combo = ttk.Combobox(content, textvariable=var,
                                     values=options, state="readonly",
                                     font=(FONT_FAMILY, 9),
                                     style="Dlg.TCombobox")
                combo.grid(row=ctrl_row, column=1, sticky="ew", pady=(0, 6))
                entries[pkey] = (lambda v=var: v.get(), lambda v, val: v.set(str(val)))

            elif ptype == "multi_choice":
                options = pdef.get("options", [])
                current_set = set(current_val) if isinstance(current_val, list) else set()
                cb_frame = tk.Frame(content)
                cb_frame.grid(row=ctrl_row, column=1, sticky="w", pady=(0, 6))
                cb_vars = {}
                for opt in options:
                    var = tk.BooleanVar(value=(opt in current_set))
                    cb = ttk.Checkbutton(cb_frame, text=opt, variable=var,
                                         style="Dlg.TCheckbutton")
                    cb.pack(side=tk.LEFT, padx=(0, 10))
                    cb_vars[opt] = var

                def _make_multi_getter(cbvd):
                    return lambda: [k for k, v in cbvd.items() if v.get()]
                def _make_multi_setter(cbvd):
                    return lambda vl: [cbvd[o].set(o in (vl or [])) for o in cbvd]
                entries[pkey] = (_make_multi_getter(cb_vars), _make_multi_setter(cb_vars))

            elif ptype in ("number", "string"):
                var = tk.StringVar(
                    value=str(current_val))
                f = ("Consolas", 10) if ptype == "number" else (FONT_FAMILY, 10)
                entry = tk.Entry(content, textvariable=var, font=f)
                entry.grid(row=ctrl_row, column=1, sticky="ew", pady=(0, 6))
                entries[pkey] = (lambda v=var: v.get(), lambda v, val: v.set(str(val)))

            else:
                var = tk.StringVar(value=str(current_val) if current_val is not None else "")
                entry = tk.Entry(content, textvariable=var, font=("Consolas", 10))
                entry.grid(row=ctrl_row, column=1, sticky="ew", pady=(0, 6))
                entries[pkey] = (lambda v=var: v.get(), lambda v, val: v.set(str(val)))

        # 列宽权重：标签列固定，控件列拉伸
        content.columnconfigure(1, weight=1)

        # --- 底部按钮 ---
        btn_bar = tk.Frame(dlg)
        btn_bar.pack(fill=tk.X, padx=16, pady=(0, 12))

        def do_save():
            for key, (getter, setter) in entries.items():
                raw_val = getter()
                pd = param_defs.get(key, {})
                pt = pd.get("type", "string")
                if pt == "number":
                    try:
                        raw_val = float(raw_val) if '.' in str(raw_val) else int(raw_val)
                    except ValueError:
                        pass
                node.params[key] = raw_val
            # 安全销毁（窗口可能已被外部关闭）
            try:
                dlg.destroy()
            except tk.TclError:
                pass
            self.redraw()

        def do_cancel():
            try:
                dlg.destroy()
            except tk.TclError:
                pass

        def on_close():
            """WM_DELETE_WINDOW 回调——先释放 grab 再销毁，避免死锁。"""
            try:
                dlg.grab_release()
            except tk.TclError:
                pass
            do_cancel()

        dlg.protocol("WM_DELETE_WINDOW", on_close)

        tk.Button(btn_bar, text="取消", font=(FONT_FAMILY, 10),
                  command=do_cancel).pack(side=tk.RIGHT, padx=(0, 8))
        tk.Button(btn_bar, text="保存", font=(FONT_FAMILY, 10, "bold"),
                  command=do_save).pack(side=tk.RIGHT)

        # --- 所有控件创建完毕后：居中 + 显示 ---
        dlg.grab_set()
        dlg.update_idletasks()
        pw = self.winfo_width() or 1200
        ph = self.winfo_height() or 750
        dw = dlg.winfo_reqwidth() or 440
        dh = dlg.winfo_reqheight() or 560
        x = self.winfo_x() + (pw - dw) // 2
        y = self.winfo_y() + (ph - dh) // 2
        x = max(0, x)
        y = max(0, y)
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        dlg.deiconify()
        dlg.lift()
        dlg.focus_force()

    def _get_param_fields(self, node_type):
        """返回节点类型对应的可编辑参数列表：(key, label, default)。（保留向后兼容，已不再使用）"""
        return []

    # ==================== 绘制系统 ====================

    def redraw(self):
        """重绘整个画布（卡片式节点 + 贝塞尔连线 + 网格背景 + 缩放/平移）。"""
        # 安全检查：窗口关闭后 canvas 已销毁，忽略后续操作
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return
        self.canvas.delete("all")
        W = self.canvas.winfo_width() or 1200
        H = self.canvas.winfo_height() or 750
        zoom = self.canvas_zoom
        pan_x = self.canvas_pan_x
        pan_y = self.canvas_pan_y

        # --- 网格背景（根据缩放级别动态调整间距） ---
        base_spacing = 24
        # 根据缩放级别选择合适的网格间距（避免太密或太稀疏）
        if zoom <= 0.25:
            grid_spacing = base_spacing * 8
        elif zoom <= 0.5:
            grid_spacing = base_spacing * 4
        elif zoom <= 1.0:
            grid_spacing = base_spacing * 2
        else:
            grid_spacing = base_spacing

        # 计算可见区域在世界坐标中的范围，从那里开始画网格
        world_left, world_top = self._canvas_to_world(0, 0)
        world_right, world_bottom = self._canvas_to_world(W, H)

        # 网格起点对齐到 grid_spacing 倍数（世界坐标）
        start_x = int(world_left // grid_spacing) * grid_spacing
        start_y = int(world_top // grid_spacing) * grid_spacing

        # 小网格点（主网格的1/4）—— 只在 zoom > 0.5 且间距>=48 时画
        if zoom > 0.5 and grid_spacing >= 48:
            sub_spacing = grid_spacing / 4
            # 裁剪：只画可见范围内的点
            sx = int(world_left // sub_spacing) * sub_spacing
            sx_max = world_right + sub_spacing
            sy_max = world_bottom + sub_spacing
            while sx < sx_max:
                sy = int(world_top // sub_spacing) * sub_spacing
                while sy < sy_max:
                    cx, cy = self._world_to_canvas(sx, sy)
                    self.canvas.create_oval(cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5,
                                            fill="#2e2e33", outline="")
                    sy += sub_spacing
                sx += sub_spacing

        # 主网格点 —— 裁剪到可见范围
        gx = start_x
        gx_max = world_right + grid_spacing
        gy_max = world_bottom + grid_spacing
        dot_size = 1.2 if zoom >= 1.0 else 1.0
        while gx < gx_max:
            gy = start_y
            while gy < gy_max:
                cx, cy = self._world_to_canvas(gx, gy)
                self.canvas.create_oval(cx - dot_size, cy - dot_size,
                                        cx + dot_size, cy + dot_size,
                                        fill="#40404a", outline="")
                gy += grid_spacing
            gx += grid_spacing

        # --- 连线（世界坐标 → 画布坐标变换） ---
        for ci, conn in enumerate(self.connections):
            is_sel = conn == self.selected_connection
            from_pos = None
            to_pos = None
            for p in conn.from_node.outputs:
                if p.get('id') == conn.from_pin_id and 'pos' in p:
                    from_pos = p['pos']
                    break
            for p in conn.to_node.inputs:
                if p.get('id') == conn.to_pin_id and 'pos' in p:
                    to_pos = p['pos']
                    break
            if not from_pos or not to_pos:
                continue

            is_exec = conn.from_pin_id == "exec"
            line_color = "#f0c060" if is_exec else "#70b0e0"
            base_w = 2.5 if is_exec else 2.0
            line_w = base_w * max(0.5, zoom)  # 线宽也随缩放变化，但有下限

            # 世界坐标转画布坐标
            x0, y0 = self._world_to_canvas(*from_pos)
            x3, y3 = self._world_to_canvas(*to_pos)
            dx = abs(x3 - x0) * 0.5
            x1 = x0 + dx
            y1 = y0
            x2 = x3 - dx
            y2 = y3
            pts = []
            for i in range(11):  # 11个采样点足够平滑贝塞尔曲线（原来21个，性能翻倍）
                t = i / 10.0
                u = 1 - t
                px = u**3*x0 + 3*u**2*t*x1 + 3*u*t**2*x2 + t**3*x3
                py = u**3*y0 + 3*u**2*t*y1 + 3*u*t**2*y2 + t**3*y3
                pts.extend([px, py])
            if len(pts) >= 4:
                lw = line_w + 1.5 if is_sel else line_w
                self.canvas.create_line(pts, fill=line_color, width=lw, smooth=True,
                                         splinesteps=20, capstyle=tk.ROUND)

        # --- 临时拖拽线 ---
        if self.temp_line:
            wx0, wy0, wx1, wy1 = self.temp_line
            # 起点是世界坐标（pin pos），终点是画布坐标（鼠标）
            x0, y0 = self._world_to_canvas(wx0, wy0)
            # 终点直接用画布坐标（鼠标位置不需要转换）
            x1, y1 = wx1, wy1
            dx = abs(x1 - x0) * 0.5
            pts_t = []
            for i in range(11):  # 同样减少到11个采样点
                t = i / 10.0; u = 1-t
                pts_t.extend([
                    u**3*x0 + 3*u**2*t*(x0+dx) + 3*u*t**2*(x1-dx) + t**3*x1,
                    u**3*y0 + 3*u**2*t*y0 + 3*u*t**2*y1 + t**3*y1,
                ])
            if len(pts_t) >= 4:
                is_exec_temp = self.drag_pin and self.drag_pin[1][1] == "exec"
                lc = "#f0c060" if is_exec_temp else "#70b0e0"
                self.canvas.create_line(pts_t, fill=lc, width=1.5, smooth=True, splinesteps=20,
                                        capstyle=tk.ROUND, dash=(6, 4))

        # --- 选择框（世界坐标 → 画布坐标） ---
        if self.rubber_band_rect:
            x0, y0, x1, y1 = self.rubber_band_rect
            cx0, cy0 = self._world_to_canvas(x0, y0)
            cx1, cy1 = self._world_to_canvas(x1, y1)
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1, outline="#88aaff", width=1, dash=(4, 4))

        # --- 节点绘制（世界坐标 → 画布坐标 + 缩放） ---
        for node in self.nodes:
            # 世界坐标转画布坐标
            x, y = self._world_to_canvas(node.x, node.y)
            # 尺寸乘以缩放
            w = node.width * zoom
            h = node.height * zoom
            hh = node.header_height * zoom
            bh = node.body_height * zoom

            # 太小就不画了（性能保护）
            if w < 4 or h < 4:
                continue

            # 圆角也随缩放缩放，但有最小值
            r = max(2, 8 * zoom)
            colors = node.colors
            is_sel = node == self.selected_node or node in self.selected_nodes

            # 节点主体（暗色圆角矩形效果）
            body_fill = colors["body"] if not is_sel else self._lighten_color(colors["body"], 15)
            self.canvas.create_rectangle(x, y, x+w, y+h, fill=body_fill,
                                          outline=colors["border"] if is_sel else "",
                                          width=2 if is_sel else 0)

            # 头部色条
            self.canvas.create_rectangle(x, y, x+w, y+hh, fill=colors["header"], outline="")
            # 头部底部高光线
            self.canvas.create_line(x, y+hh-1, x+w, y+hh-1, fill=self._lighten_color(colors["header"], 20), width=1)

            # 图标 + 标题
            title_text = f"{node.icon}  {self.NODE_TEMPLATES.get(node.type, {}).get('title', node.type)}"
            title_font_size = max(7, min(14, int(9 * zoom)))
            self.canvas.create_text(x + 8 * zoom, y + hh / 2, anchor=tk.W,
                                     text=title_text, fill=colors["header_text"],
                                     font=(FONT_FAMILY, title_font_size, "bold"))

            # ID标签（右侧半透明）
            id_font_size = max(6, min(11, int(7 * zoom)))
            self.canvas.create_text(x + w - 8 * zoom, y + hh / 2, anchor=tk.E,
                                     text=f"#{node.id}", fill=colors["header_text"],
                                     font=("Consolas", id_font_size))

            # 参数预览文本（简洁样式，最多一行）
            preview_parts = []
            for pk, pv in list(node.params.items())[:3]:
                if pk == "description":
                    continue
                # 将参数key转为简短中文显示
                label_map = {
                    "trigger_rate": "触发率", "delay_ms": "延迟",
                    "var_name": "变量", "count": "数量",
                    "base_damage": "伤害率", "base_heal": "恢复率",
                    "attr_key": "属性", "scale_factor": "系数",
                    "control_type": "控制", "duration_rounds": "持续",
                    "status_key": "状态", "stack_count": "层数",
                    "attr_key": "属性", "mode": "模式", "value": "数值",
                    "op": "运算符", "rhs_value": "右值",
                    "threshold": "阈值", "rate": "概率",
                    "filter_has_status": "状态过滤", "sort_by_hp_percent": "血量排序",
                    "damage_rate": "伤害率", "heal_rate": "恢复率",
                    "affected_attr": "影响属性",
                }
                label = label_map.get(pk, pk)
                # 数值格式化：去掉尾随.0
                if isinstance(pv, float) and pv == int(pv):
                    pv = int(pv)
                preview_parts.append(f"{label}:{pv}")
            if preview_parts:
                preview = "  ·  ".join(preview_parts)
                preview_font_size = max(6, min(11, int(8 * zoom)))
                # 只在缩放足够大时显示参数预览
                if zoom > 0.5:
                    # 截断过长文本，防止超出节点宽度（右侧留 ID 空间）
                    max_chars = int((w - 24 * zoom) / (preview_font_size * 0.7))
                    if len(preview) > max_chars:
                        preview = preview[:max_chars-1] + "…"
                    self.canvas.create_text(x + 8 * zoom, y + hh + 10 * zoom, anchor=tk.W,
                                             text=preview, fill="#777880",
                                             font=(FONT_FAMILY, preview_font_size))

            # 输入pin（左侧）—— 世界坐标转画布坐标
            for pin in node.inputs:
                if 'pos' not in pin:
                    continue
                is_exec_pin = pin['type'] == 'exec'
                pin_x, pin_y = self._world_to_canvas(*pin['pos'])
                pr = (5 if is_exec_pin else 4) * zoom
                pc = "#f0a040" if is_exec_pin else "#70b0e0"
                if is_exec_pin:
                    self.canvas.create_polygon(pin_x-pr, pin_y, pin_x, pin_y-pr*0.7,
                                               pin_x+pr, pin_y, pin_x, pin_y+pr*0.7,
                                               fill=pc, outline="")
                else:
                    self.canvas.create_oval(pin_x-pr, pin_y-pr, pin_x+pr, pin_y+pr,
                                            fill=pc, outline="")
                # pin 标签（缩放足够大时才显示）
                if zoom > 0.5:
                    label = pin.get('name') or pin.get('id', '')
                    max_label_w = w * 0.45
                    approx_len = len(label) * 9 * zoom
                    if approx_len > max_label_w:
                        label = label[:int(max_label_w / (9 * zoom))] + "\u2026"
                    pin_font_size = max(6, min(10, int(8 * zoom)))
                    self.canvas.create_text(pin_x + 14 * zoom, pin_y, anchor=tk.W,
                                             text=label, fill="#888890",
                                             font=(FONT_FAMILY, pin_font_size))

            # 输出pin（右侧）
            for pin in node.outputs:
                if 'pos' not in pin:
                    continue
                is_exec_pin = pin['type'] == 'exec'
                pin_x, pin_y = self._world_to_canvas(*pin['pos'])
                pr = (5 if is_exec_pin else 4) * zoom
                pc = "#f0a040" if is_exec_pin else "#70b0e0"
                if is_exec_pin:
                    self.canvas.create_polygon(pin_x-pr, pin_y, pin_x, pin_y-pr*0.7,
                                               pin_x+pr, pin_y, pin_x, pin_y+pr*0.7,
                                               fill=pc, outline="")
                else:
                    self.canvas.create_oval(pin_x-pr, pin_y-pr, pin_x+pr, pin_y+pr,
                                            fill=pc, outline="")
                if zoom > 0.5:
                    label = pin.get('name') or pin.get('id', '')
                    max_label_w = w * 0.45
                    approx_len = len(label) * 9 * zoom
                    if approx_len > max_label_w:
                        label = label[:int(max_label_w / (9 * zoom))] + "\u2026"
                    pin_font_size = max(6, min(10, int(8 * zoom)))
                    self.canvas.create_text(pin_x - 14 * zoom, pin_y, anchor=tk.E,
                                             text=label, fill="#888890",
                                             font=(FONT_FAMILY, pin_font_size))

            # 选中发光效果
            if is_sel:
                self.canvas.create_rectangle(x-2*zoom, y-2*zoom, x+w+2*zoom, y+h+2*zoom,
                                              outline="#ffffff", width=max(1, zoom), dash=(3, 3))

        # --- 缩放比例指示器（左下角） ---
        pct = int(self.canvas_zoom * 100)
        zoom_text = f"{pct}%"
        margin = 10
        # 半透明背景
        self.canvas.create_rectangle(margin - 4, H - margin - 18, margin + len(zoom_text) * 9 + 4,
                                     H - margin + 2, fill="#1e1e28", outline="#444", width=1)
        self.canvas.create_text(margin, H - margin - 8, anchor=tk.SW,
                                text=zoom_text, fill="#888890",
                                font=("Consolas", 9))

    @staticmethod
    def _lighten_color(hex_color, amount=10):
        """使颜色变亮。"""
        hex_color = hex_color.lstrip("#")
        r = min(255, int(hex_color[0:2], 16) + amount)
        g = min(255, int(hex_color[2:4], 16) + amount)
        b = min(255, int(hex_color[4:6], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    def show_context_menu(self, event):
        """显示右键菜单。"""
        try:
            self.context_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass  # 窗口已销毁时忽略


# ============================================================
#  两个具体子类（Toplevel / Frame），供 __new__ 工厂选择
# ============================================================

class _NodeEditorToplevel(tk.Toplevel, _NodeEditorBase):
    """独立窗口模式的节点编辑器。"""

    def __init__(self, parent, skill_name, effect_config=None, **_kwargs):
        # 防重复初始化：当 __new__ 返回已有单例时，Python 仍会调用 __init__
        if getattr(self, '_initialized', False):
            self.lift()
            return

        tk.Toplevel.__init__(self, parent)
        self.title(f"节点编辑器 - {skill_name}")
        self.geometry("1200x750")
        self.resizable(True, True)

        # 菜单栏
        menubar = Menu(self)
        self.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="保存", command=self.save, accelerator="Ctrl+S")
        file_menu.add_command(label="导入JSON", command=self.import_json, accelerator="Ctrl+I")
        file_menu.add_command(label="导出JSON", command=self.export_json, accelerator="Ctrl+E")
        file_menu.add_separator()
        file_menu.add_command(label="清空画布", command=self.clear_canvas, accelerator="Ctrl+Shift+X")
        file_menu.add_separator()
        file_menu.add_command(label="取消", command=self.destroy, accelerator="Esc")
        file_menu.add_command(label="关闭", command=self.destroy)

        # Toplevel 快捷键
        self.bind("<Escape>", lambda e: self.destroy())

        # 核心初始化
        self._init_core(skill_name, effect_config)

        # 注册到单例字典（用于防重复创建）
        _NodeEditorBase._active_instances[skill_name] = self
        self._initialized = True

    def destroy(self):
        """销毁窗口时从单例字典中移除。"""
        _NodeEditorBase._active_instances.pop(self.skill_name, None)
        super().destroy()


class _NodeEditorFrame(tk.Frame, _NodeEditorBase):
    """嵌入模式节点编辑器（可作为子控件 pack/grid 到容器中）。"""

    def __init__(self, parent, skill_name, effect_config=None, **_kwargs):
        tk.Frame.__init__(self, parent)
        # 嵌入模式不设 title/geometry/menu/Escape→destroy

        # 核心初始化
        self._init_core(skill_name, effect_config)


# 向后兼容：NodeEditor 作为工厂类的公开名称
NodeEditor = _NodeEditorBase

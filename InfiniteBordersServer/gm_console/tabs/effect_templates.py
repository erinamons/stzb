# gm_console/tabs/effect_templates.py
# 战法效果模板库（从 ServerGMConsole 类属性独立为模块）
# 用于 GM 工具的战法效果配置参考

EFFECT_TEMPLATES = {
    # 基础机制 - 伤害类
    "主动·群体攻击伤害（无需准备）": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军群体"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "对【目标】造成攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
    },
    "主动·群体策略伤害（无需准备）": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军群体"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "对【目标】造成策略伤害（伤害率【伤害率】%），受谋略属性影响。"
    },
    "主动·群体攻击伤害（需准备1回合）": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "1回合准备，对【目标】造成攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
    },
    "主动·群体策略伤害（需准备1回合）": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "1回合准备，对【目标】造成策略伤害（伤害率【伤害率】%），受谋略属性影响。"
    },
    "主动·单体多次攻击": {
        "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "对敌军单体发动【次数】次攻击（每次伤害率【伤害率】%），每次目标独立判定。"
    },
    "主动·单体多次策略伤害": {
        "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "对敌军单体发动【次数】次策略伤害（每次伤害率【伤害率】%），每次目标独立判定。"
    },
    "追击·攻击伤害": {
        "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "普通攻击后，对目标发动攻击伤害（伤害率【伤害率】%），受攻击属性影响。"
    },
    "追击·策略伤害": {
        "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "普通攻击后，对目标发动策略伤害（伤害率【伤害率】%），受谋略属性影响。"
    },
    "被动·概率触发多次攻击": {
        "params": [{"name": "触发概率", "type": "number", "default": 30, "unit": "%"},
                   {"name": "次数", "type": "number", "default": 2, "unit": "次"},
                   {"name": "伤害率", "type": "number", "default": 80, "unit": "%"}],
        "description_template": "每回合有【触发概率】%的几率对敌军单体发动【次数】次攻击（每次伤害率【伤害率】%），自身无法发动主动战法。"
    },
    "分段/额外伤害": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军全体", "敌军群体"], "default": "敌军全体"},
                   {"name": "伤害率", "type": "number", "default": 100, "unit": "%"},
                   {"name": "额外伤害类型", "type": "choice", "options": ["火攻", "恐慌", "妖术"], "default": "火攻"},
                   {"name": "额外伤害率", "type": "number", "default": 80, "unit": "%"}],
        "description_template": "对【目标】造成策略伤害（伤害率【伤害率】%），并使目标在受到下一次伤害时额外引发【额外伤害类型】伤害（伤害率【额外伤害率】%）。"
    },

    # 控制类
    "控制·混乱": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】陷入混乱状态（无法行动，攻击目标随机），持续【持续时间】回合。"
    },
    "控制·犹豫": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】陷入犹豫状态（无法发动主动战法），持续【持续时间】回合。"
    },
    "控制·怯战": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】陷入怯战状态（无法进行普通攻击），持续【持续时间】回合。"
    },
    "控制·暴走": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】陷入暴走状态（攻击目标不分敌我），持续【持续时间】回合。"
    },
    "控制·禁疗": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军单体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】陷入禁疗状态（无法恢复兵力），持续【持续时间】回合。"
    },

    # 属性增减类
    "属性·提升友军": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                   {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                   {"name": "数值", "type": "number", "default": 20, "unit": "点"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使我军【目标】的【属性】属性提升【数值】点，持续【持续时间】回合。"
    },
    "属性·降低敌军": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                   {"name": "数值", "type": "number", "default": 20, "unit": "点"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使敌军【目标】的【属性】属性下降【数值】点，持续【持续时间】回合。"
    },
    "属性·吸取": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体"], "default": "敌军单体"},
                   {"name": "属性", "type": "choice", "options": ["攻击", "防御", "谋略", "速度"], "default": "攻击"},
                   {"name": "数值", "type": "number", "default": 15, "unit": "点"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "吸取【目标】【属性】各【数值】点，附加于自身和友军单体，持续【持续时间】回合。"
    },

    # 伤害增减类
    "伤害·提升友军": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                   {"name": "伤害类型", "type": "choice", "options": ["攻击伤害", "策略伤害", "追击战法伤害", "主动战法伤害"], "default": "攻击伤害"},
                   {"name": "提升幅度", "type": "number", "default": 20, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使我军【目标】的【伤害类型】提升【提升幅度】%，持续【持续时间】回合。"
    },
    "伤害·降低敌军": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "伤害类型", "type": "choice", "options": ["攻击伤害", "策略伤害"], "default": "攻击伤害"},
                   {"name": "降低幅度", "type": "number", "default": 20, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使敌军【目标】的【伤害类型】降低【降低幅度】%，持续【持续时间】回合。"
    },

    # 增益状态类
    "状态·先手": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【目标】进入先手状态（行动顺序优先），持续【持续时间】回合。"
    },
    "状态·连击": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军单体"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【目标】获得连击效果（每回合可进行两次普通攻击），持续【持续时间】回合。"
    },
    "状态·洞察": {
        "params": [{"name": "目标", "type": "choice", "options": ["自身", "我军单体", "我军全体"], "default": "自身"},
                   {"name": "持续时间", "type": "choice", "options": ["常驻", "2回合", "3回合", "4回合"], "default": "常驻"}],
        "description_template": "使【目标】进入洞察状态（免疫所有控制效果），持续【持续时间】。"
    },
    "状态·规避（1次）": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军全体"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "使【目标】进入规避状态（免疫1次伤害），持续【持续时间】回合。"
    },
    "状态·规避（多次）": {
        "params": [{"name": "次数", "type": "number", "default": 2, "unit": "次"}],
        "description_template": "使我军全体进入规避状态（免疫接下来受到的【次数】次伤害）。"
    },
    "状态·援护": {
        "params": [{"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使自身进入援护状态（为友军全体抵挡普通攻击），持续【持续时间】回合。"
    },
    "状态·援护（交替）": {
        "params": [],
        "description_template": "前锋和中军会交替进入援护状态（为友军群体抵挡普通攻击）。"
    },

    # 恢复类
    "恢复·兵力": {
        "params": [{"name": "目标", "type": "choice", "options": ["我军单体", "我军群体", "我军全体"], "default": "我军单体"},
                   {"name": "恢复率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "恢复【目标】兵力（恢复率【恢复率】%，受谋略属性影响）。"
    },
    "恢复·移除有害效果": {
        "params": [],
        "description_template": "移除我军全体有害效果。"
    },

    # 反击类
    "反击": {
        "params": [{"name": "位置", "type": "choice", "options": ["前锋", "中军", "全体"], "default": "前锋"},
                   {"name": "伤害率", "type": "number", "default": 60, "unit": "%"},
                   {"name": "伤害类型", "type": "choice", "options": ["攻击", "策略"], "default": "攻击"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【位置】受到普通攻击时进行反击（伤害率【伤害率】%，类型为【伤害类型】），持续【持续时间】回合。"
    },

    # 持续伤害类
    "持续·恐慌": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【目标】陷入恐慌状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
    },
    "持续·妖术": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【目标】陷入妖术状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
    },
    "持续·燃烧": {
        "params": [{"name": "目标", "type": "choice", "options": ["敌军单体", "敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "伤害率", "type": "number", "default": 80, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "使【目标】陷入燃烧状态（每回合损失兵力，伤害率【伤害率】%），持续【持续时间】回合。"
    },
    "持续·火攻": {
        "params": [{"name": "伤害率", "type": "number", "default": 100, "unit": "%"},
                   {"name": "提升幅度", "type": "number", "default": 5, "unit": "%"}],
        "description_template": "对敌军单体造成火攻伤害（伤害率【伤害率】%），并使目标受到的火攻和持续性伤害提升【提升幅度】%（可叠加）。"
    },

    # 其他基础机制
    "士气·降低敌军": {
        "params": [{"name": "数值", "type": "number", "default": 10, "unit": "点"}],
        "description_template": "使敌军士气降低【数值】点。"
    },
    "士气·提升我军": {
        "params": [{"name": "数值", "type": "number", "default": 8, "unit": "点"}],
        "description_template": "使我军全体每回合开始时士气提升【数值】点。"
    },
    "跳过准备回合（自身）": {
        "params": [{"name": "跳过几率", "type": "number", "default": 80, "unit": "%"}],
        "description_template": "每当自身发动需要准备的主战法时，有【跳过几率】%几率跳过准备回合。"
    },
    "跳过准备回合（友军）": {
        "params": [{"name": "跳过几率", "type": "number", "default": 75, "unit": "%"}],
        "description_template": "使友军单体主战法有【跳过几率】%的几率跳过1回合准备时间。"
    },
    "发动率提升（主动）": {
        "params": [{"name": "目标", "type": "choice", "options": ["友军单体", "友军群体"], "default": "友军单体"},
                   {"name": "提升幅度", "type": "number", "default": 120, "unit": "%"}],
        "description_template": "使【目标】在1回合内主动主战法发动率提高【提升幅度】%（可超过100%）。"
    },
    "发动率提升（追击）": {
        "params": [{"name": "提升幅度", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "使我军群体追击战法发动率提升【提升幅度】%。"
    },
    "伤害递增": {
        "params": [{"name": "增加率", "type": "number", "default": 40, "unit": "%"}],
        "description_template": "每次发动后，伤害率增加【增加率】%。"
    },
    "无视防御/规避": {
        "params": [],
        "description_template": "造成的伤害无视防御/规避。"
    },

    # 复合机制
    "复合·控制/减益结束后触发伤害/增益": {
        "params": [{"name": "生效回合", "type": "number", "default": 2, "unit": "回合"},
                   {"name": "控制类型", "type": "choice", "options": ["怯战", "犹豫", "混乱", "暴走", "禁疗"], "default": "怯战"},
                   {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "控制持续时间", "type": "number", "default": 2, "unit": "回合"},
                   {"name": "后续伤害类型", "type": "choice", "options": ["攻击", "策略"], "default": "策略"},
                   {"name": "后续伤害率", "type": "number", "default": 215, "unit": "%"},
                   {"name": "无视规避", "type": "choice", "options": ["否", "是"], "default": "是"}],
        "description_template": "战斗开始后前【生效回合】回合，使【控制目标】陷入【控制类型】状态，持续【控制持续时间】回合。效果结束后，对敌军全体发动一次【后续伤害类型】攻击（伤害率【后续伤害率】%）" + "，造成的伤害无视规避" + "。"
    },
    "复合·每回合概率怯战/犹豫": {
        "params": [{"name": "生效回合", "type": "number", "default": 3, "unit": "回合"},
                   {"name": "控制类型", "type": "choice", "options": ["怯战", "犹豫"], "default": "怯战"},
                   {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "触发概率", "type": "number", "default": 90, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 1, "unit": "回合"}],
        "description_template": "战斗开始后前【生效回合】回合，使【控制目标】每回合有【触发概率】%的几率陷入【控制类型】状态，持续【持续时间】回合。"
    },
    "复合·首回合犹豫+后续降伤": {
        "params": [{"name": "生效回合", "type": "number", "default": 3, "unit": "回合"},
                   {"name": "控制目标", "type": "choice", "options": ["敌军群体", "敌军全体"], "default": "敌军群体"},
                   {"name": "首回合几率", "type": "number", "default": 100, "unit": "%"}],
        "description_template": "战斗开始后前【生效回合】回合，使【控制目标】发动主动战法时造成的伤害大幅下降，并在首回合有【首回合几率】%的几率使其陷入犹豫状态，无法发动主动战法。"
    },
    "复合·特定回合自身行动时施加增益/减益": {
        "params": [{"name": "触发回合", "type": "string", "default": "2,4,6", "description": "逗号分隔的回合数"},
                   {"name": "目标", "type": "choice", "options": ["我军全体", "我军群体"], "default": "我军全体"},
                   {"name": "效果", "type": "choice", "options": ["属性提升", "减伤"], "default": "属性提升"},
                   {"name": "属性1", "type": "choice", "options": ["谋略", "防御", "攻击", "速度"], "default": "谋略"},
                   {"name": "属性2", "type": "choice", "options": ["谋略", "防御", "攻击", "速度"], "default": "防御"},
                   {"name": "属性值", "type": "number", "default": 80, "unit": "点"},
                   {"name": "减伤幅度", "type": "number", "default": 20, "unit": "%"},
                   {"name": "持续时间", "type": "number", "default": 2, "unit": "回合"}],
        "description_template": "第【触发回合】回合自身行动时，使【目标】【效果】。"
    },
    "复合·每回合概率触发多层效果": {
        "params": [{"name": "触发概率", "type": "number", "default": 30, "unit": "%"},
                   {"name": "伤害率1", "type": "number", "default": 180, "unit": "%"},
                   {"name": "伤害率2", "type": "number", "default": 150, "unit": "%"}],
        "description_template": "每回合行动时有【触发概率】%几率对敌军大营和中军分别发动一次攻击（伤害率【伤害率1】%），同时使速度最高的友军单体对敌军大营及中军分别发动一次攻击（伤害率【伤害率2】%）。"
    },
    "复合·次数累计提升几率": {
        "params": [{"name": "累计次数", "type": "number", "default": 3, "unit": "次"},
                   {"name": "提升几率", "type": "number", "default": 5, "unit": "%"}],
        "description_template": "该效果每生效【累计次数】次后，生效几率提升【提升几率】%，可叠加。"
    },
    "复合·累计伤害次数触发": {
        "params": [{"name": "累计伤害次数", "type": "number", "default": 15, "unit": "次"},
                   {"name": "效果描述", "type": "string", "default": "触发效果"}],
        "description_template": "敌军全体累计造成【累计伤害次数】次伤害后，下回合自身发动：【效果描述】。"
    },
    "复合·兵力阈值触发额外伤害/恢复": {
        "params": [{"name": "阈值", "type": "number", "default": 50, "unit": "%"},
                   {"name": "比较方向", "type": "choice", "options": ["高于", "低于"], "default": "高于"},
                   {"name": "额外效果", "type": "choice", "options": ["伤害", "恢复"], "default": "伤害"},
                   {"name": "额外伤害率", "type": "number", "default": 86, "unit": "%"},
                   {"name": "恢复率", "type": "number", "default": 82, "unit": "%"}],
        "description_template": "对敌军群体造成策略攻击（伤害率【伤害率】%）并使其陷入燃烧状态，当目标兵力【比较方向】初始兵力【阈值】%时受到一次策略伤害（【额外伤害率】%）；同时使我军群体恢复兵力（恢复率【恢复率】%），当目标兵力【比较方向】初始兵力【阈值】%时恢复兵力（【恢复率】%）。"
    },
    "复合·宝物类型判定": {
        "params": [{"name": "伤害率", "type": "number", "default": 280, "unit": "%"}],
        "description_template": "对敌军群体发动攻击（伤害率【伤害率】%）。当授予不同宝物时，额外获得：剑-移除增益；刀-自身攻击伤害提升12%；长兵-目标攻击距离-1；弓-50%几率目标+1；其他-目标防御降低30%。"
    },
    "复合·回合数影响目标/效果": {
        "params": [{"name": "间隔回合", "type": "number", "default": 2, "unit": "回合"},
                   {"name": "效果描述", "type": "string", "default": "获得效果"},
                   {"name": "切换回合", "type": "number", "default": 3, "unit": "回合"}],
        "description_template": "每【间隔回合】回合使友军单体【效果描述】；第【切换回合】回合发动时目标调整为友军全体。"
    },
}

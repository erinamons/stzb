# building_configs.py — 主城建筑系统完整配置数据
#
# 包含30个建筑的定义、解锁条件、每级升级消耗和效果。
# 此数据由 GM 后台加载写入数据库，代码中不硬编码业务逻辑。
#
# 消耗数据来源：
#   - 城主府/校场/前锋营/封禅台/兵营：用户提供的《建筑升级配置总表.md》
#   - 其余建筑：按同类倍率递增公式生成合理默认值（可在 GM 后台手动调整）
#
# effects JSON 说明：
#   palace:    {"durability": int, "cost_cap": float}
#   training_ground: {"troop_slots": int}
#   vanguard_camp: {"vanguard_slots": int}
#   barracks:  {"troop_capacity": int}
#   camp_speed: {"speed_bonus": int}
#   camp_defense: {"defense_bonus": int}
#   camp_strategy: {"strategy_bonus": int}
#   martial_hall: {"attack_bonus": int}
#   residence: {"copper_per_hour": int}
#   lumber_mill: {"wood_per_hour": int}
#   iron_smelter: {"iron_per_hour": int}
#   flour_mill: {"grain_per_hour": int}
#   quarry: {"stone_per_hour": int}
#   warehouse: {"storage_cap": int}
#   recruitment: {"recruit_speed_bonus": int}
#   reserve_camp: {"reserve_cap": int}
#   city_wall: {"wall_durability": int}
#   parapet: {"damage_reduction": float}
#   watchtower: {"vision_range": int}
#   beacon_tower: {"vision_range": int}
#   garrison_hall: {"garrison_bonus": int}
#   altar_*: {"faction_bonus_atk": int, "faction_bonus_def": int, "faction_bonus_spd": int, "faction_bonus_strg": int}
#   hero_statue: {"physical_damage_reduction": float, "attack_bonus": int}
#   sandbox_map: {"strategy_damage_reduction": float, "strategy_bonus": int}
#   fengshan_altar: {"cost_cap_bonus": float}
#   altar_state: {"fame_cap": int}


# ============================================================
# 工具函数：倍率递增生成消耗
# ============================================================
def _gen_costs(base_wood, base_iron, base_stone, levels,
               base_grain=0, base_copper=0, multiplier=1.6):
    """
    按倍率递增生成每级消耗列表。
    multiplier 控制每级递增倍率（默认1.6倍）。
    返回: [(wood, iron, stone, grain, copper), ...]
    """
    costs = []
    for i in range(levels):
        m = multiplier ** i
        costs.append((
            int(base_wood * m),
            int(base_iron * m),
            int(base_stone * m),
            int(base_grain * m),
            int(base_copper * m),
        ))
    return costs


# ============================================================
# 30 个建筑定义
# ============================================================
BUILDING_DEFINITIONS = [
    # ========================================================
    # 城主府（核心建筑，layout_row=0 居顶）
    # ========================================================
    {
        "building_key": "palace",
        "building_name": "城主府",
        "category": "core",
        "unlock_palace_level": 0,
        "max_level": 8,
        "sort_order": 0,
        "description": "主城核心建筑，提升税收、城池耐久、部队COST上限",
        "prerequisites": [],
        "layout_row": 0,
        "layout_col": 0,
        # 已配置的精确消耗数据（来自用户配置表）
        "level_data": [
            # (wood, iron, stone, grain, copper, effects_dict)
            (0, 0, 0, 0, 0,
             {"durability": 500, "cost_cap": 8.0}),
            (2500, 2500, 5000, 0, 0,
             {"durability": 650, "cost_cap": 8.0}),
            (6000, 6000, 15000, 0, 0,
             {"durability": 800, "cost_cap": 8.0}),
            (14000, 15000, 35000, 0, 0,
             {"durability": 950, "cost_cap": 8.0}),
            (30500, 31500, 60000, 0, 0,
             {"durability": 1100, "cost_cap": 8.0}),
            (55500, 57500, 125000, 0, 0,
             {"durability": 1250, "cost_cap": 8.0}),
            (120000, 134000, 277500, 0, 0,
             {"durability": 1400, "cost_cap": 8.0}),
            (200500, 236500, 522500, 0, 0,
             {"durability": 1600, "cost_cap": 8.5}),
        ],
    },

    # ========================================================
    # 壹级解锁（layout_row=1）
    # ========================================================
    {
        "building_key": "training_ground",
        "building_name": "校场",
        "category": "military",
        "unlock_palace_level": 1,
        "max_level": 5,
        "sort_order": 1,
        "description": "配置出征部队，提升可出征队伍数量",
        "prerequisites": [],
        "layout_row": 1,
        "layout_col": 0,
        "level_data": [
            (2000, 2000, 2000, 0, 0, {"troop_slots": 1}),
            (3500, 3500, 5000, 0, 0, {"troop_slots": 2}),
            (6700, 5200, 12000, 0, 0, {"troop_slots": 3}),
            (24600, 16400, 36200, 0, 0, {"troop_slots": 4}),
            (56200, 37400, 82700, 0, 0, {"troop_slots": 5}),
        ],
    },
    {
        "building_key": "residence",
        "building_name": "民居",
        "category": "resource",
        "unlock_palace_level": 1,
        "max_level": 20,
        "sort_order": 2,
        "description": "产出铜钱税收，提升每小时铜钱产量",
        "prerequisites": [],
        "layout_row": 1,
        "layout_col": 1,
        "level_data": None,  # 自动生成
        "auto_gen": {
            "base_wood": 500, "base_iron": 300, "base_stone": 800,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"copper_per_hour": 50 + lv * 50},
        },
    },

    # ========================================================
    # 贰级解锁（layout_row=2）
    # ========================================================
    {
        "building_key": "camp_speed",
        "building_name": "疾风营",
        "category": "military",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 1,
        "description": "提升部队速度属性",
        "prerequisites": [],
        "layout_row": 2,
        "layout_col": 0,
        "level_data": None,
        "auto_gen": {
            "base_wood": 1000, "base_iron": 1000, "base_stone": 1500,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"speed_bonus": lv * 3},
        },
    },
    {
        "building_key": "camp_defense",
        "building_name": "铁壁营",
        "category": "military",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 2,
        "description": "提升部队防御属性",
        "prerequisites": [],
        "layout_row": 2,
        "layout_col": 1,
        "level_data": None,
        "auto_gen": {
            "base_wood": 1000, "base_iron": 1200, "base_stone": 1500,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"defense_bonus": lv * 3},
        },
    },
    {
        "building_key": "recruitment",
        "building_name": "募兵所",
        "category": "military",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 3,
        "description": "征兵、缩短征兵时间，提升征兵效率",
        "prerequisites": [{"key": "training_ground", "level": 2}],
        "layout_row": 2,
        "layout_col": 2,
        "level_data": None,
        "auto_gen": {
            "base_wood": 1200, "base_iron": 800, "base_stone": 2000,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"recruit_speed_bonus": lv * 5},
        },
    },
    {
        "building_key": "warehouse",
        "building_name": "仓库",
        "category": "resource",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 4,
        "description": "提升资源存储上限，防止资源爆仓",
        "prerequisites": [{"key": "residence", "level": 1}],
        "layout_row": 2,
        "layout_col": 3,
        "level_data": None,
        "auto_gen": {
            "base_wood": 800, "base_iron": 600, "base_stone": 1200,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"storage_cap": 50000 + lv * 10000},
        },
    },
    {
        "building_key": "lumber_mill",
        "building_name": "伐木场",
        "category": "resource",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 5,
        "description": "产出木材资源，提升每小时木材产量",
        "prerequisites": [],
        "layout_row": 2,
        "layout_col": 4,
        "level_data": None,
        "auto_gen": {
            "base_wood": 600, "base_iron": 400, "base_stone": 500,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"wood_per_hour": 80 + lv * 40},
        },
    },
    {
        "building_key": "iron_smelter",
        "building_name": "炼铁场",
        "category": "resource",
        "unlock_palace_level": 2,
        "max_level": 20,
        "sort_order": 6,
        "description": "产出铁矿资源，提升每小时铁矿产量",
        "prerequisites": [],
        "layout_row": 2,
        "layout_col": 5,
        "level_data": None,
        "auto_gen": {
            "base_wood": 500, "base_iron": 300, "base_stone": 600,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"iron_per_hour": 60 + lv * 35},
        },
    },

    # ========================================================
    # 叁级解锁（layout_row=3）
    # ========================================================
    {
        "building_key": "camp_strategy",
        "building_name": "军机营",
        "category": "military",
        "unlock_palace_level": 3,
        "max_level": 20,
        "sort_order": 1,
        "description": "提升部队谋略属性",
        "prerequisites": [],
        "layout_row": 3,
        "layout_col": 0,
        "level_data": None,
        "auto_gen": {
            "base_wood": 1500, "base_iron": 1000, "base_stone": 2000,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"strategy_bonus": lv * 3},
        },
    },
    {
        "building_key": "martial_hall",
        "building_name": "尚武营",
        "category": "military",
        "unlock_palace_level": 3,
        "max_level": 20,
        "sort_order": 2,
        "description": "提升部队攻击属性",
        "prerequisites": [],
        "layout_row": 3,
        "layout_col": 1,
        "level_data": None,
        "auto_gen": {
            "base_wood": 1500, "base_iron": 1000, "base_stone": 2000,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"attack_bonus": lv * 3},
        },
    },
    {
        "building_key": "flour_mill",
        "building_name": "磨坊",
        "category": "resource",
        "unlock_palace_level": 3,
        "max_level": 20,
        "sort_order": 3,
        "description": "产出粮草资源，提升每小时粮草产量",
        "prerequisites": [],
        "layout_row": 3,
        "layout_col": 2,
        "level_data": None,
        "auto_gen": {
            "base_wood": 600, "base_iron": 400, "base_stone": 500,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"grain_per_hour": 100 + lv * 50},
        },
    },
    {
        "building_key": "quarry",
        "building_name": "采石场",
        "category": "resource",
        "unlock_palace_level": 3,
        "max_level": 20,
        "sort_order": 4,
        "description": "产出石料资源，提升每小时石料产量",
        "prerequisites": [],
        "layout_row": 3,
        "layout_col": 3,
        "level_data": None,
        "auto_gen": {
            "base_wood": 500, "base_iron": 500, "base_stone": 300,
            "levels": 20, "multiplier": 1.45,
            "effect_fn": lambda lv: {"stone_per_hour": 70 + lv * 35},
        },
    },

    # ========================================================
    # 肆级解锁（layout_row=4）
    # ========================================================
    {
        "building_key": "altar_han",
        "building_name": "点将台（汉）",
        "category": "special",
        "unlock_palace_level": 4,
        "max_level": 10,
        "sort_order": 1,
        "description": "汉阵营武将属性加成，提升汉阵营武将全属性",
        "prerequisites": [],
        "layout_row": 4,
        "layout_col": 0,
        "level_data": None,
        "auto_gen": {
            "base_wood": 5000, "base_iron": 5000, "base_stone": 8000,
            "levels": 10, "multiplier": 1.7,
            "effect_fn": lambda lv: {
                "faction_bonus_atk": lv * 2,
                "faction_bonus_def": lv * 2,
                "faction_bonus_strg": lv * 1,
                "faction_bonus_spd": lv * 1,
            },
        },
    },
    {
        "building_key": "vanguard_camp",
        "building_name": "前锋营",
        "category": "military",
        "unlock_palace_level": 4,
        "max_level": 5,
        "sort_order": 2,
        "description": "解锁部队前锋武将位置，可组建三人部队",
        "prerequisites": [],
        "layout_row": 4,
        "layout_col": 1,
        "level_data": [
            (8300, 5800, 8400, 0, 0, {"vanguard_slots": 1}),
            (26900, 18900, 32700, 0, 0, {"vanguard_slots": 2}),
            (60600, 42600, 73600, 0, 0, {"vanguard_slots": 3}),
            (164600, 123800, 188800, 0, 0, {"vanguard_slots": 4}),
            (252100, 190600, 287600, 0, 0, {"vanguard_slots": 5}),
        ],
    },
    {
        "building_key": "city_wall",
        "building_name": "城墙",
        "category": "defense",
        "unlock_palace_level": 4,
        "max_level": 5,
        "sort_order": 3,
        "description": "提升城池基础耐久，增强城池基础防御",
        "prerequisites": [],
        "layout_row": 4,
        "layout_col": 2,
        "level_data": [
            (10000, 8000, 15000, 0, 0, {"wall_durability": 2000, "defense_bonus": 5}),
            (25000, 20000, 40000, 0, 0, {"wall_durability": 4000, "defense_bonus": 10}),
            (55000, 45000, 90000, 0, 0, {"wall_durability": 7000, "defense_bonus": 18}),
            (120000, 100000, 200000, 0, 0, {"wall_durability": 11000, "defense_bonus": 28}),
            (250000, 210000, 420000, 0, 0, {"wall_durability": 16000, "defense_bonus": 40}),
        ],
    },

    # ========================================================
    # 伍级解锁（layout_row=5）
    # ========================================================
    {
        "building_key": "altar_wei",
        "building_name": "点将台（魏）",
        "category": "special",
        "unlock_palace_level": 5,
        "max_level": 10,
        "sort_order": 1,
        "description": "魏阵营武将属性加成，提升魏阵营武将全属性",
        "prerequisites": [],
        "layout_row": 5,
        "layout_col": 0,
        "level_data": None,
        "auto_gen": {
            "base_wood": 8000, "base_iron": 8000, "base_stone": 12000,
            "levels": 10, "multiplier": 1.7,
            "effect_fn": lambda lv: {
                "faction_bonus_atk": lv * 2,
                "faction_bonus_def": lv * 2,
                "faction_bonus_strg": lv * 1,
                "faction_bonus_spd": lv * 1,
            },
        },
    },
    {
        "building_key": "altar_shu",
        "building_name": "点将台（蜀）",
        "category": "special",
        "unlock_palace_level": 5,
        "max_level": 10,
        "sort_order": 2,
        "description": "蜀阵营武将属性加成，提升蜀阵营武将全属性",
        "prerequisites": [],
        "layout_row": 5,
        "layout_col": 1,
        "level_data": None,
        "auto_gen": {
            "base_wood": 8000, "base_iron": 8000, "base_stone": 12000,
            "levels": 10, "multiplier": 1.7,
            "effect_fn": lambda lv: {
                "faction_bonus_atk": lv * 2,
                "faction_bonus_def": lv * 2,
                "faction_bonus_strg": lv * 1,
                "faction_bonus_spd": lv * 1,
            },
        },
    },
    {
        "building_key": "altar_wu",
        "building_name": "点将台（吴）",
        "category": "special",
        "unlock_palace_level": 5,
        "max_level": 10,
        "sort_order": 3,
        "description": "吴阵营武将属性加成，提升吴阵营武将全属性",
        "prerequisites": [],
        "layout_row": 5,
        "layout_col": 2,
        "level_data": None,
        "auto_gen": {
            "base_wood": 8000, "base_iron": 8000, "base_stone": 12000,
            "levels": 10, "multiplier": 1.7,
            "effect_fn": lambda lv: {
                "faction_bonus_atk": lv * 2,
                "faction_bonus_def": lv * 2,
                "faction_bonus_strg": lv * 1,
                "faction_bonus_spd": lv * 1,
            },
        },
    },
    {
        "building_key": "market",
        "building_name": "集市",
        "category": "special",
        "unlock_palace_level": 5,
        "max_level": 1,
        "sort_order": 4,
        "description": "解锁资源兑换功能，实现四大资源互换",
        "prerequisites": [],
        "layout_row": 5,
        "layout_col": 3,
        "level_data": [
            (15000, 12000, 25000, 0, 0, {"exchange_enabled": True}),
        ],
    },
    {
        "building_key": "watchtower",
        "building_name": "警戒所",
        "category": "defense",
        "unlock_palace_level": 5,
        "max_level": 10,
        "sort_order": 5,
        "description": "扩大城池视野，预警来袭敌军",
        "prerequisites": [{"key": "city_wall", "level": 2}],
        "layout_row": 5,
        "layout_col": 4,
        "level_data": None,
        "auto_gen": {
            "base_wood": 6000, "base_iron": 4000, "base_stone": 8000,
            "levels": 10, "multiplier": 1.6,
            "effect_fn": lambda lv: {"vision_range": 2 + lv},
        },
    },
    {
        "building_key": "parapet",
        "building_name": "女墙",
        "category": "defense",
        "unlock_palace_level": 5,
        "max_level": 6,
        "sort_order": 6,
        "description": "强化城墙防御，降低攻城伤害",
        "prerequisites": [{"key": "city_wall", "level": 5}],
        "layout_row": 5,
        "layout_col": 5,
        "level_data": [
            (30000, 25000, 50000, 0, 0, {"damage_reduction": 3.0}),
            (50000, 42000, 85000, 0, 0, {"damage_reduction": 6.0}),
            (80000, 68000, 140000, 0, 0, {"damage_reduction": 10.0}),
            (120000, 100000, 210000, 0, 0, {"damage_reduction": 15.0}),
            (180000, 150000, 320000, 0, 0, {"damage_reduction": 20.0}),
            (260000, 220000, 460000, 0, 0, {"damage_reduction": 25.0}),
        ],
    },

    # ========================================================
    # 陆级解锁（layout_row=6）
    # ========================================================
    {
        "building_key": "altar_meng",
        "building_name": "点将台（群）",
        "category": "special",
        "unlock_palace_level": 6,
        "max_level": 10,
        "sort_order": 1,
        "description": "群雄阵营武将属性加成，提升群雄阵营武将全属性",
        "prerequisites": [
            {"key": "altar_wei", "level": 1},
            {"key": "altar_shu", "level": 1},
            {"key": "altar_wu", "level": 1},
        ],
        "layout_row": 6,
        "layout_col": 0,
        "level_data": None,
        "auto_gen": {
            "base_wood": 15000, "base_iron": 15000, "base_stone": 25000,
            "levels": 10, "multiplier": 1.7,
            "effect_fn": lambda lv: {
                "faction_bonus_atk": lv * 2,
                "faction_bonus_def": lv * 2,
                "faction_bonus_strg": lv * 1,
                "faction_bonus_spd": lv * 1,
            },
        },
    },
    {
        "building_key": "reserve_camp",
        "building_name": "预备役所",
        "category": "military",
        "unlock_palace_level": 6,
        "max_level": 20,
        "sort_order": 2,
        "description": "提升预备兵存储上限，储存更多预备兵",
        "prerequisites": [],
        "layout_row": 6,
        "layout_col": 1,
        "level_data": None,
        "auto_gen": {
            "base_wood": 8000, "base_iron": 6000, "base_stone": 10000,
            "levels": 20, "multiplier": 1.5,
            "effect_fn": lambda lv: {"reserve_cap": 500 + lv * 500},
        },
    },
    {
        "building_key": "beacon_tower",
        "building_name": "烽火台",
        "category": "defense",
        "unlock_palace_level": 6,
        "max_level": 5,
        "sort_order": 3,
        "description": "远程预警，同盟共享敌军情报",
        "prerequisites": [{"key": "watchtower", "level": 3}],
        "layout_row": 6,
        "layout_col": 2,
        "level_data": [
            (20000, 15000, 30000, 0, 0, {"vision_range": 5, "alliance_share": True}),
            (40000, 30000, 65000, 0, 0, {"vision_range": 8, "alliance_share": True}),
            (70000, 55000, 120000, 0, 0, {"vision_range": 12, "alliance_share": True}),
            (120000, 95000, 210000, 0, 0, {"vision_range": 16, "alliance_share": True}),
            (200000, 160000, 350000, 0, 0, {"vision_range": 20, "alliance_share": True}),
        ],
    },
    {
        "building_key": "garrison_hall",
        "building_name": "守将府",
        "category": "defense",
        "unlock_palace_level": 6,
        "max_level": 3,
        "sort_order": 4,
        "description": "配置守城武将，提升城池守军强度",
        "prerequisites": [{"key": "watchtower", "level": 5}],
        "layout_row": 6,
        "layout_col": 3,
        "level_data": [
            (30000, 25000, 50000, 0, 0, {"garrison_bonus": 10}),
            (80000, 65000, 130000, 0, 0, {"garrison_bonus": 25}),
            (200000, 170000, 350000, 0, 0, {"garrison_bonus": 50}),
        ],
    },

    # ========================================================
    # 柒级解锁（layout_row=7）
    # ========================================================
    {
        "building_key": "barracks",
        "building_name": "兵营",
        "category": "military",
        "unlock_palace_level": 7,
        "max_level": 20,
        "sort_order": 1,
        "description": "提升武将带兵数量上限",
        "prerequisites": [],
        "layout_row": 7,
        "layout_col": 0,
        "level_data": [
            (20000, 22000, 33700, 0, 0, {"troop_capacity": 200}),
            (23500, 25800, 39000, 0, 0, {"troop_capacity": 400}),
            (27000, 29700, 44200, 0, 0, {"troop_capacity": 600}),
            (30500, 33500, 49500, 0, 0, {"troop_capacity": 800}),
            (34000, 37400, 54700, 0, 0, {"troop_capacity": 1000}),
            (37500, 41200, 60000, 0, 0, {"troop_capacity": 1200}),
            (41000, 45100, 65200, 0, 0, {"troop_capacity": 1400}),
            (44500, 48900, 70500, 0, 0, {"troop_capacity": 1600}),
            (48000, 52800, 75700, 0, 0, {"troop_capacity": 1800}),
            (51500, 56600, 81000, 0, 0, {"troop_capacity": 2000}),
            (55000, 60500, 86200, 0, 0, {"troop_capacity": 2300}),
            (58500, 64300, 91500, 0, 0, {"troop_capacity": 2600}),
            (64500, 68700, 105000, 0, 0, {"troop_capacity": 2900}),
            (96700, 103000, 157500, 0, 0, {"troop_capacity": 3200}),
            (145100, 142100, 232500, 0, 0, {"troop_capacity": 3500}),
            (207700, 203100, 338700, 0, 0, {"troop_capacity": 3800}),
            (272200, 266400, 436000, 0, 0, {"troop_capacity": 4100}),
            (328300, 325600, 509000, 0, 0, {"troop_capacity": 4400}),
            (378900, 386500, 623200, 0, 0, {"troop_capacity": 4700}),
            (428400, 439300, 724900, 0, 0, {"troop_capacity": 5000}),
        ],
    },
    {
        "building_key": "hero_statue",
        "building_name": "武将巨像",
        "category": "special",
        "unlock_palace_level": 7,
        "max_level": 5,
        "sort_order": 2,
        "description": "降低本城及城区部队受到的攻击伤害，受物理攻击伤害-20%，攻击+10",
        "prerequisites": [],
        "layout_row": 7,
        "layout_col": 1,
        "level_data": [
            (50000, 40000, 80000, 0, 0, {"physical_damage_reduction": 4.0, "attack_bonus": 2}),
            (80000, 65000, 130000, 0, 0, {"physical_damage_reduction": 8.0, "attack_bonus": 4}),
            (130000, 105000, 210000, 0, 0, {"physical_damage_reduction": 12.0, "attack_bonus": 6}),
            (200000, 165000, 330000, 0, 0, {"physical_damage_reduction": 16.0, "attack_bonus": 8}),
            (300000, 250000, 500000, 0, 0, {"physical_damage_reduction": 20.0, "attack_bonus": 10}),
        ],
    },
    {
        "building_key": "sandbox_map",
        "building_name": "沙盘阵图",
        "category": "special",
        "unlock_palace_level": 7,
        "max_level": 5,
        "sort_order": 3,
        "description": "降低本城及城区部队受到的策略攻击伤害，受策略/法术伤害-20%，谋略+10",
        "prerequisites": [],
        "layout_row": 7,
        "layout_col": 2,
        "level_data": [
            (50000, 40000, 80000, 0, 0, {"strategy_damage_reduction": 4.0, "strategy_bonus": 2}),
            (80000, 65000, 130000, 0, 0, {"strategy_damage_reduction": 8.0, "strategy_bonus": 4}),
            (130000, 105000, 210000, 0, 0, {"strategy_damage_reduction": 12.0, "strategy_bonus": 6}),
            (200000, 165000, 330000, 0, 0, {"strategy_damage_reduction": 16.0, "strategy_bonus": 8}),
            (300000, 250000, 500000, 0, 0, {"strategy_damage_reduction": 20.0, "strategy_bonus": 10}),
        ],
    },

    # ========================================================
    # 捌级解锁（layout_row=8）
    # ========================================================
    {
        "building_key": "fengshan_altar",
        "building_name": "封禅台",
        "category": "special",
        "unlock_palace_level": 8,
        "max_level": 3,
        "sort_order": 1,
        "description": "提升部队COST上限，可携带更高Cost武将组合",
        "prerequisites": [{"key": "barracks", "level": 10}],
        "layout_row": 8,
        "layout_col": 0,
        "level_data": [
            (67500, 60600, 117900, 0, 0, {"cost_cap_bonus": 0.5}),
            (152400, 137400, 265500, 0, 0, {"cost_cap_bonus": 1.0}),
            (377000, 340500, 656900, 0, 0, {"cost_cap_bonus": 1.5}),
        ],
    },
    {
        "building_key": "altar_state",
        "building_name": "社稷坛",
        "category": "special",
        "unlock_palace_level": 8,
        "max_level": 30,
        "sort_order": 2,
        "description": "提高名望（声望）上限，每级+600名望，可占领更多领地",
        "prerequisites": [
            {"key": "hero_statue", "level": 4},
            {"key": "sandbox_map", "level": 4},
        ],
        "layout_row": 8,
        "layout_col": 1,
        "level_data": None,
        "auto_gen": {
            "base_wood": 50000, "base_iron": 40000, "base_stone": 80000,
            "levels": 30, "multiplier": 1.5,
            "effect_fn": lambda lv: {"fame_cap": lv * 600},
        },
    },
]


# ============================================================
# 数据库加载函数
# ============================================================
def load_building_configs(db_session):
    """
    将建筑配置加载到数据库。
    如果 building_configs 表已有数据，则跳过（保护 GM 手动修改的配置）。
    返回 True=已加载，False=已存在跳过。
    """
    from models.schema import BuildingConfig, BuildingLevelConfig

    # 检查是否已有配置
    existing_count = db_session.query(BuildingConfig).count()
    if existing_count > 0:
        print(f"   建筑配置已存在（{existing_count}个），跳过加载")
        return False

    loaded_buildings = 0
    loaded_levels = 0

    for bdef in BUILDING_DEFINITIONS:
        # 插入建筑基础配置
        bc = BuildingConfig(
            building_key=bdef["building_key"],
            building_name=bdef["building_name"],
            category=bdef.get("category", "military"),
            unlock_palace_level=bdef["unlock_palace_level"],
            max_level=bdef["max_level"],
            sort_order=bdef.get("sort_order", 0),
            description=bdef.get("description", ""),
            prerequisites=bdef.get("prerequisites", []),
            layout_row=bdef.get("layout_row", 0),
            layout_col=bdef.get("layout_col", 0),
        )
        db_session.add(bc)
        loaded_buildings += 1

        # 插入每级配置
        if bdef.get("level_data"):
            # 使用精确配置数据
            for lv_idx, data in enumerate(bdef["level_data"]):
                wood, iron, stone, grain, copper, effects = data
                blc = BuildingLevelConfig(
                    building_key=bdef["building_key"],
                    level=lv_idx + 1,
                    cost_wood=wood,
                    cost_iron=iron,
                    cost_stone=stone,
                    cost_grain=grain,
                    cost_copper=copper,
                    effects=effects,
                )
                db_session.add(blc)
                loaded_levels += 1
        elif bdef.get("auto_gen"):
            # 自动生成消耗数据
            ag = bdef["auto_gen"]
            costs = _gen_costs(
                ag["base_wood"], ag["base_iron"], ag["base_stone"],
                ag["levels"], ag.get("base_grain", 0), ag.get("base_copper", 0),
                ag.get("multiplier", 1.5)
            )
            for lv_idx, (w, ir, st, gr, co) in enumerate(costs):
                effects = ag["effect_fn"](lv_idx + 1)
                blc = BuildingLevelConfig(
                    building_key=bdef["building_key"],
                    level=lv_idx + 1,
                    cost_wood=w,
                    cost_iron=ir,
                    cost_stone=st,
                    cost_grain=gr,
                    cost_copper=co,
                    effects=effects,
                )
                db_session.add(blc)
                loaded_levels += 1

    db_session.commit()
    print(f"   已加载 {loaded_buildings} 个建筑配置，{loaded_levels} 条等级配置")
    return True


def init_player_buildings(db_session, player_id: int, palace_level: int = 1):
    """
    为新玩家初始化建筑实例。
    根据城主府等级，解锁对应建筑（level=0 表示已解锁但未建造，需手动点击建造）。
    城主府本身直接设为指定等级（默认1级，已建造）。
    """
    from models.schema import BuildingConfig, PlayerBuilding

    # 获取所有建筑配置
    all_buildings = db_session.query(BuildingConfig).order_by(
        BuildingConfig.unlock_palace_level, BuildingConfig.sort_order
    ).all()

    for bc in all_buildings:
        if bc.building_key == "palace":
            # 城主府直接设等级
            pb = PlayerBuilding(
                player_id=player_id,
                building_key="palace",
                level=palace_level,
            )
        elif bc.unlock_palace_level <= palace_level:
            # 城主府等级够的建筑：解锁但未建造（level=0），需手动建造
            pb = PlayerBuilding(
                player_id=player_id,
                building_key=bc.building_key,
                level=0,
            )
        else:
            continue  # 未解锁的建筑不创建记录

        # 检查是否已存在
        existing = db_session.query(PlayerBuilding).filter(
            PlayerBuilding.player_id == player_id,
            PlayerBuilding.building_key == bc.building_key,
        ).first()
        if not existing:
            db_session.add(pb)

    db_session.commit()


def check_building_prerequisites(db_session, player_id: int, building_key: str) -> tuple:
    """
    检查建筑的前置条件是否满足。
    返回 (bool, str) — (是否满足, 不满足的原因描述)
    """
    from models.schema import BuildingConfig, PlayerBuilding

    bc = db_session.query(BuildingConfig).filter(
        BuildingConfig.building_key == building_key
    ).first()
    if not bc:
        return False, f"建筑 {building_key} 不存在"

    # 检查城主府等级
    palace_pb = db_session.query(PlayerBuilding).filter(
        PlayerBuilding.player_id == player_id,
        PlayerBuilding.building_key == "palace",
    ).first()
    if not palace_pb or palace_pb.level < bc.unlock_palace_level:
        return False, f"需要城主府 {bc.unlock_palace_level} 级"

    # 检查前置建筑
    if bc.prerequisites:
        for prereq in bc.prerequisites:
            req_key = prereq["key"]
            req_level = prereq["level"]
            req_pb = db_session.query(PlayerBuilding).filter(
                PlayerBuilding.player_id == player_id,
                PlayerBuilding.building_key == req_key,
            ).first()
            if not req_pb or req_pb.level < req_level:
                req_bc = db_session.query(BuildingConfig).filter(
                    BuildingConfig.building_key == req_key
                ).first()
                req_name = req_bc.building_name if req_bc else req_key
                return False, f"需要 {req_name} {req_level} 级"

    return True, ""

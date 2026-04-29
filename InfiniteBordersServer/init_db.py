import random
import os
from models.database import engine, Base, SessionLocal, DB_PATH
from models.schema import Player, Tile, HeroTemplate, CardPack, CardPackDrop, Troop, Skill, Hero, GmAdmin
from config import MAP_COLS, MAP_ROWS
from hex_utils import get_neighbors
from scenarios import FIXED_CITIES, FIXED_GATES, TERRAIN_PRESETS, TRIPLE_GATE_STATES, TRANSIT_GATE_STATES
from building_configs import load_building_configs, init_player_buildings



# 十三州中心坐标（六边形 offset 坐标 q=col, r=row）
REGION_CENTERS = {
    "司隶": (60, 45), "雍州": (36, 41), "兖州": (84, 36), "豫州": (66, 63),
    "凉州": (18, 22), "并州": (42, 14), "幽州": (90, 14), "冀州": (66, 18),
    "青州": (102, 27), "徐州": (102, 50), "扬州": (90, 77), "荆州": (42, 77), "益州": (18, 59)
}

# 州界合法连接（用于关口生成）
VALID_CONNECTIONS = [
    ("雍州", "司隶"), ("兖州", "司隶"), ("豫州", "司隶"),
    ("凉州", "雍州"), ("益州", "雍州"), ("并州", "雍州"),
    ("幽州", "兖州"), ("冀州", "兖州"), ("青州", "兖州"),
    ("徐州", "豫州"), ("扬州", "豫州"), ("荆州", "豫州"),
    ("凉州", "并州"), ("益州", "荆州"), ("幽州", "冀州"), ("青州", "徐州"), ("荆州", "扬州"),
    ("徐州", "兖州"),  # 补充连接
]


def get_region(q, r):
    """基于最近邻判断六边形格子属于哪个州"""
    min_d, res = 999999, "未知"
    for region, (cq, cr) in REGION_CENTERS.items():
        d = (q - cq) ** 2 + (r - cr) ** 2
        if d < min_d:
            min_d = d
            res = region
    return res


# ============================================================
# 各州土地等级权重分布
# ============================================================
REGION_LEVEL_WEIGHTS = {
    # 中心州（司隶、豫州、兖州、冀州、雍州）：6-9级为主
    "司隶": {1: 3, 2: 5, 3: 8, 4: 12, 5: 17, 6: 22, 7: 18, 8: 10, 9: 5},
    "豫州":  {1: 3, 2: 5, 3: 8, 4: 12, 5: 17, 6: 22, 7: 18, 8: 10, 9: 5},
    "兖州":  {1: 4, 2: 6, 3: 9, 4: 13, 5: 17, 6: 21, 7: 17, 8: 9, 9: 4},
    "冀州":  {1: 4, 2: 6, 3: 9, 4: 13, 5: 17, 6: 21, 7: 17, 8: 9, 9: 4},
    "雍州":  {1: 4, 2: 6, 3: 9, 4: 13, 5: 17, 6: 21, 7: 17, 8: 9, 9: 4},
    # 中间州（徐州、荆州、并州）：5-7级为主，7-9较少
    "徐州":  {1: 6, 2: 10, 3: 15, 4: 18, 5: 20, 6: 16, 7: 9, 8: 4, 9: 2},
    "荆州":  {1: 6, 2: 10, 3: 15, 4: 18, 5: 20, 6: 16, 7: 9, 8: 4, 9: 2},
    "并州":  {1: 6, 2: 10, 3: 15, 4: 18, 5: 20, 6: 16, 7: 9, 8: 4, 9: 2},
    # 边缘州（青州、益州）：4-6级为主，7-9少
    "青州":  {1: 8, 2: 14, 3: 18, 4: 22, 5: 18, 6: 12, 7: 5, 8: 2, 9: 1},
    "益州":  {1: 8, 2: 14, 3: 18, 4: 22, 5: 18, 6: 12, 7: 5, 8: 2, 9: 1},
    # 极边缘州（幽州、扬州、凉州）：以低级为主，7-9极少
    "幽州":  {1: 10, 2: 16, 3: 22, 4: 24, 5: 15, 6: 8, 7: 3, 8: 1.5, 9: 0.5},
    "扬州":  {1: 10, 2: 16, 3: 22, 4: 24, 5: 15, 6: 8, 7: 3, 8: 1.5, 9: 0.5},
    "凉州":  {1: 10, 2: 16, 3: 22, 4: 24, 5: 15, 6: 8, 7: 3, 8: 1.5, 9: 0.5},
}


def init_database(keep_templates=False):
    """初始化/重置数据库。

    Args:
        keep_templates: True 时只清玩家数据和地图，保留武将模板/战法/卡包/建筑配置等 GM 管理数据。
                        False 时全量重建（DROP ALL + CREATE ALL）。
    """
    if keep_templates:
        _reset_keep_templates()
    else:
        _reset_full()


def _reset_full():
    """全量重置：删库重建，所有数据重新初始化。"""
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _init_building_configs(db)
        _init_map(db)
        _init_seed_skills(db)
        _init_seed_heroes(db)
        _init_card_packs(db)
        _init_test_player(db)
        _init_default_gm_admin(db)
        _migrate_gm_permissions(db)
    finally:
        db.close()
    print("[OK] 数据库全量重置完成！")


def _reset_keep_templates():
    """轻量重置：只清玩家数据和地图，保留武将模板/战法/卡包/建筑配置。"""
    engine.dispose()
    db = SessionLocal()
    try:
        # 确保 GmAdmin 表存在（旧数据库可能没有这张表）
        GmAdmin.__table__.create(bind=engine, checkfirst=True)
        # 清空玩家相关数据（按外键依赖顺序）
        from models.schema import BattleReport
        for Model in (BattleReport, Troop, Hero, Player, Tile):
            db.query(Model).delete()
        db.commit()
        print("已清空玩家数据（武将/部队/玩家/地图/战报）")

        # 重建地图
        _init_map(db)

        # 重建测试玩家（引用已有的武将模板和战法）
        _init_test_player(db)

        # 确保默认超管存在
        _init_default_gm_admin(db)
        _migrate_gm_permissions(db)
    finally:
        db.close()
    print("[OK] 数据库轻量重置完成！（武将模板/战法/卡包/建筑配置已保留）")


# ============================================================
# 子步骤函数
# ============================================================

def _init_building_configs(db):
    """步骤0: 加载建筑配置。"""
    print("0. 加载建筑配置...")
    load_building_configs(db)


def _init_map(db):
    """初始化地图。小地图模式（≤20格）使用简化生成，大地图使用十三州版图。"""
    if MAP_COLS <= 20 or MAP_ROWS <= 20:
        _init_small_map(db)
    else:
        _init_full_map(db)


def _init_small_map(db):
    """10×10 简化测试地图：随机地形 + 几座城池 + 出生点保护。"""
    print(f"1. 生成 {MAP_COLS}×{MAP_ROWS} 简化测试地图...")

    # 地形权重
    terrain_pool = (
        ["PLAINS"] * 55 + ["WOODS"] * 20 +
        ["IRON"] * 10 + ["STONE"] * 10 + ["MOUNTAIN"] * 5
    )

    # 城池坐标 (col, row, name, level, type)
    small_cities = [
        (2, 2, "洛阳", 5, "郡城"),
        (8, 2, "邺城", 4, "县城"),
        (1, 7, "成都", 4, "县城"),
        (8, 8, "建业", 5, "郡城"),
        (5, 0, "虎牢关", 0, "关口"),
        (5, 9, "赤壁", 0, "关口"),
    ]
    city_set = {(q, r) for q, r, *_ in small_cities}

    tiles = []
    for r in range(MAP_ROWS):
        for q in range(MAP_COLS):
            # 出生点及周围保护（3×3 区域全为平原）
            if abs(q - 5) <= 1 and abs(r - 5) <= 1:
                terrain, level = "PLAINS", 3
            elif (q, r) in city_set:
                terrain, level = "PLAINS", 1  # 城池格子暂用占位值
            else:
                terrain = random.choice(terrain_pool)
                level = random.randint(1, 5)

            city_type = None
            city_name = None
            for cq, cr, cname, clevel, ctype in small_cities:
                if q == cq and r == cr:
                    city_type = ctype
                    city_name = cname
                    level = clevel
                    break

            tiles.append(Tile(
                x=q, y=r, terrain=terrain, level=level,
                region="", city_type=city_type, city_name=city_name
            ))

    db.bulk_save_objects(tiles)
    db.commit()
    print(f"   已生成 {len(tiles)} 格（{len(small_cities)} 座城池/关口）")


def _init_full_map(db):
    """步骤1-4: 划定十三州版图 → 州界山脉 → 关口 → 城池。"""
    # 步骤1: 划定十三州版图（六边形网格）
    print("1. 划定十三州版图（六边形网格）...")

    grid = {}
    for r in range(MAP_ROWS):
        for q in range(MAP_COLS):
            region = get_region(q, r)
            # 根据州的地形预设填充（默认平原为主）
            preset = TERRAIN_PRESETS.get(region, {"PLAINS": 0.5, "WOODS": 0.2, "IRON": 0.15, "STONE": 0.15})
            terrain = random.choices(
                list(preset.keys()),
                list(preset.values())
            )[0]
            # 根据州的等级权重随机土地等级（1~9级）
            weights = REGION_LEVEL_WEIGHTS.get(region, {1: 20, 2: 20, 3: 20, 4: 15, 5: 10, 6: 8, 7: 4, 8: 2, 9: 1})
            level = random.choices(
                list(weights.keys()),
                list(weights.values())
            )[0]
            grid[(q, r)] = {
                "q": q, "r": r,
                "region": region,
                "terrain": terrain,
                "level": level,
                "city_type": None,
                "city_name": None
            }

    # 步骤2: 州界山脉
    print("2. 隆起州界山脉...")

    # 先收集所有关口坐标（步骤3会用到）
    gate_coords = set()
    for (reg_a, reg_b), gates in FIXED_GATES.items():
        for gq, gr, gname in gates:
            gate_coords.add((gq, gr))

    for (q, r), cell in grid.items():
        region = cell["region"]
        for nq, nr in get_neighbors(q, r):
            if (nq, nr) in grid and grid[(nq, nr)]["region"] != region:
                # 跳过关口格子本身（关口将独立设置）
                if (q, r) not in gate_coords:
                    grid[(q, r)]["terrain"] = "MOUNTAIN"
                    grid[(q, r)]["level"] = 0
                break

    # 步骤3: 放置独立关口（位于州界中间）
    print("3. 放置独立关口...")

    # 预计算所有格子的 region（用于判断邻居所属州）
    tile_region = {}
    for (q, r), cell in grid.items():
        tile_region[(q, r)] = cell["region"]

    gate_count = 0
    for (reg_a, reg_b), gates in FIXED_GATES.items():
        for gq, gr, gname in gates:
            if (gq, gr) not in grid:
                print(f"   [WARN] {gname}({gq},{gr}) out of map!")
                continue

            # 设置关口格子：独立区域，不属于任何州
            grid[(gq, gr)]["terrain"] = "PLAINS"
            grid[(gq, gr)]["level"] = 7
            grid[(gq, gr)]["region"] = "关口"
            grid[(gq, gr)]["city_type"] = "关口"
            grid[(gq, gr)]["city_name"] = gname
            gate_count += 1

            # 确定需要连通的州方向
            if gname in TRIPLE_GATE_STATES:
                # 3格关口：连通3个州
                target_states = TRIPLE_GATE_STATES[gname]
            elif gname in TRANSIT_GATE_STATES:
                # 中转关口：连通两个目标州
                ta, tb, transit = TRANSIT_GATE_STATES[gname]
                target_states = [ta, tb]
            else:
                # 普通关口：连通两侧的两个州
                target_states = [reg_a, reg_b]

            # 从关口邻居中，为每个目标州找到最近的格子并打通通道
            opened = set()
            for target_state in target_states:
                # BFS：从关口的邻居开始，搜索到 target_state 的最短路径
                visited = set()
                queue = []
                for nq, nr in get_neighbors(gq, gr):
                    if (nq, nr) in grid and (nq, nr) not in visited:
                        visited.add((nq, nr))
                        queue.append((nq, nr, 0))  # (q, r, depth)

                found = False
                while queue and not found:
                    cq, cr, depth = queue.pop(0)
                    if depth > 2:  # 最多打通2格通道
                        break
                    if (cq, cr) in opened:
                        continue
                    if tile_region.get((cq, cr)) == target_state:
                        # 找到了！打通路径上的所有格子
                        # 回溯：从 (cq, cr) 回到关口需要经过的格子
                        # 简化：直接打通 (cq, cr) 和它的关口侧邻居
                        grid[(cq, cr)]["terrain"] = "PLAINS"
                        grid[(cq, cr)]["level"] = 1
                        opened.add((cq, cr))
                        # 也打通(cq,cr)朝关口方向的邻居（形成通道）
                        for nnq, nnr in get_neighbors(cq, cr):
                            if (nnq, nnr) in grid and (nnq, nnr) not in gate_coords:
                                grid[(nnq, nnr)]["terrain"] = "PLAINS"
                                grid[(nnq, nnr)]["level"] = 1
                                opened.add((nnq, nnr))
                        found = True
                        break
                    # 继续BFS
                    for nq, nr in get_neighbors(cq, cr):
                        if (nq, nr) in grid and (nq, nr) not in visited:
                            visited.add((nq, nr))
                            queue.append((nq, nr, depth + 1))

                if not found:
                    print(f"   [WARN] {gname} -> {target_state} channel not found")

            # 也直接打通关口的所有相邻山脉格子（确保关口本身可通行）
            for nq, nr in get_neighbors(gq, gr):
                if (nq, nr) in grid and grid[(nq, nr)]["terrain"] == "MOUNTAIN":
                    if (nq, nr) not in gate_coords:
                        grid[(nq, nr)]["terrain"] = "PLAINS"
                        grid[(nq, nr)]["level"] = 1

    print(f"   placed {gate_count} gates")

    # 步骤4: 使用固定坐标放置城池
    print("4. 放置三国城池（固定坐标）...")
    city_count = 0
    for region, cities in FIXED_CITIES.items():
        for q, r, name, level, city_type in cities:
            if (q, r) in grid:
                # 跳过已被关口占用的格子（双格关口可能占用了原县城位置）
                if grid[(q, r)].get("city_type") == "关口":
                    print(f"   跳过城池 {name}({q},{r})，已被关口 {grid[(q, r)]['city_name']} 占用")
                    continue
                # 城池格子强制为平原，不可能是山脉
                grid[(q, r)]["terrain"] = "PLAINS"
                grid[(q, r)]["level"] = level
                grid[(q, r)]["city_type"] = city_type
                grid[(q, r)]["city_name"] = name
                city_count += 1
            else:
                print(f"   ⚠️ 城池 {name}({q},{r}) 超出地图范围！")
    print(f"   已放置 {city_count} 座城池")

    db.bulk_save_objects([
        Tile(x=q, y=r,
             terrain=grid[(q, r)]["terrain"],
             level=grid[(q, r)]["level"],
             region=grid[(q, r)]["region"],
             city_type=grid[(q, r)]["city_type"],
             city_name=grid[(q, r)]["city_name"])
        for r in range(MAP_ROWS) for q in range(MAP_COLS)
    ])
    db.commit()


def _init_seed_skills(db):
    """步骤5: 注入种子战法（4个演示战法）。"""
    print("5. 注入战法数据（手动配置）...")

    # 金吾飞将：对处于混乱或暴走状态的敌军单体发动一次猛攻（伤害率275.0%）；
    # 对随机敌军单体发动一次猛攻（伤害率275.0%），并使其陷入混乱状态，持续2回合
    jinwu_feijiang = Skill(
        name="金吾飞将", level=1, quality="S", skill_type="主动",
        activation_rate=35, range=3, target_type="敌军单体",
        troop_type="骑",
        description="对处于混乱或暴走状态的敌军单体发动一次猛攻（伤害率275.0%）；对随机敌军单体发动一次猛攻（伤害率275.0%），并使其陷入混乱状态，持续2回合",
        effect="",
        effect_config={
            "nodes": [
                {"id": 0, "type": "Event_OnCast", "x": 100, "y": 250, "params": {}},
                {"id": 1, "type": "Sequence", "x": 300, "y": 250, "params": {"输出数量": 2}},
                {"id": 2, "type": "GetEnemy", "x": 550, "y": 150,
                 "params": {"数量": "单体", "状态过滤": "无"}},
                {"id": 3, "type": "ApplyDamage", "x": 800, "y": 100,
                 "params": {"伤害类型": "攻击", "伤害率": 275.0}},
                {"id": 4, "type": "ApplyControl", "x": 800, "y": 220,
                 "params": {"控制类型": "混乱", "持续时间": "2回合"}},
                {"id": 5, "type": "GetEnemy", "x": 550, "y": 380,
                 "params": {"数量": "单体", "状态过滤": ["混乱", "暴走"]}},
                {"id": 6, "type": "ApplyDamage", "x": 800, "y": 380,
                 "params": {"伤害类型": "攻击", "伤害率": 275.0}},
            ],
            "links": [
                # Event → Sequence
                {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
                # 分支1：GetEnemy(无过滤) → 伤害 + 混乱
                {"from_node": 1, "from_pin": "exec_out_0", "to_node": 2, "to_pin": "exec_in"},
                {"from_node": 2, "from_pin": "exec_out", "to_node": 3, "to_pin": "exec_in"},
                {"from_node": 2, "from_pin": "targets", "to_node": 3, "to_pin": "targets"},
                {"from_node": 3, "from_pin": "exec_out", "to_node": 4, "to_pin": "exec_in"},
                {"from_node": 2, "from_pin": "targets", "to_node": 4, "to_pin": "targets"},
                # 分支2：GetEnemy(有状态过滤) → 伤害
                {"from_node": 1, "from_pin": "exec_out_1", "to_node": 5, "to_pin": "exec_in"},
                {"from_node": 5, "from_pin": "exec_out", "to_node": 6, "to_pin": "exec_in"},
                {"from_node": 5, "from_pin": "targets", "to_node": 6, "to_pin": "targets"},
            ]
        }
    )

    # 天下无双：对敌军单体发动一次猛攻，并使其陷入混乱状态，持续1回合
    tianxia_wushuang = Skill(
        name="天下无双", level=1, quality="S", skill_type="主动",
        activation_rate=35, range=3, target_type="敌军单体",
        troop_type="通用",
        description="对敌军单体发动一次猛攻，并使其陷入混乱状态，持续1回合",
        effect="",
        effect_config={
            "nodes": [
                {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
                {"id": 1, "type": "GetEnemy", "x": 350, "y": 200,
                 "params": {"数量": "单体"}},
                {"id": 2, "type": "ApplyDamage", "x": 600, "y": 150,
                 "params": {"伤害类型": "攻击", "伤害率": 150.0}},
                {"id": 3, "type": "ApplyControl", "x": 600, "y": 300,
                 "params": {"控制类型": "混乱", "持续时间": 1}},
            ],
            "links": [
                {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
                {"from_node": 2, "from_pin": "exec_out", "to_node": 3, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 3, "to_pin": "targets"},
            ]
        }
    )
    # 魏武之魂：使友军全体攻击、防御、速度提升，持续2回合
    weiwu_zhihun = Skill(
        name="魏武之魂", level=1, quality="S", skill_type="指挥",
        activation_rate=100, range=3, target_type="友军全体",
        troop_type="通用",
        description="使友军全体攻击、防御、速度提升，持续2回合",
        effect="",
        effect_config={
            "nodes": [
                {"id": 0, "type": "Event_BeginCombat", "x": 100, "y": 200, "params": {}},
                {"id": 1, "type": "GetAlly", "x": 350, "y": 200,
                 "params": {"数量": "全体"}},
                {"id": 2, "type": "ModifyAttribute", "x": 600, "y": 100,
                 "params": {"属性类型": "攻击", "修改值": 20, "修改方式": "增加", "持续时间": 2}},
                {"id": 3, "type": "ModifyAttribute", "x": 600, "y": 250,
                 "params": {"属性类型": "防御", "修改值": 20, "修改方式": "增加", "持续时间": 2}},
                {"id": 4, "type": "ModifyAttribute", "x": 600, "y": 400,
                 "params": {"属性类型": "速度", "修改值": 15, "修改方式": "增加", "持续时间": 2}},
            ],
            "links": [
                {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
                {"from_node": 2, "from_pin": "exec_out", "to_node": 3, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 3, "to_pin": "targets"},
                {"from_node": 3, "from_pin": "exec_out", "to_node": 4, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 4, "to_pin": "targets"},
            ]
        }
    )

    # 血溅黄砂（马超自带被动）：以无法发动主动战法为代价，使自身攻击伤害提高60%
    xuexian_huangsha = Skill(
        name="血溅黄砂", level=1, quality="S", skill_type="被动",
        activation_rate=100, range=0, target_type="自身",
        troop_type="通用",
        description="以无法发动主动战法为代价，使自身进行攻击时的伤害提高60%",
        effect="",
        effect_config={
            "nodes": [
                {"id": 0, "type": "Event_BeginRound", "x": 100, "y": 200, "params": {}},
                {"id": 1, "type": "GetSelf", "x": 350, "y": 200, "params": {}},
                {"id": 2, "type": "ApplyDamageBuff", "x": 600, "y": 120,
                 "params": {"Buff类型": "增伤", "数值": 60, "持续时间": "本场战斗"}},
                {"id": 3, "type": "ApplyControl", "x": 600, "y": 300,
                 "params": {"控制类型": "犹豫", "持续时间": "本场战斗"}},
            ],
            "links": [
                {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
                {"from_node": 1, "from_pin": "exec_out", "to_node": 3, "to_pin": "exec_in"},
                {"from_node": 1, "from_pin": "targets", "to_node": 3, "to_pin": "targets"},
            ]
        }
    )

    # 所有战法通过节点编辑器手动配置，此处只保留种子战法
    db.add(tianxia_wushuang)
    db.add(weiwu_zhihun)
    db.add(jinwu_feijiang)
    db.add(xuexian_huangsha)
    db.commit()
    print(f"   已注入 {db.query(Skill).count()} 个战法（种子数据）")

    return jinwu_feijiang, tianxia_wushuang, weiwu_zhihun, xuexian_huangsha


def _init_seed_heroes(db):
    """步骤6: 注入种子武将模板（吕布、曹操、马超）。"""
    print("6. 注入武将模板...")

    # 获取种子战法引用（全量重置时已存在，轻量重置时也保留）
    tianxia_wushuang = db.query(Skill).filter_by(name="天下无双").first()
    weiwu_zhihun = db.query(Skill).filter_by(name="魏武之魂").first()
    jinwu_feijiang = db.query(Skill).filter_by(name="金吾飞将").first()
    xuexian_huangsha = db.query(Skill).filter_by(name="血溅黄砂").first()

    lvbu = HeroTemplate(
        name="吕布", stars=5, faction="群", troop_type="骑兵", cost=3.5, attack_range=3,
        atk=105, defs=85, strg=20, sie=10, spd=100,
        atk_g=2.8, def_g=1.5, strg_g=0.3, sie_g=0.5, spd_g=2.0,
        innate_skill_id=tianxia_wushuang.id if tianxia_wushuang else None
    )
    db.add(lvbu)

    caocao = HeroTemplate(
        name="曹操", stars=5, faction="魏", troop_type="骑兵", cost=3.5, attack_range=3,
        atk=85, defs=100, strg=95, sie=10, spd=80,
        atk_g=2.0, def_g=2.5, strg_g=2.3, sie_g=0.5, spd_g=1.8,
        innate_skill_id=weiwu_zhihun.id if weiwu_zhihun else None
    )
    db.add(caocao)

    machao = HeroTemplate(
        name="马超", stars=5, faction="群", troop_type="骑兵", cost=3.0, attack_range=3,
        atk=97, defs=91, strg=4, sie=45, spd=92,
        atk_g=2.78, def_g=1.84, strg_g=0.41, sie_g=0.52, spd_g=1.54,
        innate_skill_id=xuexian_huangsha.id if xuexian_huangsha else None
    )
    db.add(machao)
    db.commit()

    return lvbu, caocao, machao


def _init_card_packs(db):
    """步骤7: 创建种子卡包。"""
    print("7. 创建卡包...")

    # 获取武将模板引用
    lvbu = db.query(HeroTemplate).filter_by(name="吕布").first()
    caocao = db.query(HeroTemplate).filter_by(name="曹操").first()
    machao = db.query(HeroTemplate).filter_by(name="马超").first()

    pack_n = CardPack(name="名将卡包", cost_type="tiger", cost_amount=200)
    db.add(pack_n)
    db.commit()
    if lvbu:
        db.add(CardPackDrop(pack_id=pack_n.id, template_id=lvbu.id, weight=10.0))
    if caocao:
        db.add(CardPackDrop(pack_id=pack_n.id, template_id=caocao.id, weight=10.0))
    if machao:
        db.add(CardPackDrop(pack_id=pack_n.id, template_id=machao.id, weight=10.0))

    pack_c = CardPack(name="铜币卡包", cost_type="copper", cost_amount=5000)
    db.add(pack_c)
    db.commit()


def _init_test_player(db):
    """步骤8-10: 创建测试玩家、部队、建筑、初始武将。"""
    print("8. 创建测试玩家...")

    # 获取武将模板和战法引用（轻量重置时这些已存在）
    lvbu = db.query(HeroTemplate).filter_by(name="吕布").first()
    caocao = db.query(HeroTemplate).filter_by(name="曹操").first()
    machao = db.query(HeroTemplate).filter_by(name="马超").first()

    if not lvbu or not caocao:
        print("   ⚠️ 武将模板不存在，跳过测试玩家创建（请先全量重置）")
        return

    p = Player(
        username="主公_001",
        spawn_x=15,
        spawn_y=22,
        copper=50000,
        jade=0,
        tiger_tally=0,
        main_city_level=1
    )
    db.add(p)
    db.commit()

    tile = db.query(Tile).filter(Tile.x == 15, Tile.y == 22).first()
    if tile:
        tile.terrain, tile.level, tile.owner_id = "PLAINS", 3, p.id
    else:
        print(f"   ⚠️ 出生点(15,22)无效！")
    db.commit()

    for i in range(5):
        db.add(Troop(owner_id=p.id, name=f"部队{i+1}"))
    db.commit()

    # 步骤 9.5: 初始化玩家建筑
    print("9.5 初始化玩家建筑...")
    init_player_buildings(db, p.id, palace_level=p.main_city_level)
    print(f"   已为 {p.username} 初始化建筑（城主府 {p.main_city_level} 级）")

    print("10. 添加初始武将...")

    def _create_hero(template):
        return Hero(
            owner_id=p.id,
            template_id=template.id,
            name=template.name,
            stars=template.stars,
            attack=int(template.atk),
            defense=int(template.defs),
            strategy=int(template.strg),
            speed=int(template.spd),
            faction=template.faction,
            troop_type=template.troop_type,
            cost=template.cost,
            rank=1,
            duplicates=0,
            bonus_points=0,
            stamina=100,
            max_stamina=100
        )

    db.add(_create_hero(lvbu))
    db.add(_create_hero(caocao))
    if machao:
        db.add(_create_hero(machao))
    db.commit()


def _init_default_gm_admin(db):
    """创建默认超级管理员账号（仅在不存在时创建）。"""
    existing = db.query(GmAdmin).first()
    if existing:
        return
    from models.schema import DEFAULT_GM_PERMISSIONS
    import json
    admin = GmAdmin(username="admin", password="admin", role="super_admin",
                    permissions=json.dumps(DEFAULT_GM_PERMISSIONS, ensure_ascii=False))
    db.add(admin)
    db.commit()
    print("   已创建默认超管账号: admin / admin")


def _migrate_gm_permissions(db):
    """迁移：为没有 permissions 字段的旧管理员添加默认权限。"""
    from models.schema import DEFAULT_GM_PERMISSIONS
    import json
    admins = db.query(GmAdmin).filter(GmAdmin.permissions.is_(None)).all()
    if not admins:
        return
    for admin in admins:
        admin.permissions = json.dumps(DEFAULT_GM_PERMISSIONS, ensure_ascii=False)
    db.commit()
    print(f"   已为 {len(admins)} 个管理员设置默认权限")


if __name__ == "__main__":
    init_database()

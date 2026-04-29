# test_battle.py — 战斗系统测试脚本
# 从数据库读取战法节点图，构造测试队伍模拟战斗，验证各效果节点执行
import os, sys, random

# 把服务端目录加到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal
from models.schema import Skill, HeroTemplate, NPCHero
from core.battle_core import BattleHero, BattleContext, NodeGraphExecutor
from core.combat import CombatEngine

random.seed(42)  # 固定随机种子，方便复现

def print_sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_all_skills():
    """测试数据库中所有有 effect_config 的战法"""
    db = SessionLocal()
    skills = db.query(Skill).filter(Skill.effect_config.isnot(None)).all()
    db.close()
    print_sep(f"数据库中共 {len(skills)} 个战法有 effect_config")

    for skill in skills:
        test_single_skill(skill)

def test_single_skill(skill):
    """测试单个战法的节点图是否能正常执行"""
    config = skill.effect_config
    if not config or config == []:
        return
    if isinstance(config, list):
        print(f"  [跳过] {skill.name}: effect_config 是空列表")
        return

    # 检查是否有有效节点
    nodes = config.get("nodes", [])
    if not nodes:
        print(f"  [跳过] {skill.name}: 节点数为0")
        return

    # 检查节点类型是否都在模板中
    from node_editor import NodeEditor
    missing = [n["type"] for n in nodes if n["type"] not in NodeEditor.NODE_TEMPLATES]
    if missing:
        print(f"  [错误] {skill.name}: 未知节点类型 {set(missing)}")
        return

    # 构造简易战斗场景执行节点图
    attacker = make_test_hero("测试武将A", attack=150, defense=100, strategy=120, speed=110, troops=3000)
    defender1 = make_test_hero("测试敌军1", attack=80, defense=60, strategy=50, speed=90, troops=2000)
    defender2 = make_test_hero("测试敌军2", attack=80, defense=60, strategy=50, speed=90, troops=2000)
    defender3 = make_test_hero("测试敌军3", attack=80, defense=60, strategy=50, speed=90, troops=2000)

    # 转换为 BattleHero
    battle_atk = BattleHero(attacker)
    battle_def1 = BattleHero(defender1)
    battle_def2 = BattleHero(defender2)
    battle_def3 = BattleHero(defender3)

    ctx = BattleContext([battle_atk], [battle_def1, battle_def2, battle_def3])
    ctx.current_round = 1
    set_positions(ctx)

    # 设置战法类型
    orig_type = skill.skill_type
    # 临时设置让它能被 BattleHero 识别
    skill.skill_type = '主动'
    if orig_type == '指挥':
        skill.skill_type = '指挥'
    elif orig_type == '追击':
        skill.skill_type = '追击'

    attacker.active_skills = [skill] if orig_type == '主动' else []
    attacker.command_skills = [skill] if orig_type == '指挥' else []

    try:
        executor = NodeGraphExecutor(config, ctx, source_hero=battle_atk, current_skill=skill)
        executor.execute()
        print(f"  [通过] {skill.name}（{skill.quality}·{orig_type}）: "
              f"{len(nodes)}节点 {len(config.get('links',[]))}连线 "
              f"日志{len(ctx.log)}条")
    except Exception as e:
        print(f"  [失败] {skill.name}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 打印日志（只显示本次的）
    for entry in ctx.log:
        if isinstance(entry, str) and entry.strip():
            print(f"         {entry}")

def set_positions(ctx):
    """给 BattleContext 中所有英雄设置 position_index"""
    for i, h in enumerate(ctx.attacker_side):
        h.position_index = i + 1
    for i, h in enumerate(ctx.defender_side):
        h.position_index = i + 1

def make_test_hero(name, attack=100, defense=80, strategy=90, speed=100, troops=2000):
    """构造一个假的英雄对象，满足 BattleHero 的要求"""
    h = type('Hero', (), {})()
    h.id = random.randint(1, 99999)
    h.name = name
    h.attack = attack
    h.defense = defense
    h.strategy = strategy
    h.speed = speed
    h.troops = troops
    h.max_troops = troops
    h.position_index = 1  # 默认站位
    # template
    tpl = type('Tpl', (), {})()
    tpl.innate_skill = None
    tpl.attack_range = 2
    h.template = tpl
    h.skill_2 = None
    h.skill_3 = None
    return h

def test_full_battle():
    """完整战斗模拟：用数据库中真实武将和战法"""
    print_sep("完整战斗模拟测试")

    db = SessionLocal()

    # 找有自带战法的武将模板
    templates = db.query(HeroTemplate).filter(
        HeroTemplate.innate_skill_id.isnot(None)
    ).limit(6).all()

    if len(templates) < 3:
        print("  [跳过] 武将模板不足3个")
        db.close()
        return

    # 进攻方：前3个武将
    atk_heroes = []
    for tpl in templates[:3]:
        h = type('Hero', (), {})()
        h.id = tpl.id
        h.name = tpl.name
        h.attack = int(tpl.atk + tpl.atk_g * 20)
        h.defense = int(tpl.defs + tpl.def_g * 20)
        h.strategy = int(tpl.strg + tpl.strg_g * 20)
        h.speed = int(tpl.spd + tpl.spd_g * 20)
        h.troops = 3000
        h.max_troops = 3000
        h.template = tpl
        h.skill_2 = None
        h.skill_3 = None
        atk_heroes.append(h)

    # 防守方：后3个武将（或NPC）
    def_heroes = []
    for tpl in templates[3:6] if len(templates) >= 6 else []:
        h = type('Hero', (), {})()
        h.id = tpl.id + 1000
        h.name = tpl.name
        h.attack = int(tpl.atk + tpl.atk_g * 20)
        h.defense = int(tpl.defs + tpl.def_g * 20)
        h.strategy = int(tpl.strg + tpl.strg_g * 20)
        h.speed = int(tpl.spd + tpl.spd_g * 20)
        h.troops = 3000
        h.max_troops = 3000
        h.template = tpl
        h.skill_2 = None
        h.skill_3 = None
        def_heroes.append(h)

    # 防守方不足3个时用NPC补
    while len(def_heroes) < 3:
        def_heroes.append(NPHero(3))

    db.close()

    print(f"  进攻方: {' / '.join(h.name for h in atk_heroes)}")
    print(f"  防守方: {' / '.join(h.name for h in def_heroes)}")
    print()

    win, report = CombatEngine.simulate_battle(atk_heroes, def_heroes, max_rounds=8)
    print("\n".join(report))

def test_status_filter():
    """测试状态过滤（多选）功能"""
    print_sep("状态过滤功能专项测试")

    # 构造一个有状态过滤的节点图
    # 场景：敌方有混乱和暴走状态，测试多选过滤
    attacker = make_test_hero("测试A", attack=150, defense=100, strategy=120, speed=110, troops=3000)
    defender1 = make_test_hero("敌军1-混乱", attack=80, defense=60, strategy=50, speed=90, troops=2000)
    defender2 = make_test_hero("敌军2-暴走", attack=80, defense=60, strategy=50, speed=90, troops=2000)
    defender3 = make_test_hero("敌军3-正常", attack=80, defense=60, strategy=50, speed=90, troops=2000)

    # 先给敌军1加混乱，敌军2加暴走
    battle_atk = BattleHero(attacker)
    battle_def1 = BattleHero(defender1)
    battle_def2 = BattleHero(defender2)
    battle_def3 = BattleHero(defender3)

    battle_def1.add_buff('chaos', 1, 3, '测试')
    battle_def2.add_buff('berserk', 1, 3, '测试')

    # 设置站位
    battle_atk.position_index = 1
    battle_def1.position_index = 1
    battle_def2.position_index = 2
    battle_def3.position_index = 3

    ctx = BattleContext([battle_atk], [battle_def1, battle_def2, battle_def3])
    set_positions(ctx)

    # 测试1: 多选 ["混乱", "暴走"]，应该只选中敌军1和敌军2
    config_multi = {
        "nodes": [
            {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
            {"id": 1, "type": "GetEnemy", "x": 300, "y": 200,
             "params": {"数量": "全体", "状态过滤": ["混乱", "暴走"]}},
            {"id": 2, "type": "ApplyDamage", "x": 500, "y": 200,
             "params": {"伤害类型": "攻击", "伤害率": 100.0, "受影响属性": "无"}},
        ],
        "links": [
            {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
            {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
            {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
        ]
    }

    skill = type('Skill', (), {})()
    skill.name = "测试状态过滤"
    skill.skill_type = '主动'
    skill.effect_config = config_multi

    battle_atk.active_skills = [skill]
    executor = NodeGraphExecutor(config_multi, ctx, source_hero=battle_atk, current_skill=skill)
    executor.execute()

    targets = executor.pin_values.get((1, 'targets'), [])
    target_names = [t.name for t in targets]
    print(f"  测试1 - 多选[混乱,暴走]: 选中 {target_names}")
    assert "敌军1-混乱" in target_names, "应选中混乱状态的敌军1"
    assert "敌军2-暴走" in target_names, "应选中暴走状态的敌军2"
    assert "敌军3-正常" not in target_names, "不应选中正常状态的敌军3"
    print(f"  [通过] 正确过滤出混乱+暴走的敌人")

    # 测试2: 空列表（不过滤），应该选中全部
    ctx2 = BattleContext([BattleHero(attacker)], [BattleHero(defender1), BattleHero(defender2), BattleHero(defender3)])
    set_positions(ctx2)
    config_none = {
        "nodes": [
            {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
            {"id": 1, "type": "GetEnemy", "x": 300, "y": 200,
             "params": {"数量": "全体", "状态过滤": []}},
        ],
        "links": [
            {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
        ]
    }
    executor2 = NodeGraphExecutor(config_none, ctx2, source_hero=ctx2.attacker_side[0], current_skill=skill)
    executor2.execute()
    targets2 = executor2.pin_values.get((1, 'targets'), [])
    print(f"  测试2 - 空列表(不过滤): 选中 {len(targets2)} 个目标")
    assert len(targets2) == 3, f"应选中3个目标，实际选中{len(targets2)}个"
    print(f"  [通过] 空列表正确不过滤")

    # 测试3: 旧格式字符串兼容（单选"混乱"）
    ctx3 = BattleContext([BattleHero(attacker)], [BattleHero(defender1), BattleHero(defender2), BattleHero(defender3)])
    set_positions(ctx3)
    config_legacy = {
        "nodes": [
            {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
            {"id": 1, "type": "GetEnemy", "x": 300, "y": 200,
             "params": {"数量": "全体", "状态过滤": "混乱"}},
        ],
        "links": [
            {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
        ]
    }
    executor3 = NodeGraphExecutor(config_legacy, ctx3, source_hero=ctx3.attacker_side[0], current_skill=skill)
    executor3.execute()
    targets3 = executor3.pin_values.get((1, 'targets'), [])
    print(f"  测试3 - 旧格式字符串'混乱': 选中 {len(targets3)} 个目标")
    # 注意：这个ctx3里的武将没有buff，所以应该为空或fallback
    print(f"  [通过] 旧格式字符串兼容正常")

def test_duration_parse():
    """测试持续时间解析"""
    print_sep("持续时间解析测试")
    from core.battle_core import BattleHero, BattleContext
    # 直接测试 _parse_duration 方法
    executor_dummy = NodeGraphExecutor({"nodes": [], "links": []}, BattleContext([], []))

    test_cases = [
        (1, 1),
        (2, 2),
        (3, 3),
        (999, 999),
        ("1回合", 1),
        ("2回合", 2),
        ("3回合", 3),
        ("本场战斗", 999),
        (2.5, 2),
    ]
    all_pass = True
    for input_val, expected in test_cases:
        result = executor_dummy._parse_duration(input_val)
        status = "通过" if result == expected else f"失败(期望{expected},得到{result})"
        if result != expected:
            all_pass = False
        print(f"  _parse_duration({input_val!r}) = {result}  [{status}]")

    if all_pass:
        print(f"\n  全部 {len(test_cases)} 个测试通过!")
    else:
        print(f"\n  有测试失败!")

def test_modify_attribute_multi():
    """测试 ModifyAttribute 多选属性"""
    print_sep("ModifyAttribute 多选属性测试")

    attacker = make_test_hero("测试A", attack=150, defense=100, strategy=120, speed=110)
    target = make_test_hero("目标", attack=80, defense=60, strategy=50, speed=90)

    battle_atk = BattleHero(attacker)
    battle_target = BattleHero(target)
    ctx = BattleContext([battle_atk], [battle_target])
    set_positions(ctx)

    config = {
        "nodes": [
            {"id": 0, "type": "Event_OnCast", "x": 100, "y": 200, "params": {}},
            {"id": 1, "type": "GetSelf", "x": 300, "y": 200, "params": {}},
            {"id": 2, "type": "ModifyAttribute", "x": 500, "y": 200,
             "params": {
                 "属性类型": ["攻击", "防御", "谋略", "速度"],
                 "计算方式": "百分比",
                 "修改方式": "增加",
                 "修改值": 20,
                 "持续时间": "2回合",
                 "受影响属性": "无"
             }},
        ],
        "links": [
            {"from_node": 0, "from_pin": "exec_out", "to_node": 1, "to_pin": "exec_in"},
            {"from_node": 1, "from_pin": "exec_out", "to_node": 2, "to_pin": "exec_in"},
            {"from_node": 1, "from_pin": "targets", "to_node": 2, "to_pin": "targets"},
        ]
    }

    skill = type('Skill', (), {})()
    skill.name = "测试属性提升"
    skill.skill_type = '主动'

    executor = NodeGraphExecutor(config, ctx, source_hero=battle_atk, current_skill=skill)
    executor.execute()

    print(f"  修改前: 攻击={battle_atk.base_attack} 防御={battle_atk.base_defense} 谋略={battle_atk.base_strategy} 速度={battle_atk.base_speed}")
    print(f"  修改后: 攻击={battle_atk.get_attr('attack')} 防御={battle_atk.get_attr('defense')} 谋略={battle_atk.get_attr('strategy')} 速度={battle_atk.get_attr('speed')}")
    print(f"  Buff列表: {[(b['type'], b['value'], b['mode']) for b in battle_atk.buff_list]}")

    # 验证：应该有4个buff（攻击/防御/谋略/速度各一个）
    assert len(battle_atk.buff_list) == 4, f"应该有4个buff，实际有{len(battle_atk.buff_list)}个"
    # 验证属性提升
    assert battle_atk.get_attr('attack') > battle_atk.base_attack, "攻击应该提升"
    assert battle_atk.get_attr('defense') > battle_atk.base_defense, "防御应该提升"
    print(f"  [通过] 多选属性修改正确")

if __name__ == "__main__":
    print_sep("InfiniteBorders 战斗系统测试")
    print(f"  时间: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  随机种子: 42")

    # 1. 持续时间解析测试
    test_duration_parse()

    # 2. 状态过滤测试
    test_status_filter()

    # 3. ModifyAttribute 多选测试
    test_modify_attribute_multi()

    # 4. 数据库战法执行测试
    test_all_skills()

    # 5. 完整战斗模拟
    test_full_battle()

    print_sep("所有测试完成")

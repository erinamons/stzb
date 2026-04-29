# test_jinwu.py — 测试金吾飞将战法执行
import random
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(42)
from core.battle_core import BattleHero, BattleContext, NodeGraphExecutor

# 开启调试模式
NodeGraphExecutor.DEBUG = True

def make_hero(name, attack=100, defense=80, strategy=90, speed=100, troops=2000, attack_range=3):
    h = type('Hero', (), {})()
    h.id = random.randint(1, 99999)
    h.name = name
    h.attack, h.defense, h.strategy, h.speed = attack, defense, strategy, speed
    h.troops = troops
    tpl = type('Tpl', (), {})()
    tpl.innate_skill = None
    tpl.attack_range = attack_range
    h.template = tpl
    h.skill_2 = None
    h.skill_3 = None
    return h

atk = BattleHero(make_hero('关羽', 180, 120, 130, 120, 3000, attack_range=3))
def1 = BattleHero(make_hero('敌军1', 80, 60, 50, 90, 2000, attack_range=2))
def2 = BattleHero(make_hero('敌军2', 80, 60, 50, 90, 2000, attack_range=2))
def3 = BattleHero(make_hero('敌军3', 80, 60, 50, 90, 2000, attack_range=2))

atk.position_index = 1
def1.position_index = 1
def2.position_index = 2
def3.position_index = 3

ctx = BattleContext([atk], [def1, def2, def3])
ctx.current_round = 1

skill = type('Skill', (), {})()
skill.name = '金吾飞将'

print(f"[调试] 攻击方 attack_distance={atk.get_attack_distance()}")
print(f"[调试] 敌军1 position={def1.position_index}, 存活={def1.is_alive}")
print(f"[调试] 敌军2 position={def2.position_index}, 存活={def2.is_alive}")
print(f"[调试] 敌军3 position={def3.position_index}, 存活={def3.is_alive}")

# 当前数据库中的版本（没有 targets 数据连接）
config_no_data = {
    'nodes': [
        {'id': 0, 'type': 'Event_OnCast', 'x': 100, 'y': 250, 'params': {}},
        {'id': 1, 'type': 'Sequence', 'x': 300, 'y': 250, 'params': {'输出数量': 2}},
        {'id': 2, 'type': 'GetEnemy', 'x': 550, 'y': 150, 'params': {'数量': '单体', '状态过滤': '无'}},
        {'id': 3, 'type': 'ApplyDamage', 'x': 800, 'y': 150, 'params': {'伤害类型': '攻击', '伤害率': 275.0}},
        {'id': 4, 'type': 'ApplyControl', 'x': 1050, 'y': 150, 'params': {'控制类型': '混乱', '持续时间': '2回合'}},
        {'id': 5, 'type': 'GetEnemy', 'x': 550, 'y': 350, 'params': {'数量': '单体', '状态过滤': '任意控制'}},
        {'id': 6, 'type': 'ApplyDamage', 'x': 800, 'y': 350, 'params': {'伤害类型': '攻击', '伤害率': 275.0}},
    ],
    'links': [
        {'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'},
        {'from_node': 1, 'from_pin': 'exec_out_0', 'to_node': 2, 'to_pin': 'exec_in'},
        {'from_node': 2, 'from_pin': 'exec_out', 'to_node': 3, 'to_pin': 'exec_in'},
        {'from_node': 3, 'from_pin': 'exec_out', 'to_node': 4, 'to_pin': 'exec_in'},
        {'from_node': 1, 'from_pin': 'exec_out_1', 'to_node': 5, 'to_pin': 'exec_in'},
        {'from_node': 5, 'from_pin': 'exec_out', 'to_node': 6, 'to_pin': 'exec_in'},
    ]
}

print('=== 执行当前金吾飞将节点图（无数据连接）===')
ctx1 = BattleContext([atk], [def1, def2, def3])
ctx1.current_round = 1
executor = NodeGraphExecutor(config_no_data, ctx1, source_hero=atk, current_skill=skill)
executor.execute()
print(f'日志条数: {len(ctx1.log)}')
for entry in ctx1.log:
    if isinstance(entry, str):
        print(f'  {entry}')

print()
print('--- 各敌军状态 ---')
for d in [def1, def2, def3]:
    buffs = [b["type"] for b in d.buff_list]
    print(f'  {d.name}: 兵力={d.current_troops}, 存活={d.is_alive}, buffs={buffs}')

# 修复版本（添加数据连接 + 修正节点4 ApplyControl 目标选择）
config_fixed = {
    'nodes': [
        {'id': 0, 'type': 'Event_OnCast', 'x': 100, 'y': 250, 'params': {}},
        {'id': 1, 'type': 'Sequence', 'x': 300, 'y': 250, 'params': {'输出数量': 2}},
        {'id': 2, 'type': 'GetEnemy', 'x': 550, 'y': 150, 'params': {'数量': '单体', '状态过滤': '无'}},
        {'id': 3, 'type': 'ApplyDamage', 'x': 800, 'y': 150, 'params': {'伤害类型': '攻击', '伤害率': 275.0, '受影响属性': '无'}},
        {'id': 4, 'type': 'ApplyControl', 'x': 1050, 'y': 150, 'params': {'控制类型': '混乱', '持续时间': '2回合'}},
        {'id': 5, 'type': 'GetEnemy', 'x': 550, 'y': 350, 'params': {'数量': '单体', '状态过滤': '混乱,暴走'}},
        {'id': 6, 'type': 'ApplyDamage', 'x': 800, 'y': 350, 'params': {'伤害类型': '攻击', '伤害率': 275.0, '受影响属性': '无'}},
    ],
    'links': [
        {'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'},
        {'from_node': 1, 'from_pin': 'exec_out_0', 'to_node': 2, 'to_pin': 'exec_in'},
        {'from_node': 2, 'from_pin': 'exec_out', 'to_node': 3, 'to_pin': 'exec_in'},
        {'from_node': 3, 'from_pin': 'exec_out', 'to_node': 4, 'to_pin': 'exec_in'},
        # 数据连接：GetEnemy(2).targets → ApplyDamage(3).targets
        {'from_node': 2, 'from_pin': 'targets', 'to_node': 3, 'to_pin': 'targets'},
        # 数据连接：GetEnemy(2).targets → ApplyControl(4).targets
        {'from_node': 2, 'from_pin': 'targets', 'to_node': 4, 'to_pin': 'targets'},
        {'from_node': 1, 'from_pin': 'exec_out_1', 'to_node': 5, 'to_pin': 'exec_in'},
        {'from_node': 5, 'from_pin': 'exec_out', 'to_node': 6, 'to_pin': 'exec_in'},
        # 数据连接：GetEnemy(5).targets → ApplyDamage(6).targets
        {'from_node': 5, 'from_pin': 'targets', 'to_node': 6, 'to_pin': 'targets'},
    ]
}

print()
print('=== 执行修复版金吾飞将节点图（有数据连接）===')
# 重新构造武将（因为上一轮已经被修改了）
atk2 = BattleHero(make_hero('关羽2', 180, 120, 130, 120, 3000))
def4 = BattleHero(make_hero('敌军4', 80, 60, 50, 90, 2000))
def5 = BattleHero(make_hero('敌军5', 80, 60, 50, 90, 2000))
def6 = BattleHero(make_hero('敌军6', 80, 60, 50, 90, 2000))
atk2.position_index = 1
def4.position_index = 1
def5.position_index = 2
def6.position_index = 3

ctx2 = BattleContext([atk2], [def4, def5, def6])
ctx2.current_round = 1
executor2 = NodeGraphExecutor(config_fixed, ctx2, source_hero=atk2, current_skill=skill)
executor2.execute()
print(f'日志条数: {len(ctx2.log)}')
for entry in ctx2.log:
    if isinstance(entry, str):
        print(f'  {entry}')

print()
print('--- 各敌军状态 ---')
for d in [def4, def5, def6]:
    buffs = [b["type"] for b in d.buff_list]
    print(f'  {d.name}: 兵力={d.current_troops}, 存活={d.is_alive}, buffs={buffs}')

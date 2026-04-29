"""fix_skill_configs.py — 修复数据库中有问题的战法 effect_config

问题列表：
1. 魏武之世：缺少 Event→GetEnemy 入口连接
2. 金吾飞将：手动编辑后缺少入口连接和数据连接
3. 利兵谋胜/巧音唤蝶：描述含"恢复"但不是治疗类，被错误生成为 ApplyHeal
"""
import json
import copy
from models.database import SessionLocal
from models.schema import Skill
from sqlalchemy.orm.attributes import flag_modified

db = SessionLocal()

# ========== 1. 修复魏武之世 ==========
skill = db.query(Skill).filter(Skill.name == '魏武之世').first()
if skill:
    cfg = copy.deepcopy(skill.effect_config)
    has_entry = any(
        l.get('from_node') == 0 and l.get('from_pin') == 'exec_out'
        for l in cfg.get('links', [])
    )
    if not has_entry:
        cfg['links'].insert(0, {
            'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'
        })
        skill.effect_config = cfg
        flag_modified(skill, 'effect_config')
        print(f'[OK] wei_wu_zhi_shi: +Event->GetEnemy')
    else:
        print(f'[SKIP] wei_wu_zhi_shi: already has entry')

# ========== 2. 修复金吾飞将 ==========
skill2 = db.query(Skill).filter(Skill.name == '金吾飞将').first()
if skill2:
    new_cfg = {
        'nodes': [
            {'id': 0, 'type': 'Event_OnCast', 'x': 100, 'y': 250, 'params': {}},
            {'id': 1, 'type': 'Sequence', 'x': 300, 'y': 250, 'params': {'输出数量': 2}},
            {'id': 2, 'type': 'GetEnemy', 'x': 550, 'y': 150,
             'params': {'数量': '单体', '状态过滤': '无'}},
            {'id': 3, 'type': 'ApplyDamage', 'x': 800, 'y': 100,
             'params': {'伤害类型': '攻击', '伤害率': 275.0}},
            {'id': 4, 'type': 'ApplyControl', 'x': 800, 'y': 220,
             'params': {'控制类型': '混乱', '持续时间': '2回合'}},
            {'id': 5, 'type': 'GetEnemy', 'x': 550, 'y': 380,
             'params': {'数量': '单体', '状态过滤': ['混乱', '暴走']}},
            {'id': 6, 'type': 'ApplyDamage', 'x': 800, 'y': 380,
             'params': {'伤害类型': '攻击', '伤害率': 275.0}},
        ],
        'links': [
            {'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'},
            {'from_node': 1, 'from_pin': 'exec_out_0', 'to_node': 2, 'to_pin': 'exec_in'},
            {'from_node': 2, 'from_pin': 'exec_out', 'to_node': 3, 'to_pin': 'exec_in'},
            {'from_node': 2, 'from_pin': 'targets', 'to_node': 3, 'to_pin': 'targets'},
            {'from_node': 3, 'from_pin': 'exec_out', 'to_node': 4, 'to_pin': 'exec_in'},
            {'from_node': 2, 'from_pin': 'targets', 'to_node': 4, 'to_pin': 'targets'},
            {'from_node': 1, 'from_pin': 'exec_out_1', 'to_node': 5, 'to_pin': 'exec_in'},
            {'from_node': 5, 'from_pin': 'exec_out', 'to_node': 6, 'to_pin': 'exec_in'},
            {'from_node': 5, 'from_pin': 'targets', 'to_node': 6, 'to_pin': 'targets'},
        ]
    }
    skill2.effect_config = new_cfg
    flag_modified(skill2, 'effect_config')
    print(f'[OK] jin_wu_fei_jiang: replaced full graph')

# ========== 3. 修复利兵谋胜 ==========
# 描述：使敌军群体攻击和防御降低（受谋略影响），持续2回合
# 应该是 ModifyAttribute（减益）而不是 ApplyHeal
skill3 = db.query(Skill).filter(Skill.name == '利兵谋胜').first()
if skill3:
    cfg = skill3.effect_config
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    # 检查是否有 ApplyHeal 节点
    has_heal = any(n['type'] == 'ApplyHeal' for n in cfg.get('nodes', []))
    if has_heal:
        skill3.effect_config = {
            'nodes': [
                {'id': 0, 'type': 'Event_OnCast', 'x': 100, 'y': 200, 'params': {}},
                {'id': 1, 'type': 'GetEnemy', 'x': 350, 'y': 200,
                 'params': {'数量': '群体(2)'}},
                {'id': 2, 'type': 'ModifyAttribute', 'x': 600, 'y': 150,
                 'params': {'属性类型': ['攻击', '防御'], '修改值': -30, '修改方式': '增加',
                            '持续时间': '2回合', '计算方式': '固定值', '受影响属性': '谋略'}},
            ],
            'links': [
                {'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'},
                {'from_node': 1, 'from_pin': 'exec_out', 'to_node': 2, 'to_pin': 'exec_in'},
                {'from_node': 1, 'from_pin': 'targets', 'to_node': 2, 'to_pin': 'targets'},
            ]
        }
        flag_modified(skill3, 'effect_config')
        print(f'[OK] li_bing_mou_sheng: ApplyHeal->ModifyAttribute')

# ========== 4. 修复巧音唤蝶 ==========
# 描述：对敌军单体造成策略伤害，并使其无法恢复兵力，持续2回合
# 应该是 ApplyDamage + ApplyControl(禁疗)
skill4 = db.query(Skill).filter(Skill.name == '巧音唤蝶').first()
if skill4:
    cfg = skill4.effect_config
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    has_heal = any(n['type'] == 'ApplyHeal' for n in cfg.get('nodes', []))
    if has_heal:
        skill4.effect_config = {
            'nodes': [
                {'id': 0, 'type': 'Event_OnCast', 'x': 100, 'y': 200, 'params': {}},
                {'id': 1, 'type': 'GetEnemy', 'x': 350, 'y': 200,
                 'params': {'数量': '单体'}},
                {'id': 2, 'type': 'ApplyDamage', 'x': 600, 'y': 150,
                 'params': {'伤害类型': '策略', '伤害率': 150.0}},
                {'id': 3, 'type': 'ApplyControl', 'x': 600, 'y': 300,
                 'params': {'控制类型': '禁疗', '持续时间': '2回合'}},
            ],
            'links': [
                {'from_node': 0, 'from_pin': 'exec_out', 'to_node': 1, 'to_pin': 'exec_in'},
                {'from_node': 1, 'from_pin': 'exec_out', 'to_node': 2, 'to_pin': 'exec_in'},
                {'from_node': 1, 'from_pin': 'targets', 'to_node': 2, 'to_pin': 'targets'},
                {'from_node': 2, 'from_pin': 'exec_out', 'to_node': 3, 'to_pin': 'exec_in'},
                {'from_node': 1, 'from_pin': 'targets', 'to_node': 3, 'to_pin': 'targets'},
            ]
        }
        flag_modified(skill4, 'effect_config')
        print(f'[OK] qiao_yin_huan_die: ApplyHeal->ApplyDamage+Control')

# ========== 5. 扫描所有战法，检查是否有缺少入口连接的 ==========
print()
print('[扫描] 检查所有战法的入口连接...')
all_skills = db.query(Skill).filter(Skill.effect_config.isnot(None)).all()
missing_entry = []
for s in all_skills:
    cfg = s.effect_config
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    if not cfg or not isinstance(cfg, dict):
        continue
    nodes = cfg.get('nodes', [])
    links = cfg.get('links', [])
    if not nodes:
        continue
    # 找 Event 节点
    event_nodes = [n for n in nodes if n['type'].startswith('Event_')]
    if event_nodes:
        event_id = event_nodes[0]['id']
        has_out = any(l.get('from_node') == event_id for l in links)
        if not has_out:
            missing_entry.append(s.name)

if missing_entry:
    print(f'  [WARN] missing entry links for {len(missing_entry)} skills:')
    for name in missing_entry:
        print(f'    - {name}')
else:
    print('  All skills have entry links [OK]')

db.commit()
db.close()
print('\nDone!')

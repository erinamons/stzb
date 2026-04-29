# core/battle_core.py
import re
import random

class BattleHero:
    """战斗中的武将实例，按照简化算法实现"""
    def __init__(self, hero):
        self.id = hero.id
        self.name = hero.name
        self.template = hero.template
        # 基础属性（模板基础 + 等级成长 + 手动加点，与 send_heroes 计算逻辑一致）
        t = hero.template
        if t:
            self.base_attack = int(t.atk + (hero.level - 1) * t.atk_g + hero.p_atk)
            self.base_defense = int(t.defs + (hero.level - 1) * t.def_g + hero.p_def)
            self.base_strategy = int(t.strg + (hero.level - 1) * t.strg_g + hero.p_strg)
            self.base_speed = int(t.spd + (hero.level - 1) * t.spd_g + hero.p_spd)
        else:
            # 无模板时 fallback（如 NPCHero）
            self.base_attack = hero.attack
            self.base_defense = hero.defense
            self.base_strategy = hero.strategy
            self.base_speed = hero.speed
        # 攻击距离
        self.attack_distance = hero.template.attack_range if hero.template else 2
        # 站位索引（用于距离判定，1=前锋，2=中军，3=大营）
        self.position_index = None
        # 兵力
        self.max_troops = hero.troops
        self.current_troops = hero.troops
        # buff 列表
        self.buff_list = []   # 每个元素 {"type": str, "value": float, "remaining": int, "source": str}
        # 准备战法状态
        self.preparing_skill = None   # 正在准备的战法对象
        self.preparing_skill_turns = 0  # 剩余准备回合数
        self.pending_skill = None     # 准备完成的战法，待释放
        # 主动战法列表（自带+学习）
        self.active_skills = []
        self.innate_skill = hero.template.innate_skill if hero.template else None
        self.skill_2 = hero.skill_2
        self.skill_3 = hero.skill_3
        # 指挥战法（在战斗开始前释放）
        self.command_skills = []
        # 追击战法
        self.pursuit_skills = []
        # 被动战法（每回合自动触发，不受控制效果影响）
        self.passive_skills = []
        # 收集所有战法
        for skill in [self.innate_skill, self.skill_2, self.skill_3]:
            if skill:
                if skill.skill_type == '主动':
                    self.active_skills.append(skill)
                elif skill.skill_type == '指挥':
                    self.command_skills.append(skill)
                elif skill.skill_type == '追击':
                    self.pursuit_skills.append(skill)
                elif skill.skill_type == '被动':
                    self.passive_skills.append(skill)
        # P0-3 FIX: 添加 variables 字典，供 SetVariable/GetVariable/CheckVariable 节点使用
        self.variables = {}
        # 战法发动计数器
        self.skill_cast_count = {}  # {skill_name: int}
        # 阵亡标记
        self.is_alive = True

    def get_attr(self, attr_name):
        """获取当前属性值（包含临时修正：固定值 + 百分比）"""
        base = getattr(self, f"base_{attr_name}")
        # 固定值修正
        delta = sum(b['value'] for b in self.buff_list if b['type'] == f"attr_{attr_name}" and b.get('mode') != 'percent')
        # 百分比修正（累加）
        pct = sum(b['value'] for b in self.buff_list if b['type'] == f"attr_{attr_name}" and b.get('mode') == 'percent')
        return int((base + delta) * (1 + pct / 100.0))

    def get_attack_distance(self):
        """获取当前攻击距离（包含修正）"""
        base = self.attack_distance
        delta = sum(b['value'] for b in self.buff_list if b['type'] == 'attr_attack_distance' and b.get('mode') != 'percent')
        pct = sum(b['value'] for b in self.buff_list if b['type'] == 'attr_attack_distance' and b.get('mode') == 'percent')
        result = int((base + delta) * (1 + pct / 100.0))
        return max(1, result)

    def add_buff(self, buff_type, value, duration, source, mode='fixed'):
        """添加buff，同类型同源覆盖。mode: 'fixed'=固定值, 'percent'=百分比"""
        for b in self.buff_list:
            if b['type'] == buff_type and b['source'] == source and b.get('mode', 'fixed') == mode:
                b['value'] = value
                b['remaining'] = duration
                return
        self.buff_list.append({
            'type': buff_type,
            'value': value,
            'remaining': duration,
            'source': source,
            'mode': mode
        })

    def remove_buff_by_source(self, source):
        """移除指定来源的所有buff"""
        self.buff_list = [b for b in self.buff_list if b['source'] != source]

    def process_buff_round_end(self):
        """回合结束时衰减buff持续时间"""
        new_list = []
        for b in self.buff_list:
            b['remaining'] -= 1
            if b['remaining'] > 0:
                new_list.append(b)
        self.buff_list = new_list

    def get_total_damage_increase(self):
        """获取总增伤系数"""
        total = 0
        for b in self.buff_list:
            if b['type'] == 'damage_increase':
                total += b['value']
        return total

    def get_total_damage_taken_increase(self):
        """获取总受创提升系数"""
        total = 0
        for b in self.buff_list:
            if b['type'] == 'damage_taken_increase':
                total += b['value']
        return total

    def get_total_damage_reduction(self):
        """获取总减伤系数（自身造成伤害降低，百分比为负值）"""
        total = 0
        for b in self.buff_list:
            if b['type'] == 'damage_reduction':
                total += b['value']
        return total

    def get_total_damage_taken_reduction(self):
        """获取总被伤害减少系数（自身受到伤害降低）"""
        total = 0
        for b in self.buff_list:
            if b['type'] == 'damage_taken_reduction':
                total += b['value']
        return total

    def is_hesitation(self):
        """是否犹豫"""
        return any(b['type'] == 'hesitation' for b in self.buff_list)

    def is_fright(self):
        """是否怯战"""
        return any(b['type'] == 'fright' for b in self.buff_list)

    def is_chaos(self):
        """是否混乱"""
        return any(b['type'] == 'chaos' for b in self.buff_list)

    def is_berserk(self):
        """是否暴走"""
        return any(b['type'] == 'berserk' for b in self.buff_list)

    def is_healing_block(self):
        """是否禁疗"""
        return any(b['type'] == 'healing_block' for b in self.buff_list)

    def has_control_status(self):
        """是否处于任意控制状态（混乱/犹豫/怯战/暴走/禁疗）"""
        control_types = {'chaos', 'hesitation', 'fright', 'berserk', 'healing_block'}
        return any(b['type'] in control_types for b in self.buff_list)

    def take_damage(self, damage, damage_type='physical'):
        """承受伤害，返回实际伤害值"""
        if not self.is_alive:
            return 0
        # 保底伤害10
        real_damage = int(max(damage, 10))
        self.current_troops -= real_damage
        if self.current_troops <= 0:
            self.current_troops = 0
            self.is_alive = False
            # 清除准备状态
            self.preparing_skill = None
            self.preparing_skill_turns = 0
            self.pending_skill = None
        return real_damage

    def take_heal(self, heal_value):
        """治疗，返回实际治疗量"""
        if not self.is_alive or self.is_healing_block():
            return 0
        real_heal = int(max(heal_value, 0))
        old = self.current_troops
        self.current_troops = min(self.current_troops + real_heal, self.max_troops)
        return self.current_troops - old

    def start_prepare(self, skill):
        """开始准备战法，返回是否成功"""
        if self.preparing_skill is not None:
            return False
        self.preparing_skill = skill
        self.preparing_skill_turns = skill.preparation_turns
        return True

    def advance_prepare(self):
        """回合开始时推进准备进度，返回是否完成准备"""
        if self.preparing_skill is not None:
            self.preparing_skill_turns -= 1
            if self.preparing_skill_turns <= 0:
                self.pending_skill = self.preparing_skill
                self.preparing_skill = None
                self.preparing_skill_turns = 0
                return True
        return False

    def normal_attack(self, target):
        """普通攻击"""
        if not self.is_alive or not target.is_alive or self.is_fright():
            return None, 0, None, target.current_troops
        atk_val = self.get_attr('attack')
        def_val = target.get_attr('defense')
        base_dmg = atk_val - (def_val / 2)
        # 增伤/减伤（攻击方）
        dmg_increase = self.get_total_damage_increase()
        dmg_reduction = self.get_total_damage_reduction()
        # 受创提升/被伤害减少（防御方）
        target_taken = target.get_total_damage_taken_increase()
        target_reduced = target.get_total_damage_taken_reduction()
        # 增减伤 value 存的是百分比值（如 60 表示 60%），需除以 100
        final_dmg = base_dmg * 1.0 * (1 + dmg_increase / 100 - dmg_reduction / 100) * (1 + target_taken / 100 - target_reduced / 100)
        raw_real = int(max(final_dmg, 10))
        real_dmg = target.take_damage(final_dmg, 'physical')
        # 公式追踪
        formula = {
            "type": "普攻",
            "steps": [
                f"基础伤害 = 攻击力({atk_val}) - 防御力({def_val})/2 = {base_dmg:.1f}",
            ],
        }
        if dmg_increase:
            formula["steps"].append(f"增伤 +{dmg_increase}%")
        if dmg_reduction:
            formula["steps"].append(f"减伤 -{dmg_reduction}%")
        if target_taken:
            formula["steps"].append(f"受创提升 +{target_taken}%")
        if target_reduced:
            formula["steps"].append(f"被伤害减少 -{target_reduced}%")
        formula["steps"].append(
            f"最终 = {base_dmg:.1f} × (1+{dmg_increase/100:.2f}-{dmg_reduction/100:.2f}) × (1+{target_taken/100:.2f}-{target_reduced/100:.2f}) = {final_dmg:.1f}"
        )
        if raw_real != int(final_dmg):
            formula["steps"].append(f"保底伤害 = max({final_dmg:.1f}, 10) = {raw_real}")
        formula["steps"].append(f"实际造成伤害 = {real_dmg}")
        return "普攻", real_dmg, formula, target.current_troops


class BattleContext:
    """战斗上下文"""
    def __init__(self, attacker_heroes, defender_heroes):
        self.attacker_side = attacker_heroes
        self.defender_side = defender_heroes
        self.all_heroes = attacker_heroes + defender_heroes
        self.current_round = 0
        self.current_acting_hero = None
        self.delayed_tasks = []   # [(turns_left, skill, node_id, input_data, source_hero)]
        self.log = []             # 战报日志列表，统一为结构化 dict
        self.command_skill_log = []  # 指挥战法生效记录

    def add_log(self, log_type, data=None):
        """添加战报日志，统一为结构化 dict 格式。
        log_type: 日志类型（如 hero_action, skill_effect, round_start 等）
        data: 该类型对应的数据字段
        """
        self.log.append({"type": log_type, "data": data or {}})

    def add_delayed_task(self, turns, skill, node_id, input_data, source_hero=None):
        self.delayed_tasks.append({
            'turns': turns,
            'skill': skill,
            'node_id': node_id,
            'input_data': input_data,
            'source_hero': source_hero
        })

    def advance_delayed_tasks(self):
        """处理延迟任务（准备完成）"""
        for task in self.delayed_tasks[:]:
            task['turns'] -= 1
            if task['turns'] <= 0:
                # 移除准备状态
                if task['source_hero'] and task['skill']:
                    if task['source_hero'].preparing_skill == task['skill']:
                        task['source_hero'].preparing_skill = None
                # 执行战法效果
                if task['skill'] and task['skill'].effect_config is not None and task['skill'].effect_config != []:
                    executor = NodeGraphExecutor(
                        task['skill'].effect_config,
                        self,
                        source_hero=task['source_hero'],
                        current_skill=task['skill']
                    )
                    executor._execute_node(task['node_id'], task['input_data'])
                self.delayed_tasks.remove(task)


class NodeGraphExecutor:
    """节点图执行器"""
    MAX_EXECUTION_DEPTH = 64  # P0-4 FIX: 递归深度限制，防止无限循环
    DEBUG = False  # 调试开关（设为 True 可在控制台输出节点执行过程）

    def __init__(self, graph, context, source_hero=None, current_skill=None):
        self.graph = graph
        self.context = context
        self.source_hero = source_hero
        self.current_skill = current_skill
        self.pin_values = {}
        self.nodes = {node['id']: node for node in graph.get('nodes', [])}
        self.links = graph.get('links', [])
        self._execution_depth = 0  # P0-4 FIX: 当前递归深度
        self._visited_in_path = set()  # P0-4 FIX: 当前执行路径，用于检测循环
        # 快照所有武将的 buff 状态，用于状态过滤判断
        # 这样 Sequence 的后续分支不会看到本帧前面分支刚施加的状态
        self._buff_snapshot = {
            id(hero): [b['type'] for b in hero.buff_list]
            for hero in (context.attacker_side + context.defender_side)
        }

    def _has_status_in_snapshot(self, hero, status_keys):
        """基于快照检查武将是否有指定状态（避免本帧内状态变更影响后续分支判断）"""
        snapshot = self._buff_snapshot.get(id(hero), [])
        if not isinstance(status_keys, (list, tuple)):
            status_keys = [status_keys]
        return any(sk in snapshot for sk in status_keys)

    def _has_any_control_in_snapshot(self, hero):
        """基于快照检查武将是否有任意控制状态"""
        control_types = {'chaos', 'hesitation', 'fright', 'berserk', 'healing_block'}
        snapshot = self._buff_snapshot.get(id(hero), [])
        return any(t in control_types for t in snapshot)

    def execute(self, entry_node_id=None):
        if entry_node_id is None:
            for node in self.nodes.values():
                if node['type'].startswith('Event_'):
                    entry_node_id = node['id']
                    break
        if entry_node_id is not None:
            self._execute_node(entry_node_id, None)

    def _get_influence_factor(self, params):
        """根据'受影响属性'参数计算影响系数。
        返回 value/100，例如施法者谋略120时返回1.2；选"无"时返回1.0"""
        attr_name = params.get('受影响属性', '无')
        if attr_name == '无' or not self.source_hero:
            return 1.0
        attr_map = {'攻击': 'attack', '防御': 'defense', '谋略': 'strategy', '速度': 'speed'}
        attr_key = attr_map.get(attr_name, 'strategy')
        return self.source_hero.get_attr(attr_key) / 100.0

    def _parse_duration(self, duration_val):
        """解析持续时间为数值。支持数字(兼容旧数据)和字符串("1回合"/"本场战斗")。
        本场战斗用 999 表示（远超正常战斗回合数，等同于永久）。"""
        if isinstance(duration_val, (int, float)):
            return int(duration_val)
        if isinstance(duration_val, str):
            if '本场战斗' in duration_val:
                return 999
            # 从"1回合"/"2回合"等提取数字
            m = re.search(r'(\d+)', duration_val)
            return int(m.group(1)) if m else 2
        return 2

    def _execute_node(self, node_id, input_data):
        # P0-4 FIX: 递归深度保护
        self._execution_depth += 1
        if self._execution_depth > self.MAX_EXECUTION_DEPTH:
            print(f"[警告] 节点执行深度超限 ({self.MAX_EXECUTION_DEPTH})，中止执行以防止无限循环")
            self._execution_depth -= 1
            return

        # P0-4 FIX: 循环引用检测（同一条执行路径中不重复执行同一节点）
        if node_id in self._visited_in_path:
            if self.DEBUG:
                print(f"[DEBUG] 跳过循环引用 node_id={node_id}")
            self._execution_depth -= 1
            return
        self._visited_in_path.add(node_id)

        if node_id not in self.nodes:
            if self.DEBUG:
                print(f"[DEBUG] 节点不存在: node_id={node_id}")
            self._visited_in_path.discard(node_id)
            self._execution_depth -= 1
            return
        node = self.nodes[node_id]
        node_type = node['type']
        params = node.get('params', {})
        if self.DEBUG:
            print(f"[DEBUG] 执行节点 id={node_id} type={node_type} params={params}")

        # -------------------- 事件节点 --------------------
        if node_type.startswith('Event_'):
            self._continue_execution(node_id, 'exec_out')

        # -------------------- 流程控制 --------------------
        elif node_type == 'Sequence':
            out_count = params.get('输出数量', 3)
            for i in range(out_count):
                self._continue_execution(node_id, f'exec_out_{i}')

        elif node_type == 'Branch':
            condition = self._get_pin_value(node, 'condition')
            branch = 'exec_true' if condition else 'exec_false'
            self._continue_execution(node_id, branch)

        elif node_type == 'ForEach':
            array = self._get_pin_value(node, 'array') or []
            loop_var = params.get('循环变量名', 'item')
            for item in array:
                # P3-1 FIX: 变量存到武将级 variables，与后续节点 _get_pin_value 读取范围一致
                if self.source_hero:
                    self.source_hero.variables[loop_var] = item
                self._continue_execution(node_id, 'exec_loop')
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'Delay':
            turns = params.get('延迟回合', 2)
            self.context.add_delayed_task(turns, self.current_skill, node_id, input_data, self.source_hero)
            return

        elif node_type == 'DoOnce':
            if not hasattr(self, '_do_once_flag'):
                self._do_once_flag = set()
            if node_id not in self._do_once_flag:
                self._do_once_flag.add(node_id)
                self._continue_execution(node_id, 'exec_out')

        elif node_type == 'Gate':
            open_pin = self._get_pin_value(node, 'open')
            if open_pin is None:
                open_pin = params.get('初始状态', '打开') == '打开'
            if open_pin:
                self._continue_execution(node_id, 'exec_out')

        elif node_type == 'FlipFlop':
            if not hasattr(self, '_flipflop_state'):
                self._flipflop_state = {}
            state = self._flipflop_state.get(node_id, 0)
            if state == 0:
                self._continue_execution(node_id, 'exec_a')
                self._flipflop_state[node_id] = 1
            else:
                self._continue_execution(node_id, 'exec_b')
                self._flipflop_state[node_id] = 0

        # -------------------- 条件判断 --------------------
        elif node_type == 'CompareAttribute':
            target = self._get_pin_value(node, 'target')
            compare_val = self._get_pin_value(node, 'compare_value')
            if target and compare_val is not None:
                attr_map = {'攻击': 'attack', '防御': 'defense', '谋略': 'strategy', '速度': 'speed'}
                attr = attr_map.get(params.get('比较属性', '攻击'), 'attack')
                attr_val = target.get_attr(attr)
                cmp = params.get('比较类型', '大于')
                result = self._compare(attr_val, compare_val, cmp)
                self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'CompareHPPercent':
            target = self._get_pin_value(node, 'target')
            threshold = self._get_pin_value(node, 'threshold')
            if target and threshold is not None:
                percent = target.current_troops / target.max_troops
                cmp = params.get('比较类型', '大于')
                result = self._compare(percent, threshold, cmp)
                self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'HasStatus':
            target = self._get_pin_value(node, 'target')
            status_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                          '暴走': 'berserk', '禁疗': 'healing_block'}
            status = status_map.get(params.get('状态类型', '混乱'), 'chaos')
            result = self._has_status_in_snapshot(target, status) if target else False
            self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'RandomChance':
            chance = params.get('几率', 0.3)
            result = random.random() < chance
            self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'CheckCount':
            value = self._get_pin_value(node, 'value')
            threshold = params.get('阈值', 5)
            cmp = params.get('比较类型', '大于等于')
            result = self._compare(value, threshold, cmp)
            self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'CheckVariable':
            var_val = self._get_pin_value(node, 'value')
            expected = params.get('期望值', 0)
            result = (var_val == expected)
            self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'CompareValues':
            a = self._get_pin_value(node, 'a')
            b = self._get_pin_value(node, 'b')
            cmp = params.get('比较类型', '大于')
            result = self._compare(a, b, cmp)
            self.pin_values[(node_id, 'result')] = result
            self._continue_execution(node_id, 'exec_out')

        # -------------------- 效果节点（按照简化算法） --------------------
        elif node_type == 'ApplyDamage':
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = self._get_default_targets(node)
            damage_type = params.get('伤害类型', '攻击')  # 攻击/策略
            rate = params.get('伤害率', 100.0)
            # 属性影响系数
            influence = self._get_influence_factor(params)
            # 计算属性
            if self.source_hero:
                if damage_type == '攻击':
                    base_attr = self.source_hero.get_attr('attack')
                    target_attr = lambda t: t.get_attr('defense') / 2
                else:
                    base_attr = self.source_hero.get_attr('strategy')
                    target_attr = lambda t: t.get_attr('strategy') / 2
                base_val = base_attr - target_attr(targets[0]) if targets else 0
            else:
                base_attr = 100
                base_val = 100  # 默认值
            # 增伤系数（4种全部参与计算）
            dmg_increase = self.source_hero.get_total_damage_increase() if self.source_hero else 0
            dmg_reduction = self.source_hero.get_total_damage_reduction() if self.source_hero else 0
            target_taken = targets[0].get_total_damage_taken_increase() if targets else 0
            target_reduced = targets[0].get_total_damage_taken_reduction() if targets else 0
            # 增减伤 value 存的是百分比值（如 60 表示 60%），需除以 100
            final_val = base_val * (rate / 100) * influence * (1 + dmg_increase / 100 - dmg_reduction / 100) * (1 + target_taken / 100 - target_reduced / 100)
            real_dmg = 0
            for target in targets:
                real_dmg += target.take_damage(final_val, damage_type)
            if real_dmg > 0:
                # 公式追踪
                formula_steps = [
                    f"基础 = {damage_type}力({base_attr}) - 目标{damage_type}力({targets[0].get_attr('defense') if targets else '?'})/2 = {base_val:.1f}",
                ]
                if influence != 1.0:
                    formula_steps.append(f"影响系数 = {influence:.2f}")
                if rate != 100.0:
                    formula_steps.append(f"伤害率 = {rate}%")
                formula_steps.append(
                    f"最终 = {base_val:.1f} × ({rate}/100) × {influence:.2f} × (1+{dmg_increase}-{dmg_reduction}) × (1+{target_taken}-{target_reduced}) = {final_val:.1f}"
                )
                if int(max(final_val, 10)) != int(final_val):
                    formula_steps.append(f"保底 = max({final_val:.1f}, 10) = {int(max(final_val, 10))}")
                formula_steps.append(f"实际造成伤害 = {real_dmg}")
                # 目标剩余兵力（取主目标）
                target_remaining = targets[0].current_troops if targets else 0
                self.context.add_log("skill_effect", {
                    "hero": self.source_hero.name,
                    "skill": self.current_skill.name if self.current_skill else "未知",
                    "effect_type": "damage",
                    "target": ", ".join(t.name for t in targets),
                    "damage": real_dmg,
                    "damage_type": damage_type,
                    "target_remaining": target_remaining,
                    "formula": {
                        "type": f"战法伤害({damage_type})",
                        "steps": formula_steps,
                    }
                })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'ApplyHeal':
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = self._get_default_targets(node)
            heal_rate = params.get('恢复率', 100)
            influence = self._get_influence_factor(params)
            if self.source_hero:
                def_val = self.source_hero.get_attr('defense')
                strg_val = self.source_hero.get_attr('strategy')
                base_val = max(def_val, strg_val)
                heal = base_val * (heal_rate / 100) * influence
            else:
                base_val = 100
                heal = 100
            real_heal = 0
            for target in targets:
                real_heal += target.take_heal(heal)
            if real_heal > 0:
                # 公式追踪
                formula_steps = [
                    f"基础 = max(防御力({def_val}), 谋略({strg_val})) = {base_val}",
                    f"恢复 = {base_val} × ({heal_rate}/100) × {influence:.2f} = {heal:.1f}",
                    f"实际治疗 = {real_heal}",
                ]
                # 目标剩余兵力（取主目标）
                target_remaining = targets[0].current_troops if targets else 0
                self.context.add_log("skill_effect", {
                    "hero": self.source_hero.name,
                    "skill": self.current_skill.name if self.current_skill else "未知",
                    "effect_type": "heal",
                    "target": ", ".join(t.name for t in targets),
                    "amount": real_heal,
                    "target_remaining": target_remaining,
                    "formula": {
                        "type": "治疗",
                        "steps": formula_steps,
                    }
                })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'ApplyControl':
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = self._get_default_targets(node)
            control_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                           '暴走': 'berserk', '禁疗': 'healing_block'}
            ctrl_type = control_map.get(params.get('控制类型', '混乱'), 'chaos')
            duration = self._parse_duration(params.get('持续时间', 2))
            duration_text = params.get('持续时间', '2回合') if isinstance(params.get('持续时间'), str) else f"{duration}回合"
            for target in targets:
                target.add_buff(ctrl_type, 1, duration, self.current_skill.name if self.current_skill else "未知")
                self.context.add_log("skill_effect", {
                    "hero": self.source_hero.name,
                    "skill": self.current_skill.name if self.current_skill else "未知",
                    "effect_type": "control",
                    "target": target.name,
                    "control_type": params['控制类型'],
                    "duration": duration_text
                })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'ApplyStatus':
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = self._get_default_targets(node)
            status_map = {'先手': 'first_strike', '连击': 'double_attack', '洞察': 'insight',
                          '规避': 'evasion', '援护': 'taunt'}
            status = status_map.get(params.get('增益类型', '规避'), 'evasion')
            duration = self._parse_duration(params.get('持续时间', 2))
            evasion_count = params.get('规避次数', 2)
            for target in targets:
                if status == 'evasion':
                    target.add_buff(status, evasion_count, duration, self.current_skill.name if self.current_skill else "未知")
                else:
                    target.add_buff(status, 1, duration, self.current_skill.name if self.current_skill else "未知")
                self.context.add_log("skill_effect", {
                    "hero": self.source_hero.name,
                    "skill": self.current_skill.name if self.current_skill else "未知",
                    "effect_type": "status",
                    "target": target.name,
                    "status_type": params['增益类型'],
                    "duration": params.get('持续时间', '')
                })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'ModifyAttribute':
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = self._get_default_targets(node)
            attr_map = {'攻击': 'attack', '防御': 'defense', '谋略': 'strategy', '速度': 'speed', '攻击距离': 'attack_distance'}
            attr_choice = params.get('属性类型', '谋略')
            # 支持多选列表和旧格式字符串
            if isinstance(attr_choice, list):
                attr_choices = attr_choice
            else:
                attr_choices = [attr_choice]
            attr_keys = [attr_map.get(a, 'strategy') for a in attr_choices]
            attr_names = list(attr_choices)
            calc_mode = params.get('计算方式', '百分比')
            modify_type = params.get('修改方式', '增加')
            value = params.get('修改值', 15)
            duration = self._parse_duration(params.get('持续时间', 2))
            duration_text = params.get('持续时间', '2回合') if isinstance(params.get('持续时间'), str) else f"{duration}回合"
            source = self.current_skill.name if self.current_skill else "未知"

            # 符号：增加为正，减少为负
            sign = 1 if modify_type == '增加' else -1
            # 属性影响系数（仅百分比模式生效）
            influence = self._get_influence_factor(params) if calc_mode == '百分比' else 1.0

            for target in targets:
                for attr_key, attr_name in zip(attr_keys, attr_names):
                    if calc_mode == '百分比':
                        # 百分比模式：value 受属性影响，如谋略120时 15% × 1.2 = 18%
                        buff_value = sign * value * influence
                        target.add_buff(f"attr_{attr_key}", buff_value, duration, source, mode='percent')
                        unit = "%"
                    else:
                        # 固定值模式：不受额外属性影响
                        buff_value = sign * value
                        target.add_buff(f"attr_{attr_key}", buff_value, duration, source, mode='fixed')
                        unit = "点"
                    # 获取加成后的当前属性值
                    current_val = target.get_attr(attr_key)
                    self.context.add_log("skill_effect", {
                        "hero": self.source_hero.name,
                        "skill": self.current_skill.name if self.current_skill else "未知",
                        "effect_type": "modify_attr",
                        "target": target.name,
                        "attr_name": attr_name,
                        "modify_type": modify_type,
                        "value": f"{abs(value * influence):.1f}{unit}",
                        "current_value": current_val,
                        "duration": duration_text
                    })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'ApplyDamageBuff':
            """伤害增减buff：增伤/减伤/受创提升/被伤害减少"""
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = [self.source_hero] if self.source_hero else []
            buff_type_map = {
                '增伤': 'damage_increase',
                '减伤': 'damage_reduction',
                '受创提升': 'damage_taken_increase',
                '被伤害减少': 'damage_taken_reduction',
            }
            buff_type_key = params.get('Buff类型', '增伤')
            buff_type = buff_type_map.get(buff_type_key, 'damage_increase')
            value = params.get('数值', 120)
            duration = self._parse_duration(params.get('持续时间', '本场战斗'))
            source = self.current_skill.name if self.current_skill else "未知"
            for target in targets:
                target.add_buff(buff_type, value, duration, source)
            # 日志
            self.context.add_log("skill_effect", {
                "hero": self.source_hero.name,
                "skill": self.current_skill.name if self.current_skill else "未知",
                "effect_type": "status",
                "target": ", ".join(t.name for t in targets),
                "status_type": f"{buff_type_key}{value}%",
                "duration": params.get('持续时间', '')
            })
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'RemoveDebuff':
            """移除负面效果（控制状态 + 持续伤害）"""
            targets = self._get_pin_value(node, 'targets')
            if targets is None:
                targets = [self.source_hero] if self.source_hero else []
            remove_types = params.get('移除类型', ['全部负面'])
            # 负面buff类型映射
            control_types = {'混乱', '犹豫', '怯战', '暴走', '禁疗'}
            remove_all = '全部负面' in remove_types
            removed_count = 0
            for target in targets:
                original_len = len(target.buff_list)
                if remove_all:
                    # 移除所有控制类 + 持续伤害(dot_) 类buff
                    target.buff_list = [
                        b for b in target.buff_list
                        if b['type'] not in control_types and not b['type'].startswith('dot_')
                    ]
                else:
                    # 只移除选中的控制类型
                    type_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                                '暴走': 'berserk', '禁疗': 'healing_block'}
                    remove_keys = {type_map.get(rt, rt) for rt in remove_types}
                    target.buff_list = [
                        b for b in target.buff_list if b['type'] not in remove_keys
                    ]
                removed_count += original_len - len(target.buff_list)
            if removed_count > 0:
                self.context.add_log("skill_effect", {
                    "hero": self.source_hero.name,
                    "skill": self.current_skill.name if self.current_skill else "未知",
                    "effect_type": "status",
                    "target": ", ".join(t.name for t in targets),
                    "status_type": f"移除负面x{removed_count}",
                    "duration": ""
                })
            self._continue_execution(node_id, 'exec_out')

        # -------------------- 目标选择 --------------------
        elif node_type == 'GetEnemy':
            # P1-3 FIX: 只选择攻击距离内的存活目标
            enemy_side = self.context.defender_side if self.source_hero in self.context.attacker_side else self.context.attacker_side
            if self.source_hero:
                alive_in_range = [
                    h for h in enemy_side
                    if h.is_alive and abs(h.position_index - self.source_hero.position_index) <= self.source_hero.get_attack_distance()
                ]
            else:
                alive_in_range = [h for h in enemy_side if h.is_alive]
            if not alive_in_range:
                alive_in_range = [h for h in enemy_side if h.is_alive]  # fallback: 所有存活敌人

            # 状态过滤（基于快照，避免本帧内状态变更影响后续分支判断）
            status_filter = params.get('状态过滤', '无')
            if isinstance(status_filter, list) and status_filter:
                # 新格式：多选列表，如 ["混乱", "暴走"]
                status_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                              '暴走': 'berserk', '禁疗': 'healing_block'}
                status_keys = [status_map[s] for s in status_filter if s in status_map]
                if status_keys:
                    filtered = [h for h in alive_in_range
                                if self._has_status_in_snapshot(h, status_keys)]
                    # 过滤后如果为空，仍然尝试在全体存活敌人中过滤
                    if not filtered:
                        fallback_pool = [h for h in enemy_side if h.is_alive]
                        filtered = [h for h in fallback_pool
                                    if self._has_status_in_snapshot(h, status_keys)]
                    alive_in_range = filtered
            elif isinstance(status_filter, str) and status_filter != '无':
                # 旧格式兼容：单选字符串
                status_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                              '暴走': 'berserk', '禁疗': 'healing_block', '任意控制': '_any_control'}
                if status_filter == '任意控制':
                    filtered = [h for h in alive_in_range if self._has_any_control_in_snapshot(h)]
                    if not filtered:
                        fallback_pool = [h for h in enemy_side if h.is_alive]
                        filtered = [h for h in fallback_pool if self._has_any_control_in_snapshot(h)]
                    alive_in_range = filtered
                else:
                    status_key = status_map.get(status_filter)
                    if status_key:
                        filtered = [h for h in alive_in_range if self._has_status_in_snapshot(h, status_key)]
                        if not filtered:
                            fallback_pool = [h for h in enemy_side if h.is_alive]
                            filtered = [h for h in fallback_pool if self._has_status_in_snapshot(h, status_key)]
                        alive_in_range = filtered

            count = params.get('数量', '全体')
            if count == '全体':
                targets = alive_in_range[:]
            elif count == '群体(2)':
                targets = random.sample(alive_in_range, min(2, len(alive_in_range)))
            else:
                targets = random.sample(alive_in_range, min(1, len(alive_in_range)))
            self.pin_values[(node_id, 'targets')] = targets
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'GetAlly':
            # P1-3 FIX: 只选择存活的友军
            target_pool = self.context.attacker_side if self.source_hero in self.context.attacker_side else self.context.defender_side
            alive_allies = [h for h in target_pool if h.is_alive]

            # 状态过滤（基于快照，避免本帧内状态变更影响后续分支判断）
            status_filter = params.get('状态过滤', '无')
            if isinstance(status_filter, list) and status_filter:
                # 新格式：多选列表，如 ["混乱", "暴走"]
                status_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                              '暴走': 'berserk', '禁疗': 'healing_block'}
                status_keys = [status_map[s] for s in status_filter if s in status_map]
                if status_keys:
                    alive_allies = [h for h in alive_allies
                                    if self._has_status_in_snapshot(h, status_keys)]
            elif isinstance(status_filter, str) and status_filter != '无':
                # 旧格式兼容：单选字符串
                status_map = {'混乱': 'chaos', '犹豫': 'hesitation', '怯战': 'fright',
                              '暴走': 'berserk', '禁疗': 'healing_block'}
                if status_filter == '任意控制':
                    alive_allies = [h for h in alive_allies if self._has_any_control_in_snapshot(h)]
                else:
                    status_key = status_map.get(status_filter)
                    if status_key:
                        alive_allies = [h for h in alive_allies if self._has_status_in_snapshot(h, status_key)]

            count = params.get('数量', '群体(2)')
            if count == '全体':
                targets = alive_allies[:]
            elif count == '群体(2)':
                targets = random.sample(alive_allies, min(2, len(alive_allies)))
            else:
                targets = random.sample(alive_allies, min(1, len(alive_allies)))
            self.pin_values[(node_id, 'targets')] = targets
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'GetSelf':
            self.pin_values[(node_id, 'targets')] = [self.source_hero] if self.source_hero else []
            self._continue_execution(node_id, 'exec_out')

        # -------------------- 数值操作（保留） --------------------
        elif node_type == 'GetAttributeValue':
            target = self._get_pin_value(node, 'target')
            attr_map = {'攻击': 'attack', '防御': 'defense', '谋略': 'strategy', '速度': 'speed'}
            attr = attr_map.get(params.get('属性', '谋略'), 'strategy')
            val = target.get_attr(attr) if target else 0
            self.pin_values[(node_id, 'value')] = val
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'CalculateDamage':
            attr_val = self._get_pin_value(node, 'attribute')
            base_rate = params.get('基础伤害率', 100)
            coef = params.get('属性系数', 1)
            damage = base_rate * (1 + (attr_val / 100) * coef)
            self.pin_values[(node_id, 'damage')] = damage
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'SetVariable':
            var_name = params.get('变量名', 'var')
            value = self._get_pin_value(node, 'value')
            self.source_hero.variables[var_name] = value
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'AddToVariable':
            var_name = params.get('变量名', 'var')
            inc = self._get_pin_value(node, 'increment')
            current = self.source_hero.variables.get(var_name, 0)
            self.source_hero.variables[var_name] = current + inc
            self._continue_execution(node_id, 'exec_out')

        elif node_type == 'GetVariable':
            var_name = params.get('变量名', 'var')
            val = self.source_hero.variables.get(var_name, 0)
            self.pin_values[(node_id, 'value')] = val
            self._continue_execution(node_id, 'exec_out')

        else:
            self.context.add_log("unknown_node", {"node_type": node_type})
            self._continue_execution(node_id, 'exec_out')

        # P0-4 FIX: 方法退出时清理路径标记和深度计数
        self._visited_in_path.discard(node_id)
        self._execution_depth -= 1

    def _get_pin_value(self, node, pin_id):
        """获取数据引脚输入值。优先从缓存读取，避免重复执行已完成的节点。"""
        # 先检查是否有直接连接的数据引脚
        for link in self.links:
            if link.get('to_node') == node['id'] and link.get('to_pin') == pin_id:
                from_node_id = link.get('from_node')
                from_pin = link.get('from_pin')
                if from_node_id is None or from_pin is None:
                    continue
                if from_node_id not in self.nodes:
                    continue
                # 优先使用缓存值，避免对已执行节点重复执行导致循环误报
                cached = self.pin_values.get((from_node_id, from_pin))
                if cached is not None:
                    return cached
                # 缓存未命中，需要执行源节点获取数据
                self._execute_node(from_node_id, None)
                return self.pin_values.get((from_node_id, from_pin))
        return None

    def _get_default_targets(self, node):
        """默认目标：根据节点类型智能推断"""
        node_type = node.get('type', '')
        if node_type in ('ApplyHeal', 'ApplyStatus', 'ModifyAttribute'):
            # 增益/治疗/属性修改默认目标为友军全体
            if self.source_hero:
                ally_side = self.context.attacker_side if self.source_hero in self.context.attacker_side else self.context.defender_side
                return [h for h in ally_side if h.is_alive]
            return []
        else:
            # 伤害/控制默认目标为敌方全体
            return [h for h in self.context.defender_side if h.is_alive]

    def _compare(self, a, b, cmp):
        if cmp == '大于':
            return a > b
        elif cmp == '小于':
            return a < b
        elif cmp == '等于':
            return a == b
        elif cmp == '大于等于':
            return a >= b
        elif cmp == '小于等于':
            return a <= b
        return False

    def _continue_execution(self, node_id, output_pin_id):
        for link in self.links:
            if link.get('from_node') == node_id and link.get('from_pin') == output_pin_id:
                to_node_id = link.get('to_node')
                if to_node_id is not None:
                    self._execute_node(to_node_id, None)
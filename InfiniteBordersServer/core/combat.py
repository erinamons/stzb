# core/combat.py
import random
import time
from .battle_core import BattleHero, BattleContext, NodeGraphExecutor


class CombatEngine:
    @staticmethod
    def apply_building_effects_to_heroes(battle_heroes, building_effects: dict, hero_objects: list):
        """
        将建筑效果作为永久 buff 注入战斗武将。
        building_effects: manager.get_building_effects() 返回的dict
        hero_objects: 原始 Hero 或 NPCHero 对象列表（用于读取 faction）
        """
        if not building_effects:
            return

        atk_bonus = building_effects.get("attack_bonus", 0)
        def_bonus = building_effects.get("defense_bonus", 0)
        spd_bonus = building_effects.get("speed_bonus", 0)
        strg_bonus = building_effects.get("strategy_bonus", 0)
        faction_bonus = building_effects.get("faction_bonus", {})

        for i, bh in enumerate(battle_heroes):
            # 全军通用加成（尚武营/疾风营/铁壁营/军机营 + 武将巨像/沙盘阵图）
            if atk_bonus:
                bh.add_buff("attr_attack", atk_bonus, duration=9999, source="building_attack")
            if def_bonus:
                bh.add_buff("attr_defense", def_bonus, duration=9999, source="building_defense")
            if spd_bonus:
                bh.add_buff("attr_speed", spd_bonus, duration=9999, source="building_speed")
            if strg_bonus:
                bh.add_buff("attr_strategy", strg_bonus, duration=9999, source="building_strategy")

            # 点将台阵营专属加成
            hero_obj = hero_objects[i] if i < len(hero_objects) else None
            if hero_obj and hasattr(hero_obj, 'faction') and hero_obj.faction:
                fb = faction_bonus.get(hero_obj.faction, {})
                if fb.get("atk"):
                    bh.add_buff("attr_attack", fb["atk"], duration=9999, source="altar_atk")
                if fb.get("def"):
                    bh.add_buff("attr_defense", fb["def"], duration=9999, source="altar_def")
                if fb.get("spd"):
                    bh.add_buff("attr_speed", fb["spd"], duration=9999, source="altar_spd")
                if fb.get("strg"):
                    bh.add_buff("attr_strategy", fb["strg"], duration=9999, source="altar_strg")

    @staticmethod
    def simulate_battle(attacker_heroes, defender_heroes, max_rounds=8, max_battles=50,
                        attacker_building_effects: dict = None, defender_building_effects: dict = None):
        """模拟战斗，返回 (是否胜利, 结构化战报dict)。
        平局时双方保留剩余兵力重新开战，直到分出胜负。
        attacker_building_effects / defender_building_effects: 双方玩家建筑效果（可选）
        """
        # 转换为战斗英雄
        battle_attackers = [BattleHero(h) for h in attacker_heroes]
        battle_defenders = [BattleHero(h) for h in defender_heroes]

        # 注入建筑效果 buff（开战前）
        if attacker_building_effects:
            CombatEngine.apply_building_effects_to_heroes(
                battle_attackers, attacker_building_effects, attacker_heroes)
        if defender_building_effects:
            CombatEngine.apply_building_effects_to_heroes(
                battle_defenders, defender_building_effects, defender_heroes)

        all_reports = []  # 收集每轮战斗的战报

        for battle_num in range(1, max_battles + 1):
            context, winner, command_log = CombatEngine._run_single_battle(
                battle_attackers, battle_defenders, max_rounds
            )

            # 生成本轮战报
            report = CombatEngine.generate_report(
                attacker_heroes, defender_heroes,
                battle_attackers, battle_defenders,
                context, winner, command_log
            )

            # 记录第几场战斗
            if battle_num > 1:
                report["header"]["battle_num"] = battle_num
                report["header"]["result_text"] = (
                    f"第{battle_num}场战斗结束 - "
                    + ("进攻方胜利" if winner == "attack" else
                       "防守方胜利" if winner == "defend" else
                       f"{context.current_round}回合未分胜负")
                )

            all_reports.append(report)

            if winner != "draw":
                break

            # === 平局：双方保留剩余兵力，重置战斗状态，重新开战 ===
            battle_attackers = [BattleHero(h) for h in attacker_heroes]
            battle_defenders = [BattleHero(h) for h in defender_heroes]
            # 注入建筑效果 buff（每场重新应用）
            if attacker_building_effects:
                CombatEngine.apply_building_effects_to_heroes(
                    battle_attackers, attacker_building_effects, attacker_heroes)
            if defender_building_effects:
                CombatEngine.apply_building_effects_to_heroes(
                    battle_defenders, defender_building_effects, defender_heroes)
            # 将上一轮的剩余兵力应用到新战斗英雄
            for i, bat in enumerate(battle_attackers):
                bat.current_troops = all_reports[-1]["attacker_heroes"][i]["remaining_troops"]
            for i, bat in enumerate(battle_defenders):
                bat.current_troops = all_reports[-1]["defender_heroes"][i]["remaining_troops"]

        # 合并战报：多场战斗合并为一份连续战报
        final_report = all_reports[0]
        if len(all_reports) > 1:
            final_report["header"]["total_battles"] = len(all_reports)
            final_report["header"]["result_text"] = (
                f"经过{len(all_reports)}场战斗，进攻方胜利"
                if winner == "attack" else
                f"经过{len(all_reports)}场战斗，防守方胜利"
                if winner == "defend" else
                f"经过{len(all_reports)}场战斗仍未分胜负"
            )
            # 合并后续战报的回合数据，用 "--- 第N场战斗 ---" 分隔
            for extra in all_reports[1:]:
                bn = extra["header"].get("battle_num", 0)
                # 添加场次分隔标记
                final_report["rounds"].append({
                    "round": -bn,  # 负数表示场次分隔
                    "events": [{"type": "battle_break", "data": {
                        "battle_num": bn,
                        "attacker_troops": sum(h["remaining_troops"] for h in extra["attacker_heroes"]),
                        "defender_troops": sum(h["remaining_troops"] for h in extra["defender_heroes"]),
                    }}]
                })
                # 追加该场的回合数据
                final_report["rounds"].extend(extra["rounds"])
                # 更新武将战后状态为最终状态
                final_report["attacker_heroes"] = extra["attacker_heroes"]
                final_report["defender_heroes"] = extra["defender_heroes"]

        return winner == "attack", final_report

    @staticmethod
    def _run_single_battle(battle_attackers, battle_defenders, max_rounds):
        """执行单场战斗（可能因平局被循环调用），返回 (context, winner, command_log)"""
        # 设置站位索引（按照顺序，前锋=1，中军=2，大营=3）
        for i, h in enumerate(battle_attackers):
            h.position_index = i + 1
        for i, h in enumerate(battle_defenders):
            h.position_index = i + 1

        context = BattleContext(battle_attackers, battle_defenders)
        all_heroes = battle_attackers + battle_defenders

        # ==================== 准备回合 (Round 0) ====================
        context.add_log("round_start", {"round": 0})

        # 1. 记录设施加成（从 buff_list 中提取 building 来源的 buff）
        for hero in all_heroes:
            building_buffs = [b for b in hero.buff_list if b.get('source', '').startswith('building_') or b.get('source', '').startswith('altar_')]
            if building_buffs:
                buffs_info = []
                for b in building_buffs:
                    src = b['source']
                    attr_name = src.replace('building_', '').replace('altar_', '')
                    attr_cn = {'attack': '攻击', 'defense': '防御', 'speed': '速度', 'strategy': '谋略'}.get(attr_name, attr_name)
                    buffs_info.append({"attr": attr_cn, "value": b['value'], "source": src})
                context.add_log("building_bonus", {
                    "hero": hero.name,
                    "buffs": buffs_info
                })

        # 2. 触发被动战法（优先级最高，不受控制效果影响）
        passive_log = []
        for hero in all_heroes:
            for skill in getattr(hero, 'passive_skills', []):
                if skill.effect_config is not None and skill.effect_config != []:
                    executor = NodeGraphExecutor(
                        skill.effect_config, context,
                        source_hero=hero, current_skill=skill
                    )
                    executor.execute()
                    passive_log.append({
                        "caster": hero.name,
                        "skill": skill.name,
                        "effect": skill.description
                    })

        # 3. 触发指挥战法（优先级低于被动战法）
        command_log = []
        for hero in all_heroes:
            for skill in hero.command_skills:
                if skill.effect_config is not None and skill.effect_config != []:
                    executor = NodeGraphExecutor(skill.effect_config, context, source_hero=hero, current_skill=skill)
                    executor.execute()
                    command_log.append({
                        "caster": hero.name,
                        "skill": skill.name,
                        "effect": skill.description
                    })
        context.command_skill_log = command_log

        # 准备回合结束：记录被动战法和指挥战法生效汇总
        if passive_log:
            context.add_log("passive_summary", {"skills": passive_log})
        if command_log:
            context.add_log("command_summary", {"skills": command_log})

        # 回合循环
        for round_num in range(1, max_rounds + 1):
            context.current_round = round_num
            context.add_log("round_start", {"round": round_num})

            # === 回合开始：触发被动战法（优先级最高，不受控制效果影响） ===
            for hero in all_heroes:
                if hero.is_alive:
                    for skill in getattr(hero, 'passive_skills', []):
                        if skill.effect_config is not None and skill.effect_config != []:
                            executor = NodeGraphExecutor(
                                skill.effect_config, context,
                                source_hero=hero, current_skill=skill
                            )
                            executor.execute()

            # 回合开始：推进延迟任务（延迟效果，非准备战法）
            context.advance_delayed_tasks()

            # 处理持续伤害（所有英雄）
            for hero in all_heroes:
                if hero.is_alive:
                    for buff in hero.buff_list:
                        if buff['type'].startswith('dot_'):
                            dot_rate = buff['value']
                            damage = int(hero.max_troops * (dot_rate / 100))
                            hero.take_damage(damage, 'dot')
                            context.add_log("dot_damage", {
                                "target": hero.name,
                                "damage": damage,
                                "dot_type": buff['type'][4:]
                            })

            # 推进所有武将的准备战法进度
            all_alive = [h for h in all_heroes if h.is_alive]
            for hero in all_alive:
                if hero.advance_prepare():
                    context.add_log("prepare_done", {
                        "hero": hero.name,
                        "skill": hero.pending_skill.name
                    })

            # 确定行动顺序（按速度降序）
            all_alive.sort(key=lambda h: -h.get_attr('speed'))
            action_order = [h.name for h in all_alive]
            context.add_log("action_order", {"order": action_order})

            # 武将依次行动
            for hero in all_alive:
                if not hero.is_alive:
                    continue
                context.current_acting_hero = hero
                actions = []

                # 1. 优先释放准备完成的战法
                if hero.pending_skill:
                    skill = hero.pending_skill
                    hero.pending_skill = None
                    if skill.effect_config is not None and skill.effect_config != []:
                        hero.skill_cast_count[skill.name] = hero.skill_cast_count.get(skill.name, 0) + 1
                        # 先记录战法发动日志，再执行效果（保证日志顺序正确）
                        context.add_log("hero_action", {
                            "hero": hero.name,
                            "actions": [{"type": "pending_skill", "skill": skill.name}]
                        })
                        executor = NodeGraphExecutor(skill.effect_config, context, source_hero=hero, current_skill=skill)
                        executor.execute()

                # 2. 尝试主动战法（如果没有混乱）
                if not hero.is_chaos():
                    for skill in hero.active_skills:
                        # 如果正在准备该战法，不能再次发动
                        if hero.preparing_skill == skill:
                            context.add_log("hero_action", {
                                "hero": hero.name,
                                "actions": [{"type": "preparing", "skill": skill.name}]
                            })
                            continue
                        # 犹豫检查
                        if hero.is_hesitation():
                            context.add_log("hero_action", {
                                "hero": hero.name,
                                "actions": [{"type": "hesitation", "skill": skill.name}]
                            })
                            continue
                        # 发动概率
                        if random.random() * 100 <= skill.activation_rate:
                            if skill.preparation_turns > 0:
                                # 开始准备
                                hero.start_prepare(skill)
                                context.add_log("hero_action", {
                                    "hero": hero.name,
                                    "actions": [{"type": "start_prepare", "skill": skill.name, "turns": skill.preparation_turns}]
                                })
                            else:
                                # 直接释放
                                if skill.effect_config is not None and skill.effect_config != []:
                                    hero.skill_cast_count[skill.name] = hero.skill_cast_count.get(skill.name, 0) + 1
                                    # 先记录战法发动日志，再执行效果（保证日志顺序正确）
                                    context.add_log("hero_action", {
                                        "hero": hero.name,
                                        "actions": [{"type": "active_skill", "skill": skill.name}]
                                    })
                                    executor = NodeGraphExecutor(skill.effect_config, context, source_hero=hero, current_skill=skill)
                                    executor.execute()
                        else:
                            context.add_log("hero_action", {
                                "hero": hero.name,
                                "actions": [{"type": "active_fail", "skill": skill.name}]
                            })

                # 3. 普通攻击（如果没有怯战且没有混乱）
                if not hero.is_fright() and not hero.is_chaos():
                    # 获取攻击目标（最远距离优先）
                    enemy_army = context.defender_side if hero in context.attacker_side else context.attacker_side
                    target = CombatEngine.get_attack_target(hero, enemy_army)
                    if target:
                        atk_name, dmg, formula, target_remaining = hero.normal_attack(target)
                        if atk_name:
                            act_entry = {"type": "normal_attack", "target": target.name, "damage": dmg}
                            if formula:
                                act_entry["formula"] = formula
                            if target_remaining is not None:
                                act_entry["target_remaining"] = target_remaining
                            actions.append(act_entry)
                    else:
                        actions.append({"type": "no_target"})

                # 记录普攻/无目标日志（战法类行动已提前写入）
                if actions:
                    context.add_log("hero_action", {
                        "hero": hero.name,
                        "actions": actions
                    })

            # 回合结束：衰减 buff 持续时间
            for hero in all_heroes:
                hero.process_buff_round_end()

            # 检查战斗结束
            attacker_alive = any(h.is_alive for h in battle_attackers)
            defender_alive = any(h.is_alive for h in battle_defenders)
            if not attacker_alive or not defender_alive:
                break

        # 战斗结果
        winner = None
        if attacker_alive and not defender_alive:
            winner = "attack"
        elif not attacker_alive and defender_alive:
            winner = "defend"
        else:
            winner = "draw"

        return context, winner, command_log

    @staticmethod
    def get_attack_target(attacker, enemy_army):
        """获取攻击目标（最远距离优先）"""
        alive = [h for h in enemy_army if h.is_alive]
        if not alive:
            return None
        # 筛选距离内可攻击的目标
        valid = [h for h in alive if attacker.position_index + attacker.get_attack_distance() >= h.position_index]
        if not valid:
            return None
        # 按站位从大到小排序，取第一个（最远）
        valid.sort(key=lambda h: -h.position_index)
        return valid[0]

    @staticmethod
    def _get_army_name(heroes):
        """安全获取部队名称"""
        if heroes and hasattr(heroes[0], 'owner') and heroes[0].owner:
            return heroes[0].owner.username
        return "守军"

    @staticmethod
    def _build_hero_info(hero, battle_hero, position):
        """构建单个武将的战报信息"""
        skill_name = "无"
        prep_turns = 0
        if hero.template and hero.template.innate_skill:
            skill_name = hero.template.innate_skill.name
            prep_turns = hero.template.innate_skill.preparation_turns or 0
        return {
            "name": hero.name,
            "position": position,
            "initial_troops": hero.troops,
            "remaining_troops": battle_hero.current_troops,
            "is_alive": battle_hero.is_alive,
            "skill": skill_name,
            "prep_turns": prep_turns,
            "attack": battle_hero.base_attack,
            "defense": battle_hero.base_defense,
            "strategy": battle_hero.base_strategy,
            "speed": battle_hero.base_speed,
            "skill_cast_count": dict(battle_hero.skill_cast_count)
        }

    @staticmethod
    def generate_report(original_attackers, original_defenders, battle_attackers, battle_defenders, context, winner, command_log):
        """生成结构化战报，返回 dict（率土之滨风格分区布局）"""
        get_name = CombatEngine._get_army_name
        positions = ["前锋", "中军", "大营"]

        # 构建双方武将信息
        atk_heroes = [
            CombatEngine._build_hero_info(orig, bat, positions[i])
            for i, (orig, bat) in enumerate(zip(original_attackers, battle_attackers))
        ]
        def_heroes = [
            CombatEngine._build_hero_info(orig, bat, positions[i])
            for i, (orig, bat) in enumerate(zip(original_defenders, battle_defenders))
        ]

        # 将 context.log 转为可序列化格式，按回合分组
        rounds = []
        current_round = None
        for entry in context.log:
            entry_type = entry.get("type", "")
            entry_data = entry.get("data", {})

            if entry_type == "round_start":
                current_round = {
                    "round": entry_data.get("round", 0),
                    "events": []
                }
                rounds.append(current_round)
            elif current_round is not None:
                current_round["events"].append({
                    "type": entry_type,
                    "data": entry_data
                })

        # 战斗结果文案
        if winner == "attack":
            result_text = "进攻方胜利"
        elif winner == "defend":
            result_text = "防守方胜利"
        else:
            result_text = f"{context.current_round}回合未分胜负，战斗平局"

        # 收集准备回合信息（兵种克制、建筑加成等）
        preparation_info = {
            "troop_bonus": [],     # 兵种特性加成（预留）
        }
        # 从 context.log 中提取准备回合的被动/指挥战法汇总
        for entry in context.log:
            if entry.get("type") == "passive_summary":
                preparation_info["passive_skills"] = entry.get("data", {}).get("skills", [])
            elif entry.get("type") == "command_summary":
                preparation_info["command_skills"] = entry.get("data", {}).get("skills", [])

        return {
            # 头部信息
            "header": {
                "attacker_name": get_name(original_attackers),
                "defender_name": get_name(original_defenders),
                "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "total_rounds": context.current_round,
                "result": winner,
                "result_text": result_text
            },
            # 双方阵容
            "attacker_heroes": atk_heroes,
            "defender_heroes": def_heroes,
            # 准备回合信息（兵种加成、被动/指挥战法）
            "preparation": preparation_info,
            # 指挥战法（保留兼容）
            "command_skills": [
                {"caster": c["caster"], "skill": c["skill"], "effect": c["effect"]}
                for c in command_log
            ],
            # 回合详情（round 0 = 准备回合，round 1~N = 正式回合）
            "rounds": rounds
        }

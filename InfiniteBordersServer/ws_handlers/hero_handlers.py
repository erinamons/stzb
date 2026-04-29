# ws_handlers/hero_handlers.py
# 武将相关消息处理：查询列表、加点、减点、满加、升阶、GM命令
from shared.protocol import MsgType, build_packet
from models.database import SessionLocal
from models.schema import Player, Hero, Skill, Troop
from core.connection_manager import manager


async def send_heroes(username: str):
    """查询并发送武将列表。"""
    _db = SessionLocal()
    try:
        db_player = _db.query(Player).filter(Player.username == username).first()
        if not db_player:
            await manager.send_to(username, build_packet(MsgType.ERROR, "玩家数据丢失"))
            return
        heroes = _db.query(Hero).filter(Hero.owner_id == db_player.id).all()
        h_data = []
        for h in heroes:
            t = h.template
            if not t:
                print(f"警告：武将 {h.id} 的 template 为 None")
                continue
            try:
                total_pts = (h.level // 10) * 10 + h.bonus_points
                used_pts = h.p_atk + h.p_def + h.p_strg + h.p_sie + h.p_spd

                innate_skill_name = ""
                if t.innate_skill_id:
                    skill = _db.query(Skill).filter(Skill.id == t.innate_skill_id).first()
                    if skill:
                        innate_skill_name = skill.name
                skill_2_name = ""
                if h.skill_2_id:
                    skill = _db.query(Skill).filter(Skill.id == h.skill_2_id).first()
                    if skill:
                        skill_2_name = skill.name
                skill_3_name = ""
                if h.skill_3_id:
                    skill = _db.query(Skill).filter(Skill.id == h.skill_3_id).first()
                    if skill:
                        skill_3_name = skill.name

                atk = int(t.atk + (h.level - 1) * t.atk_g + h.p_atk)
                defense = int(t.defs + (h.level - 1) * t.def_g + h.p_def)
                strategy = int(t.strg + (h.level - 1) * t.strg_g + h.p_strg)
                siege = int(t.sie + (h.level - 1) * t.sie_g + h.p_sie)
                speed = int(t.spd + (h.level - 1) * t.spd_g + h.p_spd)

                h_data.append({
                    "id": h.id,
                    "name": t.name,
                    "stars": t.stars,
                    "level": h.level,
                    "exp": h.exp,
                    "rank": h.rank,
                    "template_id": t.id,
                    "p_atk": h.p_atk,
                    "p_def": h.p_def,
                    "p_strg": h.p_strg,
                    "p_spd": h.p_spd,
                    "faction": t.faction,
                    "troop_type": t.troop_type,
                    "cost": t.cost,
                    "range": t.attack_range,
                    "atk": atk,
                    "atk_g": t.atk_g,
                    "def": defense,
                    "def_g": t.def_g,
                    "strg": strategy,
                    "strg_g": t.strg_g,
                    "sie": siege,
                    "sie_g": t.sie_g,
                    "spd": speed,
                    "spd_g": t.spd_g,
                    "unallocated": total_pts - used_pts,
                    "troops": h.troops,
                    "max_troops": h.max_troops,
                    "stamina": h.stamina,
                    "max_stamina": h.max_stamina,
                    "skills": [innate_skill_name, skill_2_name, skill_3_name],
                })
            except Exception as e:
                print(f"处理武将 {h.id} 时出错: {e}")
                continue
        await manager.send_to(username, build_packet(MsgType.RES_HEROES, h_data))
    except Exception as e:
        print(f"send_heroes 错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, "获取武将列表失败"))
    finally:
        _db.close()


async def handle_add_point(username, db, db_player, msg_data):
    """武将加点。"""
    from ws_handlers.hero_handlers import send_heroes
    try:
        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        total_pts = (hero.level // 10) * 10 + hero.bonus_points
        used_pts = hero.p_atk + hero.p_def + hero.p_strg + hero.p_sie + hero.p_spd
        if total_pts - used_pts > 0:
            if attr == "atk":
                hero.p_atk += 1
            elif attr == "def":
                hero.p_def += 1
            elif attr == "strg":
                hero.p_strg += 1
            elif attr == "spd":
                hero.p_spd += 1
            else:
                await manager.send_to(username, build_packet(MsgType.ERROR, "无效属性"))
                return
            db.commit()
            await send_heroes(username)
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "没有可用属性点"))
    except Exception as e:
        print(f"加点错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"加点失败: {e}"))


async def handle_cheat_level(username, db, db_player, msg_data):
    """GM命令：武将快速升级。"""
    from ws_handlers.hero_handlers import send_heroes
    if not msg_data.get("_gm_token"):
        await manager.send_to(username, build_packet(MsgType.ERROR, "无权限"))
        return
    try:
        hero = db.query(Hero).filter(Hero.id == msg_data.get("hero_id"), Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        if hero.level < 50:
            hero.level = min(50, hero.level + 10)
            db.commit()
            await manager.send_to(
                username, build_packet(MsgType.ERROR, f"{hero.template.name} 升级啦！当前Lv.{hero.level}")
            )
            await send_heroes(username)
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "已达等级上限"))
    except Exception as e:
        print(f"升级错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"升级失败: {e}"))


async def handle_rank_up(username, db, db_player, msg_data):
    """武将升阶：消耗同名卡。"""
    from ws_handlers.hero_handlers import send_heroes
    try:
        hero_id = msg_data.get("hero_id")
        material_id = msg_data.get("material_id")
        hero = db.query(Hero).filter(Hero.id == hero_id, Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        if hero.rank >= 5:
            await manager.send_to(username, build_packet(MsgType.ERROR, "已达最高阶"))
            return
        if not material_id:
            await manager.send_to(username, build_packet(MsgType.ERROR, "请选择一张同名武将卡用于升阶"))
            return
        material = db.query(Hero).filter(
            Hero.id == material_id,
            Hero.owner_id == db_player.id,
            Hero.template_id == hero.template_id,
            Hero.id != hero_id
        ).first()
        if not material:
            await manager.send_to(username, build_packet(MsgType.ERROR, "无效的升阶材料（需同名武将卡）"))
            return
        mat_in_troop = db.query(Troop).filter(
            Troop.owner_id == db_player.id,
            (Troop.slot1_hero_id == material_id)
            | (Troop.slot2_hero_id == material_id)
            | (Troop.slot3_hero_id == material_id)
        ).first()
        if mat_in_troop:
            await manager.send_to(username, build_packet(MsgType.ERROR, "该武将卡正在部队中，无法用作升阶材料"))
            return
        db.delete(material)
        hero.rank += 1
        hero.bonus_points += 10
        db.commit()
        await send_heroes(username)
        await manager.send_to(username, build_packet(MsgType.ERROR,
            f"{hero.name} 升阶成功！当前阶数 {hero.rank}/5，获得10点自由属性"))
    except Exception as e:
        print(f"升阶错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"升阶失败: {e}"))


async def handle_sub_point(username, db, db_player, msg_data):
    """武将减点。"""
    from ws_handlers.hero_handlers import send_heroes
    try:
        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        if attr == "atk" and hero.p_atk > 0:
            hero.p_atk -= 1
        elif attr == "def" and hero.p_def > 0:
            hero.p_def -= 1
        elif attr == "strg" and hero.p_strg > 0:
            hero.p_strg -= 1
        elif attr == "spd" and hero.p_spd > 0:
            hero.p_spd -= 1
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "无法减少该属性"))
            return
        db.commit()
        await send_heroes(username)
    except Exception as e:
        print(f"减点错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, f"减点失败: {e}"))


async def handle_max_point(username, db, db_player, msg_data):
    """武将最大加点（一键全加）。"""
    from ws_handlers.hero_handlers import send_heroes
    try:
        h_id, attr = msg_data.get("hero_id"), msg_data.get("attr")
        hero = db.query(Hero).filter(Hero.id == h_id, Hero.owner_id == db_player.id).first()
        if not hero:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将不存在"))
            return
        total_pts = (hero.level // 10) * 10 + hero.bonus_points
        used_pts = hero.p_atk + hero.p_def + hero.p_strg + hero.p_sie + hero.p_spd
        available = total_pts - used_pts
        if available <= 0:
            await manager.send_to(username, build_packet(MsgType.ERROR, "没有可用属性点"))
            return
        if attr == "atk":
            hero.p_atk += available
        elif attr == "def":
            hero.p_def += available
        elif attr == "strg":
            hero.p_strg += available
        elif attr == "spd":
            hero.p_spd += available
        else:
            await manager.send_to(username, build_packet(MsgType.ERROR, "无效属性"))
            return
        db.commit()
        await send_heroes(username)
    except Exception as e:
        print(f"最大加点错误: {e}")
        await manager.send_to(username, build_packet(MsgType.ERROR, f"最大加点失败: {e}"))

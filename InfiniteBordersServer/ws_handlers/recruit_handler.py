# ws_handlers/recruit_handler.py
# 武将招募处理
import random
from shared.protocol import MsgType, build_packet
from models.schema import Player, CardPack, CardPackDrop, HeroTemplate, Hero
from core.connection_manager import manager
from ws_handlers.hero_handlers import send_heroes


async def handle_recruit(username, state, db, db_player, msg_data):
    """处理卡包招募请求。"""
    try:
        pack = db.query(CardPack).filter(CardPack.id == msg_data.get("pack_id")).first()
        if not pack:
            await manager.send_to(username, build_packet(MsgType.ERROR, "卡包不存在"))
            return
        if pack.cost_type == "tiger" and db_player.tiger_tally >= pack.cost_amount:
            db_player.tiger_tally -= pack.cost_amount
        elif pack.cost_type == "copper" and db_player.copper >= pack.cost_amount:
            db_player.copper -= pack.cost_amount
        else:
            await manager.send_to(
                username,
                build_packet(MsgType.ERROR, f"{'虎符' if pack.cost_type == 'tiger' else '铜币'}不足！"),
            )
            return

        drops = db.query(CardPackDrop).filter(CardPackDrop.pack_id == pack.id).all()
        if not drops:
            await manager.send_to(username, build_packet(MsgType.ERROR, "卡包没有掉落配置"))
            return
        t_id = random.choices([d.template_id for d in drops], weights=[d.weight for d in drops], k=1)[0]
        t = db.query(HeroTemplate).filter(HeroTemplate.id == t_id).first()
        if not t:
            await manager.send_to(username, build_packet(MsgType.ERROR, "武将模板不存在"))
            return

        new_hero = Hero(
            owner_id=db_player.id,
            template_id=t.id,
            name=t.name,
            stars=t.stars,
            attack=int(t.atk),
            defense=int(t.defs),
            strategy=int(t.strg),
            speed=int(t.spd),
            faction=t.faction,
            troop_type=t.troop_type,
            cost=t.cost,
            rank=0,
            duplicates=0,
            bonus_points=0,
            stamina=100,
            max_stamina=100
        )
        db.add(new_hero)
        db.commit()
        msg = f"★金光一闪★ 获得 {t.stars}星【{t.faction}·{t.name}】！"

        state["currencies"]["copper"] = db_player.copper
        state["currencies"]["tiger_tally"] = db_player.tiger_tally
        await manager.send_to(username, build_packet(MsgType.RES_RECRUIT, msg))
        await send_heroes(username)
    except Exception as e:
        print(f"招募错误: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_to(username, build_packet(MsgType.ERROR, f"招募失败: {e}"))

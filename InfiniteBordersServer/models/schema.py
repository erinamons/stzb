from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from models.database import Base
import time


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String, default="")            # 密码（空=无密码，兼容旧数据）
    wood = Column(Integer, default=5000)
    iron = Column(Integer, default=5000)
    stone = Column(Integer, default=5000)
    grain = Column(Integer, default=10000)
    copper = Column(Integer, default=10000)
    jade = Column(Integer, default=0)
    tiger_tally = Column(Integer, default=0)
    spawn_x = Column(Integer)
    spawn_y = Column(Integer)
    main_city_level = Column(Integer, default=1)   # 主城等级
    max_troops = Column(Integer, default=3)        # 最大部队数量

    heroes = relationship("Hero", back_populates="owner", cascade="all, delete-orphan")
    tiles = relationship("Tile", back_populates="owner")
    troops = relationship("Troop", back_populates="owner", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    level = Column(Integer, default=1)              # 战法等级（预留）
    quality = Column(String)                        # 品质: S/A/B/C
    skill_type = Column(String)                     # 类型: 主动/被动/指挥/追击
    activation_rate = Column(Integer)               # 发动率 (0-100)
    range = Column(Integer)                         # 有效距离
    target_type = Column(String)                    # 目标类型（UI用）
    troop_type = Column(String)                     # 兵种限制: 通用/步兵/骑兵/弓兵
    description = Column(String)                    # 战法描述（展示用）
    effect = Column(String)                         # 保留字段（可废弃）
    effect_config = Column(JSON)                    # 节点图 JSON，存储效果配置
    preparation_turns = Column(Integer, default=0)  # 准备回合数（0表示无需准备）


class HeroTemplate(Base):
    __tablename__ = "hero_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    stars = Column(Integer)
    atk = Column(Float)
    defs = Column(Float)
    strg = Column(Float)
    sie = Column(Float)
    spd = Column(Float)
    atk_g = Column(Float)
    def_g = Column(Float)
    strg_g = Column(Float)
    sie_g = Column(Float)
    spd_g = Column(Float)
    attack_range = Column(Integer, default=2)
    faction = Column(String, default="群")
    troop_type = Column(String, default="步兵")
    cost = Column(Float, default=2.5)
    innate_skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)   # 自带战法

    innate_skill = relationship("Skill", foreign_keys=[innate_skill_id])


class Hero(Base):
    __tablename__ = "heroes"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("players.id"))
    template_id = Column(Integer, ForeignKey("hero_templates.id"))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    p_atk = Column(Integer, default=0)
    p_def = Column(Integer, default=0)
    p_strg = Column(Integer, default=0)
    p_sie = Column(Integer, default=0)
    p_spd = Column(Integer, default=0)
    skill_2_id = Column(Integer, ForeignKey("skills.id"), nullable=True)   # 第二战法槽
    skill_3_id = Column(Integer, ForeignKey("skills.id"), nullable=True)   # 第三战法槽

    # 从模板继承的固定值（用于快速读取）
    name = Column(String)
    stars = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    strategy = Column(Integer)
    speed = Column(Integer)
    faction = Column(String)
    troop_type = Column(String)
    cost = Column(Float)

    # 兵力系统
    troops = Column(Integer, default=1000)       # 当前兵力
    max_troops = Column(Integer, default=1000)  # 最大兵力

    # 升阶系统
    rank = Column(Integer, default=1)            # 当前阶数（1-5）
    duplicates = Column(Integer, default=0)      # 可升阶次数（重复武将数量）
    bonus_points = Column(Integer, default=0)    # 升阶获得的额外属性点

    # 体力系统
    stamina = Column(Integer, default=100)       # 当前体力
    max_stamina = Column(Integer, default=100)   # 最大体力

    owner = relationship("Player", back_populates="heroes")
    template = relationship("HeroTemplate")
    skill_2 = relationship("Skill", foreign_keys=[skill_2_id])
    skill_3 = relationship("Skill", foreign_keys=[skill_3_id])


class CardPack(Base):
    __tablename__ = "card_packs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    cost_type = Column(String)   # tiger / copper
    cost_amount = Column(Integer)


class CardPackDrop(Base):
    __tablename__ = "card_pack_drops"
    id = Column(Integer, primary_key=True, index=True)
    pack_id = Column(Integer, ForeignKey("card_packs.id"))
    template_id = Column(Integer, ForeignKey("hero_templates.id"))
    weight = Column(Float)


class Tile(Base):
    __tablename__ = "tiles"
    id = Column(Integer, primary_key=True, index=True)
    x = Column(Integer, index=True)
    y = Column(Integer, index=True)
    terrain = Column(String)
    level = Column(Integer)
    region = Column(String, default="未知")
    city_type = Column(String, nullable=True)   # 州府/郡城/县城/关口
    city_name = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("players.id"), nullable=True)

    owner = relationship("Player", back_populates="tiles")


class Troop(Base):
    __tablename__ = "troops"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("players.id"))
    name = Column(String, default="新编部队")
    slot1_hero_id = Column(Integer, ForeignKey("heroes.id"), nullable=True)
    slot2_hero_id = Column(Integer, ForeignKey("heroes.id"), nullable=True)
    slot3_hero_id = Column(Integer, ForeignKey("heroes.id"), nullable=True)

    owner = relationship("Player", back_populates="troops")
    slot1_hero = relationship("Hero", foreign_keys=[slot1_hero_id])
    slot2_hero = relationship("Hero", foreign_keys=[slot2_hero_id])
    slot3_hero = relationship("Hero", foreign_keys=[slot3_hero_id])


class NPCHero:
    """P0-5 FIX: 正式NPC数据模型，替代 class Dummy: pass。
    兼容 BattleHero 所需的全部属性。
    """

    def __init__(self, level: int):
        self.id = -1
        self.name = f"Lv{level}守军"
        self.stars = min(5, level)
        self.attack = 30 + level * 15
        self.defense = 30 + level * 15
        self.strategy = 40 + level * 5
        self.speed = 40 + level * 5
        self.troops = max(1, level * 800)
        self.max_troops = max(1, level * 800)
        self.template = None
        self.innate_skill = None
        self.skill_2 = None
        self.skill_3 = None


class BattleReport(Base):
    """战报历史记录表。每场战斗保存一份完整战报。"""
    __tablename__ = "battle_reports"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), index=True)  # 战斗所属玩家
    attacker_id = Column(Integer, ForeignKey("players.id"), nullable=True)  # 进攻方玩家ID（PVP时）
    tile_x = Column(Integer, index=True)     # 战斗发生地格坐标
    tile_y = Column(Integer, index=True)
    is_victory = Column(Integer, default=0)  # 1=胜利 0=失败
    report = Column(JSON)                    # 完整的结构化战报dict
    created_at = Column(String, default=lambda: time.strftime('%Y-%m-%d %H:%M:%S'))  # SQLite兼容用String

    player = relationship("Player", foreign_keys=[player_id])


# ============================================================
# 主城建筑系统
# ============================================================

class BuildingConfig(Base):
    """建筑基础配置表（全局唯一，GM后台管理，重建数据库不丢失）。"""
    __tablename__ = "building_configs"

    id = Column(Integer, primary_key=True, index=True)
    building_key = Column(String, unique=True, nullable=False, index=True)  # 建筑唯一标识
    building_name = Column(String, nullable=False)                          # 显示名称
    category = Column(String, default="military")     # 分类: core/resource/military/defense/special
    unlock_palace_level = Column(Integer, default=0)  # 需要城主府几级解锁（0=初始可用）
    max_level = Column(Integer, default=1)            # 该建筑自身最高等级
    sort_order = Column(Integer, default=0)           # 同一解锁等级内的显示排序
    description = Column(String, default="")          # 功能描述
    # 前置建筑条件（JSON数组，每个元素 {"key": "building_key", "level": N}）
    # 例如：仓库需要 ["palace:2", "residence:1"] 表示城主府2级+民居1级
    # 空列表或null表示只需城主府等级即可
    prerequisites = Column(JSON, default=list)
    # UI 布局坐标（阶梯式布局中该建筑的位置，预留）
    layout_row = Column(Integer, default=0)           # 所在行（0=城主府行，1-8对应壹到捌）
    layout_col = Column(Integer, default=0)           # 所在列（同行内的位置）


class BuildingLevelConfig(Base):
    """建筑每级配置表（消耗资源 + 等级效果，GM后台管理）。"""
    __tablename__ = "building_level_configs"

    id = Column(Integer, primary_key=True, index=True)
    building_key = Column(String, nullable=False, index=True)  # 关联 BuildingConfig.building_key
    level = Column(Integer, nullable=False)                     # 等级（1~max_level）
    cost_wood = Column(Integer, default=0)     # 升级消耗木材
    cost_iron = Column(Integer, default=0)     # 升级消耗铁矿
    cost_stone = Column(Integer, default=0)    # 升级消耗石料
    cost_grain = Column(Integer, default=0)    # 升级消耗粮草
    cost_copper = Column(Integer, default=0)   # 升级消耗铜币
    # 等级效果（JSON，灵活存储各种数值加成）
    # 例如城主府: {"durability": 500, "cost_cap": 8.0}
    #     兵营:   {"troop_capacity": 2000}
    effects = Column(JSON, default=dict)


class PlayerBuilding(Base):
    """玩家建筑实例表（每个玩家每种建筑一条记录）。"""
    __tablename__ = "player_buildings"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    building_key = Column(String, nullable=False, index=True)  # 关联 BuildingConfig.building_key
    level = Column(Integer, default=0)                          # 当前等级（0=未建造）

    player = relationship("Player", backref="buildings")


# ============================================================
# GM 管理员权限系统
# ============================================================

class GmAdmin(Base):
    """GM 管理员账号表。"""
    __tablename__ = "gm_admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)       # 明文密码
    role = Column(String, default="admin")          # super_admin / admin
    created_at = Column(String, default=lambda: time.strftime('%Y-%m-%d %H:%M:%S'))
    permissions = Column(Text, nullable=True)       # JSON 权限配置


# 默认权限配置
DEFAULT_GM_PERMISSIONS = {
    "tabs": {
        "dashboard": "editable",    # editable / readonly / hidden
        "player": "editable",
        "skill": "editable",
        "hero": "editable",
        "pack": "editable",
        "building": "editable",
        "report": "editable",
        "snapshot": "editable",
    },
    "player_detail": {
        "edit_username": True,      # 可修改用户名
        "edit_password": True,      # 可修改密码
        "edit_position": True,      # 可修改出生点
        "edit_resources": True,     # 可修改资源（木材/铁矿/石料/粮草）
        "edit_currencies": True,    # 可修改货币（铜币/玉符/虎符）
        "edit_heroes": True,        # 可管理武将（添加/移除）
        "edit_buildings": True,     # 可管理建筑（升级/降级）
    }
}


class GmOperationLog(Base):
    """GM 操作日志表。"""
    __tablename__ = "gm_operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, nullable=False, index=True)
    operator = Column(String, nullable=False)      # 操作人（GM 用户名）
    action = Column(String, nullable=False)         # 操作类型：create/update/delete/error
    target_type = Column(String, default="")        # 目标类型：player/skill/hero/pack/building/admin 等
    target_id = Column(String, default="")          # 目标 ID
    detail = Column(String, default="")             # 操作详情（JSON 或纯文本）
    error_hash = Column(String, default="")         # 错误摘要的哈希（用于去重）
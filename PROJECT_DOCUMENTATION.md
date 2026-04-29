# InfiniteBorders 项目完整文档

> **最后更新**: 2026-04-04  
> **项目类型**: 2D MMO SLG 沙盘战略游戏（类率土之滨）  
> **当前阶段**: 阶段2（战斗系统、节点编辑器、主城建筑系统）

---

## 目录

1. [项目概述](#1-项目概述)
2. [环境配置与启动](#2-环境配置与启动)
3. [项目结构总览](#3-项目结构总览)
4. [服务端架构详解](#4-服务端架构详解)
5. [客户端架构详解](#5-客户端架构详解)
6. [共享协议模块](#6-共享协议模块)
7. [数据库模型](#7-数据库模型)
8. [战斗系统](#8-战斗系统)
9. [战法节点图系统](#9-战法节点图系统)
10. [主城建筑系统](#10-主城建筑系统)
11. [地图系统](#11-地图系统)
12. [数据编辑器（DataEditor）](#12-数据编辑器dataeditor)
13. [节点编辑器（NodeEditor）](#13-节点编辑器nodeeditor)
14. [GM 控制台](#14-gm-控制台)
15. [通信协议完整列表](#15-通信协议完整列表)
16. [开发指南](#16-开发指南)
17. [已知问题与注意事项](#17-已知问题与注意事项)
18. [历史修复记录](#18-历史修复记录)

---

## 1. 项目概述

### 1.1 游戏概念
InfiniteBorders 是一款 2D MMO SLG（大型多人在线策略）沙盘战略游戏，灵感来源于《率土之滨》。玩家在一张六边形网格地图上发展势力、招募武将、配置战法、出征战斗、占领土地。

### 1.2 技术栈
| 层级 | 技术 |
|------|------|
| 服务端 | Python 3.11 + FastAPI + WebSocket + SQLAlchemy + SQLite |
| 客户端 | Pygame + asyncio + websockets |
| 工具 | tkinter（GM控制台、数据编辑器、节点编辑器） |
| 数据库 | SQLite（文件：`infinite_borders.sqlite3`） |
| 通信 | WebSocket（JSON 数据包） |

### 1.3 项目路径
```
E:/pyproject/PythonProject/
├── InfiniteBordersServer/    # 服务端
├── InfiniteBordersClient/    # 客户端
├── shared/                   # 共享协议模块
│   └── protocol.py           # 通信协议定义（单一权威源）
├── requirements.txt
└── .venv/                    # 虚拟环境
```

### 1.4 团队规范
- **代码注释**: 中文
- **缩进**: 4空格
- **团队水平**: 初级到中级

---

## 2. 环境配置与启动

### 2.1 环境要求
- Python 3.11+
- pip 依赖：见 `requirements.txt`（fastapi, uvicorn, websockets, pygame, sqlalchemy, pygame 等）

### 2.2 虚拟环境
```bash
# 创建虚拟环境
python -m venv E:/pyproject/PythonProject/.venv

# 激活（Windows PowerShell）
E:\pyproject\PythonProject\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r E:/pyproject/PythonProject/requirements.txt
```

### 2.3 启动顺序

#### 启动服务端（含 GM 控制台）
```bash
cd E:/pyproject/PythonProject/InfiniteBordersServer
python server.py
```
- FastAPI 服务监听 `0.0.0.0:8000`
- WebSocket 端点：`/ws/{username}`
- 同时启动 tkinter GM 控制台
- 首次启动自动建表 + 加载建筑配置

#### 启动客户端
```bash
cd E:/pyproject/PythonProject/InfiniteBordersClient
python main.py
```
- 窗口：1024×768
- 连接地址：`ws://127.0.0.1:8000/ws/{username}`

#### 启动数据编辑器（独立）
```bash
cd E:/pyproject/PythonProject/InfiniteBordersServer
python data_editor.py              # 离线模式（直接操作本地 SQLite）
python data_editor.py --online     # 在线模式（连接服务器 HTTP API）
```

### 2.4 初始化数据库
```bash
cd E:/pyproject/PythonProject/InfiniteBordersServer
python init_db.py                  # 全量重置（删除所有数据重建）
```

数据库有两种重置模式：
- **全量重置** (`init_database(keep_templates=False)`)：DROP ALL + CREATE ALL，所有数据重建
- **轻量重置** (`init_database(keep_templates=True)`)：只清玩家数据/地图/战报，保留武将模板/战法/卡包/建筑配置

---

## 3. 项目结构总览

### 3.1 服务端 (`InfiniteBordersServer/`)
```
InfiniteBordersServer/
├── server.py              # FastAPI 入口 + WebSocket 端点
├── config.py              # 服务器配置（端口/地图参数/颜色）
├── init_db.py             # 数据库初始化/重置
├── building_configs.py    # 30个建筑定义 + 消耗/效果数据
├── hex_utils.py           # 六边形工具函数
├── scenarios.py           # 地图场景预设（城池/关口/地形）
├── protocol.py            # [废弃] 旧协议，用 shared/protocol.py
├── data_editor.py         # 独立数据编辑器（tkinter）
├── data_editor_api.py     # 数据编辑器 HTTP API（FastAPI Router）
├── node_editor.py         # 战法节点图编辑器（tkinter Canvas）
├── server_gui.py          # [旧] GUI 启动器（已被 server.py 替代）
├── server_runner.py       # [辅助] 纯服务启动（不含 GM GUI）
├── gm_building_editor.py  # [旧] 独立建筑编辑器（保留可单独使用）
├── gm_console/            # GM 控制台（tkinter Notebook）
│   ├── __init__.py        # ServerGMConsole + 暗色主题
│   └── tabs/              # 各管理标签页
│       ├── building_tab.py
│       └── ...
├── models/                # 数据库模型
│   ├── database.py        # SQLAlchemy 引擎/Session/Base
│   └── schema.py          # ORM 模型定义
├── core/                  # 核心逻辑
│   ├── connection_manager.py  # WebSocket连接管理 + 资源产出
│   ├── game_loop.py           # 服务器心跳循环 + 启动事件
│   ├── battle_core.py         # 战斗核心（BattleHero/BattleContext/NodeGraphExecutor）
│   └── combat.py              # CombatEngine（战斗模拟 + 战报生成）
├── ws_handlers/           # WebSocket 消息处理器
│   ├── __init__.py        # 消息路由分发入口
│   ├── march_handler.py   # 行军出征
│   ├── hero_handlers.py   # 武将管理（查询/加点/升阶）
│   ├── recruit_handler.py # 招募武将
│   ├── troop_handlers.py  # 部队管理（编辑/招兵）
│   ├── building_handlers.py   # 建筑系统（查询/升级/详情）
│   ├── report_handler.py  # 战报历史
│   ├── shop_handlers.py   # 商店/充值/兑换
│   └── ...
├── db_snapshots/          # 数据库快照存储目录
└── infinite_borders.sqlite3  # SQLite 数据库文件
```

### 3.2 客户端 (`InfiniteBordersClient/`)
```
InfiniteBordersClient/
├── main.py                # Pygame 入口 + 状态管理 + 事件分发
├── client_config.py       # 客户端配置（窗口/地图参数/颜色）
├── client_protocol.py     # [废弃] 旧协议，用 shared/protocol.py
├── hex_utils.py           # 六边形工具函数（客户端版本）
├── scenarios.py           # 地图场景预设（客户端版本）
├── ui_utils.py            # UI 工具函数（圆角矩形/渐变/按钮/城池标签）
├── network.py             # WebSocket 异步通信层
├── network/
│   └── __init__.py        # [空] 网络模块占位
├── ui/                    # UI 面板模块
│   ├── __init__.py
│   ├── hud.py             # HUD 绘制（顶栏/消息栏/底栏/右按钮/地图过滤）
│   ├── map_renderer.py    # 地图渲染（六边形格子 + 宏观地图）
│   ├── hero_panel.py      # 武将面板（武将列表/武将详情/招募面板）
│   ├── troops_panel.py    # 部队面板（部队列表/编辑部队）
│   ├── building_panel.py  # 建筑面板（建筑列表/建筑详情）
│   ├── report_panel.py    # 战报面板（历史列表/详细战报）
│   ├── recharge_panel.py  # 充值面板
│   └── panels/            # [子目录] 面板子组件
├── state/                 # [预留] 状态管理
└── _*.py                  # [调试/检查脚本]
```

### 3.3 共享模块 (`shared/`)
```
shared/
├── protocol.py            # 通信协议定义（MsgType 类 + build_packet 函数）
```

---

## 4. 服务端架构详解

### 4.1 启动流程
```
server.py
├── FastAPI app 创建
├── CORS 中间件配置
├── setup_startup_event(app) → 注册 startup 事件
│   ├── Base.metadata.create_all()  # 自动建表
│   ├── load_building_configs(db)   # 加载建筑配置
│   └── asyncio.create_task(game_loop())  # 启动心跳循环
├── app.include_router(snapshot_router)  # 注册快照 API
├── WebSocket 端点 /ws/{username}
├── HTTP 端点 /, /api/players
└── ServerGMConsole().mainloop()  # 启动 GM 控制台（阻塞）
```

### 4.2 核心模块

#### 4.2.1 ConnectionManager (`core/connection_manager.py`)
全局单例 `manager`，管理所有在线玩家：
- `active_connections: dict[str, WebSocket]` — 用户名到 WebSocket 连接
- `online_players: dict` — 用户名到在线状态（资源/产出/行军/建筑效果）
- **connect()**: 接受连接 → 加载玩家数据 → 发送全量地图 → 发送资源
- **disconnect()**: 资源写回数据库 → 清理连接
- **recalculate_production()**: 重算每秒资源产出（领地格子 + 建筑产出）
- **recalculate_building_effects()**: 汇总玩家所有建筑效果
- **get_building_effects()**: 获取建筑效果汇总（供战斗系统使用）
- **is_tile_reachable()**: 检查目标格子是否与领地相连
- **get_territory_border()**: 获取领地边界格子

建筑效果汇总 (`building_effects`) 结构：
```python
{
    "storage_cap": 50000,        # 仓库上限
    "troop_slots": 1,            # 可出征队伍数（校场）
    "troop_capacity": 200,       # 单队最大兵力（兵营）
    "vanguard_slots": 0,         # 前锋营武将槽
    "reserve_cap": 0,            # 预备役上限
    "recruit_speed_bonus": 0,    # 招募速度加成%
    "attack_bonus": 0,           # 全军攻击加成
    "defense_bonus": 0,          # 全军防御加成
    "speed_bonus": 0,            # 全军速度加成
    "strategy_bonus": 0,         # 全军谋略加成
    "faction_bonus": {           # 点将台阵营加成
        "汉": {"atk": 0, "def": 0, "spd": 0, "strg": 0},
        "魏": {...}, "蜀": {...}, "吴": {...}, "群": {...}
    },
    "wall_durability": 0,        # 城墙耐久
    "damage_reduction": 0.0,     # 守城伤害减免%
    "physical_damage_reduction": 0.0,  # 物理伤害减免%
    "strategy_damage_reduction": 0.0,  # 策略伤害减免%
    "cost_cap": 8.0,             # COST 上限
    "cost_cap_bonus": 0.0,       # COST 上限加成
    "fame_cap": 0,               # 名望上限
    "copper_per_hour": 0,        # 铜币每小时产出
}
```

#### 4.2.2 GameLoop (`core/game_loop.py`)
异步心跳循环，每秒 tick（`TICK_RATE=1.0`）：
1. **资源累加**: 每秒累加资源产出，应用仓库上限
2. **铜币产出**: 民居产出（`copper_per_hour / 3600`）
3. **资源存库**: 每秒将资源写回数据库
4. **体力恢复**: 每秒恢复 1 点体力
5. **行军处理**: 推进行军倒计时，到达时触发 `_process_march()`
6. **状态同步**: `SYNC_STATE` 推送给客户端

`_process_march()` 行军抵达处理：
1. 查询目标格子
2. 获取部队武将
3. 创建 NPC 守军（`NPCHero`）
4. 调用 `CombatEngine.simulate_battle()` 执行战斗
5. 胜利则占领格子、重算产出、推送 `sync_map`
6. 保存战报到 `BattleReport` 表
7. 推送 `PUSH_REPORT` 给客户端

#### 4.2.3 消息路由 (`ws_handlers/__init__.py`)
`websocket_endpoint()` 是 WebSocket 主入口：
1. 调用 `manager.connect()` 建立连接
2. 循环接收消息 → `_dispatch_message()` 分发到对应 handler
3. 断开时调用 `manager.disconnect()` 资源写回

消息分发映射表：
| 消息类型 | Handler | 模块 |
|---------|---------|------|
| CMD_LOGIN | (connect 时自动处理) | connection_manager |
| CMD_MARCH | handle_march | march_handler |
| CMD_RECHARGE | handle_recharge | shop_handlers |
| CMD_EXCHANGE | handle_exchange | shop_handlers |
| REQ_PACKS | handle_req_packs | shop_handlers |
| CMD_RECRUIT | handle_recruit | recruit_handler |
| REQ_HEROES | send_heroes | hero_handlers |
| CMD_ADD_POINT | handle_add_point | hero_handlers |
| CMD_SUB_POINT | handle_sub_point | hero_handlers |
| CMD_MAX_POINT | handle_max_point | hero_handlers |
| CMD_RANK_UP | handle_rank_up | hero_handlers |
| CMD_CHEAT_LVL | handle_cheat_level | hero_handlers |
| REQ_TROOPS | handle_req_troops | troop_handlers |
| CMD_EDIT_TROOP | handle_edit_troop | troop_handlers |
| CMD_RECRUIT_TROOPS | handle_recruit_troops | troop_handlers |
| REQ_BUILDINGS | handle_req_buildings | building_handlers |
| CMD_UPGRADE_BUILDING | handle_upgrade_building | building_handlers |
| REQ_BUILDING_DETAIL | handle_req_building_detail | building_handlers |
| REQ_REPORT_HISTORY | handle_req_report_history | report_handler |
| CMD_RESET_DATABASE | (GM 专用) | ws_handlers |

---

## 5. 客户端架构详解

### 5.1 主入口 (`main.py`)
`AsyncGameClient` 类是客户端核心：
- **初始化**: Pygame 窗口 + 相机 + 状态变量 + UI 组件
- **事件处理**: `handle_events()` 处理 Pygame 事件 + 按钮点击
- **网络接收**: `network_loop()` 接收 WebSocket 消息 → `_handle_res()` 分发处理
- **渲染循环**: `draw()` 60fps 渲染

### 5.2 状态变量（部分关键变量）
```python
# 地图
game_map = []                    # 服务端返回的地图数据列表
map_dict = {}                    # {(x, y): tile_data} 快速查找
zoom = 1.0                       # 缩放级别
camera_x, camera_y = 0, 0       # 相机位置
in_macro_map = False             # 是否在宏观地图模式

# 资源
resources = {"wood": 0, "iron": 0, "stone": 0, "grain": 0}
currencies = {"copper": 0, "jade": 0, "tiger_tally": 0}

# 面板
current_panel = None             # 当前打开的面板名称
panel_buttons = []               # 当前面板的可点击按钮列表
detail_hero = None               # 当前查看详情的武将

# 武将/部队
heroes_list = []                 # 武将列表
troops_list = []                 # 部队列表
editing_troop = None             # 当前编辑的部队

# 建筑
buildings_data = []              # 建筑列表
building_detail = None           # 建筑详情
building_effects = {}            # 建筑效果汇总

# 战报
report_panel = None              # 当前查看的战报
report_history = []              # 战报历史列表
```

### 5.3 UI 模块架构
```
ui/
├── hud.py              # draw_top_bar, draw_message_bar, draw_bottom_nav,
│                       # draw_right_buttons, draw_map_filter, draw_location_bookmark
├── map_renderer.py     # draw_map (微观), draw_macro_map (宏观)
├── hero_panel.py       # draw_hero_list, draw_hero_detail, draw_recruit_panel, get_star_color
├── troops_panel.py     # draw_troops_panel, draw_edit_troop_panel
├── building_panel.py   # draw_building_panel, draw_building_detail
├── report_panel.py     # draw_report_history, draw_detailed_report
└── recharge_panel.py   # draw_recharge_panel, refresh_recharge_panel
```

### 5.4 面板导航
底部导航栏按钮：`["武将", "招募", "内政", "势力", "国家", "天下", "排行", "系统", "充值", "部队", "战报"]`

`open_panel()` 方法根据面板名称初始化状态并发送请求协议。

### 5.5 客户端渲染特点
- **率土风格**: 暗色主题、圆角矩形、渐变效果
- **六边形地图**: Pointy-top 六边形网格，支持缩放/拖动
- **宏观地图**: 缩小到全局视图查看州域分布
- **战报渲染**: 分区布局（头部→阵容→指挥→回合详情→战损统计）
  - 伤害=红(255,120,120) 治疗=绿(100,255,140) 控制=紫(210,140,255)
  - 战法=蓝(100,220,255) 属性=黄绿(180,200,130)

---

## 6. 共享协议模块

### 6.1 位置
`shared/protocol.py` — 服务端和客户端的**唯一协议权威源**。

### 6.2 导入方式
两端通过 `sys.path` 将父目录加入搜索路径：
```python
# 服务端 (server.py)
_project_root = os.path.dirname(_server_root)
sys.path.insert(0, _project_root)

# 客户端 (main.py)
_project_root = os.path.dirname(_client_root)
sys.path.insert(0, _project_root)
```

### 6.3 协议结构
```python
class MsgType:
    # 基础协议
    CMD_LOGIN = "cmd_login"
    CMD_MARCH = "cmd_march"
    RES_LOGIN = "res_login"
    SYNC_STATE = "sync_state"
    PUSH_REPORT = "push_report"
    ERROR = "error"
    # ... 更多见下方完整列表

def build_packet(msg_type: str, data: dict) -> dict:
    return {"type": msg_type, "data": data}
```

---

## 7. 数据库模型

### 7.1 数据库配置 (`models/database.py`)
- 引擎：SQLite，文件 `infinite_borders.sqlite3`
- `Base = declarative_base()` — 所有 ORM 模型的基类
- `SessionLocal` — Session 工厂
- `get_db()` — FastAPI 依赖注入用的生成器

### 7.2 ORM 模型 (`models/schema.py`)

| 模型 | 表名 | 说明 |
|------|------|------|
| `Player` | players | 玩家（资源/货币/出生点/主城等级） |
| `HeroTemplate` | hero_templates | 武将模板（基础属性/成长率/阵营/兵种/COST） |
| `Hero` | heroes | 玩家武将实例（等级/经验/加点/兵力/体力/升阶） |
| `Skill` | skills | 战法定义（类型/发动率/效果/节点图配置） |
| `CardPack` | card_packs | 卡包（名称/消耗类型/消耗数量） |
| `CardPackDrop` | card_pack_drops | 卡包掉落（卡包→武将模板+权重） |
| `Tile` | tiles | 地图格子（坐标/地形/等级/区域/城池/归属） |
| `Troop` | troops | 部队（3个武将槽位） |
| `BattleReport` | battle_reports | 战报历史（坐标/胜负/完整战报JSON） |
| `BuildingConfig` | building_configs | 建筑基础配置（全局唯一） |
| `BuildingLevelConfig` | building_level_configs | 建筑每级配置（消耗+效果） |
| `PlayerBuilding` | player_buildings | 玩家建筑实例（等级） |
| `NPCHero` | (非ORM) | NPC 守军数据模型 |

### 7.3 Player 模型字段
```python
class Player(Base):
    id, username, spawn_x, spawn_y
    main_city_level     # 主城等级
    max_troops          # 最大部队数量
    # 资源
    wood, iron, stone, grain
    # 货币
    copper, jade, tiger_tally
    # 关系
    heroes → Hero[]
    tiles → Tile[]
    troops → Troop[]
    buildings → PlayerBuilding[]  (via backref)
```

### 7.4 Hero/HeroTemplate 关系
```
HeroTemplate (模板，全局共享)
├── name, stars, faction, troop_type, cost
├── atk, defs, strg, sie, spd (基础属性)
├── atk_g, def_g, strg_g, sie_g, spd_g (成长率)
├── attack_range
└── innate_skill_id → Skill (自带战法)

Hero (实例，属于玩家)
├── owner_id → Player
├── template_id → HeroTemplate
├── level, exp
├── p_atk, p_def, p_strg, p_sie, p_spd (手动加点)
├── troops, max_troops (兵力)
├── rank, duplicates, bonus_points (升阶系统)
├── stamina, max_stamina (体力系统)
├── skill_2_id → Skill (第二战法槽)
├── skill_3_id → Skill (第三战法槽)
└── name, stars, attack, defense, strategy, speed, faction, troop_type, cost
    (从模板继承的固定值，用于快速读取)
```

### 7.5 Skill 模型
```python
class Skill(Base):
    name                    # 战法名称
    level                   # 战法等级（预留）
    quality                 # 品质: S/A/B/C
    skill_type              # 类型: 主动/被动/指挥/追击
    activation_rate         # 发动率 (0-100)
    range                   # 有效距离
    target_type             # 目标类型（UI展示用）
    troop_type              # 兵种限制: 通用/步兵/骑兵/弓兵
    description             # 描述（展示用）
    effect                  # 保留字段（可废弃）
    effect_config           # ★ 节点图 JSON（核心配置）
    preparation_turns       # 准备回合数（0=无需准备）
```

---

## 8. 战斗系统

### 8.1 战斗流程
```
CombatEngine.simulate_battle()
├── 1. 转换为 BattleHero
├── 2. 注入建筑效果 buff
├── 3. 循环（最多 max_battles=50 场）:
│   ├── _run_single_battle()
│   │   ├── 设置站位（前锋=1, 中军=2, 大营=3）
│   │   ├── 释放指挥战法（NodeGraphExecutor）
│   │   ├── 回合循环（最多 max_rounds=8）:
│   │   │   ├── 推进延迟任务
│   │   │   ├── 处理持续伤害
│   │   │   ├── 推进准备战法进度
│   │   │   ├── 按速度排序行动顺序
│   │   │   ├── 武将依次行动:
│   │   │   │   ├── 释放准备完成的战法
│   │   │   │   ├── 尝试主动战法（发动率判定）
│   │   │   │   └── 普通攻击
│   │   │   └── 衰减 buff 持续时间
│   │   └── 返回 (context, winner, command_log)
│   ├── 生成战报 generate_report()
│   └── 平局时保留剩余兵力重新开战
└── 返回 (is_attack_win, final_report)
```

### 8.2 BattleHero（战斗武将）
```python
class BattleHero:
    # 基础属性
    base_attack, base_defense, base_strategy, base_speed
    attack_distance  # 攻击距离
    position_index   # 站位（1=前锋, 2=中军, 3=大营）
    current_troops, max_troops  # 兵力

    # Buff 系统
    buff_list = []  # [{"type", "value", "remaining", "source", "mode"}]
    # mode: 'fixed' (固定值) 或 'percent' (百分比)

    # 战法
    active_skills     # 主动战法列表
    command_skills    # 指挥战法列表
    pursuit_skills    # 追击战法列表
    preparing_skill   # 正在准备的战法
    pending_skill     # 准备完成待释放的战法

    # 变量系统
    variables = {}    # 供 SetVariable/GetVariable 节点使用

    # 计数器
    skill_cast_count = {}  # {skill_name: int}

    # 状态检查方法
    is_chaos(), is_hesitation(), is_fright(), is_berserk(), is_healing_block()
    has_control_status()

    # 核心方法
    get_attr(attr_name)    # 获取含 buff 的属性值
    add_buff(type, value, duration, source, mode)
    take_damage(damage)    # 承受伤害
    take_heal(heal_value)  # 治疗
    normal_attack(target)  # 普通攻击
```

**属性计算公式**：
```python
def get_attr(attr_name):
    base = getattr(self, f"base_{attr_name}")
    delta = sum(b['value'] for b in buff_list if b['type'] == f"attr_{attr_name}" and mode != 'percent')
    pct = sum(b['value'] for b in buff_list if b['type'] == f"attr_{attr_name}" and mode == 'percent')
    return int((base + delta) * (1 + pct / 100.0))
```

### 8.3 战斗规则
- **行动顺序**: 按速度降序
- **攻击目标**: 最远距离优先（在攻击距离内）
- **普攻伤害**: `攻击 - 防御/2` × 增伤系数 × 受创系数
- **控制效果**: 混乱（无法释放主动）、犹豫（主动可能不释放）、怯战（无法普攻）、暴走、禁疗
- **平局**: 双方保留剩余兵力重新开战，最多 50 场
- **保底伤害**: 10 点

### 8.4 建筑效果注入
开战前，`CombatEngine.apply_building_effects_to_heroes()` 将建筑效果作为永久 buff（duration=9999）注入战斗武将：
- 全军加成：攻击/防御/速度/谋略（尚武营/疾风营/铁壁营/军机营）
- 阵营加成：点将台（汉/魏/蜀/吴/群）
- 特殊加成：武将巨像/沙盘阵图

---

## 9. 战法节点图系统

### 9.1 架构概述
战法效果通过**可视化节点图**配置，而非硬编码。

- **存储**: `Skill.effect_config` (JSON)
- **格式**: `{"nodes": [...], "links": [...]}`
- **编辑器**: `NodeEditor` (tkinter Canvas)
- **执行器**: `NodeGraphExecutor` (battle_core.py)

### 9.2 节点图 JSON 格式
```json
{
    "nodes": [
        {
            "id": 0,
            "type": "Event_OnCast",
            "x": 100, "y": 250,
            "params": {}
        },
        {
            "id": 1,
            "type": "Sequence",
            "x": 300, "y": 250,
            "params": {"输出数量": 2}
        }
    ],
    "links": [
        {
            "from_node": 0,
            "from_pin": "exec_out",
            "to_node": 1,
            "to_pin": "exec_in"
        }
    ]
}
```

**兼容性**: `load_from_config()` 同时支持旧格式 `from/to` 和新格式 `from_node/to_node`。

### 9.3 26 种节点类型

#### 事件入口（金色）
| 节点类型 | 说明 |
|---------|------|
| `Event_OnCast` | 战法释放时触发 |
| `Event_BeginCombat` | 战斗开始时触发（指挥战法） |
| `Event_OnPursuit` | 追击时触发 |

#### 流程控制（蓝色）
| 节点类型 | 参数 | 说明 |
|---------|------|------|
| `Sequence` | `输出数量` | 顺序执行多个分支 |
| `Branch` | (condition pin) | 条件分支 |
| `ForEach` | `循环变量名` | 遍历数组 |
| `Delay` | `延迟回合` | 延迟执行 |
| `DoOnce` | — | 仅执行一次 |
| `Gate` | `初始状态` | 门控开关 |
| `FlipFlop` | — | 交替执行 A/B |

#### 条件判断（紫色）
| 节点类型 | 参数 | 输出 |
|---------|------|------|
| `CompareAttribute` | `比较属性`, `比较类型` | result: bool |
| `CompareHPPercent` | `比较类型` | result: bool |
| `HasStatus` | `状态类型` | result: bool |
| `RandomChance` | `几率` | result: bool |
| `CheckCount` | `阈值`, `比较类型` | result: bool |
| `CheckVariable` | `期望值` | result: bool |
| `CompareValues` | `比较类型` | result: bool |

#### 效果节点（红色）
| 节点类型 | 参数 | 说明 |
|---------|------|------|
| `ApplyDamage` | `伤害类型`, `伤害率`, `受影响属性` | 造成伤害 |
| `ApplyHeal` | `恢复率`, `受影响属性` | 治疗 |
| `ApplyControl` | `控制类型`, `持续时间` | 施加控制 |
| `ApplyStatus` | `增益类型`, `持续时间`, `规避次数` | 施加增益 |
| `ModifyAttribute` | `属性类型`, `修改值`, `修改方式`, `持续时间`, `计算方式`, `受影响属性` | 修改属性 |

#### 目标选择（绿色）
| 节点类型 | 参数 | 输出 |
|---------|------|------|
| `GetEnemy` | `数量`, `状态过滤` | targets: BattleHero[] |
| `GetAlly` | `数量`, `状态过滤` | targets: BattleHero[] |
| `GetSelf` | — | targets: [self] |

#### 数值操作（橙色）
| 节点类型 | 参数 | 输出 |
|---------|------|------|
| `GetAttributeValue` | `属性` | value: int |
| `CalculateDamage` | `基础伤害率`, `属性系数` | damage: float |
| `SetVariable` | `变量名` | — |
| `AddToVariable` | `变量名` | — |
| `GetVariable` | `变量名` | value: any |

### 9.4 NodeGraphExecutor 执行机制
```
execute(entry_node_id)
├── 找到入口节点（type 以 Event_ 开头）
└── _execute_node(node_id, input_data)
    ├── 递归深度保护 (MAX_EXECUTION_DEPTH=64)
    ├── 循环引用检测 (_visited_in_path)
    ├── 执行节点逻辑
    └── _continue_execution(node_id, output_pin_id)
        └── 遍历 links 找到连接的下游节点 → _execute_node()
```

**数据引脚机制**：
- 执行引脚 (`exec_in`/`exec_out`)：控制执行流
- 数据引脚 (`targets`/`value`/`result` 等)：传递数据
- `_get_pin_value(node, pin_id)`：从上游节点的数据引脚获取值
  - 优先使用缓存 (`pin_values`)
  - 缓存未命中时执行源节点

**默认目标推断** (`_get_default_targets`)：
- 伤害/控制 → 敌方全体存活
- 治疗/增益/属性修改 → 友方全体存活

### 9.5 战法分类与触发时机
| 类型 | 触发时机 | 说明 |
|------|---------|------|
| 指挥 | 战斗开始前 | 100% 发动，buff 友军 |
| 主动 | 武将行动时 | 按 `activation_rate` 判定 |
| 被动 | （预留） | 尚未实现 |
| 追击 | （预留） | 尚未实现 |

**准备回合机制**：
- `preparation_turns > 0` 的战法需要多回合准备
- `start_prepare()` 开始准备 → 每回合 `advance_prepare()` 推进 → 完成后 `pending_skill` 待释放
- 准备中的战法不能再次发动

### 9.6 Buff 状态快照
`NodeGraphExecutor.__init__` 快照所有武将 buff：
```python
self._buff_snapshot = {
    id(hero): [b['type'] for b in hero.buff_list]
    for hero in (context.attacker_side + context.defender_side)
}
```
`HasStatus`/`GetEnemy(状态过滤)`/`GetAlly(状态过滤)` 基于快照判断，避免 Sequence 分支间状态"穿越"。

---

## 10. 主城建筑系统

### 10.1 架构
**配置与数据分离**：GM 后台可修改配置，持久化在 SQLite 中，重建 DB 不丢失。

三张表：
- `building_configs` — 建筑基础定义（全局唯一）
- `building_level_configs` — 每级消耗资源 + 效果
- `player_buildings` — 玩家建筑实例

### 10.2 30 个建筑
| 建筑 | key | 最大等级 | 分类 |
|------|-----|---------|------|
| 城主府 | palace | 8 | core |
| 校场 | training_ground | 5 | military |
| 前锋营 | vanguard_camp | 5 | military |
| 兵营 | barracks | 20 | military |
| 募兵所 | recruitment | 20 | military |
| 尚武营 | martial_hall | 20 | military |
| 疾风营 | camp_speed | 20 | military |
| 铁壁营 | camp_defense | 20 | military |
| 军机营 | camp_strategy | 20 | military |
| 民居 | residence | 20 | resource |
| 伐木场 | lumber_mill | 20 | resource |
| 炼铁场 | iron_smelter | 20 | resource |
| 磨坊 | flour_mill | 20 | resource |
| 采石场 | quarry | 20 | resource |
| 仓库 | warehouse | 20 | resource |
| 城墙 | city_wall | 5 | defense |
| 女墙 | parapet | 6 | defense |
| 警戒所 | watchtower | 10 | defense |
| 烽火台 | beacon_tower | 5 | defense |
| 守将府 | garrison_hall | 3 | defense |
| 预备役所 | reserve_camp | 20 | military |
| 集市 | market | 1 | special |
| 点将台(汉/魏/蜀/吴/群) | altar_han/wei/shu/wu/meng | 各10 | special |
| 武将巨像 | hero_statue | 5 | special |
| 沙盘阵图 | sandbox_map | 5 | special |
| 封禅台 | fengshan_altar | 3 | special |
| 社稷坛 | altar_state | 30 | special |

### 10.3 解锁体系
双重解锁：
1. **城主府等级**: `unlock_palace_level`（建筑需要城主府达到此等级）
2. **前置建筑**: `prerequisites`（JSON 数组，如 `[{"key": "training_ground", "level": 2}]`）

示例：
- 募兵所 = 城主府 2 级 + 校场 2 级
- 仓库 = 城主府 2 级 + 民居 1 级
- 封禅台 = 城主府 8 级 + 兵营 10 级
- 社稷坛 = 城主府 8 级 + 武将巨像 4 级 + 沙盘阵图 4 级

### 10.4 建筑效果字段 (effects JSON)
| 建筑 | effects 字段 | 说明 |
|------|-------------|------|
| 城主府 | `durability`, `cost_cap` | 耐久、COST上限 |
| 校场 | `troop_slots` | 可出征队伍数 |
| 前锋营 | `vanguard_slots` | 前锋武将槽 |
| 兵营 | `troop_capacity` | 单队最大兵力 |
| 募兵所 | `recruit_speed_bonus` | 招募速度加成% |
| 尚武营 | `attack_bonus` | 全军攻击加成(固定值) |
| 疾风营 | `speed_bonus` | 全军速度加成 |
| 铁壁营 | `defense_bonus` | 全军防御加成 |
| 军机营 | `strategy_bonus` | 全军谋略加成 |
| 民居 | `copper_per_hour` | 铜币每小时产出 |
| 伐木场 | `wood_per_hour` | 木材每小时产出 |
| 炼铁场 | `iron_per_hour` | 铁矿每小时产出 |
| 磨坊 | `grain_per_hour` | 粮草每小时产出 |
| 采石场 | `stone_per_hour` | 石料每小时产出 |
| 仓库 | `storage_cap` | 资源上限 |
| 城墙 | `wall_durability` | 城墙耐久 |
| 女墙 | `damage_reduction` | 伤害减免%(float) |
| 武将巨像 | `physical_damage_reduction`, `attack_bonus` | 物免+攻加 |
| 沙盘阵图 | `strategy_damage_reduction`, `strategy_bonus` | 策免+谋加 |
| 点将台 | `faction_bonus_atk/def/spd/strg` | 阵营属性加成 |
| 封禅台 | `cost_cap_bonus` | COST上限加成(float) |
| 社稷坛 | `fame_cap` | 名望上限 |

### 10.5 升级协议
```
客户端发送:
  REQ_BUILDINGS {}                    # 获取建筑列表
  CMD_UPGRADE_BUILDING {"key": "..."} # 升级建筑
  REQ_BUILDING_DETAIL {"key": "..."}  # 获取建筑详情

服务端返回:
  RES_BUILDINGS {buildings: [...]}
  RES_BUILDING_DETAIL {key, levels: [...]}
```

---

## 11. 地图系统

### 11.1 坐标系
- **类型**: Pointy-top 六边形
- **坐标系**: odd-q offset
- **尺寸**: 120 列 × 90 行 = 10,800 格子
- **六边形大小**: HEX_SIZE = 28（外接圆半径，像素）

### 11.2 坐标工具 (`hex_utils.py`)
客户端和服务端各有一份 `hex_utils.py`。

核心函数：
```python
hex_to_pixel(q, r, size)     # 六边形中心 → 像素坐标
pixel_to_hex(px, py, size)   # 像素坐标 → 六边形坐标
get_neighbors(q, r)          # 获取6个邻居坐标（使用 q%2 + pointy-top odd-q 偏移表）
hex_distance(q1, r1, q2, r2) # 六边形距离（立方坐标转换）
get_hex_vertices_list(...)    # 绘制用顶点列表
get_map_pixel_size(...)       # 地图像素尺寸
draw_hex(surface, ...)        # 绘制单个六边形
```

**重要**: `get_neighbors` 使用 `q % 2` 判断奇偶列偏移，`hex_distance` 立方坐标转换：
```python
x = q
z = r - (q - (q & 1)) // 2
y = -x - z
```

### 11.3 地形类型
| 地形 | 颜色 | 资源 |
|------|------|------|
| PLAINS (平原) | (144, 238, 144) | 粮草 |
| WOODS (树林) | (34, 139, 34) | 木材 |
| IRON (铁矿) | (169, 169, 169) | 铁矿 |
| STONE (石料) | (139, 115, 85) | 石料 |
| MOUNTAIN (山脉) | (80, 80, 80) | 不可通行 |

### 11.4 地图生成 (`init_db.py`)
1. **十三州版图**: 基于最近邻分配格子到州域
2. **地形填充**: 按州的地形预设（`TERRAIN_PRESETS`）随机分配
3. **等级权重**: 按州的 `REGION_LEVEL_WEIGHTS` 随机 1-9 级
4. **州界山脉**: 跨州邻居 → 设为 MOUNTAIN
5. **关口**: 28 个固定坐标关口（独立区域，不属于任何州），BFS 打通通道
6. **城池**: 154 个固定坐标城池（州府/郡城/县城）

### 11.5 十三州
```
司隶(洛阳附近), 雍州, 兖州, 豫州, 凉州, 并州, 幽州, 冀州, 青州, 徐州, 扬州, 荆州, 益州
```

---

## 12. 数据编辑器（DataEditor）

### 12.1 概述
`InfiniteBordersServer/data_editor.py` — 独立的 tkinter 数据管理工具。

### 12.2 启动方式
```bash
python data_editor.py              # 离线模式（直接操作 SQLite）
python data_editor.py --online     # 在线模式（连接服务器 HTTP API）
```

也可作为模块导入：
```python
from data_editor import DataEditor
DataEditor().mainloop()
```

### 12.3 5 个标签页
| 标签 | 功能 |
|------|------|
| 武将管理 | CRUD 武将模板（属性/成长率/阵营/自带战法） |
| 战法管理 | CRUD 战法（含内嵌 NodeEditor 编辑效果图） |
| 卡包管理 | 卡包定义 + 掉落权重配置 |
| 建筑管理 | 建筑配置查看/编辑（复用 BuildingTab） |
| 数据库版本 | 快照管理（上传/列表/恢复/导出/删除） |

### 12.4 双模式
- **离线模式**: 直接操作本地 `infinite_borders.sqlite3`
- **在线模式**: 通过 HTTP API 与运行中的服务器通信

### 12.5 战法标签页交互
- **单击**战法: 在右侧显示属性详情（不打开编辑器）
- **双击**战法: 打开独立 NodeEditor 窗口编辑节点图
- **嵌入模式**: 勾选"嵌入右侧面板"复选框 → NodeEditor 内嵌在右侧

### 12.6 快照系统
服务端 API (`data_editor_api.py`) 提供 6 个端点：
- `POST /api/snapshots/upload` — 上传快照
- `GET /api/snapshots/list` — 列出快照
- `GET /api/snapshots/stats` — 快照统计
- `POST /api/snapshots/restore/{id}` — 恢复快照
- `GET /api/snapshots/export/{id}` — 导出快照
- `DELETE /api/snapshots/delete/{id}` — 删除快照

快照存储在 `db_snapshots/` 目录。

---

## 13. 节点编辑器（NodeEditor）

### 13.1 概述
`InfiniteBordersServer/node_editor.py` — 战法效果可视化节点图编辑器。

### 13.2 使用方式
```python
from node_editor import NodeEditor
editor = NodeEditor(parent_widget, skill_name, effect_config)
```

### 13.3 工厂模式
`NodeEditor` 实际是 `_NodeEditorBase.__new__` 工厂方法，根据 `embed_mode` 返回：
- `embed_mode=True` → `_NodeEditorFrame`（内嵌 Frame）
- `embed_mode=False` → `_NodeEditorToplevel`（独立 Toplevel 窗口）

**单例机制**: `_active_instances` dict 按战法名跟踪活跃实例，重复打开同战法时 lift 现有窗口。

### 13.4 节点类型颜色分类
| 分类 | 颜色 | 包含节点 |
|------|------|---------|
| 事件 | 金色 | Event_OnCast, Event_BeginCombat, Event_OnPursuit |
| 流程 | 蓝色 | Sequence, Branch, ForEach, Delay, DoOnce, Gate, FlipFlop |
| 目标 | 绿色 | GetEnemy, GetAlly, GetSelf |
| 效果 | 红色 | ApplyDamage, ApplyHeal, ApplyControl, ApplyStatus, ModifyAttribute |
| 条件 | 紫色 | CompareAttribute, CompareHPPercent, HasStatus, RandomChance, CompareValues |
| 数值 | 橙色 | GetAttributeValue, CalculateDamage, SetVariable, GetVariable, AddToVariable |

### 13.5 操作方式
- **添加节点**: 右键菜单选择节点类型
- **连接**: 从输出引脚拖拽到输入引脚
- **删除**: 选中节点/连线后 Delete 键
- **参数编辑**: 双击节点编辑参数
- **保存**: 调用 `on_node_editor_save` 回调保存 `effect_config` 到数据库

### 13.6 保存验证
`_validate_graph()` 检查：
1. 入口节点（Event_ 开头）是否存在
2. 是否有孤立节点（无连接）
验证失败弹窗警告，用户可强制保存。

---

## 14. GM 控制台

### 14.1 概述
`InfiniteBordersServer/gm_console/` — 服务端 GM 管理后台。

### 14.2 启动
随 `server.py` 自动启动（`ServerGMConsole().mainloop()`）。

### 14.3 标签页
| 标签 | 来源 | 功能 |
|------|------|------|
| 运行状态 | `tabs/dashboard.py` | 服务器启停/在线玩家 |
| 武将管理 | `data_editor.py` → `HeroEditorTab` | 武将模板 CRUD（左右分栏+搜索） |
| 战法管理 | `data_editor.py` → `SkillEditorTab` | 战法 CRUD + 内嵌 NodeEditor |
| 卡包管理 | `data_editor.py` → `PackEditorTab` | 卡包定义 + 掉落权重（合并为一个标签页） |
| 建筑管理 | `tabs/building_tab.py` | 建筑配置（表格+效果可视化） |
| 数据库版本 | `tabs/snapshot_tab.py` | 快照上传/列表/恢复/导出/删除 |

**重要**：武将/战法/卡包三个标签页直接从 `data_editor.py` 导入类复用（`HeroEditorTab`、`SkillEditorTab`、`PackEditorTab`），不再维护独立的 `gm_console/tabs/hero_tab.py` 等文件。创建顺序：SkillEditorTab → HeroEditorTab（武将 tab 引用 skill_tab）。

### 14.4 暗色主题
`theme.py` 统一暗色主题模块，提供：
- **颜色常量**: `BG_DARK`, `BG_SURFACE`, `BG_ELEVATED`, `FG_PRIMARY`, `BTN_SUCCESS`, `ACCENT_*` 等
- **字体常量**: `FONT_FAMILY`（微软雅黑）、`FONT_MONO`（Consolas）
- **按钮快捷函数**: `btn_success()`, `btn_danger()`, `btn_accent()`, `btn_muted()`
- **应用函数**: `apply_dark_theme(root)` — 全局 ttk 样式 + 递归 tk 控件暗色覆盖

**开发规范**：
1. 所有颜色值必须从 `theme.py` 导入常量，禁止硬编码 `#xxxxxx`
2. 所有字体必须使用 `FONT_FAMILY` / `FONT_MONO`，禁止硬编码 `"微软雅黑"`
3. `tk.Entry` 和 `tk.Label` 是原生控件，不会自动继承 ttk 暗色主题，**创建时必须显式传 `bg=BG_ELEVATED, fg=FG_PRIMARY, insertbackground=FG_PRIMARY`**
4. `ttk.Combobox` / `ttk.Treeview` 等 ttk 控件通过全局 Style 自动生效

---

## 15. 通信协议完整列表

### 15.1 基础协议
| 协议 | 方向 | 说明 |
|------|------|------|
| `cmd_login` | C→S | 登录（通过 WebSocket URL 传递用户名） |
| `res_login` | S→C | 登录响应（spawn + resources + currencies + map） |
| `sync_state` | S→C | 状态同步（resources + currencies + marches） |
| `sync_map` | S→C | 地图变更推送（增量数据） |
| `push_report` | S→C | 战报推送（x, y, is_victory, report） |
| `error` | S→C | 错误消息 |

### 15.2 武将系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `req_heroes` | C→S | 请求武将列表 |
| `res_heroes` | S→C | 武将列表响应 |
| `cmd_add_point` | C→S | 武将加点 |
| `cmd_sub_point` | C→S | 武将减点 |
| `cmd_max_point` | C→S | 武将满加 |
| `cmd_rank_up` | C→S | 武将升阶 |
| `cmd_cheat_lvl` | C→S | GM 命令：设置等级 |

### 15.3 部队系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `req_troops` | C→S | 请求部队列表 |
| `res_troops` | S→C | 部队列表响应 |
| `cmd_edit_troop` | C→S | 编辑部队（更换武将） |
| `cmd_recruit_troops` | C→S | 部队招兵 |

### 15.4 行军系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `cmd_march` | C→S | 行军出征（x, y, troop_id） |

### 15.5 招募系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `req_packs` | C→S | 请求卡包列表 |
| `res_packs` | S→C | 卡包列表响应 |
| `cmd_recruit` | C→S | 抽卡（pack_id） |

### 15.6 商店系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `cmd_recharge` | C→S | 充值 |
| `cmd_exchange` | C→S | 货币兑换 |

### 15.7 建筑系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `req_buildings` | C→S | 请求建筑列表 |
| `res_buildings` | S→C | 建筑列表响应 |
| `cmd_upgrade_building` | C→S | 升级建筑（key） |
| `req_building_detail` | C→S | 请求建筑详情 |
| `res_building_detail` | S→C | 建筑详情响应 |
| `push_building_effects` | S→C | 建筑效果汇总推送 |

### 15.8 战报系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `req_report_history` | C→S | 请求战报历史（分页） |
| `res_report_history` | S→C | 战报历史响应 |

### 15.9 GM 系统
| 协议 | 方向 | 说明 |
|------|------|------|
| `cmd_reset_database` | C→S | GM 重置数据库（需 _gm_token 验证） |

---

## 16. 开发指南

### 16.1 添加新战法
1. 在 DataEditor 的"战法管理"标签页中点击"添加"
2. 填写战法基本信息（名称/品质/类型/发动率/描述等）
3. 双击战法打开 NodeEditor
4. 在画布上右键添加节点，连线配置效果
5. 保存节点图（自动写入 `Skill.effect_config`）

### 16.2 添加新节点类型
1. **编辑器** (`node_editor.py`):
   - 在 `Node` 类中添加到 `TYPE_CATEGORIES`、`TYPE_ICONS`
   - 在 `NodeEditor._get_pin_defs()` 中定义引脚
   - 在 `NodeEditor._create_node()` 中创建节点对象
2. **执行器** (`core/battle_core.py`):
   - 在 `NodeGraphExecutor._execute_node()` 中添加 case
   - 实现节点逻辑
   - 如有数据输出，写入 `self.pin_values[(node_id, pin_id)]`

### 16.3 添加新建筑
1. 在 `building_configs.py` 的 `BUILDING_DEFINITIONS` 列表中添加定义
2. 添加每级消耗数据（`_gen_costs()` 或手动配置）
3. 添加每级效果数据
4. 在 `connection_manager.py` 的 `recalculate_building_effects()` 中添加效果处理逻辑
5. 在 `_default_building_effects()` 中添加默认值
6. 重启服务器，GM 控制台可查看/编辑

### 16.4 添加新协议
1. **shared/protocol.py**: 在 `MsgType` 类中添加协议常量
2. **服务端**: 在 `ws_handlers/__init__.py` 的 `_dispatch_message()` 中添加路由
3. **服务端**: 创建对应的 handler 函数
4. **客户端**: 在 `network_loop` 的 `_handle_res()` 中添加处理逻辑

### 16.5 添加新 UI 面板
1. 在 `InfiniteBordersClient/ui/` 下创建新模块
2. 实现 `draw_xxx_panel()` 函数
3. 在 `main.py` 中导入并注册
4. 在 `open_panel()` 中添加面板初始化逻辑

### 16.6 数据库迁移
- **自动建表**: `startup_event` 中 `Base.metadata.create_all()` 会创建缺失的表
- **全量重置**: `python init_db.py`（删除所有数据）
- **轻量重置**: `init_database(keep_templates=True)`（保留配置数据）

---

## 17. 已知问题与注意事项

### 17.1 开发注意事项

#### SQLAlchemy JSON 修改
```python
# ❌ 错误：直接修改 dict 内容不会被 SQLAlchemy 检测到
skill.effect_config["nodes"].append(new_node)

# ✅ 正确方式1：使用 flag_modified
from sqlalchemy.orm.attributes import flag_modified
skill.effect_config["nodes"].append(new_node)
flag_modified(skill, "effect_config")

# ✅ 正确方式2：deepcopy + 整体替换
import copy
new_config = copy.deepcopy(skill.effect_config)
new_config["nodes"].append(new_node)
skill.effect_config = new_config
```

#### effect_config 空值判断
```python
# ❌ 错误：空列表 [] 是 falsy，会导致 fallback 到默认目标
if config:
    executor = NodeGraphExecutor(config, ...)

# ✅ 正确：显式判断
if config is not None and config != []:
    executor = NodeGraphExecutor(config, ...)
```

#### Python __new__ + __init__ 交互
当 `__new__` 返回子类实例时，Python 仍会调用 `__init__`。需要用标志位防止重复初始化：
```python
class MyClass:
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        # ... 初始化逻辑 ...
        self._initialized = True
```

#### tkinter Toplevel vs winfo_children
`winfo_children()` 不包含 Toplevel 窗口，只包含常规子控件。管理 Toplevel 需要自己维护实例列表。

### 17.2 配置同步
- `config.py`（服务端）和 `client_config.py`（客户端）需要保持 MAP_COLS/MAP_ROWS/HEX_SIZE 等参数一致
- `hex_utils.py` 和 `scenarios.py` 两端各有一份，修改时需要同步

### 17.3 Windows 注意事项
- asyncio 需要 `asyncio.WindowsSelectorEventLoopPolicy()`
- SQLite `check_same_thread=False` 允许跨线程访问

---

## 18. 历史修复记录

### 2026-04-01
- 战报系统重构为结构化 dict 格式
- 数据包 PUSH_REPORT 的 `log` 字段改为 `report`
- 效果节点日志统一为 `skill_effect` 类型

### 2026-04-02
- **hex_utils 坐标系修正**: 实际是 Pointy-top odd-q（非 flat-top odd-r）
- **NPCHero/BattleReport 类结构 bug**: `__init__` 错误缩进
- **客户端拆分**: main.py (~3000行) 拆分为 10 个模块
- **客户端多轮 bug 修复**: flip/地图加载/事件处理/面板闪烁等
- **平局机制**: 最多 50 场循环战斗
- **战报历史**: BattleReport 表 + 分页查询
- **Buff 状态快照**: 避免分支间状态穿越
- **空列表 targets fallback bug**: `[]` falsy 问题

### 2026-04-04
- **NodeEditor 双窗口 bug**: `__new__` 返回子类实例时 `__init__` 重复调用。修复：`_initialized` 标志位
- **DataEditor 交互改进**: 单击=属性、双击=独立窗口、checkbox=嵌入模式
- **独立数据编辑器**: data_editor.py 5 标签页 + 快照系统 + 双模式
- **GM Console 标签页统一**: 删除旧的 hero_tab/skill_tab/pack_tab/pack_drop_tab（4个文件），改为从 data_editor.py 复用 HeroEditorTab/SkillEditorTab/PackEditorTab 类。卡包+掉落合并为一个标签页
- **主题统一后连续 NameError 修复**（多轮）:
  - `SessionLocal` 未导入 → building_tab.py 补导入
  - `BuildingConfig`/`BuildingLevelConfig` 未导入 → building_tab.py 补导入
  - `BTN_ACCENT` 未导入 → snapshot_tab.py 补导入
  - `BG_SELECTED`/`FG_PRIMARY` 未导入 → node_editor.py 补导入
  - `add_skill()` 方法不存在 → 修正为 `_add_skill_dialog()`
  - `BTN_SUCCESS`/`BTN_DANGER`/`FONT_MONO` 等常量未导入 → data_editor.py/dashboard.py/building_tab.py 逐一补全
- **颜色全面统一**（硬编码→theme 常量）:
  - data_editor.py: 17处按钮/状态颜色（`#238636`→`BTN_SUCCESS`, `#da3633`→`BTN_DANGER` 等）
  - dashboard.py: 3处（停止按钮→`ACCENT_WARNING`）
  - building_tab.py: 2处（重载按钮→`ACCENT_WARNING`）
  - 全部字体 `"微软雅黑"` → `FONT_FAMILY`/`FONT_MONO`
- **武将详情区白底控件修复**: tk.Entry/tk.Label 创建时未传 bg/fg 参数，在 GM Console 中显示为 Windows 默认白色。为所有 Entry 显式设置 `bg=BG_ELEVATED, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, relief="flat"`，Label 设置 `bg=BG_SURFACE, fg=FG_PRIMARY`
- **教训总结**:
  1. 批量字符串替换前必须备份，替换多行块时检查行边界是否跨越无关代码
  2. 每次修改导入后应做"使用但未导入"的自动化扫描，而非等运行时报错
  3. tkinter 原生控件（tk.Entry/tk.Label）不继承 ttk 主题，必须创建时显式设样式

---

*本文档由 AI 辅助生成，后续开发时如有架构变更请及时更新。*

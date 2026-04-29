# server config
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
TICK_RATE = 1.0

FPS = 60
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768

# 六边形地图参数（pointy-top, odd-q offset）
MAP_COLS = 120      # 列数（东西方向）
MAP_ROWS = 90       # 行数（南北方向）
HEX_SIZE = 28       # 六边形外接圆半径（像素，基础大小）

COLORS = {
    "PLAINS": (144, 238, 144),
    "WOODS": (34, 139, 34),
    "IRON": (169, 169, 169),
    "STONE": (139, 115, 85),
    "MOUNTAIN": (80, 80, 80),
    "PLAYER": (65, 105, 225),
    "GRID": (50, 50, 50),
    "UI_BG": (30, 30, 30, 200),
}

RES_MAP = {
    "WOODS": {"key": "wood", "name": "木材"},
    "IRON": {"key": "iron", "name": "铁矿"},
    "STONE": {"key": "stone", "name": "石料"},
    "PLAINS": {"key": "grain", "name": "粮草"}
}

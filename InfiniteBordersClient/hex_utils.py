# hex_utils.py — 六边形地图工具
# Pointy-top 六边形（尖顶朝上），odd-q offset 坐标系（奇数列下移半格）
# 适用于客户端和服务端共享的六边形坐标计算

import math

# Flat-top 六边形的 6 个顶点角度（弧度），从右侧开始顺时针
# Flat-top: 第一个顶点在正右方 (3点方向)，角度从0度开始每60度
HEX_VERTEX_ANGLES = [
    math.radians(0),    # 右
    math.radians(60),   # 右下
    math.radians(120),  # 左下
    math.radians(180),  # 左
    math.radians(240),  # 左上
    math.radians(300),  # 右上
]

# 六边形邻居偏移（实际为 Pointy-top + odd-q offset 坐标系）
# 奇数列(q为奇数)向下偏移半格，邻居偏移不同
HEX_DIRS_EVEN_Q = [
    ( 0, -1),  # 上
    ( 1, -1),  # 右上
    ( 1,  0),  # 右
    ( 0,  1),  # 下
    (-1,  0),  # 左
    (-1, -1),  # 左上
]

HEX_DIRS_ODD_Q = [
    ( 0, -1),  # 上
    ( 1,  0),  # 右上
    ( 1,  1),  # 右下
    ( 0,  1),  # 下
    (-1,  1),  # 左下
    (-1,  0),  # 左
]


def get_neighbors(q, r):
    """获取六边形格子的 6 个邻居坐标 (q, r) = (col, row)"""
    dirs = HEX_DIRS_ODD_Q if q % 2 == 1 else HEX_DIRS_EVEN_Q
    return [(q + dq, r + dr) for dq, dr in dirs]


def hex_to_pixel(q, r, size):
    """
    offset 坐标 → 像素中心坐标
    q = 列, r = 行, size = 六边形外接圆半径（外半径）
    
    Flat-top, odd-r offset:
    - 水平间距 = size * 1.5
    - 垂直间距 = size * sqrt(3)
    - 奇数行向右偏移 size * 0.75
    """
    sqrt3 = math.sqrt(3)
    x = size * 1.5 * q
    y = size * sqrt3 * (r + 0.5 * (q % 2))
    return (x, y)


def pixel_to_hex(px, py, size):
    """
    像素中心坐标 → offset 坐标 (q, r)
    反转 hex_to_pixel 的计算，四舍五入到最近的格子
    """
    sqrt3 = math.sqrt(3)
    # 近似 q（列）
    q = round(px / (size * 1.5))
    q = max(0, q)

    # 根据 q 是奇数还是偶数，调整偏移（与 hex_to_pixel 的 q%2 对应）
    offset = 0.5 * (q % 2)
    r = round((py / (size * sqrt3)) - offset)
    r = max(0, r)

    # 检查候选格子，选最近的
    best_q, best_r = q, r
    best_dist = float('inf')
    for dq in range(-1, 2):
        for dr in range(-1, 2):
            cq, cr = q + dq, r + dr
            cx, cy = hex_to_pixel(cq, cr, size)
            d = (px - cx) ** 2 + (py - cy) ** 2
            if d < best_dist:
                best_dist = d
                best_q, best_r = cq, cr

    return (best_q, best_r)


def get_hex_corners(cx, cy, size):
    """
    返回六边形 6 个顶点的坐标列表 [(x1,y1), (x2,y2), ...]
    Flat-top: 第一个顶点在正右方，顺时针
    cx, cy = 中心坐标, size = 外半径
    """
    corners = []
    for angle in HEX_VERTEX_ANGLES:
        x = cx + size * math.cos(angle)
        y = cy + size * math.sin(angle)
        corners.append((x, y))
    return corners


def get_hex_vertices_list(cx, cy, size):
    """
    返回用于 pygame.draw.polygon 的顶点列表 [(x1,y1), (x2,y2), ...]
    从正右方顺时针
    """
    return get_hex_corners(cx, cy, size)


def hex_distance(q1, r1, q2, r2):
    """
    计算两个六边形之间的距离（格子数）
    通过转换为 cube 坐标计算
    Pointy-top + odd-q offset → cube 转换
    """
    # offset (col=q, row=r) → cube (x, y, z)
    # odd-q: 奇数列下移半格
    x1 = q1
    z1 = r1 - (q1 - (q1 & 1)) // 2
    y1 = -x1 - z1

    x2 = q2
    z2 = r2 - (q2 - (q2 & 1)) // 2
    y2 = -x2 - z2

    return max(abs(x1 - x2), abs(y1 - y2), abs(z1 - z2))


def get_map_pixel_size(hex_size, map_cols, map_rows):
    """
    计算整个六边形地图的像素宽高
    Flat-top: 水平方向由列决定，垂直方向由行决定
    """
    sqrt3 = math.sqrt(3)
    # 宽度：列数 × 水平间距 + 半个格子宽度
    width = hex_size * 1.5 * (map_cols - 1) + hex_size * 2
    # 高度：所有行 + 奇数列的半格偏移
    height = hex_size * sqrt3 * (map_rows + 0.5)
    return (width, height)


def draw_hex(surface, cx, cy, size, color, border_color=None, border_width=1):
    """
    在 Pygame surface 上绘制一个六边形
    color 为 None 时只画边框不填充
    """
    import pygame
    vertices = get_hex_vertices_list(cx, cy, size)
    int_vertices = [(int(x), int(y)) for x, y in vertices]
    if color is not None:
        pygame.draw.polygon(surface, color, int_vertices)
    if border_color:
        pygame.draw.polygon(surface, border_color, int_vertices, border_width)

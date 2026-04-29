"""分析十三州区域范围，用于确定城池坐标"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import MAP_COLS, MAP_ROWS
from hex_utils import get_neighbors

REGION_CENTERS = {
    "司隶": (40, 30), "雍州": (24, 27), "兖州": (56, 24), "豫州": (44, 42),
    "凉州": (12, 15), "并州": (28, 9), "幽州": (60, 9), "冀州": (44, 12),
    "青州": (68, 18), "徐州": (68, 33), "扬州": (60, 51), "荆州": (28, 51), "益州": (12, 39)
}

def get_region(q, r):
    min_d, res = 999999, "未知"
    for region, (cq, cr) in REGION_CENTERS.items():
        d = (q - cq) ** 2 + (r - cr) ** 2
        if d < min_d:
            min_d, res = d, region
    return res

# 统计每州的格子数和范围
regions = {}
for r in range(MAP_ROWS):
    for q in range(MAP_COLS):
        reg = get_region(q, r)
        if reg not in regions:
            regions[reg] = {"count": 0, "qs": [], "rs": [], "tiles": []}
        regions[reg]["count"] += 1
        regions[reg]["qs"].append(q)
        regions[reg]["rs"].append(r)
        regions[reg]["tiles"].append((q, r))

for reg in sorted(regions.keys(), key=lambda x: REGION_CENTERS.get(x, (0,0))[1]):
    info = regions[reg]
    q_min, q_max = min(info["qs"]), max(info["qs"])
    r_min, r_max = min(info["rs"]), max(info["rs"])
    print(f"{reg}({REGION_CENTERS[reg]}): {info['count']}格 "
          f"q=[{q_min},{q_max}] r=[{r_min},{r_max}]")

# 找出每州所有非山格子
print("\n=== 各州非山格子（城池候选） ===")
import random
# 先生成地图（不含城池逻辑）
grid = {}
for r in range(MAP_ROWS):
    for q in range(MAP_COLS):
        grid[(q, r)] = {
            "region": get_region(q, r),
            "terrain": random.choices(["PLAINS", "WOODS", "IRON", "STONE"], [0.4, 0.2, 0.2, 0.2])[0],
        }

# 标记山脉
for (q, r), cell in grid.items():
    region = cell["region"]
    for nq, nr in get_neighbors(q, r):
        if (nq, nr) in grid and grid[(nq, nr)]["region"] != region:
            cell["terrain"] = "MOUNTAIN"
            break

# 统计非山格子
for reg in sorted(regions.keys(), key=lambda x: REGION_CENTERS.get(x, (0,0))[1]):
    candidates = [(q, r) for (q, r), cell in grid.items() 
                  if cell["region"] == reg and cell["terrain"] != "MOUNTAIN"]
    center = REGION_CENTERS[reg]
    # 按距离中心排序
    candidates.sort(key=lambda t: (t[0]-center[0])**2 + (t[1]-center[1])**2)
    # 取离中心最近的15个
    top15 = candidates[:15]
    coords_str = ", ".join([f"({q},{r})" for q, r in top15])
    print(f"\n{reg}: {len(candidates)}个可用地格")
    print(f"  中心{center} 最近15格: {coords_str}")

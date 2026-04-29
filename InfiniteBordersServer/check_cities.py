"""验证新数据库中的城池和关口数据"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from models.database import SessionLocal
from models.schema import Tile
from sqlalchemy import func

db = SessionLocal()

# 总览
total = db.query(Tile).count()
cities = db.query(Tile).filter(Tile.city_type != None, Tile.city_type != "关口").count()
gates = db.query(Tile).filter(Tile.city_type == "关口").count()
mountains = db.query(Tile).filter(Tile.terrain == "MOUNTAIN").count()

print(f"总格子: {total}")
print(f"城池: {cities}  关口: {gates}  山脉: {mountains}")

# 各州城池统计
print("\n=== 各州城池 ===")
region_cities = db.query(
    Tile.region, Tile.city_type, func.count(Tile.id)
).filter(
    Tile.city_type != None, Tile.city_type != "关口"
).group_by(
    Tile.region, Tile.city_type
).order_by(Tile.region).all()

regions_summary = {}
for region, city_type, count in region_cities:
    if region not in regions_summary:
        regions_summary[region] = {}
    regions_summary[region][city_type] = count

for region in sorted(regions_summary.keys()):
    info = regions_summary[region]
    total_c = sum(info.values())
    print(f"  {region}: {total_c}城 " + 
          f"(州府:{info.get('州府',0)} 郡城:{info.get('郡城',0)} 县城:{info.get('县城',0)})")

# 列出所有城池
print("\n=== 城池列表 ===")
all_cities = db.query(Tile).filter(
    Tile.city_type != None
).order_by(
    Tile.region, Tile.level.desc()
).all()

for t in all_cities:
    print(f"  [{t.region}] {t.city_name} ({t.x},{t.y}) Lv{t.level} {t.city_type}")

db.close()

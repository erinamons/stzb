import sqlite3

conn = sqlite3.connect('infinite_borders.sqlite3')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("数据库中的表:")
for t in tables:
    print(f"  {t[0]}")

# 查看每个表中包含 rank 列的
for t in tables:
    tname = t[0]
    cursor.execute(f"PRAGMA table_info({tname})")
    cols = cursor.fetchall()
    col_names = [c[1] for c in cols]
    if 'rank' in col_names:
        print(f"\n表 {tname} 有 rank 列:")
        cursor.execute(f"SELECT rank, COUNT(*) FROM {tname} GROUP BY rank")
        rows = cursor.fetchall()
        for row in rows:
            print(f"  rank={row[0]}: {row[1]}条")

        # 将 rank > 0 的改为 0
        cursor.execute(f"UPDATE {tname} SET rank = 0 WHERE rank > 0")
        affected = cursor.rowcount
        if affected > 0:
            print(f"  -> 已将 {affected} 条记录的 rank 重置为 0")

conn.commit()
conn.close()
print("\n完成!")

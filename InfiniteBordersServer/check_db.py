import sqlite3
conn = sqlite3.connect("infinite_borders.sqlite3")
c = conn.cursor()
total = c.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
mtn = c.execute("SELECT COUNT(*) FROM tiles WHERE terrain='MOUNTAIN'").fetchone()[0]
gates = c.execute("SELECT COUNT(*) FROM tiles WHERE city_type='关口'").fetchone()[0]
caps = c.execute("SELECT COUNT(*) FROM tiles WHERE city_type='州府'").fetchone()[0]
spawn = c.execute("SELECT x,y,terrain,owner_id FROM tiles WHERE x=10 AND y=15").fetchone()
print(f"Total={total} Mountain={mtn} Gates={gates} Capitals={caps}")
print(f"Spawn(10,15): terrain={spawn[2]} owner={spawn[3]}")
conn.close()

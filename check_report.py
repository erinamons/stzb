import sqlite3, json

conn = sqlite3.connect('InfiniteBordersServer/infinite_borders.sqlite3')
conn.row_factory = sqlite3.Row
row = conn.execute('SELECT * FROM battle_reports WHERE id = 2').fetchone()
if row:
    report = json.loads(row['report'])

    # 检查是否有 battle_break（多场战斗）
    if 'battle_break' in report:
        print("注意：有多场战斗（battle_break）")

    # 查找所有回合中的事件
    rounds = report.get('rounds', [])
    print(f"总共 {len(rounds)} 个回合条目")

    for i, r in enumerate(rounds):
        # rounds可能是 {"round": N, "events": [...]} 格式
        if isinstance(r, dict):
            rnd_num = r.get('round', i+1)
            events = r.get('events', [])
        else:
            continue

        for ev in events:
            # 找马超相关事件
            ev_str = json.dumps(ev, ensure_ascii=False)
            if '马超' in ev_str or 'Ma Chao' in ev_str:
                print(f"\n{'='*60}")
                print(f"回合 {rnd_num} - 马超事件:")
                print(json.dumps(ev, ensure_ascii=False, indent=2))

    # 也打印所有伤害超过1000的事件
    print(f"\n{'='*60}")
    print("所有伤害超过500的事件:")
    for i, r in enumerate(rounds):
        if isinstance(r, dict):
            events = r.get('events', [])
            for ev in events:
                dmg = ev.get('damage', 0)
                if dmg > 500:
                    print(json.dumps(ev, ensure_ascii=False, indent=2))
else:
    print('未找到ID=2的战报')
conn.close()

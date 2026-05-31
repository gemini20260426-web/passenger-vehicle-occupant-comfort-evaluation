import sqlite3, json
conn = sqlite3.connect(r'data_output/analysis_results_1779602677.db')
cur = conn.execute('SELECT id, start_time, end_time, event_data FROM behavior_events ORDER BY start_time')
rows = cur.fetchall()
print(f'Total events: {len(rows)}')
c01 = c02 = 0
for r in rows:
    d = json.loads(r[3])
    tp = d.get('type', '?')
    nm = d.get('event_name', d.get('label_cn', ''))
    t0 = r[1]
    tag = '01' if t0 < 20 else ('02' if t0 >= 60 else '--')
    if t0 < 20: c01 += 1
    elif t0 >= 60: c02 += 1
    print(f'#{r[0]:3d} [{r[1]:7.2f}-{r[2]:7.2f}]s  d={r[2]-r[1]:.2f}s  {tp:25s} [{tag}]')
print(f'\n01号: {c01}, 02号: {c02}')
conn.close()
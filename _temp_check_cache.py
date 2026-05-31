import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')
from core.core.data_processing.multi_source_cache import MultiSourceCache
cache = MultiSourceCache(db_path=r'd:\UI重构_全量备份_20250824_233403\data_output\cache_1779591508.db')
recs = cache.query_records_raw()
print(f"Total: {len(recs)} records")
for i, r in enumerate(recs[:3]):
    k = sorted(r.keys())
    print(f"\nRecord {i}: keys={k[:25]}")
    print(f"  imu_name={r.get('imu_name','MISS')}, channel={r.get('channel','MISS')}")
    print(f"  _imu_name={r.get('_imu_name','MISS')}, _source_type={r.get('_source_type','MISS')}")
    print(f"  speed={r.get('speed','MISS')}, Ax_m_s2={r.get('Ax_m_s2','MISS')}")
    print(f"  ax={r.get('ax','MISS')}, rel_time={r.get('rel_time','MISS')}")

# Check unique imu_names
imu_set = set()
ch_set = set()
for r in recs:
    imu_set.add(r.get('imu_name', ''))
    ch_set.add(r.get('channel', ''))
print(f"\nUnique imu_names: {sorted(imu_set)}")
print(f"Unique channels: {sorted(ch_set)}")

# Count by imu_name
from collections import Counter
imu_counts = Counter(r.get('imu_name', '?') for r in recs)
print(f"\nCounts by IMU: {imu_counts.most_common(10)}")
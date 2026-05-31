"""SciClaw 事件检测桥接模块"""

def detect_events_from_csv(csv_path: str):
    """从CSV文件检测驾驶事件"""
    import sys, os
    # 尝试导入内置模块, 否则回退到外部模块
    try:
        from driving_event_detector import DrivingEventDetector
        d = DrivingEventDetector(csv_path)
        return d.detect_all()
    except ImportError:
        pass

    # 尝试从上层路径导入
    for p in ['.', '..', '../..']:
        sys.path.insert(0, p)
    try:
        from driving_event_detector import DrivingEventDetector
        d = DrivingEventDetector(csv_path)
        return d.detect_all()
    except:
        return []

def detect_events_from_df(df):
    """从DataFrame检测驾驶事件 (保存临时文件)"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
        df.to_csv(f.name, index=False)
        events = detect_events_from_csv(f.name)
    try: os.unlink(f.name)
    except: pass
    return events

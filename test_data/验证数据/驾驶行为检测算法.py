YTHON
#!/usr/bin/env python3
"""
驾驶行为事件检测引擎 V3.0
22种事件: 匀速直行/正常加速/正常减速/恒速行驶/停车/驻车/
          车道保持/左转/右转/小半径转弯/大半径转弯/U型转弯/
          弯道加速/弯道减速/激进加速/激进减速/急刹车/
          蛇形驾驶/急速变向/剧烈颠簸/侧滑风险/侧翻风险

用法: python driving_event_detector.py <parsed_data.csv> [output_prefix]
"""

import pandas as pd
import numpy as np
from scipy import signal
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import json, sys

# 事件类型中英文映射
EVENT_TYPES = {
    'constant_speed': '匀速直行', 'normal_accel': '正常加速',
    'normal_decel': '正常减速', 'cruising': '恒速行驶',
    'stopped': '停车', 'parked': '驻车',
    'lane_keeping': '车道保持', 'left_turn': '左转', 'right_turn': '右转',
    'tight_turn': '小半径转弯', 'wide_turn': '大半径转弯', 'u_turn': 'U型转弯',
    'corner_accel': '弯道加速', 'corner_decel': '弯道减速',
    'aggressive_accel': '激进加速', 'aggressive_decel': '激进减速',
    'hard_brake': '急刹车', 'slalom': '蛇形驾驶',
    'rapid_lane_change': '急速变向', 'severe_bump': '剧烈颠簸',
    'side_slip_risk': '侧滑风险', 'rollover_risk': '侧翻风险',
}

@dataclass
class Event:
    event_id: int; event_type: str; event_name: str
    t_start: float; t_end: float; duration_s: float
    confidence: float; features: Dict = field(default_factory=dict)
    def to_dict(self):
        return {'event_id':self.event_id,'event_type':self.event_type,
                'event_name':self.event_name,'t_start':round(self.t_start,3),
                't_end':round(self.t_end,3),'duration_s':round(self.duration_s,3),
                'confidence':round(self.confidence,3),
                'features':{k:round(v,4) if isinstance(v,float) else v
                            for k,v in self.features.items()}}

class DrivingEventDetector:
    def __init__(self, csv_path, ref_imu='IMU1_头部眉心-1'):
        df = pd.read_csv(csv_path)
        ref = df[(df.channel=='ch1')&(df.imu_name==ref_imu)].sort_values('rel_time')
        self.t = ref.rel_time.values; self.speed = ref.speed.values.astype(float)
        self.wheel = ref.wheel.values.astype(float)
        imu = ref[['Ax_m_s2','Ay_m_s2','Az_m_s2','Gx_dps','Gy_dps','Gz_dps']].values
        self.ax,self.ay,self.az = imu[:,0],imu[:,1],imu[:,2]
        self.gx,self.gy,self.gz = imu[:,3],imu[:,4],imu[:,5]
        self.dt = np.median(np.diff(self.t)); self.fs = 1/self.dt
        self.N = len(self.t); self.events=[]; self.eid=0; self._precompute()

    def _precompute(self):
        dt = self.dt
        raw = np.gradient(self.speed,dt)/3.6
        b,a = signal.butter(2,5/(self.fs/2))
        self.vehicle_accel = signal.filtfilt(b,a,raw)
        self.steer_rate = np.abs(np.gradient(self.wheel,dt))
        self.a_lat = np.abs(self.ay); self.a_vert = np.abs(self.az)
        self.roll_rate = np.abs(self.gx)
        w = int(0.5/dt)
        self.speed_ma = pd.Series(self.speed).rolling(w,center=True).mean().bfill().ffill().values
        self.speed_std = pd.Series(self.speed).rolling(w,center=True).std().bfill().ffill().values
        self.wheel_std = pd.Series(self.wheel).rolling(w,center=True).std().bfill().ffill().values
        self.accel_ma = pd.Series(self.vehicle_accel).rolling(w,center=True).mean().bfill().ffill().values

    def _add(self, etype, t0, t1, conf=0.8, feat=None):
        e = Event(self.eid, etype, EVENT_TYPES.get(etype,etype), t0, t1, t1-t0, conf, feat or {})
        self.events.append(e); self.eid += 1; return e

    def _segments(self, cond, min_dur=0.2, max_gap=0.3):
        if not np.any(cond): return []
        idx = np.where(cond)[0]
        gaps = np.where(np.diff(idx)>int(max_gap/self.dt))[0]
        groups = np.split(idx, gaps+1)
        min_n = int(min_dur/self.dt)
        return [(g[0],g[-1]) for g in groups if len(g)>=min_n]

    # ---- 速度基 ----
    def detect_speed_events(self):
        for i0,i1 in self._segments(self.speed<=1, 0.3, 1.0):
            d = self.t[i1]-self.t[i0]
            self._add('parked' if d>1 else 'stopped', self.t[i0], self.t[i1], 0.95)
        for i0,i1 in self._segments((self.speed>5)&(self.speed_std<3), 1.0, 0.5):
            self._add('cruising', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments((self.speed>5)&(self.speed_std<2)&(np.abs(self.wheel)<1), 1.0, 0.5):
            self._add('constant_speed', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments((self.accel_ma>0.5)&(self.accel_ma<3)&(self.speed>3), 0.2, 0.3):
            if self.speed[i1]-self.speed[i0]>1:
                self._add('normal_accel', self.t[i0], self.t[i1], 0.80)
        for i0,i1 in self._segments((self.accel_ma<-0.5)&(self.accel_ma>-3)&(self.speed>3), 0.2, 0.3):
            if self.speed[i1]-self.speed[i0]<-1:
                self._add('normal_decel', self.t[i0], self.t[i1], 0.80)

    # ---- 转向基 ----
    def detect_steering_events(self):
        aw = np.abs(self.wheel)
        for i0,i1 in self._segments((aw<1)&(self.speed>5), 2.0, 0.5):
            self._add('lane_keeping', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments(self.wheel<-2, 0.3, 0.3):
            if self.speed[i0:i1].mean()>3:
                self._add('left_turn', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments(self.wheel>2, 0.3, 0.3):
            if self.speed[i0:i1].mean()>3:
                self._add('right_turn', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments(aw>15, 0.3, 0.2):
            if self.speed[i0:i1].mean()>3:
                self._add('tight_turn', self.t[i0], self.t[i1], 0.80)
        for i0,i1 in self._segments((aw>3)&(aw<15), 1.0, 0.5):
            if self.speed[i0:i1].mean()>5:
                self._add('wide_turn', self.t[i0], self.t[i1], 0.75)
        for i0,i1 in self._segments((self.wheel_std>5)&(self.speed>2), 1.0, 0.5):
            r = self.wheel[i0:i1].max()-self.wheel[i0:i1].min()
            if r>30 and np.sign(self.wheel[i0])!=np.sign(self.wheel[i1]):
                self._add('u_turn', self.t[i0], self.t[i1], 0.70)

    # ---- 复合 ----
    def detect_compound_events(self):
        ic = np.abs(self.wheel)>3
        for i0,i1 in self._segments(ic&(self.vehicle_accel>0.5)&(self.speed>3), 0.3, 0.3):
            if self.speed[i1]-self.speed[i0]>1:
                self._add('corner_accel', self.t[i0], self.t[i1], 0.75)
        for i0,i1 in self._segments(ic&(self.vehicle_accel<-0.5)&(self.speed>3), 0.3, 0.3):
            if self.speed[i1]-self.speed[i0]<-1:
                self._add('corner_decel', self.t[i0], self.t[i1], 0.75)

    # ---- 激进 ----
    def detect_aggressive_events(self):
        for i0,i1 in self._segments((self.vehicle_accel>3)&(self.speed>3), 0.2, 0.2):
            self._add('aggressive_accel', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments((self.vehicle_accel<-3)&(self.speed>3), 0.2, 0.2):
            self._add('aggressive_decel', self.t[i0], self.t[i1], 0.85)
        for i0,i1 in self._segments((self.vehicle_accel<-5)&(self.speed>5), 0.15, 0.2):
            self._add('hard_brake', self.t[i0], self.t[i1], 0.90)

    # ---- 动态 ----
    def detect_dynamic_events(self):
        w,s = int(1.5/self.dt), int(0.3/self.dt)
        for start in range(0,self.N-w,s):
            end=start+w; ww=self.wheel[start:end]
            zc=np.sum(np.diff(np.signbit(ww)))
            if zc>=2 and ww.max()-ww.min()>5 and self.speed[start:end].mean()>10:
                self._add('slalom',self.t[start],self.t[end],0.75)
        for i0,i1 in self._segments((self.steer_rate>50)&(self.speed>10),0.2,0.2):
            self._add('rapid_lane_change',self.t[i0],self.t[i1],0.80)

    # ---- IMU基 ----
    def detect_imu_events(self):
        for i0,i1 in self._segments(self.a_vert>15,0.05,0.1):
            self._add('severe_bump',self.t[i0],self.t[i1],0.85)
        for i0,i1 in self._segments((self.a_lat>5)&(self.speed>20),0.2,0.2):
            self._add('side_slip_risk',self.t[i0],self.t[i1],0.75)
        for i0,i1 in self._segments((self.a_lat>6)&(self.roll_rate>20)&(self.speed>20),0.15,0.2):
            self._add('rollover_risk',self.t[i0],self.t[i1],0.70)

    # ---- 全量检测 ----
    def detect_all(self):
        self.events=[]; self.eid=0
        for m in [self.detect_speed_events,self.detect_steering_events,
                   self.detect_compound_events,self.detect_aggressive_events,
                   self.detect_dynamic_events,self.detect_imu_events]:
            m()
        self.events.sort(key=lambda e:(e.t_start,-e.confidence))
        for i,e in enumerate(self.events): e.event_id=i
        return self.events

    def print_summary(self):
        print(f"检测到 {len(self.events)} 个事件")
        by_type={}
        for e in self.events: by_type.setdefault(e.event_type,[]).append(e)
        for et in sorted(by_type):
            print(f"  {EVENT_TYPES.get(et,et):<12} ×{len(by_type[et]):>2}  "
                  f"[{by_type[et][0].t_start:.1f}s~{by_type[et][-1].t_end:.1f}s]")

    def export(self, prefix='events'):
        json.dump([e.to_dict() for e in self.events],
                  open(f'{prefix}.json','w',encoding='utf-8'), indent=2, ensure_ascii=False)
        pd.DataFrame([{**e.to_dict(),**{f'f_{k}':v for k,v in e.features.items()}}
                       for e in self.events]).to_csv(f'{prefix}.csv',index=False,encoding='utf-8-sig')
        print(f"导出: {prefix}.json + {prefix}.csv")

if __name__=='__main__':
    if len(sys.argv)<2: print(__doc__); sys.exit(1)
    d=DrivingEventDetector(sys.argv[1]); d.detect_all()
    d.print_summary(); d.export(sys.argv[2] if len(sys.argv)>2 else 'events')

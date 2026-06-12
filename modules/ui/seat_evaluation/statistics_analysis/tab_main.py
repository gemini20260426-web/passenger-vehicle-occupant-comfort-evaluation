#!/usr/bin/env python3
"""
tab_main.py — 全量统计分析标签页 v11.0 (全新图表模块版)

━━ v10.0 UI布局 + v11.0 全新图表模块 ━━
  ✅ v9.0数据管线 (UnifiedEvaluationWorker)
  ✅ v10.0专业仪表盘UI布局
  ✅ 全新 charts/ 模块 (替换 visualization_manager + advanced_charts)
"""

import logging, os, json, sqlite3, traceback, statistics as _stat
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict
import csv as csv_mod
import numpy as np
import matplotlib; matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QTextEdit,
    QFrame, QCheckBox, QHeaderView, QScrollArea, QGridLayout,
    QTabWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QColor

# ═══ 原版核心import (数据管线) ═══
from core.core.seat_evaluation.engine_v2 import MultiChannelSeatEvaluationEngine
from core.core.seat_evaluation.data_preprocessor import DataPreprocessor
from core.core.seat_evaluation.evaluation_report import EvaluationReportGenerator
from core.core.seat_evaluation.full_timeseries_evaluator import FullTimeseriesEvaluator
from core.core.seat_evaluation.imu_location_config import (
    LOCATION_IDS, get_location_config, get_channel_by_location,
)
from core.core.data_processing.floor_imu_parser import FloorIMUParser
from core.core.seat_evaluation.metadata_registry import (
    METRIC_THRESHOLDS, get_global_registry, EvaluationDirection,
)

# ═══ 全新图表模块 (替换 visualization_manager + advanced_charts) ═══
from .charts.style import S, C, EV, EV_CN, DIM_C, CN
from .charts.timeline import create_event_timeline
from .charts.psd import create_psd_comparison, create_psd_band_comparison
from .charts.radar import (
    create_comparison_radar, create_attenuation_bar,
    create_acceleration_waveform, create_srs_comparison,
    create_metric_heatmap, create_stft_chart,
    create_sliding_window_chart, create_band_attenuation_chart,
    create_band_radar_chart,
)

logger = logging.getLogger(__name__)

LOC_LABELS = {'head':'头部眉心','torso':'躯干T8','seat_r':'座垫R点','seat_bottom':'座椅底部','sternum':'胸骨剑突'}
PRE_LABELS = {0:'原始数据',1:'零偏校准+对齐',2:'校准+对齐+10Hz滤波'}
ALL_MG = [
    ("瞬态冲击",['HIC15','ACC_H_PEAK','JERK_H','SRS_MRS','SRS_Q','SRS_PV','SRS_ATT']),
    ("稳态舒适",['SEAT_Z','SEAT_XY','AW_Z','AW_XY','OVTV','R_FACTOR']),
    ("动态响应",['VDV_Z','TR_Z','DISP_HR','DISP_TR','ATTEN_H']),
    ("疲劳耐久",['RFC_CC','FDS_D','FDS_R']),
    ("时频分析",['STFT_FC','STFT_KT','STFT_CE']),
    ("通用综合",['ACC_RMS','ACC_PEAK','S_D']),
]
DIM_MAP = {'时域-冲击':'瞬态-冲击','冲击域-结构响应':'瞬态-冲击','冲击域-参数':'瞬态-冲击','冲击域-响应':'瞬态-冲击','冲击域-隔振效率':'瞬态-冲击','频域-传递特性':'稳态-舒适度','频域-舒适度':'稳态-舒适度','频域-综合':'稳态-舒适度','频域-方向性':'稳态-舒适度','时域-剂量':'动态-响应','时域-位移':'动态-响应','隔振-综合':'动态-响应','疲劳-计数':'疲劳-损伤','疲劳-累积损伤':'疲劳-损伤','疲劳-剩余寿命':'疲劳-损伤','时频域-频率':'时频-分析','时频域-扩展':'时频-分析','时频域-集中度':'时频-分析','生物力学-脊柱':'生物力学','通用-振动能量':'通用-基础','通用-冲击强度':'通用-基础'}
DIM_ORD = {'瞬态-冲击':0,'稳态-舒适度':1,'动态-响应':2,'疲劳-损伤':3,'时频-分析':4,'生物力学':5,'通用-基础':6}

SHEET = """
QTableWidget{font-size:11px;gridline-color:#E2E8F0;border:1px solid #E2E8F0;border-radius:6px;background:white;}
QTableWidget::item{padding:6px 10px;}
QHeaderView::section{background:#F1F5F9;color:#1E293B;padding:8px 10px;border:none;border-bottom:2px solid #E2E8F0;font-weight:600;font-size:11px;}
QScrollArea{background:#F8FAFC;border:none;}QScrollBar:vertical{width:6px;background:transparent;}QScrollBar::handle:vertical{background:#CBD5E1;border-radius:3px;}
QPushButton{font-size:12px;padding:8px 18px;border-radius:6px;background:white;border:1px solid #CBD5E1;color:#1E293B;}
QPushButton:hover{background:#F1F5F9;border-color:#2563EB;color:#2563EB;}
QComboBox{border:1px solid #CBD5E1;border-radius:6px;padding:6px 10px;font-size:12px;background:white;}
QGroupBox{font-size:13px;font-weight:600;border:1px solid #E2E8F0;border-radius:8px;margin-top:8px;padding:16px 12px 12px 12px;background:white;}
QProgressBar{border:none;border-radius:6px;background:#E2E8F0;text-align:center;font-size:10px;height:20px;}QProgressBar::chunk{background:#2563EB;border-radius:6px;}
"""

# ═══════════════════ UnifiedEvaluationWorker ═══════════════════
# (与v9.0相同, 保证数据兼容)

class UnifiedEvaluationWorker(QObject):
    progress_updated = Signal(int, str)
    analysis_completed = Signal(dict)
    analysis_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._engine = MultiChannelSeatEvaluationEngine()
        self._report_generator = EvaluationReportGenerator()
        self._is_running = False
        self._dataset_path = ''; self._preprocess_level = 1
        self._selected_metrics = []; self._locations = []

    def configure(self, dp, pl, sm, locs):
        self._dataset_path = dp; self._preprocess_level = pl
        self._selected_metrics = sm; self._locations = locs

    def run(self):
        self._is_running = True
        try:
            self.progress_updated.emit(5, '加载数据集...')
            mcd, vd, si = self._load()
            if not mcd: self.analysis_failed.emit('数据集解析失败'); return
            is_csv = vd.get('_csv_parsed', False)
            sr = float(mcd.get('_sample_rate', 1000.0))
            self.progress_updated.emit(15, '提取通道...')
            cm = self._extract(mcd, sr)
            self.progress_updated.emit(25, '预处理...')
            pp = DataPreprocessor(sample_rate=sr, lowpass_cutoff=10.0)
            pc = {}
            for ch, cd in cm.items():
                if self._preprocess_level > 0 and len(cd['ax']) > 4:
                    acc = np.column_stack([cd['ax'], cd['ay'], cd['az']])
                    gyr = np.column_stack([cd['gx'], cd['gy'], cd['gz']])
                    pr = pp.process(acc, gyr, cd['timestamps'], level=self._preprocess_level)
                    pc[ch] = {'ax': pr['acc'][:,0] if pr['acc'].ndim>1 else pr['acc'],
                              'ay': pr['acc'][:,1] if pr['acc'].ndim>1 else np.zeros_like(pr['acc']),
                              'az': pr['acc'][:,2] if pr['acc'].ndim>1 else np.zeros_like(pr['acc']),
                              'gx': pr.get('gyro',cd.get('gx',np.array([]))),
                              'gy': pr.get('gyro',cd.get('gy',np.array([]))),
                              'gz': pr.get('gyro',cd.get('gz',np.array([]))),
                              'timestamps': pr['timestamps'], 'sample_rate': sr,
                              'speed': cd['speed'], 'wheel': cd['wheel']}
                else: pc[ch] = cd

            self.progress_updated.emit(35, '计算指标...')
            lr = {}
            for idx, loc in enumerate(self._locations):
                if not self._is_running: return
                cfg = get_location_config(loc)
                if not cfg: continue
                mr = {}
                for gt in ['experimental','control']:
                    cid = get_channel_by_location(loc, gt)
                    if not cid: continue
                    cd = pc.get(cid)
                    if cd is None: continue
                    dw = {'ax': cd['ax']/9.81, 'ay': cd['ay']/9.81, 'az': cd['az']/9.81,
                          'sample_rate': sr, 'speed': np.array(cd.get('speed',[])),
                          'wheel': np.array(cd.get('wheel',[]))}
                    ms = {}
                    for mid in self._selected_metrics:
                        if mid == 'ATTEN_H': continue
                        try: ms[mid] = self._engine._calculate_single_metric(mid, dw)
                        except: ms[mid] = float('nan')
                    prof = self._engine._build_vibration_profile(dw, ms, loc)
                    mr[gt] = {'metrics': ms, 'profile': prof}
                exp = mr.get('experimental',{}); ctrl = mr.get('control',{})
                eh = exp.get('metrics',{}).get('DISP_HR',0.0)
                ch_hr = ctrl.get('metrics',{}).get('DISP_HR',0.0)
                ah = (ch_hr-eh)/ch_hr*100 if abs(ch_hr)>1e-9 else 0.0
                exp.setdefault('metrics',{})['ATTEN_H'] = ah
                ctrl.setdefault('metrics',{})['ATTEN_H'] = ah
                ct = {}
                if exp.get('profile') and ctrl.get('profile'):
                    ct = self._engine._build_contrast_profile(exp['profile'],ctrl['profile'],loc,
                            exp_metrics=exp.get('metrics'),ctrl_metrics=ctrl.get('metrics'))
                lr[loc] = {'profile':exp.get('profile'),'contrast':ct,'control_profile':ctrl.get('profile'),
                           'metrics':exp.get('metrics',{}),'control_metrics':ctrl.get('metrics',{})}
                self.progress_updated.emit(35+int((idx+1)/max(len(self._locations),1)*30),
                    f'计算:{LOC_LABELS.get(loc,loc)}')

            self.progress_updated.emit(68, '驾驶行为...')
            bs = self._behavior(vd, cm, is_csv, sr)
            self.progress_updated.emit(72, '生成报告...')
            dur = 0.0
            for cd in cm.values():
                ts = cd.get('timestamps',np.array([]))
                if len(ts)>0: dur = max(dur, float(ts[-1]-ts[0]))
            lr['preprocess_level'] = self._preprocess_level
            lr['sample_rate'] = sr; lr['duration_s'] = dur
            lr['behavior_summary'] = bs
            lr['vehicle_summary'] = self._vsum(cm)
            fts = self._fts(cm, sr); lr['_full_timeseries'] = fts
            ov = self._overview(cm); lr['_overview_data'] = ov
            report = self._report_generator.generate_full_statistics_report(
                os.path.basename(self._dataset_path), lr, 'full')
            report['_full_timeseries'] = fts; report['_overview_data'] = ov
            report['_channel_data_map'] = cm; report['behavior_summary'] = bs
            report['vehicle_summary'] = lr.get('vehicle_summary',{})
            report['preprocess_level'] = self._preprocess_level
            report['sample_rate'] = sr; report['duration_s'] = dur
            self.progress_updated.emit(100, '完成'); self.analysis_completed.emit(report)
        except Exception as e:
            logger.error(f"分析失败: {e}", exc_info=True)
            self.analysis_failed.emit(f'分析失败: {str(e)}')
        finally: self._is_running = False
    def stop(self): self._is_running = False

    # ── 内部方法 ──
    def _load(self):
        fp = self._dataset_path
        if fp.lower().endswith('.csv'):
            try:
                with open(fp,'r',encoding='utf-8-sig') as f:
                    r = csv_mod.DictReader(f)
                    if 'imu_name' in (r.fieldnames or []) and 'Ax_m_s2' in (r.fieldnames or []):
                        bi = defaultdict(lambda:{'ax':[],'ay':[],'az':[],'gx':[],'gy':[],'gz':[],'timestamps':[],'speed':[],'wheel':[]})
                        raw=[]
                        for row in r:
                            imu=row.get('imu_name','')
                            if not imu: continue
                            try:
                                for k in ['ax','ay','az','gx','gy','gz']: bi[imu][k].append(float(row.get({'ax':'Ax_m_s2','ay':'Ay_m_s2','az':'Az_m_s2','gx':'Gx_dps','gy':'Gy_dps','gz':'Gz_dps'}[k],0)))
                                bi[imu]['timestamps'].append(float(row.get('rel_time',0)))
                                bi[imu]['speed'].append(float(row.get('speed',0)))
                                bi[imu]['wheel'].append(float(row.get('wheel',0)))
                                raw.append(row)
                            except: continue
                        mcd={};sr=1000.0
                        for imu,d in bi.items():
                            n=len(d['ax'])
                            if n<2: continue
                            ts=d['timestamps']
                            if len(ts)>=2 and ts[-1]-ts[0]>0:
                                dts=np.diff(ts);md=np.median(dts) if len(dts)>0 else 0.0
                                sr=1.0/md if md>0 else (n-1)/(ts[-1]-ts[0])
                            mcd[imu]={k:d[k] for k in d}
                        mcd['_sample_rate']=sr
                        vd={'speed_data':[],'steering_data':[],'brake_data':[],'_csv_parsed':True,'_raw_records':raw}
                        return mcd,vd,{'channels':list(bi.keys()),'total_records':sum(len(v['ax']) for v in bi.values())}
            except: pass
        elif fp.lower().endswith('.db'):
            try:
                conn=sqlite3.connect(fp)
                cur=conn.execute("SELECT source_type,rel_time,channel,imu_name,payload FROM data_records ORDER BY rel_time")
                bi={}
                for row in cur.fetchall():
                    try: rec=json.loads(row[4])
                    except: continue
                    imu=row[3] or rec.get('imu_name',rec.get('_imu_name',row[2] or 'unknown'))
                    if imu not in bi: bi[imu]={'ax':[],'ay':[],'az':[],'gx':[],'gy':[],'gz':[],'timestamps':[],'speed':[],'wheel':[]}
                    if 'Ax_m_s2' in rec:
                        for k in ['ax','ay','az','gx','gy','gz']: bi[imu][k].append(float(rec.get({'ax':'Ax_m_s2','ay':'Ay_m_s2','az':'Az_m_s2','gx':'Gx_dps','gy':'Gy_dps','gz':'Gz_dps'}[k],0)))
                        bi[imu]['timestamps'].append(float(row[1]));bi[imu]['speed'].append(float(rec.get('speed',0)));bi[imu]['wheel'].append(float(rec.get('wheel',0)))
                    elif 'ax' in rec:
                        for k in ['ax','ay','az','gx','gy','gz']: bi[imu][k].append(float(rec.get(k,0)))
                        bi[imu]['timestamps'].append(float(row[1]));bi[imu]['speed'].append(float(rec.get('speed',0)));bi[imu]['wheel'].append(float(rec.get('wheel',0)))
                conn.close()
                mcd={};sr=1000.0
                for imu,d in bi.items():
                    n=len(d['ax'])
                    if n<2: continue
                    ts=d['timestamps']
                    if len(ts)>=2 and ts[-1]-ts[0]>0: sr=(n-1)/(ts[-1]-ts[0])
                    mcd[imu]={k:d[k] for k in d}
                mcd['_sample_rate']=sr
                return mcd,{'speed_data':[],'steering_data':[],'brake_data':[],'_csv_parsed':True},{'channels':list(bi.keys()),'total_records':sum(len(v['ax']) for v in bi.values())}
            except: pass
        parser=FloorIMUParser();return parser.parse_file_and_select(fp)

    def _extract(self,mcd,sr):
        cm={}
        for ch in mcd:
            if ch.startswith('_'): continue
            d=mcd[ch];ts=np.array(d.get('timestamps',[]))
            if len(ts)==0 and len(d.get('ax',[]))>0: ts=np.arange(len(d['ax']))/sr
            cm[ch]={k:np.array(d.get(k,[])) for k in ['ax','ay','az','gx','gy','gz']}
            cm[ch]['timestamps']=ts;cm[ch]['sample_rate']=sr
            cm[ch]['speed']=np.array(d.get('speed',[]));cm[ch]['wheel']=np.array(d.get('wheel',[]))
        return cm

    def _behavior(self,vd,cm,is_csv,sr):
        bs={'hard_acceleration_count':0,'hard_braking_count':0,'sharp_turning_count':0,'overspeeding_count':0,'events':[],'total_events':0,'event_types':{}}
        raw=vd.get('_raw_records')
        if raw is None and not is_csv:
            ref_imu='IMU1_头部眉心-1';rd=cm.get(ref_imu)
            if rd is None:
                for n,d in cm.items():
                    if not n.startswith('_') and isinstance(d,dict):rd=d;ref_imu=n;break
            if rd and len(rd.get('ax',[]))>0:
                n=len(rd['ax']);ts=rd.get('timestamps',np.arange(n)/sr);raw=[]
                for i in range(n):raw.append({'rel_time':float(ts[i]) if i<len(ts) else i/sr,'channel':'ch1','imu_name':ref_imu,'Ax_m_s2':float(rd['ax'][i]) if i<len(rd['ax']) else 0,'Ay_m_s2':float(rd['ay'][i]) if i<len(rd['ay']) else 0,'Az_m_s2':float(rd['az'][i]) if i<len(rd['az']) else 0,'speed':float(rd.get('speed',np.zeros(n))[i]) if i<n else 0,'wheel':float(rd.get('wheel',np.zeros(n))[i]) if i<n else 0})
        if raw:
            try:
                from core.core.analysis.data_bridge import DataBridge
                br=DataBridge().analyze_behavior_batch(raw,ref_channel='ch1',ref_imu='IMU1_头部眉心-1')
                events=br.get('events',[]);by_type=br.get('summary',{}).get('by_type',{})
                st=np.array([float(r.get('rel_time',r.get('timestamp',0))) for r in raw],dtype=np.float64)
                sv=np.array([float(r.get('speed',0)) for r in raw],dtype=np.float64)
                for evt in events:
                    t0=evt.get('t_start',0);t1=evt.get('t_end',0)
                    i0=min(np.searchsorted(st,t0),len(sv)-1);i1=min(np.searchsorted(st,t1),len(sv)-1)
                    evt['speed_at_start']=round(float(sv[i0]),1);evt['speed_at_end']=round(float(sv[i1]),1)
                    evt['speed_delta']=round(evt['speed_at_end']-evt['speed_at_start'],1)
                bs['events']=events[:200];bs['_truncated']=len(events)>200
                bs['_total_detected']=len(events);bs['total_events']=len(events)
                bs['event_types']={et:info['count'] for et,info in by_type.items()}
            except Exception as e:logger.warning(f"行为检测失败:{e}")
        return bs

    def _vsum(self,cm):
        sa=[];wa=[]
        for ch in cm.values():
            sp=np.array(ch.get('speed',[]));wh=np.array(ch.get('wheel',[]))
            if len(sp)>0:sa.append(sp)
            if len(wh)>0:wa.append(wh)
        vs={}
        if sa:
            cs=np.concatenate(sa);vs['speed_mean']=float(np.mean(cs));vs['speed_std']=float(np.std(cs))
            vs['speed_median']=float(np.median(cs));vs['speed_max']=float(np.max(cs))
            iqr=np.percentile(cs,75)-np.percentile(cs,25)
            bw=max(2.0,min(20.0,2*iqr/(len(cs)**(1/3))))
            vmax=np.percentile(cs,99);bins=list(np.arange(0,vmax+bw,bw))
            hist,_=np.histogram(cs,bins=bins)
            vs['speed_histogram']={'bins':bins,'counts':hist.tolist() if hasattr(hist,'tolist') else list(hist)}
        if wa:
            cw=np.concatenate(wa);vs['wheel_mean']=float(np.mean(np.abs(cw)));vs['wheel_max']=float(np.max(np.abs(cw)))
            vs['turning_ratio_pct']=float(np.sum(np.abs(cw)>10)/len(cw)*100)
        return vs

    def _fts(self,cm,sr):
        try:
            ev=FullTimeseriesEvaluator()
            if not self._is_running:return None;ev.load_from_csv(self._dataset_path)
            if not self._is_running:return None;ev.detect_events()
            if not self._is_running:return None;ev.window_analysis()
            if not self._is_running:return None;ev.event_analysis()
            if not self._is_running:return None;ev.spectrum_analysis()
            if not self._is_running:return None;ev.stft_analysis()
            if not self._is_running:return None;ev.statistical_analysis()
            if not self._is_running:return None;ev.comprehensive_metrics()
            od=os.path.join(os.path.dirname(self._dataset_path),f"expert_{datetime.now():%Y%m%d_%H%M%S}")
            r={'events':ev.events,'results':ev.results}
            try:ev.generate_report(od);r['output_dir']=od
            except:pass
            try:
                from modules.ui.seat_evaluation.visualization_manager import VisualizationManager
                VisualizationManager().generate_all_plots(ev,od)
                r['num_plots']=len([f for f in os.listdir(od) if f.endswith('.png')])
            except:pass
            return r
        except Exception as e:logger.warning(f"全时域:{e}");return{'error':str(e)}

    def _overview(self,cm):
        eh=None;ch_h=None
        for cn in cm:
            if cn.startswith('_'):continue
            try:inum=int(cn.split('_')[0].replace('IMU',''))
            except:continue
            is_seat='座垫' in cn or 'R点' in cn
            if inum%2==1 and is_seat and eh is None:eh=cn
            elif inum%2==0 and is_seat and ch_h is None:ch_h=cn
        if eh is None or ch_h is None:
            for cn in cm:
                if cn.startswith('_'):continue
                try:inum=int(cn.split('_')[0].replace('IMU',''))
                except:continue
                is_h='head' in cn.lower() or '头部' in cn
                if inum%2==1 and is_h and eh is None:eh=cn
                elif inum%2==0 and is_h and ch_h is None:ch_h=cn
        for cn in cm:
            if cn.startswith('_'):continue
            try:inum=int(cn.split('_')[0].replace('IMU',''))
            except:continue
            if inum%2==1 and eh is None:eh=cn
            elif inum%2==0 and ch_h is None:ch_h=cn
        if not eh or not ch_h:return None
        ed=cm[eh];cd=cm[ch_h]
        ll='座垫R点' if ('座垫' in eh or 'R点' in eh) else ('头部眉心' if ('头部' in eh or 'head' in eh.lower()) else eh[:8])
        return{'timestamps':ed.get('timestamps'),'speed':ed.get('speed'),'wheel':ed.get('wheel'),
               'exp_ax':ed.get('ax'),'exp_ay':ed.get('ay'),'exp_az':ed.get('az'),
               'ctrl_ax':cd.get('ax'),'ctrl_ay':cd.get('ay'),'ctrl_az':cd.get('az'),
               'exp_channel':eh,'ctrl_channel':ch_h,'location_label':ll}


# ═══════════════════ StatisticsAnalysisTab v11.0 ═══════════════════

class StatisticsAnalysisTab(QWidget):
    """全量统计分析标签页 v11.0 — 全新图表模块"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self._registry = get_global_registry()
        self._report_generator = EvaluationReportGenerator()
        self._cr = None; self._dp = ''; self._wk = None; self._wkt = None
        self._mcbs = {}; self._charts = []
        self._init_ui(); self.setStyleSheet(SHEET)
        self.logger.info("v11.0 全新图表模块版 初始化完成")

    def clear_data(self):
        """清理数据（兼容 seat_evaluation_tab.py 调用）"""
        self._cr = None
        for c in self._charts:
            if c and c.isVisible():
                c.setVisible(False)
                if hasattr(c, '_cc'): self._clr(c._cc)
        self._charts.clear()

    def _init_ui(self):
        o = QVBoxLayout(self); o.setContentsMargins(0,0,0,0)
        self._sc = QScrollArea(); self._sc.setWidgetResizable(True); self._sc.setFrameShape(QFrame.NoFrame)
        o.addWidget(self._sc)
        cw = QWidget(); self._cw = cw; L = QVBoxLayout(cw); L.setSpacing(14); L.setContentsMargins(16,14,16,14)

        # 空状态
        self._empty = self._fc(""); el = QVBoxLayout(self._empty)
        el.setAlignment(Qt.AlignCenter); el.setContentsMargins(40,80,40,80)
        el.addWidget(QLabel("📊",alignment=Qt.AlignCenter,styleSheet="font-size:56px;"))
        el.addWidget(QLabel("全量统计分析",alignment=Qt.AlignCenter,styleSheet=f"font-size:24px;font-weight:700;color:{C['text']};"))
        el.addWidget(QLabel("加载已解析数据集，执行全量多通道座椅评测及IMU点位对照分析\n支持: CSV预解析 / SQLite缓存 / CAN原始日志",
                            alignment=Qt.AlignCenter,wordWrap=True,styleSheet=f"font-size:14px;color:{C['muted']};padding:16px 0;"))
        L.addWidget(self._empty)

        # 控制栏
        self._ctrl = self._fc(""); L.addWidget(self._ctrl); self._bc()

        # ═══ 1. 分析总览 (v8.0移植) ═══
        self._ov_grp = self._ovg("1. 分析总览"); L.addWidget(self._ov_grp)
        self._ov_dash = self._chc(""); self._ov_grp._cl.addWidget(self._ov_dash)
        self._ov_cond = self._chc(""); self._ov_grp._cl.addWidget(self._ov_cond)

        # 驾驶行为事件 (分析总览独立卡片)
        self._ov_bev = self._chc("驾驶行为事件分布"); L.addWidget(self._ov_bev)

        # 座垫R点三轴加速度
        self._ov_accel = self._chc("座垫R点三轴加速度"); L.addWidget(self._ov_accel)

        # 行程时间轴
        self._ov_timeline = self._chc("行程时间轴"); L.addWidget(self._ov_timeline)

        # KPI摘要行
        self._kpi_row = QWidget(); kpi_l = QHBoxLayout(self._kpi_row); kpi_l.setSpacing(12)
        self._kpi_w = {}
        for key,label in [('duration','⏱ 时长'),('speed','🚗 车速'),('events','📋 事件'),
                          ('sample','📡 采样率'),('locations','📍 位置'),('preprocess','🔧 预处理')]:
            c = self._fc(""); cl = QVBoxLayout(c); cl.setContentsMargins(12,10,12,10); cl.setSpacing(4)
            cl.addWidget(QLabel(label,styleSheet=f"font-size:11px;color:{C['muted']};"))
            vl = QLabel("—"); vl.setStyleSheet(f"font-size:20px;font-weight:700;color:{C['text']};"); cl.addWidget(vl)
            self._kpi_w[key] = vl; kpi_l.addWidget(c)
        self._kpi_row.setVisible(False); L.addWidget(self._kpi_row)

        # 图表行1-4 (双列)
        self._r1 = self._mrow(); L.addWidget(self._r1[0])
        self._r2 = self._mrow(); L.addWidget(self._r2[0])
        self._r3 = self._mrow(); L.addWidget(self._r3[0])
        self._r4 = self._mrow(); L.addWidget(self._r4[0])

        # 结果表
        self._res_card = self._chc("指标结果总览 (11列)"); self._res_card.setVisible(False); L.addWidget(self._res_card)
        self._beh_card = self._chc("驾驶行为事件统计"); self._beh_card.setVisible(False); L.addWidget(self._beh_card)

        # 输出QTabWidget
        self._otw = QTabWidget(); self._otw.setVisible(False); L.addWidget(self._otw); self._bot()

        # 全时域图表
        self._fts_card = self._chc("全时域滑动窗口评测"); self._fts_card.setVisible(False); L.addWidget(self._fts_card)
        self._stft_card = self._chc("STFT时频分析"); self._stft_card.setVisible(False); L.addWidget(self._stft_card)

        L.addStretch(); self._sc.setWidget(cw)

    def _fc(self, t):
        c = QFrame(); c.setStyleSheet(f"background:{C['bg']};border:1px solid {C['grid']};border-radius:10px;")
        lay = QVBoxLayout(c); lay.setContentsMargins(16,12,16,12); lay.setSpacing(8)
        if t: lay.addWidget(QLabel(t,styleSheet=f"font-size:14px;font-weight:700;color:{C['text']};padding-bottom:4px;border-bottom:1px solid {C['grid']};"))
        return c
    def _chc(self, t):
        c = QFrame(); c.setStyleSheet(f"background:white;border:1px solid {C['grid']};border-radius:10px;")
        lay = QVBoxLayout(c); lay.setContentsMargins(14,10,14,10); lay.setSpacing(6)
        lay.addWidget(QLabel(t,styleSheet=f"font-size:13px;font-weight:600;color:{C['text']};"))
        cc = QVBoxLayout(); cc.setContentsMargins(0,0,0,0); lay.addLayout(cc); c._cc = cc; c.setVisible(False)
        return c
    def _mrow(self):
        w = QWidget(); w.setVisible(False)
        l = QHBoxLayout(w); l.setSpacing(12); l.setContentsMargins(0,0,0,0)
        a = self._chc(""); b = self._chc(""); l.addWidget(a); l.addWidget(b)
        return w, a, b
    def _ovg(self, t):
        g = QGroupBox(t); g.setStyleSheet(f"QGroupBox{{font-size:14px;font-weight:bold;color:{C['exp']};border:2px solid {C['exp']};border-radius:8px;margin-top:12px;padding:20px 12px 12px 12px;}}QGroupBox::title{{subcontrol-origin:margin;left:14px;padding:0 6px;}}")
        g.setVisible(False); cl = QVBoxLayout(); cl.setContentsMargins(0,0,0,0)
        g._cl = QVBoxLayout(); cl.addLayout(g._cl); g.setLayout(cl); return g

    def _bc(self):
        L = self._ctrl.layout()
        fl = QHBoxLayout(); self._fl = QLabel("未选择文件"); self._fl.setStyleSheet(f"color:{C['muted']};"); fl.addWidget(self._fl,1)
        b = QPushButton("选择数据集"); b.setStyleSheet(f"background:{C['exp']};color:white;font-weight:600;padding:10px 24px;border:none;"); b.clicked.connect(self._brf); fl.addWidget(b)
        L.addLayout(fl)
        pl = QHBoxLayout(); pl.addWidget(QLabel("预处理级别:")); self._pc = QComboBox()
        for k,v in PRE_LABELS.items(): self._pc.addItem(f"Level {k}: {v}", k)
        self._pc.setCurrentIndex(1); pl.addWidget(self._pc); pl.addStretch()
        self._sel_all = QPushButton("全选"); self._sel_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self._mcbs.values()]); pl.addWidget(self._sel_all)
        self._sel_none = QPushButton("取消"); self._sel_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self._mcbs.values()]); pl.addWidget(self._sel_none)
        L.addLayout(pl)
        mg = QGridLayout()
        for i,(gn,ms) in enumerate(ALL_MG):
            gb = QGroupBox(gn); gl = QVBoxLayout(gb); gl.setSpacing(1)
            for mid in ms: cb = QCheckBox(mid); cb.setChecked(True); cb.setStyleSheet("font-size:11px;"); self._mcbs[mid] = cb; gl.addWidget(cb)
            mg.addWidget(gb,i//3,i%3)
        L.addLayout(mg)
        bl = QHBoxLayout()
        self._sb = QPushButton("▶ 开始分析"); self._sb.setStyleSheet(f"background:{C['exp']};color:white;font-weight:700;padding:12px 32px;border:none;font-size:14px;"); self._sb.clicked.connect(self._sa); bl.addWidget(self._sb)
        self._xb = QPushButton("⏹ 停止"); self._xb.setEnabled(False); self._xb.clicked.connect(self._xa); bl.addWidget(self._xb)
        self._pb = QProgressBar(); self._pb.setVisible(False); bl.addWidget(self._pb,1); L.addLayout(bl)
        self._stl = QLabel(""); self._stl.setStyleSheet(f"color:{C['muted']};font-size:11px;"); L.addWidget(self._stl)

    def _bot(self):
        pw = QWidget(); pl = QVBoxLayout(pw); pl.setContentsMargins(0,8,0,0)
        ec = QFrame(); el = QHBoxLayout(ec); el.setContentsMargins(0,0,0,4)
        el.addWidget(QLabel("综合分析报告",styleSheet=f"font-size:13px;font-weight:600;color:{C['text']};")); el.addStretch()
        for l,f in [("JSON","json"),("Markdown","md"),("CSV","csv")]:
            b = QPushButton(f"导出{l}"); b.setEnabled(False); b.clicked.connect(lambda _,ff=f: self._ex(ff)); el.addWidget(b)
            setattr(self,f"_ex_{f}_btn",b)
        pl.addWidget(ec)
        self._rp = QTextEdit(); self._rp.setReadOnly(True); self._rp.setMinimumHeight(250)
        self._rp.setStyleSheet(f"font-size:12px;color:{C['text']};background:white;border:1px solid {C['grid']};border-radius:8px;padding:12px;")
        self._rp.setPlaceholderText("分析完成后此处展示详细报告..."); pl.addWidget(self._rp)
        ct = QWidget(); cl = QVBoxLayout(ct); cl.setContentsMargins(0,8,0,0)
        self._cdt = QTableWidget(); self._cdt.setColumnCount(10)
        self._cdt.setHorizontalHeaderLabels(["ID","名称","位置","实验组","对照组","变化率%","评级","裁决","阈值","改进"])
        self._cdt.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); cl.addWidget(self._cdt)
        self._ctsl = QLabel(""); cl.addWidget(self._ctsl)
        self._otw.addTab(pw,"📊 报告预览"); self._otw.addTab(ct,"📋 对比数据表")

    def _clr(self, lay):
        if lay is None: return
        while lay.count():
            it = lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.layout(): self._clr(it.layout())

    def _add(self, card, fig, mh=180):
        if fig is None: return
        can = FigureCanvas(fig); can.setMinimumHeight(mh); self._charts.append(can)
        self._clr(card._cc); card._cc.addWidget(can); card.setVisible(True)

    # ═══ 事件 ═══
    def _brf(self):
        p,_ = QFileDialog.getOpenFileName(self,"选择数据集","","所有支持(*.csv *.txt *.db);;CSV(*.csv);;数据库(*.db);;所有(*.*)")
        if p: self._dp = p; self._fl.setText(os.path.basename(p))

    def _sa(self):
        if not self._dp: return QMessageBox.warning(self,"提示","请选择数据集")
        sel = [m for m,cb in self._mcbs.items() if cb.isChecked()]
        if not sel: return QMessageBox.warning(self,"提示","请至少选择一个指标")
        self._sb.setEnabled(False); self._xb.setEnabled(True); self._pb.setVisible(True)
        self._empty.setVisible(False); self._stl.setText("分析中...")
        self._wk = UnifiedEvaluationWorker()
        self._wk.configure(self._dp, self._pc.currentData(), sel, list(LOC_LABELS.keys()))
        self._wk.progress_updated.connect(lambda p,m: (self._pb.setValue(p),self._pb.setFormat(f"{m}({p}%)")))
        self._wk.analysis_completed.connect(self._od)
        self._wk.analysis_failed.connect(lambda e: (QMessageBox.critical(self,"失败",e),self._sb.setEnabled(True)))
        self._wkt = QThread(); self._wk.moveToThread(self._wkt)
        self._wkt.started.connect(self._wk.run); self._wkt.finished.connect(self._wkt.deleteLater)
        self._wkt.start()

    def _xa(self):
        if self._wk: self._wk.stop()
        if hasattr(self,'_wkt') and self._wkt: self._wkt.quit(); self._wkt.wait(3000)
        self._sb.setEnabled(True); self._xb.setEnabled(False)

    def _od(self, report):
        self._cr = report; self._pb.setValue(100); self._pb.setFormat("✅完成")
        self._sb.setEnabled(True); self._xb.setEnabled(False)
        self._stl.setText(f"✅ 分析完成 — {os.path.basename(self._dp)}"); self._stl.setStyleSheet(f"color:{C['diff']};font-weight:700;")

        vs = report.get('vehicle_summary',{}); bs = report.get('behavior_summary',{})
        ov = report.get('_overview_data'); cm = report.get('_channel_data_map',{})
        fts = report.get('_full_timeseries',{}); locs = report.get('locations',{})

        # ═══ 1. 分析总览 (v8.0移植) ═══
        self._r_ov_dashboard(report, vs)
        self._r_ov_condition(vs, bs)
        self._r_ov_behavior(bs)
        self._r_ov_accel(ov)
        self._r_ov_timeline(ov, bs)
        self._ov_grp.setVisible(True)

        # KPI
        self._setk('duration',f"{report.get('duration_s',0):.1f}s"); self._setk('speed',f"{vs.get('speed_mean',0):.0f}km/h")
        self._setk('events',str(bs.get('total_events',0))); self._setk('sample',f"{report.get('sample_rate',0):.0f}Hz")
        self._setk('locations',str(len(locs))); self._setk('preprocess',f"Lv.{report.get('preprocess_level',1)}")
        self._kpi_row.setVisible(True)

        # 图表行1
        self._r_speed(vs, self._r1[1]); self._r_timeline(ov, bs.get('events',[]), self._r1[2]); self._r1[0].setVisible(True)
        # 图表行2
        self._r_psd(cm, self._r2[1]); self._r_wave(cm, self._r2[2]); self._r2[0].setVisible(True)
        # 图表行3
        self._r_radar(report, self._r3[1]); self._r_atten(report, self._r3[2]); self._r3[0].setVisible(True)
        # 图表行4
        self._r_srs(cm, self._r4[1]); self._r_heat(locs, self._r4[2]); self._r4[0].setVisible(True)
        # 结果表
        self._r_results(locs)
        # 行为表
        self._r_behavior(bs)
        # 对比表
        self._r_contrast(locs)
        # 报告
        try: md = self._report_generator.export_to_markdown(report); self._rp.setMarkdown(md)
        except: self._rp.setPlainText("报告预览生成失败")
        # 全时域
        if fts and isinstance(fts,dict):
            self._r_sliding(fts); self._r_stft(fts)
        self._otw.setVisible(True)
        for f in ['json','md','csv']:
            b = getattr(self,f'_ex_{f}_btn',None)
            if b: b.setEnabled(True)
        if self._wkt: self._wkt.quit(); self._wkt.wait(1000)

    def _setk(self,k,v):
        w = self._kpi_w.get(k)
        if w: w.setText(v)

    # ═══ 分析总览渲染 (v8.0移植) ═══
    def _r_ov_dashboard(self, report, vs):
        """总览仪表盘 — HTML摘要 + 速度直方图 + 速度统计量"""
        c = self._ov_dash; self._clr(c._cc)
        dur = report.get('duration_s', 0); sr = report.get('sample_rate', 0)
        pre = report.get('preprocess_level', 1)
        pre_label = PRE_LABELS.get(pre, 'N/A')
        html = (f"<b>⏱ 时长:</b> {dur:.1f}s ({dur/60:.1f}min) &nbsp; "
                f"<b>📡 采样率:</b> {sr:.0f}Hz &nbsp; "
                f"<b>🔧 预处理:</b> {pre_label}<br>")
        if vs:
            html += (f"<b>🚗 均速:</b> {vs.get('speed_mean',0):.1f}km/h &nbsp; "
                     f"<b>📈 极速:</b> {vs.get('speed_max',0):.1f}km/h &nbsp; "
                     f"<b>📊 中位:</b> {vs.get('speed_median',0):.1f}km/h<br>"
                     f"<b>🔄 转向比:</b> {vs.get('turning_ratio_pct',0):.1f}% &nbsp; "
                     f"<b>🎯 方向盘:</b> {vs.get('wheel_mean',0):.1f}°")
        c._cc.addWidget(QLabel(html, wordWrap=True,
            styleSheet=f"font-size:12px;color:{C['text']};padding:4px 0;"))

        # 速度直方图
        hist = vs.get('speed_histogram')
        if hist:
            bins = np.array(hist.get('bins',[])); counts = np.array(hist.get('counts',[]))
            if len(bins) > 1:
                fig = S.fig(7, 2.2); ax = fig.add_subplot(111)
                ax.bar((bins[:-1]+bins[1:])/2, counts, width=np.diff(bins)*0.9,
                       alpha=0.75, color=C['exp'], edgecolor='white')
                ax.set_xlabel('车速 (km/h)', fontsize=9, **S.cn(9))
                ax.set_ylabel('计数', fontsize=9, **S.cn(9))
                ax.set_title('车速分布直方图', fontsize=10, **S.cnb(10)); ax.grid(axis='y', alpha=0.2)
                fig.tight_layout(); c._cc.addWidget(FigureCanvas(fig))

        # 速度统计量柱状图
        if vs and vs.get('speed_mean'):
            fig = S.fig(7, 2.5); ax = fig.add_subplot(111)
            vals = [vs.get('speed_mean',0), vs.get('speed_median',0),
                    vs.get('speed_max',0), vs.get('speed_std',0)]
            labels = ['均值', '中位数', '最大值', '标准差']
            colors = [C['exp'], '#5DADE2', C['bad'], C['ctrl']]
            ax.bar(labels, vals, color=colors, alpha=0.7, edgecolor='white')
            ax.set_ylabel('车速 (km/h)', fontsize=9, **S.cn(9))
            ax.set_title('车速统计量', fontsize=10, **S.cnb(10)); ax.grid(axis='y', alpha=0.2)
            for i, v in enumerate(vals): ax.text(i, v+0.5, f'{v:.1f}', ha='center', fontsize=8)
            fig.tight_layout(); c._cc.addWidget(FigureCanvas(fig))
        c.setVisible(True)

    def _r_ov_condition(self, vs, bh):
        """工况概览 — HTML摘要"""
        c = self._ov_cond; self._clr(c._cc)
        html = "<b>车辆工况:</b><br>"
        if vs:
            html += (f"• 均速: {vs.get('speed_mean',0):.1f} | 极速: {vs.get('speed_max',0):.1f} | "
                     f"中位: {vs.get('speed_median',0):.1f} km/h<br>"
                     f"• 速度σ: {vs.get('speed_std',0):.1f} km/h | "
                     f"转向比: {vs.get('turning_ratio_pct',0):.1f}%<br>")
        if bh:
            et = bh.get('event_types', {})
            html += f"<b>驾驶行为:</b><br>• 总事件: {bh.get('total_events',0)}个 ({len(et)}种)<br>"
            for etype, ct in sorted(et.items(), key=lambda x: -x[1])[:6]:
                cn = EV_CN.get(etype, etype)
                html += f"  {cn}: {ct}个<br>"
        c._cc.addWidget(QLabel(html, wordWrap=True,
            styleSheet=f"font-size:12px;color:{C['text']};padding:4px 0;"))
        c.setVisible(True)

    def _r_ov_behavior(self, bh):
        """驾驶行为事件 — 表格 + 分布图"""
        c = self._ov_bev; self._clr(c._cc)
        et = bh.get('event_types', {})
        if not et:
            c._cc.addWidget(QLabel("未检测到驾驶行为事件",
                styleSheet=f"color:{C['muted']};")); c.setVisible(True); return
        total = max(bh.get('total_events', 1), 1)
        nr = len(et) + (1 if bh.get('_truncated', False) else 0)
        t = QTableWidget(); t.setColumnCount(4); t.setRowCount(nr)
        t.setHorizontalHeaderLabels(['事件类型', '数量', '占比', ''])
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        row = 0
        for etype, count in sorted(et.items(), key=lambda x: -x[1]):
            t.setItem(row, 0, QTableWidgetItem(EV_CN.get(etype, etype)))
            t.setItem(row, 1, QTableWidgetItem(str(count)))
            t.setItem(row, 2, QTableWidgetItem(f"{count/total*100:.1f}%"))
            ci = QTableWidgetItem("■"); ci.setForeground(QColor(EV.get(etype, '#94A3B8')))
            t.setItem(row, 3, ci); row += 1
        if bh.get('_truncated', False):
            wi = QTableWidgetItem(f"⚠ 仅显示前200/{bh.get('_total_detected', bh.get('total_events',0))}个事件")
            wi.setForeground(QColor(C['bad'])); t.setItem(row, 0, wi); t.setSpan(row, 0, 1, 4)
        c._cc.addWidget(t)

        # 行为分布图
        if len(et) > 0:
            fig = S.fig(7, 3); ax = fig.add_subplot(111)
            types = list(et.keys())[:12]; counts = [et[t] for t in types]
            colors = [EV.get(t, '#3498DB') for t in types]
            ax.barh(range(len(types)), counts, color=colors, alpha=0.7, edgecolor='white')
            ax.set_yticks(range(len(types))); ax.set_yticklabels([EV_CN.get(t, t) for t in types], fontsize=8)
            ax.set_xlabel('事件数', fontsize=9, **S.cn(9))
            ax.set_title('驾驶行为事件分布', fontsize=10, **S.cnb(10))
            ax.invert_yaxis(); ax.grid(axis='x', alpha=0.2); fig.tight_layout()
            c._cc.addWidget(FigureCanvas(fig))
        c.setVisible(True)

    def _r_ov_accel(self, ov):
        """座垫R点三轴加速度 — 时域波形"""
        c = self._ov_accel; self._clr(c._cc)
        if not ov:
            c._cc.addWidget(QLabel("加速度数据不足",
                styleSheet=f"color:{C['muted']};")); c.setVisible(True); return
        ts = ov.get('timestamps'); ax_d = ov.get('exp_ax'); ay = ov.get('exp_ay'); az = ov.get('exp_az')
        if ts is None or ax_d is None:
            c._cc.addWidget(QLabel("加速度数据不足",
                styleSheet=f"color:{C['muted']};")); c.setVisible(True); return
        ts = np.asarray(ts); ax_d = np.asarray(ax_d)
        ay = np.asarray(ay) if ay is not None else np.zeros_like(ax_d)
        az = np.asarray(az) if az is not None else np.zeros_like(ax_d)
        step = max(1, len(ts)//3000)
        fig = S.fig(8, 4)
        axes = fig.subplots(3, 1, sharex=True)
        for i, (data, ylabel, color) in enumerate([
            (ax_d, 'Ax (m/s²)', C['bad']),
            (ay, 'Ay (m/s²)', C['exp']),
            (az, 'Az (m/s²)', C['diff'])]):
            axes[i].plot(ts[::step], data[::step], linewidth=0.6, color=color, alpha=0.8)
            axes[i].set_ylabel(ylabel, fontsize=8, **S.cn(8)); axes[i].grid(alpha=0.2)
        axes[0].set_title(f'座垫R点三轴加速度 — {ov.get("location_label","")}', fontsize=10, **S.cnb(10))
        axes[-1].set_xlabel('时间 (s)', fontsize=9, **S.cn(9)); fig.tight_layout()
        c._cc.addWidget(FigureCanvas(fig)); c.setVisible(True)

    def _r_ov_timeline(self, ov, bh):
        """行程时间轴 — 事件时间线"""
        c = self._ov_timeline; self._clr(c._cc)
        if not ov or ov.get('timestamps') is None:
            c._cc.addWidget(QLabel("时间轴数据不足",
                styleSheet=f"color:{C['muted']};")); c.setVisible(True); return
        ts = np.asarray(ov.get('timestamps',[])); sp = np.asarray(ov.get('speed',[]))
        wh = np.asarray(ov.get('wheel',[]))
        ev = bh.get('events', []) if bh else []
        loc = ov.get('location_label', '')
        if len(ts) < 2:
            c._cc.addWidget(QLabel("时间序列太短",
                styleSheet=f"color:{C['muted']};")); c.setVisible(True); return
        try:
            fig = create_event_timeline(ts, sp, wh, ev,
                title=f"驾驶事件时间线 — {loc}通道")
            c._cc.addWidget(FigureCanvas(fig))
        except Exception as e:
            c._cc.addWidget(QLabel(f"渲染失败: {e}",
                styleSheet=f"color:{C['bad']};"))
        c.setVisible(True)

    # ═══ 图表渲染 ═══
    def _r_speed(self,vs,card):
        hist = vs.get('speed_histogram')
        if not hist: return
        bins = np.array(hist.get('bins',[])); counts = np.array(hist.get('counts',[]))
        if len(bins)<2: return
        fig = S.fig(5,2.5); ax = fig.add_subplot(111)
        ax.bar((bins[:-1]+bins[1:])/2, counts, width=np.diff(bins)*0.9, alpha=0.8, color=C['exp'], edgecolor='white')
        ax.set_xlabel('车速(km/h)',fontsize=9); ax.set_ylabel('计数',fontsize=9)
        ax.set_title(f'车速分布 (均{vs.get("speed_mean",0):.0f}, 极{vs.get("speed_max",0):.0f}km/h)',fontsize=10,fontweight='bold')
        ax.grid(axis='y',alpha=0.2); fig.tight_layout(); self._add(card,fig,160)

    def _r_timeline(self,ov,events,card):
        if not ov or ov.get('timestamps') is None: return
        ts=np.asarray(ov.get('timestamps',[])); sp=np.asarray(ov.get('speed',[])); wh=np.asarray(ov.get('wheel',[]))
        if len(ts)<2: return
        try: self._add(card, create_event_timeline(ts,sp,wh,events or [],title=f"事件时间线 — {ov.get('location_label','')}"),220)
        except: pass

    def _r_psd(self,cm,card):
        e=[k for k in cm if k.endswith('-1')]; ct=[k for k in cm if k.endswith('-2')]
        if not e: return
        try: self._add(card, create_psd_comparison(cm,e,ct,axis='Z'),200)
        except: pass

    def _r_wave(self,cm,card):
        e=[k for k in cm if k.endswith('-1')][:3]
        if not e: return
        try: self._add(card, create_acceleration_waveform(cm,e,figsize=(6,6)),280)
        except: pass

    def _r_radar(self,report,card):
        comp = self._bcd(report)
        if comp:
            try: self._add(card, create_comparison_radar(comp),250)
            except: pass

    def _r_atten(self,report,card):
        comp = self._bcd(report)
        if comp:
            try: self._add(card, create_attenuation_bar(comp),230)
            except: pass

    def _bcd(self,report):
        r={}
        for lid,ld in report.get('locations',{}).items():
            ct=ld.get('contrast') or {}; mag=ct.get('magnitude',{})
            for mid,md in mag.items():
                if not isinstance(md,dict):continue
                ev=md.get('experimental',md.get('exp')); cv=md.get('control',md.get('ctrl')); dp=md.get('delta_pct')
                if ev is not None and cv is not None and dp is not None:
                    r[f"{lid[:6]}-{mid[:8]}"]={'exp':float(ev) if ev else 0,'ctrl':float(cv) if cv else 0,'atten_pct':float(dp)}
        return r

    def _r_srs(self,cm,card):
        he=next((k for k in cm if '头部' in k and k.endswith('-1')),next((k for k in cm if k.endswith('-1')),None))
        hc=next((k for k in cm if '头部' in k and k.endswith('-2')),next((k for k in cm if k.endswith('-2')),None))
        ln='头部眉心' if (he and '头部' in he) else '默认'
        if he and hc:
            try: self._add(card, create_srs_comparison(cm,he,hc,location_name=ln,axis='Z'),180)
            except: pass

    def _r_heat(self,locs,card):
        all_m=sorted(set(mid for lr in locs.values() for mid in lr.get('metrics',{}).keys() if not mid.endswith('_')))
        all_l=[loc for loc in locs if isinstance(locs.get(loc),dict)]
        if len(all_m)<2 or len(all_l)<2: return
        try: self._add(card, create_metric_heatmap(locs,all_m,all_l),320)
        except: pass

    def _r_results(self,locs):
        c=self._res_card;self._clr(c._cc)
        all_ids=set()
        for ld in locs.values():
            if isinstance(ld,dict): all_ids.update(ld.get('metrics',{}).keys())
        grouped={}
        for mid in all_ids:
            meta=self._registry.get_indicator_meta(mid)
            dim=DIM_MAP.get(meta.evaluation_dimension if meta else '通用-基础','通用-基础')
            grouped.setdefault(dim,[]).append(mid)
        for v in grouped.values():v.sort()
        rows=[]
        for dim in sorted(grouped.keys(),key=lambda d:DIM_ORD.get(d,99)):
            for mid in grouped[dim]:rows.append((mid,dim))

        t=QTableWidget();t.setColumnCount(11);t.setRowCount(len(rows))
        t.setHorizontalHeaderLabels(['编码','名称','维度','单位','实验组','对照组','绝对差','变化率%','状态','阈值','位置'])
        t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for row,(mid,dim) in enumerate(rows):
            meta=self._registry.get_indicator_meta(mid);thr=self._registry.get_threshold(mid)
            t.setItem(row,0,QTableWidgetItem(mid))
            ni=QTableWidgetItem(meta.display_name_cn if meta else mid)
            if meta:
                tips=[f"{meta.display_name_cn}({meta.display_name_en})",f"单位:{meta.unit}",f"公式:{meta.formula_text}"]
                if meta.standard_refs:tips.append(f"标准:{','.join([str(r) for r in meta.standard_refs[:3]])}")
                ni.setToolTip('\n'.join(tips))
            t.setItem(row,1,ni)
            di=QTableWidgetItem(dim);di.setForeground(QColor(DIM_C.get(dim,C['muted'])));t.setItem(row,2,di)
            t.setItem(row,3,QTableWidgetItem(meta.unit if meta and meta.unit!='-' else ''))
            ev=None;cv=None
            for loc,lr in locs.items():
                if not isinstance(lr,dict):continue
                em=lr.get('metrics',{}).get(mid);cm=lr.get('control_metrics',{}).get(mid)
                if isinstance(em,(int,float)) and np.isfinite(em):ev=em
                if isinstance(cm,(int,float)) and np.isfinite(cm):cv=cm
                if ev is not None:break
            t.setItem(row,4,QTableWidgetItem(f"{ev:.4f}" if ev is not None else "--"))
            t.setItem(row,5,QTableWidgetItem(f"{cv:.4f}" if cv is not None else "--"))
            t.setItem(row,6,QTableWidgetItem(f"{ev-cv:+.4f}" if ev is not None and cv is not None else "--"))
            pi=QTableWidgetItem("--");pi.setForeground(QColor(C['muted']))
            if ev is not None and cv is not None and abs(cv)>1e-9:
                dp=(ev-cv)/abs(cv)*100;pi=QTableWidgetItem(f"{dp:+.1f}%")
                lb=meta.direction.name in ('LOWER_IS_BETTER','LOWER_BETTER') if meta else True
                pi.setForeground(QColor(C['diff'] if (dp<0 if lb else dp>0) else C['bad']))
            t.setItem(row,7,pi)
            si=QTableWidgetItem('-');si.setForeground(QColor(C['muted']))
            if ev is not None:
                pt=meta.threshold_pass if meta else (thr.get('pass') if thr else None)
                wt=thr.get('warn') if thr else None
                if pt is not None:
                    try:
                        pv=float(pt);wv=float(wt) if wt else None
                        d=meta.direction.name if meta else 'LOWER_IS_BETTER'
                        if d in ('LOWER_IS_BETTER','LOWER_BETTER'):
                            if ev<=pv:si=QTableWidgetItem('✓通过');si.setForeground(QColor(C['diff']))
                            elif wv and ev<=wv:si=QTableWidgetItem('⚠警告');si.setForeground(QColor(C['ctrl']))
                            else:si=QTableWidgetItem('✗超标');si.setForeground(QColor(C['bad']))
                        else:
                            if ev>=pv:si=QTableWidgetItem('✓通过');si.setForeground(QColor(C['diff']))
                            elif wv and ev>=wv:si=QTableWidgetItem('⚠警告');si.setForeground(QColor(C['ctrl']))
                            else:si=QTableWidgetItem('✗超标');si.setForeground(QColor(C['bad']))
                    except:pass
            t.setItem(row,8,si)
            tt=meta.threshold_pass if meta else (str(thr.get('pass')) if thr and thr.get('pass') is not None else '')
            t.setItem(row,9,QTableWidgetItem(tt if tt else '-'))
            t.setItem(row,10,QTableWidgetItem(','.join(meta.applicable_locations) if meta and meta.applicable_locations else '-'))
        c._cc.addWidget(t);c.setVisible(True)

    def _r_behavior(self,bs):
        c=self._beh_card;self._clr(c._cc)
        et=bs.get('event_types',{});total=max(bs.get('total_events',1),1)
        if not et: c._cc.addWidget(QLabel("未检测到事件"));c.setVisible(True);return
        nr=len(et)+(1 if bs.get('_truncated',False) else 0)
        t=QTableWidget();t.setColumnCount(4);t.setRowCount(nr)
        t.setHorizontalHeaderLabels(['事件类型','数量','占比','']);t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        row=0
        for etype,count in sorted(et.items(),key=lambda x:-x[1]):
            t.setItem(row,0,QTableWidgetItem(etype));t.setItem(row,1,QTableWidgetItem(str(count)))
            t.setItem(row,2,QTableWidgetItem(f"{count/total*100:.1f}%"))
            ci=QTableWidgetItem("■");ci.setForeground(QColor(EV.get(etype,'#94A3B8')));t.setItem(row,3,ci);row+=1
        if bs.get('_truncated',False):
            wi=QTableWidgetItem(f"⚠仅显示前200/{bs.get('_total_detected',bs.get('total_events',0))}个");wi.setForeground(QColor(C['bad']))
            t.setItem(row,0,wi);t.setSpan(row,0,1,4)
        c._cc.addWidget(t)
        if len(et)>0:
            fig=S.fig(5,2.5);ax=fig.add_subplot(111)
            types=list(et.keys())[:12];counts=[et[t] for t in types]
            colors=[EV.get(t,'#3498DB') for t in types]
            ax.barh(range(len(types)),counts,color=colors,alpha=0.7,edgecolor='white')
            ax.set_yticks(range(len(types)));ax.set_yticklabels([EV_CN.get(t, t) for t in types],fontsize=7);ax.invert_yaxis()
            ax.set_xlabel('事件数',fontsize=9);ax.grid(axis='x',alpha=0.2);fig.tight_layout()
            c._cc.addWidget(FigureCanvas(fig))
        c.setVisible(True)

    def _r_contrast(self,locs):
        t=self._cdt;t.setRowCount(0);row=0
        for lid,ld in locs.items():
            if not isinstance(ld,dict):continue
            for mid,val in ld.get('metrics',{}).items():
                if mid.endswith('_'):continue
                cm=ld.get('control_metrics',{}).get(mid,float('nan'))
                meta=self._registry.get_indicator_meta(mid);name=meta.display_name_cn if meta else mid
                thr=self._registry.get_threshold(mid);pt=meta.threshold_pass if meta else (thr.get('pass') if thr else None)
                t.setRowCount(row+1);t.setItem(row,0,QTableWidgetItem(mid));t.setItem(row,1,QTableWidgetItem(name))
                t.setItem(row,2,QTableWidgetItem(LOC_LABELS.get(lid,lid)))
                t.setItem(row,3,QTableWidgetItem(f"{val:.4f}" if isinstance(val,(int,float)) and np.isfinite(val) else "--"))
                t.setItem(row,4,QTableWidgetItem(f"{cm:.4f}" if isinstance(cm,(int,float)) and np.isfinite(cm) else "--"))
                pct="—";rating="—";verdict="—"
                if isinstance(val,(int,float)) and isinstance(cm,(int,float)) and np.isfinite(val) and np.isfinite(cm) and abs(cm)>1e-9:
                    pv=(val-cm)/abs(cm)*100;pct=f"{pv:+.1f}%"
                    rating='✅' if pv<-10 else '✔' if pv<0 else '≈' if pv<5 else '⚠' if pv<15 else '❌'
                    verdict='改善' if pv<-5 else ('恶化' if pv>5 else '无变化')
                t.setItem(row,5,QTableWidgetItem(pct));t.setItem(row,6,QTableWidgetItem(rating))
                t.setItem(row,7,QTableWidgetItem(verdict));t.setItem(row,8,QTableWidgetItem(str(pt) if pt else '—'))
                t.setItem(row,9,QTableWidgetItem('—'));row+=1
        self._ctsl.setText(f"共{row}条");self._otw.setVisible(True)

    def _r_sliding(self,fts):
        wr=fts.get('results',{}).get('windows',[])
        if wr: self._add(self._fts_card, create_sliding_window_chart(wr),180)

    def _r_stft(self,fts):
        st=fts.get('results',{}).get('stft',{})
        if st: self._add(self._stft_card, create_stft_chart(st),220)

    # ═══ 导出 ═══
    def _ex(self,fmt):
        if not self._cr:return QMessageBox.warning(self,"提示","请先完成分析")
        p,_=QFileDialog.getSaveFileName(self,f"导出{fmt.upper()}","",f"{fmt.upper()}(*.{fmt})")
        if not p:return
        try:
            if fmt=='csv':self._ex_csv(p)
            elif fmt=='json':json.dump(self._cr,open(p,'w',encoding='utf-8'),indent=2,default=str,ensure_ascii=False)
            elif fmt=='md':open(p,'w',encoding='utf-8').write(self._rp.toPlainText())
            QMessageBox.information(self,"成功",f"已导出:{p}")
        except Exception as e:QMessageBox.critical(self,"失败",str(e))

    def _ex_csv(self,p):
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv_mod.writer(f);w.writerow(['位置','指标','实验组','对照组','改善率%'])
            for lid,ld in self._cr.get('locations',{}).items():
                if not isinstance(ld,dict):continue
                for mid,val in ld.get('metrics',{}).items():
                    if mid.endswith('_'):continue
                    cm=ld.get('control_metrics',{}).get(mid,float('nan'))
                    pct=(float(cm)-float(val))/max(abs(float(cm)),1e-9)*100;w.writerow([lid,mid,val,cm,f"{pct:.1f}"])

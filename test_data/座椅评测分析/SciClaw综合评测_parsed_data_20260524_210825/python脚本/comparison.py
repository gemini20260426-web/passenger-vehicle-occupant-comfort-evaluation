"""SciClaw 实验组vs对照组对比模块"""

import numpy as np
import pandas as pd

def _atten(exp, ctrl):
    """计算衰减率"""
    if abs(ctrl) > 1e-9:
        return (ctrl - exp) / ctrl * 100
    return 0.0

def _verdict(atten):
    if atten > 10: return '✅ 实验组显著优于对照组'
    elif atten > 3: return '✓ 实验组略优'
    elif atten < -10: return '⚠ 对照组显著优于实验组'
    elif atten < -3: return '⚠ 对照组略优'
    return '≈ 无显著差异'

def compare(df):
    """实验组 vs 对照组全指标对比"""
    results = {}

    # ---- 头部对比 (IMU1 vs IMU2) ----
    try:
        d1 = df[df['imu_name']=='IMU1_头部眉心-1'].sort_values('rel_time')
        d2 = df[df['imu_name']=='IMU2_头部眉心-2'].sort_values('rel_time')
        if len(d1) > 10 and len(d2) > 10:
            a1 = np.max(np.sqrt(d1['Ax_m_s2']**2+d1['Ay_m_s2']**2+d1['Az_m_s2']**2))
            a2 = np.max(np.sqrt(d2['Ax_m_s2']**2+d2['Ay_m_s2']**2+d2['Az_m_s2']**2))
            atten = _atten(a1, a2)
            results['头部加速度峰值(g)'] = {
                'exp': round(float(a1),3), 'ctrl': round(float(a2),3),
                'atten_pct': round(atten,1), 'verdict': _verdict(atten)
            }

        # 头部RMS
        rms1 = np.sqrt(np.mean((d1['Az_m_s2'])**2))
        rms2 = np.sqrt(np.mean((d2['Az_m_s2'])**2))
        atten = _atten(rms1, rms2)
        results['头部Az RMS(m/s²)'] = {
            'exp': round(float(rms1),3), 'ctrl': round(float(rms2),3),
            'atten_pct': round(atten,1), 'verdict': _verdict(atten)
        }
    except: pass

    # ---- 座垫对比 (IMU5 vs IMU6 with IMU7/8 base) ----
    try:
        from indicator_metadata_engine import DataPipeline

        def build(imu):
            d = df[df['imu_name']==imu].sort_values('rel_time')
            return {'rel_time':d['rel_time'].values,'Ax_m_s2':d['Ax_m_s2'].values,
                    'Ay_m_s2':d['Ay_m_s2'].values,'Az_m_s2':d['Az_m_s2'].values,
                    'Gx_dps':d['Gx_dps'].values,'Gy_dps':d['Gy_dps'].values,
                    'Gz_dps':d['Gz_dps'].values}

        imus = df['imu_name'].unique()
        if all(n in imus for n in ['IMU5_座垫R点-1','IMU6_座垫R点-2','IMU7_座椅底部-1','IMU8_座椅底部-2']):
            p = DataPipeline()
            for n in ['IMU5_座垫R点-1','IMU6_座垫R点-2','IMU7_座椅底部-1','IMU8_座椅底部-2']:
                p.load_imu(n, build(n))
            p.step_cfc_filter(1000).step_psd_welch().step_frequency_weighting().step_rms()

            se = p.compute_seat('IMU5_座垫R点-1','IMU7_座椅底部-1')
            sc = p.compute_seat('IMU6_座垫R点-2','IMU8_座椅底部-2')
            ve = p.step_vdv('IMU5_座垫R点-1','Z')
            vc = p.step_vdv('IMU6_座垫R点-2','Z')

            for name, e, c in [('座垫SEAT-Z', se['SEAT_Z'], sc['SEAT_Z']),
                                ('座垫VDV-Z', ve, vc)]:
                atten = _atten(e, c)
                results[name] = {'exp':round(float(e),3), 'ctrl':round(float(c),3),
                                 'atten_pct':round(atten,1), 'verdict':_verdict(atten)}
    except: pass

    return results

def compare_from_dict(data: dict):
    """从字典对比 (暂未实现)"""
    return {}

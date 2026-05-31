"""SciClaw 考核指标桥接模块"""

import numpy as np

def compute_all(df):
    """计算CSV数据的全部考核指标"""
    results = {}
    try:
        from indicator_metadata_engine import DataPipeline

        def build(imu):
            d = df[df['imu_name']==imu].sort_values('rel_time')
            return {'rel_time':d['rel_time'].values,'Ax_m_s2':d['Ax_m_s2'].values,
                    'Ay_m_s2':d['Ay_m_s2'].values,'Az_m_s2':d['Az_m_s2'].values,
                    'Gx_dps':d['Gx_dps'].values,'Gy_dps':d['Gy_dps'].values,
                    'Gz_dps':d['Gz_dps'].values}

        # 头部指标
        imus = df['imu_name'].unique()
        if 'IMU1_头部眉心-1' in imus:
            p = DataPipeline()
            p.load_imu('head', build('IMU1_头部眉心-1'))
            p.step_cfc_filter(600).step_vector_synthesis()
            results['头部ACC-PEAK(g)'] = float(np.max(p.derived['head/A_MAG_g']))
            results['HIC15'] = p.step_hic15('head')['HIC15']

        # SEAT/VDV
        if all(n in imus for n in ['IMU5_座垫R点-1','IMU7_座椅底部-1']):
            p = DataPipeline()
            p.load_imu('seat', build('IMU5_座垫R点-1'))
            p.load_imu('base', build('IMU7_座椅底部-1'))
            p.step_cfc_filter(1000).step_psd_welch().step_frequency_weighting().step_rms()
            results['SEAT-Z'] = p.compute_seat('seat','base')['SEAT_Z']
            results['VDV-Z'] = p.step_vdv('seat','Z')

    except ImportError:
        pass

    return results

def compute_all_from_dict(data: dict):
    """从字典计算指标 (暂未实现)"""
    return {}

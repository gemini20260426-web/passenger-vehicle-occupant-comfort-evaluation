"""
IMU 通道映射器 — 本项目IMU编号 ↔ 仓库IMU编号双向映射

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第二部分 4.1 节。
"""

from typing import Dict, List, Optional


class IMUChannelMapper:
    """IMU通道映射器

    解决报告第二部分 3.1 节发现的 P0 问题:
    - 仓库定义: imu1-5 (实验组), imu6-10 (对照组)
    - 本项目: 奇数IMU=实验组, 偶数IMU=对照组
    - 身体部位映射完全不同

    提供双向映射和分组查询。
    """

    # 本项目 IMU 编号 → 仓库 IMU 编号 映射
    PROJECT_TO_REPO = {
        # 实验组 (奇数)
        'IMU1_头部眉心-1':  'imu1',   # 头部
        'IMU3_躯干T8-1':   'imu2',   # 躯干 (仓库: 靠背)
        'IMU5_座垫R点-1':  'imu3',   # 座垫
        'IMU7_座椅底部-1': 'imu4',   # 座椅底部 (仓库: 地板)
        'IMU9_胸骨剑突-1': 'imu5',   # 胸骨 (仓库: 头枕旁)
        # 对照组 (偶数)
        'IMU2_头部眉心-2':  'imu6',
        'IMU4_躯干T8-2':   'imu7',
        'IMU6_座垫R点-2':  'imu8',
        'IMU8_座椅底部-2': 'imu9',
        'IMU10_胸骨剑突-2': 'imu10',
    }

    # 仓库 IMU 编号 → 本项目 IMU 编号 映射
    REPO_TO_PROJECT = {v: k for k, v in PROJECT_TO_REPO.items()}

    # 身体部位标签
    BODY_PART_LABELS = {
        'IMU1_头部眉心-1':  'head',
        'IMU2_头部眉心-2':  'head',
        'IMU3_躯干T8-1':   'torso',
        'IMU4_躯干T8-2':   'torso',
        'IMU5_座垫R点-1':  'seat_r',
        'IMU6_座垫R点-2':  'seat_r',
        'IMU7_座椅底部-1': 'seat_bottom',
        'IMU8_座椅底部-2': 'seat_bottom',
        'IMU9_胸骨剑突-1': 'sternum',
        'IMU10_胸骨剑突-2': 'sternum',
    }

    # 中文身体部位标签
    BODY_PART_LABELS_CN = {
        'head': '头部',
        'torso': '躯干T8',
        'seat_r': '座垫R点',
        'seat_bottom': '座椅底部',
        'sternum': '胸骨剑突',
    }

    # 分组映射
    GROUP_MAP = {
        # 实验组 (奇数)
        'IMU1_头部眉心-1':  'experimental',
        'IMU3_躯干T8-1':   'experimental',
        'IMU5_座垫R点-1':  'experimental',
        'IMU7_座椅底部-1': 'experimental',
        'IMU9_胸骨剑突-1': 'experimental',
        # 对照组 (偶数)
        'IMU2_头部眉心-2':  'control',
        'IMU4_躯干T8-2':   'control',
        'IMU6_座垫R点-2':  'control',
        'IMU8_座椅底部-2': 'control',
        'IMU10_胸骨剑突-2': 'control',
    }

    def to_repo(self, project_imu_name: str) -> Optional[str]:
        """本项目IMU名 → 仓库IMU编号"""
        return self.PROJECT_TO_REPO.get(project_imu_name)

    def to_project(self, repo_imu_id: str) -> Optional[str]:
        """仓库IMU编号 → 本项目IMU名"""
        return self.REPO_TO_PROJECT.get(repo_imu_id)

    def get_group(self, imu_name: str) -> str:
        """获取IMU所属分组 (experimental/control/unknown)"""
        return self.GROUP_MAP.get(imu_name, 'unknown')

    def get_body_part(self, imu_name: str) -> str:
        """获取IMU对应的身体部位 (英文)"""
        return self.BODY_PART_LABELS.get(imu_name, 'unknown')

    def get_body_part_cn(self, imu_name: str) -> str:
        """获取IMU对应的身体部位 (中文)"""
        en = self.BODY_PART_LABELS.get(imu_name, 'unknown')
        return self.BODY_PART_LABELS_CN.get(en, en)

    def get_imus_by_group(self, group: str) -> List[str]:
        """获取指定分组的所有IMU名称"""
        return [k for k, v in self.GROUP_MAP.items() if v == group]

    def get_imus_by_body_part(self, body_part: str) -> List[str]:
        """获取指定身体部位的所有IMU名称"""
        return [k for k, v in self.BODY_PART_LABELS.items() if v == body_part]

    def get_experimental_imus(self) -> List[str]:
        """获取所有实验组IMU名称"""
        return self.get_imus_by_group('experimental')

    def get_control_imus(self) -> List[str]:
        """获取所有对照组IMU名称"""
        return self.get_imus_by_group('control')

    def get_all_imu_names(self) -> List[str]:
        """获取所有IMU名称"""
        return list(self.PROJECT_TO_REPO.keys())

    def get_experimental_control_pairs(self) -> List[Dict[str, str]]:
        """获取实验组↔对照组配对

        Returns:
            [{body_part, experimental, control}, ...]
        """
        pairs = [
            ('head', 'IMU1_头部眉心-1', 'IMU2_头部眉心-2'),
            ('torso', 'IMU3_躯干T8-1', 'IMU4_躯干T8-2'),
            ('seat_r', 'IMU5_座垫R点-1', 'IMU6_座垫R点-2'),
            ('seat_bottom', 'IMU7_座椅底部-1', 'IMU8_座椅底部-2'),
            ('sternum', 'IMU9_胸骨剑突-1', 'IMU10_胸骨剑突-2'),
        ]
        return [
            {'body_part': bp, 'experimental': exp, 'control': ctrl}
            for bp, exp, ctrl in pairs
        ]

    def get_mapping_summary(self) -> dict:
        """获取映射摘要"""
        return {
            'total_imus': len(self.PROJECT_TO_REPO),
            'experimental_imus': self.get_experimental_imus(),
            'control_imus': self.get_control_imus(),
            'body_parts': list(self.BODY_PART_LABELS_CN.values()),
            'pairs': self.get_experimental_control_pairs(),
        }
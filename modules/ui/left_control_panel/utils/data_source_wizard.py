"""
7级数据源配置向导 — 替换原 ConfigWidget 的8 Tab扁平配置

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第四部分 4.4.1 节。
"""

import os
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class WizardConfig:
    """向导配置容器"""
    # Step 1: 项目预设
    project_preset: str = 'active_seat_suspension'

    # Step 2: 数据源类型
    data_source_type: str = 'can_file'

    # Step 3: 物理通道
    file_path: str = ''
    com_port: str = ''
    baudrate: int = 921600

    # Step 4: IMU通道分组
    imu_mapping: dict = field(default_factory=dict)
    grouping_rule: str = ''

    # Step 5: 信号字段映射
    signal_mapping: dict = field(default_factory=dict)

    # Step 6: 采样参数
    fs: int = 1000
    trigger_condition: str = 'continuous'
    timeout_seconds: int = 30

    # Step 7: 连接测试结果
    test_results: dict = field(default_factory=dict)


class DataSourceWizard:
    """7级数据源配置向导

    替换原 ConfigWidget 的 8 个 Tab 页，采用分步向导模式。
    每一步有明确的输入验证和下一步/上一步导航。
    """

    # ── 项目预设模板 ──
    PRESETS = {
        'active_seat_suspension': {
            'name': '主动控制座椅悬架',
            'description': '多自由度多轴主动控制座椅悬架乘员舒适性评测',
            'grouping_rule': '奇数=实验组(主动) / 偶数=对照组(被动)',
            'fs': 1000,
            'imu_mapping': {
                'experimental': [
                    'IMU1_头部眉心-1', 'IMU3_躯干T8-1', 'IMU5_座垫R点-1',
                    'IMU7_座椅底部-1', 'IMU9_胸骨剑突-1',
                ],
                'control': [
                    'IMU2_头部眉心-2', 'IMU4_躯干T8-2', 'IMU6_座垫R点-2',
                    'IMU8_座椅底部-2', 'IMU10_胸骨剑突-2',
                ],
            },
            'body_parts': ['头部', '躯干T8', '座垫R点', '座椅底部', '胸骨剑突'],
            'signal_mapping': {
                'Ax_m_s2': 'ax', 'Ay_m_s2': 'ay', 'Az_m_s2': 'az',
                'Gx_dps': 'gx', 'Gy_dps': 'gy', 'Gz_dps': 'gz',
                'speed': 'speed', 'wheel': 'wheel',
            },
        },
        'generic': {
            'name': '通用配置',
            'description': '自定义IMU通道配置',
            'grouping_rule': '手动指定',
            'fs': 100,
            'imu_mapping': {'experimental': [], 'control': []},
            'body_parts': [],
            'signal_mapping': {},
        },
    }

    # 数据源类型
    DATA_SOURCE_TYPES = {
        'can_file': 'CAN文件 (CSV)',
        'serial': '串口实时采集',
        'mqtt': 'MQTT消息队列',
        'database': '数据库读取',
    }

    def __init__(self):
        self.config = WizardConfig()
        self.current_step = 1
        self.total_steps = 7
        self.step_validators = {
            1: self._validate_step1,
            2: self._validate_step2,
            3: self._validate_step3,
            4: self._validate_step4,
            5: self._validate_step5,
            6: self._validate_step6,
            7: self._validate_step7,
        }

    # ── Step 1: 项目预设选择 ──

    def get_preset_options(self) -> List[dict]:
        """获取可用预设列表"""
        return [
            {'key': k, 'name': v['name'], 'description': v['description']}
            for k, v in self.PRESETS.items()
        ]

    def select_preset(self, preset_key: str) -> bool:
        """选择预设模板"""
        if preset_key not in self.PRESETS:
            return False

        preset = self.PRESETS[preset_key]
        self.config.project_preset = preset_key
        self.config.grouping_rule = preset['grouping_rule']
        self.config.fs = preset['fs']
        self.config.imu_mapping = preset['imu_mapping']
        self.config.signal_mapping = preset['signal_mapping']
        return True

    def _validate_step1(self) -> bool:
        return self.config.project_preset in self.PRESETS

    # ── Step 2: 数据源类型 ──

    def get_data_source_types(self) -> Dict[str, str]:
        return self.DATA_SOURCE_TYPES

    def select_data_source_type(self, ds_type: str) -> bool:
        if ds_type not in self.DATA_SOURCE_TYPES:
            return False
        self.config.data_source_type = ds_type
        return True

    def _validate_step2(self) -> bool:
        return self.config.data_source_type in self.DATA_SOURCE_TYPES

    # ── Step 3: 物理通道配置 ──

    def set_physical_channel(self, file_path: str = '', com_port: str = '',
                              baudrate: int = 921600) -> None:
        self.config.file_path = file_path
        self.config.com_port = com_port
        self.config.baudrate = baudrate

    def _validate_step3(self) -> bool:
        if self.config.data_source_type == 'can_file':
            return bool(self.config.file_path) and os.path.exists(self.config.file_path)
        elif self.config.data_source_type == 'serial':
            return bool(self.config.com_port)
        return True

    # ── Step 4: IMU通道分组映射 (核心新增) ──

    def get_imu_mapping(self) -> Dict[str, List[str]]:
        return self.config.imu_mapping

    def set_imu_group(self, group: str, imu_list: List[str]) -> bool:
        if group not in ('experimental', 'control'):
            return False
        self.config.imu_mapping[group] = imu_list
        return True

    def add_imu_to_group(self, group: str, imu_name: str) -> bool:
        if group not in self.config.imu_mapping:
            return False
        if imu_name not in self.config.imu_mapping[group]:
            self.config.imu_mapping[group].append(imu_name)
        return True

    def remove_imu_from_group(self, group: str, imu_name: str) -> bool:
        if group in self.config.imu_mapping:
            if imu_name in self.config.imu_mapping[group]:
                self.config.imu_mapping[group].remove(imu_name)
                return True
        return False

    def auto_detect_groups(self, imu_names: List[str]) -> Dict[str, List[str]]:
        """自动检测分组: 奇数=实验组, 偶数=对照组"""
        import re
        experimental = []
        control = []
        for name in imu_names:
            match = re.search(r'IMU(\d+)', name)
            if match:
                num = int(match.group(1))
                if num % 2 == 1:
                    experimental.append(name)
                else:
                    control.append(name)
        return {'experimental': experimental, 'control': control}

    def _validate_step4(self) -> bool:
        exp = self.config.imu_mapping.get('experimental', [])
        ctrl = self.config.imu_mapping.get('control', [])
        return len(exp) > 0 or len(ctrl) > 0

    # ── Step 5: 信号字段映射 ──

    def get_signal_mapping(self) -> Dict[str, str]:
        return self.config.signal_mapping

    def set_signal_mapping(self, mapping: Dict[str, str]) -> None:
        self.config.signal_mapping = mapping

    def auto_detect_signal_mapping(self, csv_columns: List[str]) -> Dict[str, str]:
        """从CSV列名自动检测信号映射"""
        mapping = {}
        for col in csv_columns:
            for pattern, field in [
                ('Ax', 'ax'), ('Ay', 'ay'), ('Az', 'az'),
                ('Gx', 'gx'), ('Gy', 'gy'), ('Gz', 'gz'),
                ('speed', 'speed'), ('wheel', 'wheel'),
            ]:
                if pattern.lower() in col.lower() and field not in mapping.values():
                    mapping[col] = field
                    break
        return mapping

    def _validate_step5(self) -> bool:
        return len(self.config.signal_mapping) >= 3  # 至少 ax/ay/az

    # ── Step 6: 采样参数配置 ──

    def set_sampling_params(self, fs: int = 1000, trigger: str = 'continuous',
                            timeout: int = 30) -> None:
        self.config.fs = fs
        self.config.trigger_condition = trigger
        self.config.timeout_seconds = timeout

    def _validate_step6(self) -> bool:
        return self.config.fs > 0

    # ── Step 7: 连接测试 + 信号验证 ──

    def test_connection(self) -> dict:
        """自动检测信号有效性"""
        results = {
            'status': 'pending',
            'checks': [],
            'errors': [],
            'warnings': [],
        }

        # 检查1: 文件存在性
        if self.config.data_source_type == 'can_file':
            if self.config.file_path and os.path.exists(self.config.file_path):
                results['checks'].append({
                    'name': '文件存在',
                    'status': 'pass',
                    'detail': self.config.file_path,
                })
            else:
                results['errors'].append({
                    'name': '文件存在',
                    'status': 'fail',
                    'detail': f'文件不存在: {self.config.file_path}',
                })

        # 检查2: IMU列完整性
        if self.config.file_path and os.path.exists(self.config.file_path):
            try:
                import pandas as pd
                df = pd.read_csv(self.config.file_path, nrows=5)
                csv_cols = set(df.columns)
                for group, imus in self.config.imu_mapping.items():
                    for imu in imus:
                        # 检查该IMU是否有Ax列
                        ax_col = f'{imu}_Ax_m_s2'
                        if ax_col in csv_cols:
                            results['checks'].append({
                                'name': f'IMU列: {imu}',
                                'status': 'pass',
                            })
                        else:
                            results['warnings'].append({
                                'name': f'IMU列: {imu}',
                                'status': 'warning',
                                'detail': f'缺少 Ax_m_s2 列',
                            })
            except Exception as e:
                results['errors'].append({
                    'name': 'CSV读取',
                    'status': 'fail',
                    'detail': str(e),
                })

        # 检查3: 信号值范围
        # (实际实现时读取前1000行检查)

        # 总体状态
        if results['errors']:
            results['status'] = 'failed'
        elif results['warnings']:
            results['status'] = 'warning'
        else:
            results['status'] = 'passed'

        self.config.test_results = results
        return results

    def _validate_step7(self) -> bool:
        return self.config.test_results.get('status') in ('passed', 'warning')

    # ── 导航 ──

    def next_step(self) -> bool:
        if self.current_step < self.total_steps:
            if self._validate_current_step():
                self.current_step += 1
                return True
        return False

    def previous_step(self) -> bool:
        if self.current_step > 1:
            self.current_step -= 1
            return True
        return False

    def go_to_step(self, step: int) -> bool:
        if 1 <= step <= self.total_steps:
            self.current_step = step
            return True
        return False

    def _validate_current_step(self) -> bool:
        validator = self.step_validators.get(self.current_step)
        return validator() if validator else True

    # ── 导出 ──

    def export_config(self) -> dict:
        """导出完整配置"""
        return {
            'project': self.config.project_preset,
            'data_source_type': self.config.data_source_type,
            'physical_channel': {
                'file_path': self.config.file_path,
                'com_port': self.config.com_port,
                'baudrate': self.config.baudrate,
            },
            'imu_mapping': self.config.imu_mapping,
            'grouping_rule': self.config.grouping_rule,
            'signal_mapping': self.config.signal_mapping,
            'sampling': {
                'fs': self.config.fs,
                'trigger': self.config.trigger_condition,
                'timeout': self.config.timeout_seconds,
            },
            'test_results': self.config.test_results,
        }

    def export_to_ini(self, filepath: str) -> None:
        """导出配置到INI文件"""
        config = self.export_config()
        import configparser
        parser = configparser.ConfigParser()

        parser.add_section('project')
        parser.set('project', 'name', config['project'])

        parser.add_section('data_source')
        parser.set('data_source', 'type', config['data_source_type'])
        parser.set('data_source', 'file_path', config['physical_channel']['file_path'])
        parser.set('data_source', 'com_port', config['physical_channel']['com_port'])
        parser.set('data_source', 'baudrate', str(config['physical_channel']['baudrate']))

        parser.add_section('imu')
        parser.set('imu', 'grouping_rule', config['grouping_rule'])
        parser.set('imu', 'experimental', ','.join(config['imu_mapping'].get('experimental', [])))
        parser.set('imu', 'control', ','.join(config['imu_mapping'].get('control', [])))

        parser.add_section('sampling')
        parser.set('sampling', 'fs', str(config['sampling']['fs']))
        parser.set('sampling', 'trigger', config['sampling']['trigger'])
        parser.set('sampling', 'timeout', str(config['sampling']['timeout']))

        with open(filepath, 'w', encoding='utf-8') as f:
            parser.write(f)

        logger.info(f"配置已导出到: {filepath}")


# ── PySide6 QWizard 页面组件 ──

try:
    from PySide6.QtWidgets import (
        QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QComboBox, QPushButton, QListWidget, QListWidgetItem,
        QSpinBox, QCheckBox, QTextEdit, QProgressBar, QFileDialog,
        QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    )
    from PySide6.QtCore import Qt, Signal
    HAS_QWIDGET = True
except ImportError:
    HAS_QWIDGET = False
    logger.debug("PySide6.QtWidgets 不可用, QWizardPage 组件将跳过加载")


class BaseWizardPage(QWizardPage if HAS_QWIDGET else object):
    """向导页面基类"""

    def __init__(self, wizard: 'DataSourceWizard', title: str, subtitle: str = ''):
        if HAS_QWIDGET:
            super().__init__()
        self.wizard = wizard
        self.setTitle(title)
        if subtitle:
            self.setSubTitle(subtitle)
        self._setup_ui()

    def _setup_ui(self):
        raise NotImplementedError

    def isComplete(self) -> bool:
        if not HAS_QWIDGET:
            return True
        step = self._step_number()
        validator = self.wizard.step_validators.get(step)
        return validator() if validator else True

    def _step_number(self) -> int:
        """子类覆盖以返回步骤编号"""
        return 1


if HAS_QWIDGET:

    class ProjectPresetPage(BaseWizardPage):
        """Step 1: 项目预设选择"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '项目预设选择', '选择评测项目类型以自动加载预设配置')
            self.preset_combo: QComboBox = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel('选择项目类型:'))
            self.preset_combo = QComboBox()
            for preset in self.wizard.get_preset_options():
                self.preset_combo.addItem(
                    f"{preset['name']} - {preset['description']}", preset['key']
                )
            self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
            layout.addWidget(self.preset_combo)
            layout.addStretch()

        def _on_preset_changed(self, index: int):
            key = self.preset_combo.itemData(index)
            self.wizard.select_preset(key)
            self.completeChanged.emit()

        def _step_number(self) -> int:
            return 1


    class DataSourceTypePage(BaseWizardPage):
        """Step 2: 数据源类型选择"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '数据源类型', '选择信号数据来源')
            self.radio_group: QButtonGroup = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            self.radio_group = QButtonGroup(self)
            for key, label in self.wizard.get_data_source_types().items():
                radio = QRadioButton(label)
                radio.setProperty('ds_type', key)
                self.radio_group.addButton(radio)
                layout.addWidget(radio)
                if key == self.wizard.config.data_source_type:
                    radio.setChecked(True)
            self.radio_group.buttonClicked.connect(self._on_type_changed)
            layout.addStretch()

        def _on_type_changed(self, button):
            ds_type = button.property('ds_type')
            self.wizard.select_data_source_type(ds_type)
            self.completeChanged.emit()

        def _step_number(self) -> int:
            return 2


    class PhysicalChannelPage(BaseWizardPage):
        """Step 3: 物理通道配置"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '物理通道配置', '配置文件路径或串口参数')
            self.file_edit: QLineEdit = None
            self.browse_btn: QPushButton = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            if self.wizard.config.data_source_type == 'can_file':
                hl = QHBoxLayout()
                self.file_edit = QLineEdit()
                self.file_edit.setPlaceholderText('选择 CSV 文件...')
                self.file_edit.textChanged.connect(self._on_file_changed)
                hl.addWidget(self.file_edit)
                self.browse_btn = QPushButton('浏览...')
                self.browse_btn.clicked.connect(self._browse_file)
                hl.addWidget(self.browse_btn)
                layout.addLayout(hl)
            layout.addStretch()

        def _browse_file(self):
            path, _ = QFileDialog.getOpenFileName(
                self, '选择CSV文件', '', 'CSV Files (*.csv);;All Files (*)'
            )
            if path:
                self.file_edit.setText(path)

        def _on_file_changed(self, text: str):
            self.wizard.set_physical_channel(file_path=text)
            self.completeChanged.emit()

        def _step_number(self) -> int:
            return 3


    class IMUGroupMappingPage(BaseWizardPage):
        """Step 4: IMU通道分组映射 (核心新增)"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, 'IMU通道分组', '将IMU通道分配到实验组(奇数)和对照组(偶数)')
            self.exp_list: QListWidget = None
            self.ctrl_list: QListWidget = None

        def _setup_ui(self):
            layout = QHBoxLayout(self)

            # 实验组
            exp_group = QGroupBox('实验组 (主动)')
            exp_layout = QVBoxLayout(exp_group)
            self.exp_list = QListWidget()
            for imu in self.wizard.config.imu_mapping.get('experimental', []):
                self.exp_list.addItem(imu)
            exp_layout.addWidget(self.exp_list)
            exp_layout.addWidget(QLabel(
                f'共 {self.exp_list.count()} 个通道'))
            layout.addWidget(exp_group)

            # 对照组
            ctrl_group = QGroupBox('对照组 (被动)')
            ctrl_layout = QVBoxLayout(ctrl_group)
            self.ctrl_list = QListWidget()
            for imu in self.wizard.config.imu_mapping.get('control', []):
                self.ctrl_list.addItem(imu)
            ctrl_layout.addWidget(self.ctrl_list)
            ctrl_layout.addWidget(QLabel(
                f'共 {self.ctrl_list.count()} 个通道'))
            layout.addWidget(ctrl_group)

        def _step_number(self) -> int:
            return 4


    class SignalFieldMappingPage(BaseWizardPage):
        """Step 5: 信号字段映射"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '信号字段映射', '配置CSV列名到物理信号的映射关系')
            self.mapping_text: QTextEdit = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel(
                '格式: CSV列名 → 物理信号 (每行一个)'
            ))
            self.mapping_text = QTextEdit()
            mapping = self.wizard.get_signal_mapping()
            text = '\n'.join(f'{k} → {v}' for k, v in mapping.items())
            self.mapping_text.setPlainText(text)
            self.mapping_text.setPlaceholderText(
                '示例:\nIMU1_Ax_m_s2 → ax\nIMU1_Ay_m_s2 → ay'
            )
            layout.addWidget(self.mapping_text)
            layout.addStretch()

        def _step_number(self) -> int:
            return 5


    class SamplingParamsPage(BaseWizardPage):
        """Step 6: 采样参数配置"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '采样参数', '配置采样率和触发条件')
            self.fs_spin: QSpinBox = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            hl = QHBoxLayout()
            hl.addWidget(QLabel('采样率 (Hz):'))
            self.fs_spin = QSpinBox()
            self.fs_spin.setRange(1, 100000)
            self.fs_spin.setValue(self.wizard.config.fs)
            self.fs_spin.setSingleStep(100)
            self.fs_spin.valueChanged.connect(self._on_fs_changed)
            hl.addWidget(self.fs_spin)
            hl.addStretch()
            layout.addLayout(hl)

            self.continuous_cb = QCheckBox('连续采集')
            self.continuous_cb.setChecked(True)
            layout.addWidget(self.continuous_cb)
            layout.addStretch()

        def _on_fs_changed(self, value: int):
            self.wizard.set_sampling_params(fs=value)
            self.completeChanged.emit()

        def _step_number(self) -> int:
            return 6


    class ConnectionTestPage(BaseWizardPage):
        """Step 7: 连接测试 + 信号验证"""

        def __init__(self, wizard: 'DataSourceWizard'):
            super().__init__(wizard, '连接测试', '验证数据源连接和信号有效性')
            self.result_text: QTextEdit = None
            self.test_btn: QPushButton = None
            self.progress: QProgressBar = None

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            self.test_btn = QPushButton('运行连接测试')
            self.test_btn.clicked.connect(self._run_test)
            layout.addWidget(self.test_btn)

            self.progress = QProgressBar()
            self.progress.setVisible(False)
            layout.addWidget(self.progress)

            self.result_text = QTextEdit()
            self.result_text.setReadOnly(True)
            self.result_text.setPlaceholderText('点击"运行连接测试"开始...')
            layout.addWidget(self.result_text)

        def _run_test(self):
            self.test_btn.setEnabled(False)
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)  # 不确定进度

            try:
                results = self.wizard.test_connection()
                self._display_results(results)
            except Exception as e:
                self.result_text.setPlainText(f'测试失败: {e}')
            finally:
                self.test_btn.setEnabled(True)
                self.progress.setVisible(False)
                self.completeChanged.emit()

        def _display_results(self, results: dict):
            lines = [f'状态: {results["status"].upper()}', '']
            for check in results.get('checks', []):
                icon = '✓' if check['status'] == 'pass' else '✗'
                lines.append(f'{icon} {check["name"]}: {check.get("detail", "")}')
            for warn in results.get('warnings', []):
                lines.append(f'⚠ {warn["name"]}: {warn.get("detail", "")}')
            for err in results.get('errors', []):
                lines.append(f'✗ {err["name"]}: {err.get("detail", "")}')
            self.result_text.setPlainText('\n'.join(lines))

        def _step_number(self) -> int:
            return 7
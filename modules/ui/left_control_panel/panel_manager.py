from PySide6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame
from PySide6.QtCore import Signal, Qt

# 
def _get_base_control_panel():
    """BaseControlPanel"""
    try:
        from .base_control_panel import BaseControlPanel
        return BaseControlPanel
    except ImportError:
        try:
            import importlib.util
            import sys
            from pathlib import Path
            
            current_dir = Path(__file__).parent
            base_file = current_dir / "base_control_panel.py"
            
            if base_file.exists():
                spec = importlib.util.spec_from_file_location(
                    "base_control_panel", 
                    str(base_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'BaseControlPanel'):
                        return module.BaseControlPanel
                    else:
                        raise ImportError("base_control_panelBaseControlPanel")
                else:
                    raise ImportError("base_control_panel")
            else:
                raise ImportError(f"base_control_panel.py: {base_file}")
                
        except Exception as e:
            print(f"BaseControlPanel: {e}")
            return None


def _import_module_class(module_rel_path, class_name):
    try:
        import importlib
        pkg = __package__ if __package__ else None
        if pkg:
            mod = importlib.import_module(f".{module_rel_path}", pkg)
        else:
            raise ImportError("No package context")
        return getattr(mod, class_name)
    except Exception:
        try:
            import importlib.util
            from pathlib import Path
            
            current_dir = Path(__file__).parent
            module_file = current_dir / f"{module_rel_path}.py"
            
            if module_file.exists():
                spec = importlib.util.spec_from_file_location(
                    module_rel_path,
                    str(module_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, class_name):
                        return getattr(module, class_name)
            
            return None
        except Exception as e:
            print(f"Import fallback failed for {module_rel_path}.{class_name}: {e}")
            return None

class LeftPanelManager(QWidget):
    """"""
    
    #  - 
    data_source_changed = Signal(str, dict)
    analysis_toggled = Signal(bool, str)
    load_file_requested = Signal(str)
    record_toggled = Signal(bool)
    export_data_requested = Signal()
    source_added = Signal(int, str, dict)
    source_removed = Signal(int)
    active_source_changed = Signal(int)
    data_sources_selected = Signal(list)
    advanced_analysis_started = Signal()
    advanced_analysis_stopped = Signal()
    model_load_requested = Signal()
    model_unload_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 
        self.main_window = parent
        
        # UI
        self.scroll_area = None
        self.content_widget = None
        self.layout = None
        self.main_layout = None
        self.panels = {}
        
        # 
        self._setup_compatibility_interfaces()
        
        # UI
        self._init_ui()
    
    def _init_ui(self):
        """UI"""
        try:
            self.setObjectName("leftPanelContainer")
            # 
            self.setMinimumWidth(300)
            self.setMaximumWidth(400)
            
            # 
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
            
            # 
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)     # 
            self.scroll_area.setFrameShape(QFrame.NoFrame)  # 
            self.scroll_area.setStyleSheet("background-color: transparent;")
            
            # 
            self.content_widget = QWidget()
            self.content_layout = QVBoxLayout(self.content_widget)
            self.content_layout.setContentsMargins(5, 5, 5, 5)
            self.content_layout.setSpacing(10)
            self.content_layout.setAlignment(Qt.AlignTop)  # 
            
            # widget
            self.scroll_area.setWidget(self.content_widget)
            
            # 
            self.main_layout.addWidget(self.scroll_area)
            
            # self.layout
            self.layout = self.content_layout
            
            # 
            if self.layout is None:
                print(" ")
                self.layout = QVBoxLayout(self)
                self.layout.setContentsMargins(5, 5, 5, 5)
                self.layout.setSpacing(10)
            
            # 
            self._create_default_panels()
            
        except Exception as e:
            print(f"UI: {e}")
            # 
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            # self.layout
            self.layout = self.main_layout
    
    def _create_default_panels(self):
        """"""
        try:
            # 
            self._create_integrated_control_panel()
            
            # 
            self._register_existing_modules_to_integrated_panel()
            
        except Exception as e:
            print(f": {e}")
            # 
            try:
                self._create_startup_guide_panel()
                self._create_data_source_panel()
                self._create_simple_status_panel()
            except Exception as e2:
                print(f": {e2}")
    
    def _create_integrated_control_panel(self):
        try:
            IntegratedControlPanel = _import_module_class("integrated_control_panel", "IntegratedControlPanel")
            if IntegratedControlPanel is None:
                raise ImportError("无法导入IntegratedControlPanel")
            
            if self.layout is None:
                print("布局未初始化，无法创建集成控制面板")
                return
            
            self.integrated_panel = IntegratedControlPanel(self)
            self.integrated_panel.setObjectName("integrated_control_panel")
            
            self.integrated_panel.action_triggered.connect(self._handle_integrated_action)
            self.integrated_panel.module_status_changed.connect(self._handle_module_status_change)
            
            self.register_panel(self.integrated_panel)
            
            print("集成控制面板创建成功")
            
        except Exception as e:
            print(f"创建集成控制面板失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_integrated_action(self, action_type, action_data):
        """"""
        print(f" : {action_type}")
        # 
        if action_type == "add_data_source":
            # 
            pass
        elif action_type == "start_sync":
            # 
            pass
        elif action_type == "start_parsing":
            # 
            pass
        elif action_type == "start_analysis":
            # 
            pass
    
    
    def _handle_module_status_change(self, module_id, status):
        """"""
        print(f" : {module_id} - {status}")
    
    def _register_existing_modules_to_integrated_panel(self):
        """"""
        try:
            if not hasattr(self, 'integrated_panel') or self.integrated_panel is None:
                print(" ")
                return
            
            # 
            print(" ...")
            
            # 
            try:
                from .startup_sequence_guide import StartupSequenceGuide
                startup_guide = StartupSequenceGuide(self)
                startup_guide.setObjectName("startup_guide_module")
                self.integrated_panel.register_module('startup_guide', startup_guide)
                print(" ")
            except Exception as e:
                print(f" : {e}")
            
            # 
            try:
                from .data_source_control import DataSourceControlPanel
                data_source_panel = DataSourceControlPanel(self)
                data_source_panel.setObjectName("data_source_module")
                self.integrated_panel.register_module('data_source', data_source_panel)
                print(" ")
            except Exception as e:
                print(f" : {e}")
            
            # ...
            
            print(" ")
            
        except Exception as e:
            print(f" : {e}")
            import traceback
            traceback.print_exc()
    
    def _create_simple_status_panel(self):
        """"""
        try:
            from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QFont
            
            # 
            if self.layout is None:
                print(" ")
                return
            
            # 
            status_panel = QGroupBox(" ")
            status_layout = QVBoxLayout(status_panel)
            
            # 
            self.status_label = QLabel("🟢 ")
            self.status_label.setFont(QFont("Microsoft YaHei", 10))
            status_layout.addWidget(self.status_label)
            
            self.modules_status_label = QLabel("  ")
            self.modules_status_label.setFont(QFont("Microsoft YaHei", 9))
            status_layout.addWidget(self.modules_status_label)
            
            # 
            status_panel.panel_name = ""
            status_panel.action_triggered = None  # 
            
            # 
            self.register_panel(status_panel)
            
            print(" ")
            
        except Exception as e:
            print(f" : {e}")
    
    def _create_startup_guide_panel(self):
        try:
            StartupSequenceGuide = _import_module_class("startup_sequence_guide", "StartupSequenceGuide")
            if StartupSequenceGuide is None:
                raise ImportError("无法导入StartupSequenceGuide")
            
            if self.layout is None:
                print("布局未初始化，无法创建启动引导面板")
                return
            
            startup_guide = StartupSequenceGuide(self)
            startup_guide.setObjectName("startup_guide_panel")
            
            startup_guide.guide_completed.connect(self._on_guide_completed)
            
            self.register_panel(startup_guide)
            
            print("启动引导面板创建成功")
            
        except Exception as e:
            print(f"创建启动引导面板失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_guide_completed(self):
        """"""
        print(" ")
        # 
    
    
    def _create_data_source_panel(self):
        try:
            DataSourceControlPanel = _import_module_class("data_source_control", "DataSourceControlPanel")
            if DataSourceControlPanel is None:
                raise ImportError("无法导入DataSourceControlPanel")
            
            if self.layout is None:
                print("布局未初始化，无法创建数据源面板")
                return
            
            data_source_panel = DataSourceControlPanel(self)
            
            self.register_panel(data_source_panel)
            
            print("数据源控制面板创建成功")
            
        except Exception as e:
            print(f"创建数据源控制面板失败: {e}")
            import traceback
            traceback.print_exc()
        
    def register_panel(self, panel):
        """"""
        # 
        try:
            # 
            required_attrs = ['panel_name', 'action_triggered']
            missing_attrs = [attr for attr in required_attrs if not hasattr(panel, attr)]
            
            if missing_attrs:
                print(f": : {missing_attrs}")
                return
            
            # BaseControlPanel
            BaseControlPanel = _get_base_control_panel()
            if BaseControlPanel is not None:
                # BaseControlPanel
                if not isinstance(panel, BaseControlPanel):
                    # 
                    panel_class_name = panel.__class__.__name__
                    panel_module = getattr(panel.__class__, '__module__', '')
                    
                    # 
                    if (hasattr(panel, '__module__') and 
                        ('left_control_panel' in str(panel.__module__) or 
                         'panel_' in str(panel.__module__))):
                        # 
                        pass
                    elif (hasattr(panel.__class__, '__bases__') and 
                          any('BaseControlPanel' in str(base) for base in panel.__class__.__bases__)):
                        # BaseControlPanel
                        pass
                    elif (hasattr(panel.__class__, '__mro__') and 
                          any('BaseControlPanel' in str(cls) for cls in panel.__class__.__mro__)):
                        # BaseControlPanel
                        pass
                    else:
                        # 
                        if hasattr(panel, 'panel_name') and hasattr(panel, 'action_triggered'):
                            # 
                            pass
                        else:
                            print(f":  {panel.panel_name} ")
            else:
                # BaseControlPanel
                pass
        
        except Exception as e:
            print(f": {e}")
        
        self.panels[panel.panel_name] = panel
        
        # UI
        if self.layout is None:
            self._init_ui()
        
        # layoutNone
        if self.layout is None:
            print(f"  {panel.panel_name}")
            return
        
        # 
        self.layout.addWidget(panel)
        # 
        panel.setVisible(True)
        panel.show()
        print(f"  {panel.panel_name} ")
        
        # action_triggered
        if hasattr(panel, 'action_triggered') and panel.action_triggered is not None:
            panel.action_triggered.connect(self._handle_panel_action)
        else:
            print(f":  {panel.panel_name} action_triggered")
        
        # 
        # if isinstance(panel, UnifiedDataSourceManager):
        #     self.panels['unified_data_source'] = panel
        #     self.layout.addWidget(panel)
        #     logger.info("")
    
    def _get_module_id_from_panel_name(self, panel_name):
        """ID"""
        name_mapping = {
            '': 'startup_guide',
            '': 'data_source',
            '': 'sync_config',
            '': 'parsing_control',
            '': 'analysis',
            '': 'system_control'
        }
        
        # ID
        for name, module_id in name_mapping.items():
            if name in panel_name:
                return module_id
        
        return None
    
    def _add_panel_in_order(self, panel):
        """"""
        # 
        panel_order = [
            "",
            "", 
            "",
            "",
            # "",  # 
            ""
        ]
        
        try:
            # 
            panel_index = panel_order.index(panel.panel_name)
            
            # 
            if len(self.panels) == 1:
                self.layout.addWidget(panel)
                print(f"  {panel.panel_name}  {panel_index}")
                return
            
            # 
            insert_position = 0
            for i, expected_panel_name in enumerate(panel_order):
                if expected_panel_name in self.panels:
                    insert_position = i + 1
                    if expected_panel_name == panel.panel_name:
                        break
            
            # 
            for panel_name in list(self.panels.keys()):
                existing_panel = self.panels[panel_name]
                if existing_panel.parent() == self.content_widget:
                    self.layout.removeWidget(existing_panel)
            
            # 
            for expected_panel_name in panel_order:
                if expected_panel_name in self.panels:
                    self.layout.addWidget(self.panels[expected_panel_name])
                    print(f" : {expected_panel_name}")
            
            print(f"  {panel.panel_name} ")
            
        except ValueError as e:
            print(f" : {panel.panel_name}, ")
            self.layout.addWidget(panel)
        except Exception as e:
            print(f" : {e}, ")
            self.layout.addWidget(panel)
        
    def _handle_panel_action(self, action_type, payload):
        """"""
        # 
        print(f"[] {action_type} - {payload}")
        
        # 
        self._forward_signal(action_type, payload)
        
        # 
        if self.main_window and hasattr(self.main_window, 'handle_control_action'):
            self.main_window.handle_control_action(action_type, payload)
        else:
            print(f": handle_control_action")
            
    def get_panel(self, panel_name: str):
        """"""
        return self.panels.get(panel_name)
        
    def update_panel_status(self, panel_name: str, status: str):
        """"""
        panel = self.panels.get(panel_name)
        if panel and hasattr(panel, 'update_status'):
            panel.update_status(status)
            
    def update_all_panels(self, update_func: str, *args, **kwargs):
        """"""
        for panel in self.panels.values():
            if hasattr(panel, update_func):
                func = getattr(panel, update_func)
                if callable(func):
                    try:
                        func(*args, **kwargs)
                    except Exception as e:
                        print(f" {panel.panel_name} : {e}")
    
    def _setup_compatibility_interfaces(self):
        """"""
        # 
        self._signal_mapping = {
            # 
            "DATA_SOURCE_CHANGED": self.data_source_changed,
            "LOAD_DATA": self.load_file_requested,
            "CLEAR_DATA": self.export_data_requested,
            "ADD_SOURCE": self.source_added,
            "REMOVE_SOURCE": self.source_removed,
            "SET_ACTIVE_SOURCE": self.active_source_changed,
            
            # 
            "BASIC_ANALYSIS_START": self.analysis_toggled,
            "BASIC_ANALYSIS_PAUSE": self.analysis_toggled,
            "BASIC_ANALYSIS_STOP": self.analysis_toggled,
            "ADVANCED_ANALYSIS_START": self.advanced_analysis_started,
            "ADVANCED_ANALYSIS_PAUSE": self.advanced_analysis_stopped,
            "ADVANCED_ANALYSIS_STOP": self.advanced_analysis_stopped,
            "MODEL_LOAD_REQUEST": self.model_load_requested,
            "MODEL_UNLOAD_REQUEST": self.model_unload_requested,
            "TRAINING_START": self.analysis_toggled,
            "TRAINING_STOP": self.analysis_toggled,
            
            # 
            "START_PARSING": self.parsing_toggled,
            "PAUSE_PARSING": self.parsing_toggled,
            "STOP_PARSING": self.parsing_toggled,
            "PARSING_CONFIG_CHANGED": self.parsing_config_changed,
            
            # 
            "ONE_CLICK_SYNC": self.analysis_toggled,
            "START_SYNC": self.analysis_toggled,
            "STOP_SYNC": self.analysis_toggled,
            "PAUSE_SYNC": self.analysis_toggled,
            "SYNC_CONFIG_CHANGED": self.analysis_toggled,
            
            # 
            "THEME_CHANGED": self.analysis_toggled,
            "LOG_LEVEL_CHANGED": self.analysis_toggled,
            "AUTO_SAVE_CHANGED": self.analysis_toggled,
            "AUTO_OPTIMIZATION_CHANGED": self.analysis_toggled,
            "SAVE_CONFIG": self.analysis_toggled,
            "LOAD_CONFIG": self.analysis_toggled,
            "EXPORT_DATA": self.export_data_requested,
            "SYSTEM_OPTIMIZATION": self.analysis_toggled,
            "CLEAR_CACHE": self.analysis_toggled,
            "RESTART_SYSTEM": self.analysis_toggled,
            
            # 
            "TOGGLE_RECORD": self.record_toggled,
            "RESET_SYSTEM": self.analysis_toggled,
        }
    
    def _forward_signal(self, action_type, payload):
        """"""
        try:
            if action_type in self._signal_mapping:
                signal = self._signal_mapping[action_type]
                
                # payload
                if action_type == "DATA_SOURCE_CHANGED":
                    signal.emit(payload.get("type", ""), payload)
                elif action_type in ["BASIC_ANALYSIS_START", "BASIC_ANALYSIS_PAUSE", "BASIC_ANALYSIS_STOP"]:
                    # 
                    enabled = action_type == "BASIC_ANALYSIS_START"
                    signal.emit(enabled, "basic")
                elif action_type in ["ADVANCED_ANALYSIS_START", "ADVANCED_ANALYSIS_PAUSE", "ADVANCED_ANALYSIS_STOP"]:
                    # 
                    if action_type == "ADVANCED_ANALYSIS_START":
                        self.advanced_analysis_started.emit()
                    else:
                        self.advanced_analysis_stopped.emit()
                elif action_type == "MODEL_LOAD_REQUEST":
                    self.model_load_requested.emit()
                elif action_type == "MODEL_UNLOAD_REQUEST":
                    self.model_unload_requested.emit()
                elif action_type == "LOAD_DATA":
                    # payload
                    imu_file = payload.get("imu_file", "")
                    cnap_file = payload.get("cnap_file", "")
                    file_path = imu_file if imu_file else cnap_file
                    signal.emit(file_path)
                elif action_type == "ADD_SOURCE":
                    # ID
                    source_id = len(self.panels) + 1
                    source_type = payload.get("type", "unknown")
                    signal.emit(source_id, source_type, payload)
                elif action_type == "REMOVE_SOURCE":
                    signal.emit(payload.get("id", 0))
                elif action_type == "SET_ACTIVE_SOURCE":
                    signal.emit(payload.get("id", 0))
                elif action_type == "EXPORT_DATA":
                    signal.emit()
                elif action_type == "TOGGLE_RECORD":
                    # 
                    enabled = payload.get("enabled", True)
                    signal.emit(enabled)
                else:
                    # 
                    try:
                        signal.emit()
                    except Exception:
                        # 
                        print(f"[]  {action_type} ")
                    
                print(f"[] : {action_type} -> {signal}")
                
        except Exception as e:
            print(f"[] : {action_type} - {e}")
    
    def _handle_panel_action(self, action_type, payload):
        """"""
        # 
        print(f"[] {action_type} - {payload}")
        
        # 
        self._forward_signal(action_type, payload)
        
        # 
        if self.main_window and hasattr(self.main_window, 'handle_control_action'):
            self.main_window.handle_control_action(action_type, payload)
        else:
            print(f": handle_control_action")
    
    def update_translations(self, lang):
        """"""
        self.update_all_panels("update_translations", lang)

    def export_data_requested(self):
        """"""
        print("[] ")
        # 
        
    def parsing_toggled(self, enabled=True):
        """"""
        print(f"[] : {enabled}")
        # 
        
    def parsing_config_changed(self, config):
        """"""
        print(f"[] : {config}")
        # 
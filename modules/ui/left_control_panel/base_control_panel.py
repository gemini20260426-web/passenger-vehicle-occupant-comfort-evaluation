from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox

class BaseControlPanel(QWidget):
    """"""
    action_triggered = Signal(str, dict)  # , 
    
    def __init__(self, panel_name: str, parent=None):
        super().__init__(parent)
        self.panel_name = panel_name
        
        # UI
        self.layout = None
        self.group_box = None
        self.inner_layout = None
        
        # UI
        
    def _init_ui(self):
        if hasattr(self, '_ui_initialized') and self._ui_initialized:
            return
        self._ui_initialized = True
        
        try:
            self.layout = QVBoxLayout(self)
            self.group_box = QGroupBox(self.panel_name)
            self.inner_layout = QVBoxLayout()
            
            self.init_ui()
            self.group_box.setLayout(self.inner_layout)
            self.layout.addWidget(self.group_box)
            self.connect_signals()
            
        except Exception as e:
            print(f" {self.panel_name} UI: {e}")
            self.layout = QVBoxLayout(self)
            placeholder = QGroupBox(f" {self.panel_name} ")
            self.layout.addWidget(placeholder)
            self.inner_layout = QVBoxLayout()
        
    def init_ui(self):
        """UI"""
        raise NotImplementedError
        
    def connect_signals(self):
        """"""
        raise NotImplementedError
        
    def update_status(self, message: str):
        """"""
        pass
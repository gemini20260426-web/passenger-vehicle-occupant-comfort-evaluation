#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QCheckBox
UI
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton
from PySide6.QtCore import Qt, Signal
from typing import List, Dict, Any

class MultiSelectComboBox(QWidget):
    """QCheckBox
    
    
    - QCheckBox
    - 
    - 
    - UI
    """
    
    # 
    selection_changed = Signal(list)  # 
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 
        self.selected_items = set()  # 
        self.item_list = []  # 
        self.checkboxes = {}  # 
        
        # UI
        self._init_ui()
        
    def _init_ui(self):
        """UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 
        self.display_label = QLabel("...")
        self.display_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px 10px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.display_label)
        
        # 
        self.checkbox_container = QWidget()
        self.checkbox_container.setVisible(False)
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        self.checkbox_layout.setContentsMargins(8, 8, 8, 8)
        self.checkbox_layout.setSpacing(4)
        
        # 
        layout.addWidget(self.checkbox_container)
        
        # 
        self.display_label.mousePressEvent = self._on_label_clicked
        
    def _on_label_clicked(self, event):
        """"""
        if event.button() == Qt.LeftButton:
            # 
            is_visible = self.checkbox_container.isVisible()
            self.checkbox_container.setVisible(not is_visible)
            
            # 
            if not is_visible:
                self.display_label.setStyleSheet("""
                    QLabel {
                        background-color: white;
                        border: 2px solid #3498db;
                        border-radius: 4px;
                        padding: 6px 10px;
                        color: #2c3e50;
                        font-size: 12px;
                    }
                """)
            else:
                self.display_label.setStyleSheet("""
                    QLabel {
                        background-color: white;
                        border: 1px solid #bdc3c7;
                        border-radius: 4px;
                        padding: 6px 10px;
                        color: #2c3e50;
                        font-size: 12px;
                    }
                """)
        
    def add_item(self, text: str, user_data: Any = None):
        """"""
        # 
        checkbox = QCheckBox(text)
        if user_data is not None:
            checkbox.setProperty("user_data", user_data)
            
        # 
        checkbox.toggled.connect(self._on_checkbox_toggled)
        
        # 
        self.checkbox_layout.addWidget(checkbox)
        self.checkboxes[text] = checkbox
        self.item_list.append(text)
        
    def add_items(self, items: List[str]):
        """"""
        for item in items:
            self.add_item(item)
            
    def get_selected_items(self) -> List[str]:
        """"""
        selected = []
        for text, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(text)
        return selected
            
    def set_selected_items(self, items: List[str]):
        """"""
        self.selected_items = set(items)
        
        # 
        for text, checkbox in self.checkboxes.items():
            checkbox.setChecked(text in items)
                
        self._update_display_text()
                    
    def clear_selection(self):
        """"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
        self.selected_items.clear()
        self._update_display_text()
            
    def _on_checkbox_toggled(self):
        """"""
        selected_items = self.get_selected_items()
        self.selected_items = set(selected_items)
        self._update_display_text()
        self.selection_changed.emit(selected_items)
        
    def _update_display_text(self):
        """"""
        selected_count = len(self.selected_items)
        if selected_count == 0:
            display_text = "..."
        elif selected_count == 1:
            display_text = list(self.selected_items)[0]
        else:
            display_text = f" {selected_count} "
            
        # 
        self.display_label.setText(display_text)
        
    def get_selection_summary(self) -> Dict[str, Any]:
        """"""
        return {
            'selected_items': self.get_selected_items(),
            'selected_count': len(self.selected_items),
            'total_items': len(self.item_list)
        }
        
    def hideEvent(self, event):
        """ - """
        self.checkbox_container.setVisible(False)
        self.display_label.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px 10px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        super().hideEvent(event)



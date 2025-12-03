# -*- coding: utf-8 -*-
"""
集装箱配载软件 (Container Loading Software) - 现代UI版本
使用 PyQt6 + OpenGL 实现可拖动旋转的3D视图
"""

import sys
import json
import math
import numpy as np
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Tuple
import copy

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFileDialog, QMessageBox, QSplitter, QFrame, QSpinBox,
    QDoubleSpinBox, QStyle, QStyleFactory, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

from OpenGL.GL import *
from OpenGL.GLU import *
from PyQt6.QtOpenGLWidgets import QOpenGLWidget


@dataclass
class Cargo:
    """货物类"""
    name: str
    length: float  # 长度 (cm)
    width: float   # 宽度 (cm)
    height: float  # 高度 (cm)
    weight: float  # 重量 (kg)
    quantity: int  # 数量
    stackable: bool = True  # 是否可堆叠
    max_stack: int = 3  # 最大堆叠层数
    color: Tuple[float, float, float] = (0.3, 0.7, 0.3)  # RGB颜色
    
    @property
    def volume(self) -> float:
        return self.length * self.width * self.height
    
    @property
    def total_volume(self) -> float:
        return self.volume * self.quantity
    
    @property
    def total_weight(self) -> float:
        return self.weight * self.quantity


@dataclass
class Container:
    """集装箱类"""
    name: str
    length: float
    width: float
    height: float
    max_weight: float
    
    @property
    def volume(self) -> float:
        return self.length * self.width * self.height
    
    @property
    def volume_cbm(self) -> float:
        return self.volume / 1000000


@dataclass
class PlacedCargo:
    """已放置的货物"""
    cargo: Cargo
    x: float
    y: float
    z: float
    rotated: bool = False
    
    @property
    def actual_length(self) -> float:
        return self.cargo.width if self.rotated else self.cargo.length
    
    @property
    def actual_width(self) -> float:
        return self.cargo.length if self.rotated else self.cargo.width


# 标准集装箱
STANDARD_CONTAINERS = {
    "20英尺标准箱 (20' GP)": Container("20英尺标准箱", 589, 234, 238, 21770),
    "40英尺标准箱 (40' GP)": Container("40英尺标准箱", 1203, 234, 238, 26680),
    "40英尺高箱 (40' HC)": Container("40英尺高箱", 1203, 234, 269, 26460),
    "45英尺高箱 (45' HC)": Container("45英尺高箱", 1351, 234, 269, 25600),
}

# 预设颜色 (RGB 0-1)
CARGO_COLORS = [
    (0.30, 0.69, 0.31),  # 绿色
    (0.13, 0.59, 0.95),  # 蓝色
    (1.00, 0.60, 0.00),  # 橙色
    (0.91, 0.12, 0.39),  # 粉红
    (0.61, 0.15, 0.69),  # 紫色
    (0.00, 0.74, 0.83),  # 青色
    (1.00, 0.92, 0.23),  # 黄色
    (0.47, 0.33, 0.28),  # 棕色
    (0.38, 0.49, 0.55),  # 灰蓝
    (0.96, 0.26, 0.21),  # 红色
    (0.55, 0.76, 0.29),  # 浅绿
    (0.01, 0.66, 0.96),  # 浅蓝
    (0.80, 0.86, 0.22),  # 黄绿
    (0.40, 0.23, 0.72),  # 深紫
    (0.00, 0.59, 0.53),  # 深青
]


class LoadingAlgorithm:
    """装载算法类"""
    
    def __init__(self, container: Container):
        self.container = container
        self.placed_cargos: List[PlacedCargo] = []
    
    def can_place(self, cargo: Cargo, x: float, y: float, z: float, rotated: bool) -> bool:
        length = cargo.width if rotated else cargo.length
        width = cargo.length if rotated else cargo.width
        height = cargo.height
        
        if x + length > self.container.length + 0.01:
            return False
        if y + width > self.container.width + 0.01:
            return False
        if z + height > self.container.height + 0.01:
            return False
        
        for placed in self.placed_cargos:
            pl = placed.actual_length
            pw = placed.actual_width
            ph = placed.cargo.height
            
            if (x < placed.x + pl and x + length > placed.x and
                y < placed.y + pw and y + width > placed.y and
                z < placed.z + ph and z + height > placed.z):
                return False
        
        if z > 0.01:
            support_area = 0
            required_support = length * width * 0.7
            
            for placed in self.placed_cargos:
                if abs(placed.z + placed.cargo.height - z) < 0.01:
                    pl = placed.actual_length
                    pw = placed.actual_width
                    
                    overlap_x = max(0, min(x + length, placed.x + pl) - max(x, placed.x))
                    overlap_y = max(0, min(y + width, placed.y + pw) - max(y, placed.y))
                    support_area += overlap_x * overlap_y
            
            if support_area < required_support:
                return False
        
        return True
    
    def find_position(self, cargo: Cargo) -> Optional[Tuple[float, float, float, bool]]:
        best_position = None
        best_score = float('inf')
        
        positions = [(0, 0, 0)]
        
        for placed in self.placed_cargos:
            pl = placed.actual_length
            pw = placed.actual_width
            ph = placed.cargo.height
            
            positions.append((placed.x + pl, placed.y, placed.z))
            positions.append((placed.x, placed.y + pw, placed.z))
            if placed.cargo.stackable:
                positions.append((placed.x, placed.y, placed.z + ph))
        
        for x, y, z in positions:
            for rotated in [False, True]:
                if self.can_place(cargo, x, y, z, rotated):
                    score = x + y * 2 + z * 3
                    if score < best_score:
                        best_score = score
                        best_position = (x, y, z, rotated)
        
        return best_position
    
    def place_cargo(self, cargo: Cargo) -> bool:
        position = self.find_position(cargo)
        if position:
            x, y, z, rotated = position
            placed = PlacedCargo(cargo, x, y, z, rotated)
            self.placed_cargos.append(placed)
            return True
        return False
    
    def load_all(self, cargos: List[Cargo]) -> Tuple[List[PlacedCargo], List[Cargo]]:
        sorted_cargos = []
        for cargo in cargos:
            for _ in range(cargo.quantity):
                single_cargo = copy.copy(cargo)
                single_cargo.quantity = 1
                sorted_cargos.append(single_cargo)
        
        sorted_cargos.sort(key=lambda c: c.volume, reverse=True)
        
        loaded = []
        not_loaded = []
        
        for cargo in sorted_cargos:
            if self.place_cargo(cargo):
                loaded.append(self.placed_cargos[-1])
            else:
                not_loaded.append(cargo)
        
        return loaded, not_loaded
    
    def get_statistics(self) -> dict:
        total_cargo_volume = sum(p.cargo.volume for p in self.placed_cargos)
        total_cargo_weight = sum(p.cargo.weight for p in self.placed_cargos)
        
        return {
            "loaded_count": len(self.placed_cargos),
            "total_volume": total_cargo_volume,
            "volume_utilization": (total_cargo_volume / self.container.volume) * 100,
            "total_weight": total_cargo_weight,
            "weight_utilization": (total_cargo_weight / self.container.max_weight) * 100,
        }


class Container3DView(QOpenGLWidget):
    """OpenGL 3D视图组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.container: Optional[Container] = None
        self.placed_cargos: List[PlacedCargo] = []
        
        # 视角控制
        self.rotation_x = 25
        self.rotation_y = 45
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        # 鼠标控制
        self.last_mouse_pos = None
        self.mouse_button = None
        
        self.setMinimumSize(600, 400)
    
    def initializeGL(self):
        """初始化OpenGL"""
        glClearColor(0.15, 0.15, 0.18, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        # 光源设置
        glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    def resizeGL(self, w, h):
        """调整视口"""
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / h if h > 0 else 1
        gluPerspective(45, aspect, 0.1, 10000)
        glMatrixMode(GL_MODELVIEW)
    
    def paintGL(self):
        """渲染场景"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        if not self.container:
            return
        
        # 计算观察距离
        max_dim = max(self.container.length, self.container.width, self.container.height)
        distance = max_dim * 2.5 / self.zoom
        
        # 设置相机
        glTranslatef(self.pan_x, self.pan_y, -distance)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # 将原点移到集装箱中心
        glTranslatef(-self.container.length/2, -self.container.height/2, -self.container.width/2)
        
        # 绘制地面网格
        self.draw_grid()
        
        # 绘制集装箱
        self.draw_container_wireframe()
        
        # 绘制已放置的货物
        for placed in self.placed_cargos:
            self.draw_cargo(placed)
        
        # 绘制坐标轴
        self.draw_axes()
    
    def draw_grid(self):
        """绘制地面网格"""
        glDisable(GL_LIGHTING)
        glColor4f(0.3, 0.3, 0.35, 0.5)
        glLineWidth(1)
        
        grid_size = max(self.container.length, self.container.width) * 1.5
        step = 50  # 50cm 网格
        
        glBegin(GL_LINES)
        x = -grid_size / 4
        while x <= self.container.length + grid_size / 4:
            glVertex3f(x, 0, -grid_size / 4)
            glVertex3f(x, 0, self.container.width + grid_size / 4)
            x += step
        
        z = -grid_size / 4
        while z <= self.container.width + grid_size / 4:
            glVertex3f(-grid_size / 4, 0, z)
            glVertex3f(self.container.length + grid_size / 4, 0, z)
            z += step
        glEnd()
        
        glEnable(GL_LIGHTING)
    
    def draw_container_wireframe(self):
        """绘制集装箱线框"""
        l, w, h = self.container.length, self.container.width, self.container.height
        
        # 绘制半透明底面
        glDisable(GL_LIGHTING)
        glColor4f(0.5, 0.5, 0.55, 0.3)
        glBegin(GL_QUADS)
        glVertex3f(0, 0, 0)
        glVertex3f(l, 0, 0)
        glVertex3f(l, 0, w)
        glVertex3f(0, 0, w)
        glEnd()
        
        # 绘制半透明背面
        glColor4f(0.4, 0.4, 0.45, 0.2)
        glBegin(GL_QUADS)
        # 后面
        glVertex3f(0, 0, w)
        glVertex3f(l, 0, w)
        glVertex3f(l, h, w)
        glVertex3f(0, h, w)
        # 左面
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, w)
        glVertex3f(0, h, w)
        glVertex3f(0, h, 0)
        glEnd()
        
        # 绘制边框
        glColor4f(0.7, 0.7, 0.75, 1.0)
        glLineWidth(2)
        
        glBegin(GL_LINE_LOOP)
        glVertex3f(0, 0, 0)
        glVertex3f(l, 0, 0)
        glVertex3f(l, 0, w)
        glVertex3f(0, 0, w)
        glEnd()
        
        glBegin(GL_LINE_LOOP)
        glVertex3f(0, h, 0)
        glVertex3f(l, h, 0)
        glVertex3f(l, h, w)
        glVertex3f(0, h, w)
        glEnd()
        
        glBegin(GL_LINES)
        for x, z in [(0, 0), (l, 0), (l, w), (0, w)]:
            glVertex3f(x, 0, z)
            glVertex3f(x, h, z)
        glEnd()
        
        glEnable(GL_LIGHTING)
    
    def draw_cargo(self, placed: PlacedCargo):
        """绘制货物"""
        x, y, z = placed.x, placed.z, placed.y
        l = placed.actual_length
        h = placed.cargo.height
        w = placed.actual_width
        
        r, g, b = placed.cargo.color
        
        # 定义顶点
        vertices = [
            (x, y, z), (x+l, y, z), (x+l, y, z+w), (x, y, z+w),
            (x, y+h, z), (x+l, y+h, z), (x+l, y+h, z+w), (x, y+h, z+w)
        ]
        
        glColor3f(r, g, b)
        
        # 绘制面
        glBegin(GL_QUADS)
        # 底面
        glNormal3f(0, -1, 0)
        glVertex3f(*vertices[0]); glVertex3f(*vertices[1]); glVertex3f(*vertices[2]); glVertex3f(*vertices[3])
        # 顶面
        glNormal3f(0, 1, 0)
        glVertex3f(*vertices[4]); glVertex3f(*vertices[7]); glVertex3f(*vertices[6]); glVertex3f(*vertices[5])
        # 前面
        glNormal3f(0, 0, -1)
        glVertex3f(*vertices[0]); glVertex3f(*vertices[4]); glVertex3f(*vertices[5]); glVertex3f(*vertices[1])
        # 后面
        glNormal3f(0, 0, 1)
        glVertex3f(*vertices[2]); glVertex3f(*vertices[6]); glVertex3f(*vertices[7]); glVertex3f(*vertices[3])
        # 左面
        glNormal3f(-1, 0, 0)
        glVertex3f(*vertices[0]); glVertex3f(*vertices[3]); glVertex3f(*vertices[7]); glVertex3f(*vertices[4])
        # 右面
        glNormal3f(1, 0, 0)
        glVertex3f(*vertices[1]); glVertex3f(*vertices[5]); glVertex3f(*vertices[6]); glVertex3f(*vertices[2])
        glEnd()
        
        # 绘制边框
        glDisable(GL_LIGHTING)
        glColor3f(0.1, 0.1, 0.1)
        glLineWidth(1.5)
        
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]
        
        glBegin(GL_LINES)
        for i, j in edges:
            glVertex3f(*vertices[i])
            glVertex3f(*vertices[j])
        glEnd()
        
        glEnable(GL_LIGHTING)
    
    def draw_axes(self):
        """绘制坐标轴"""
        glDisable(GL_LIGHTING)
        glLineWidth(3)
        
        axis_length = min(self.container.length, self.container.width, self.container.height) * 0.2
        
        glBegin(GL_LINES)
        # X轴 - 红色
        glColor3f(1, 0.3, 0.3)
        glVertex3f(0, 0, 0)
        glVertex3f(axis_length, 0, 0)
        # Y轴 - 绿色 (高度)
        glColor3f(0.3, 1, 0.3)
        glVertex3f(0, 0, 0)
        glVertex3f(0, axis_length, 0)
        # Z轴 - 蓝色 (宽度)
        glColor3f(0.3, 0.3, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, axis_length)
        glEnd()
        
        glEnable(GL_LIGHTING)
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        self.last_mouse_pos = event.pos()
        self.mouse_button = event.button()
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if self.last_mouse_pos is None:
            return
        
        dx = event.pos().x() - self.last_mouse_pos.x()
        dy = event.pos().y() - self.last_mouse_pos.y()
        
        if self.mouse_button == Qt.MouseButton.LeftButton:
            # 左键拖动 - 旋转
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.5
            self.rotation_x = max(-90, min(90, self.rotation_x))
        elif self.mouse_button == Qt.MouseButton.RightButton:
            # 右键拖动 - 平移
            self.pan_x += dx * 0.5
            self.pan_y -= dy * 0.5
        elif self.mouse_button == Qt.MouseButton.MiddleButton:
            # 中键拖动 - 缩放
            self.zoom *= 1 + dy * 0.005
            self.zoom = max(0.1, min(5, self.zoom))
        
        self.last_mouse_pos = event.pos()
        self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        self.last_mouse_pos = None
        self.mouse_button = None
    
    def wheelEvent(self, event):
        """鼠标滚轮"""
        delta = event.angleDelta().y()
        self.zoom *= 1 + delta * 0.001
        self.zoom = max(0.1, min(5, self.zoom))
        self.update()
    
    def reset_view(self):
        """重置视角"""
        self.rotation_x = 25
        self.rotation_y = 45
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update()
    
    def set_view(self, preset: str):
        """设置预设视角"""
        views = {
            "front": (0, 0),
            "back": (0, 180),
            "left": (0, -90),
            "right": (0, 90),
            "top": (90, 0),
            "iso": (25, 45),
        }
        if preset in views:
            self.rotation_x, self.rotation_y = views[preset]
            self.update()


class ModernButton(QPushButton):
    """现代风格按钮"""
    def __init__(self, text, primary=False, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(36)
        if primary:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #1565C0;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #37474F;
                    color: white;
                    border: 1px solid #546E7A;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #455A64;
                    border-color: #78909C;
                }
                QPushButton:pressed {
                    background-color: #263238;
                }
            """)


class ContainerLoadingApp(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("集装箱配载软件 v2.0")
        self.setMinimumSize(1400, 900)
        self.resize(1500, 950)
        
        self.cargos: List[Cargo] = []
        self.container: Optional[Container] = None
        self.placed_cargos: List[PlacedCargo] = []
        self.color_index = 0
        
        self.setup_style()
        self.setup_ui()
        self.setup_default_container()
    
    def setup_style(self):
        """设置应用样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QGroupBox {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #81D4FA;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #9e9e9e;
                margin-right: 10px;
            }
            QTableWidget {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                gridline-color: #3d3d3d;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #2196F3;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #81D4FA;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                font-weight: bold;
            }
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #2d2d2d;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196F3, stop:1 #21CBF3);
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #546E7A;
            }
            QCheckBox::indicator:checked {
                background-color: #2196F3;
                border-color: #2196F3;
            }
            QLabel {
                font-size: 13px;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4d4d4d;
            }
        """)
    
    def setup_ui(self):
        """设置界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 左侧面板
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 集装箱选择
        container_group = QGroupBox("📦 集装箱选择")
        container_layout = QVBoxLayout(container_group)
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(STANDARD_CONTAINERS.keys())
        self.container_combo.currentTextChanged.connect(self.on_container_selected)
        container_layout.addWidget(self.container_combo)
        
        self.container_info = QLabel()
        self.container_info.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        container_layout.addWidget(self.container_info)
        
        left_layout.addWidget(container_group)
        
        # 货物添加
        cargo_group = QGroupBox("📋 添加货物")
        cargo_layout = QVBoxLayout(cargo_group)
        
        # 货物名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("名称:"))
        self.cargo_name = QLineEdit("货物1")
        name_layout.addWidget(self.cargo_name)
        cargo_layout.addLayout(name_layout)
        
        # 尺寸输入
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("尺寸:"))
        self.cargo_length = QDoubleSpinBox()
        self.cargo_length.setRange(1, 10000)
        self.cargo_length.setValue(100)
        self.cargo_length.setSuffix(" cm")
        size_layout.addWidget(self.cargo_length)
        size_layout.addWidget(QLabel("×"))
        self.cargo_width = QDoubleSpinBox()
        self.cargo_width.setRange(1, 10000)
        self.cargo_width.setValue(80)
        self.cargo_width.setSuffix(" cm")
        size_layout.addWidget(self.cargo_width)
        size_layout.addWidget(QLabel("×"))
        self.cargo_height = QDoubleSpinBox()
        self.cargo_height.setRange(1, 10000)
        self.cargo_height.setValue(60)
        self.cargo_height.setSuffix(" cm")
        size_layout.addWidget(self.cargo_height)
        cargo_layout.addLayout(size_layout)
        
        # 重量和数量
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("重量:"))
        self.cargo_weight = QDoubleSpinBox()
        self.cargo_weight.setRange(0.1, 100000)
        self.cargo_weight.setValue(50)
        self.cargo_weight.setSuffix(" kg")
        weight_layout.addWidget(self.cargo_weight)
        weight_layout.addWidget(QLabel("数量:"))
        self.cargo_quantity = QSpinBox()
        self.cargo_quantity.setRange(1, 10000)
        self.cargo_quantity.setValue(10)
        weight_layout.addWidget(self.cargo_quantity)
        cargo_layout.addLayout(weight_layout)
        
        # 可堆叠
        self.cargo_stackable = QCheckBox("可堆叠")
        self.cargo_stackable.setChecked(True)
        cargo_layout.addWidget(self.cargo_stackable)
        
        # 添加按钮
        add_btn = ModernButton("➕ 添加货物", primary=True)
        add_btn.clicked.connect(self.add_cargo)
        cargo_layout.addWidget(add_btn)
        
        left_layout.addWidget(cargo_group)
        
        # 货物列表
        list_group = QGroupBox("📜 货物列表")
        list_layout = QVBoxLayout(list_group)
        
        self.cargo_table = QTableWidget()
        self.cargo_table.setColumnCount(5)
        self.cargo_table.setHorizontalHeaderLabels(["名称", "尺寸(cm)", "重量", "数量", "体积(m³)"])
        self.cargo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cargo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cargo_table.setAlternatingRowColors(True)
        list_layout.addWidget(self.cargo_table)
        
        # 列表操作按钮
        list_btn_layout = QHBoxLayout()
        del_btn = ModernButton("🗑 删除")
        del_btn.clicked.connect(self.delete_cargo)
        clear_btn = ModernButton("清空")
        clear_btn.clicked.connect(self.clear_cargos)
        import_btn = ModernButton("📥 导入")
        import_btn.clicked.connect(self.import_cargos)
        export_btn = ModernButton("📤 导出")
        export_btn.clicked.connect(self.export_cargos)
        
        list_btn_layout.addWidget(del_btn)
        list_btn_layout.addWidget(clear_btn)
        list_btn_layout.addWidget(import_btn)
        list_btn_layout.addWidget(export_btn)
        list_layout.addLayout(list_btn_layout)
        
        left_layout.addWidget(list_group)
        
        # 配载操作
        action_group = QGroupBox("⚙️ 配载操作")
        action_layout = QVBoxLayout(action_group)
        
        start_btn = ModernButton("🚀 开始配载", primary=True)
        start_btn.clicked.connect(self.start_loading)
        action_layout.addWidget(start_btn)
        
        clear_result_btn = ModernButton("清除结果")
        clear_result_btn.clicked.connect(self.clear_loading)
        action_layout.addWidget(clear_result_btn)
        
        export_plan_btn = ModernButton("📋 导出方案")
        export_plan_btn.clicked.connect(self.export_loading_plan)
        action_layout.addWidget(export_plan_btn)
        
        left_layout.addWidget(action_group)
        left_layout.addStretch()
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 3D视图
        view_group = QGroupBox("🎮 3D配载视图 (鼠标左键拖动旋转，滚轮缩放，右键平移)")
        view_layout = QVBoxLayout(view_group)
        
        self.gl_widget = Container3DView()
        view_layout.addWidget(self.gl_widget)
        
        # 视图控制按钮
        view_btn_layout = QHBoxLayout()
        
        views = [("正视", "front"), ("后视", "back"), ("左视", "left"), 
                 ("右视", "right"), ("俯视", "top"), ("等轴", "iso")]
        for name, preset in views:
            btn = ModernButton(name)
            btn.setFixedWidth(60)
            btn.clicked.connect(lambda checked, p=preset: self.gl_widget.set_view(p))
            view_btn_layout.addWidget(btn)
        
        view_btn_layout.addStretch()
        
        reset_btn = ModernButton("🔄 重置视图")
        reset_btn.clicked.connect(self.gl_widget.reset_view)
        view_btn_layout.addWidget(reset_btn)
        
        view_layout.addLayout(view_btn_layout)
        right_layout.addWidget(view_group)
        
        # 统计信息
        stats_group = QGroupBox("📊 配载统计")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("请先添加货物并开始配载")
        self.stats_label.setStyleSheet("font-size: 14px; color: #81D4FA;")
        stats_layout.addWidget(self.stats_label)
        
        # 空间利用率
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("空间利用率:"))
        self.volume_progress = QProgressBar()
        self.volume_progress.setRange(0, 100)
        self.volume_progress.setValue(0)
        self.volume_progress.setFormat("%p%")
        volume_layout.addWidget(self.volume_progress)
        self.volume_label = QLabel("0%")
        self.volume_label.setFixedWidth(50)
        volume_layout.addWidget(self.volume_label)
        stats_layout.addLayout(volume_layout)
        
        # 载重利用率
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("载重利用率:"))
        self.weight_progress = QProgressBar()
        self.weight_progress.setRange(0, 100)
        self.weight_progress.setValue(0)
        self.weight_progress.setFormat("%p%")
        self.weight_progress.setStyleSheet("""
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF9800, stop:1 #FFEB3B);
            }
        """)
        weight_layout.addWidget(self.weight_progress)
        self.weight_label = QLabel("0%")
        self.weight_label.setFixedWidth(50)
        weight_layout.addWidget(self.weight_label)
        stats_layout.addLayout(weight_layout)
        
        right_layout.addWidget(stats_group)
        
        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)
    
    def setup_default_container(self):
        """设置默认集装箱"""
        self.container_combo.setCurrentIndex(1)  # 40英尺标准箱
        self.on_container_selected(self.container_combo.currentText())
    
    def on_container_selected(self, name):
        """集装箱选择事件"""
        self.container = STANDARD_CONTAINERS.get(name)
        if self.container:
            info = f"内部尺寸: {self.container.length} × {self.container.width} × {self.container.height} cm\n"
            info += f"容积: {self.container.volume_cbm:.1f} m³ | 最大载重: {self.container.max_weight:,} kg"
            self.container_info.setText(info)
            
            self.gl_widget.container = self.container
            self.gl_widget.placed_cargos = self.placed_cargos
            self.gl_widget.update()
    
    def get_next_color(self):
        """获取下一个颜色"""
        color = CARGO_COLORS[self.color_index % len(CARGO_COLORS)]
        self.color_index += 1
        return color
    
    def add_cargo(self):
        """添加货物"""
        cargo = Cargo(
            name=self.cargo_name.text() or f"货物{len(self.cargos)+1}",
            length=self.cargo_length.value(),
            width=self.cargo_width.value(),
            height=self.cargo_height.value(),
            weight=self.cargo_weight.value(),
            quantity=self.cargo_quantity.value(),
            stackable=self.cargo_stackable.isChecked(),
            color=self.get_next_color()
        )
        
        self.cargos.append(cargo)
        self.update_cargo_table()
        self.cargo_name.setText(f"货物{len(self.cargos)+1}")
    
    def update_cargo_table(self):
        """更新货物表格"""
        self.cargo_table.setRowCount(len(self.cargos))
        for i, cargo in enumerate(self.cargos):
            self.cargo_table.setItem(i, 0, QTableWidgetItem(cargo.name))
            self.cargo_table.setItem(i, 1, QTableWidgetItem(
                f"{cargo.length}×{cargo.width}×{cargo.height}"))
            self.cargo_table.setItem(i, 2, QTableWidgetItem(f"{cargo.weight} kg"))
            self.cargo_table.setItem(i, 3, QTableWidgetItem(str(cargo.quantity)))
            self.cargo_table.setItem(i, 4, QTableWidgetItem(
                f"{cargo.total_volume/1000000:.3f}"))
    
    def delete_cargo(self):
        """删除选中货物"""
        row = self.cargo_table.currentRow()
        if row >= 0:
            del self.cargos[row]
            self.update_cargo_table()
    
    def clear_cargos(self):
        """清空货物"""
        if self.cargos:
            reply = QMessageBox.question(self, "确认", "确定要清空货物列表吗？")
            if reply == QMessageBox.StandardButton.Yes:
                self.cargos.clear()
                self.color_index = 0
                self.update_cargo_table()
    
    def import_cargos(self):
        """导入货物"""
        file_filter = "Excel文件 (*.xlsx);;JSON文件 (*.json)" if EXCEL_SUPPORT else "JSON文件 (*.json)"
        filename, selected_filter = QFileDialog.getOpenFileName(
            self, "导入货物", "", file_filter)
        if filename:
            try:
                if filename.endswith('.xlsx'):
                    self.import_from_excel(filename)
                else:
                    with open(filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.cargos = []
                    for item in data:
                        if 'color' in item and isinstance(item['color'], list):
                            item['color'] = tuple(item['color'])
                        else:
                            item['color'] = self.get_next_color()
                        self.cargos.append(Cargo(**item))
                    self.update_cargo_table()
                    QMessageBox.information(self, "成功", f"成功导入 {len(self.cargos)} 种货物")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def import_from_excel(self, filename):
        """从Excel导入货物"""
        wb = load_workbook(filename)
        ws = wb.active
        
        self.cargos = []
        self.color_index = 0
        
        # 跳过标题行，从第2行开始读取
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:  # 空行跳过
                continue
            
            name = str(row[0]) if row[0] else f"货物{len(self.cargos)+1}"
            length = float(row[1]) if row[1] else 100
            width = float(row[2]) if row[2] else 80
            height = float(row[3]) if row[3] else 60
            weight = float(row[4]) if row[4] else 50
            quantity = int(row[5]) if row[5] else 1
            stackable = True
            if len(row) > 6 and row[6] is not None:
                stackable = str(row[6]).lower() in ('true', '是', '1', 'yes')
            
            cargo = Cargo(
                name=name,
                length=length,
                width=width,
                height=height,
                weight=weight,
                quantity=quantity,
                stackable=stackable,
                color=self.get_next_color()
            )
            self.cargos.append(cargo)
        
        self.update_cargo_table()
        QMessageBox.information(self, "成功", f"成功从Excel导入 {len(self.cargos)} 种货物")
    
    def export_cargos(self):
        """导出货物"""
        if not self.cargos:
            QMessageBox.warning(self, "警告", "没有货物可导出")
            return
        
        file_filter = "Excel文件 (*.xlsx);;JSON文件 (*.json)" if EXCEL_SUPPORT else "JSON文件 (*.json)"
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "导出货物", "", file_filter)
        if filename:
            try:
                if filename.endswith('.xlsx'):
                    self.export_to_excel(filename)
                else:
                    data = []
                    for cargo in self.cargos:
                        d = asdict(cargo)
                        d['color'] = list(d['color'])
                        data.append(d)
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(self, "成功", "货物导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def export_to_excel(self, filename):
        """导出货物到Excel"""
        wb = Workbook()
        ws = wb.active
        ws.title = "货物清单"
        
        # 设置标题样式
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 写入标题行
        headers = ["货物名称", "长度(cm)", "宽度(cm)", "高度(cm)", "重量(kg)", "数量", "可堆叠", "单件体积(m³)", "总体积(m³)", "总重量(kg)"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # 写入数据
        for row, cargo in enumerate(self.cargos, 2):
            ws.cell(row=row, column=1, value=cargo.name).border = thin_border
            ws.cell(row=row, column=2, value=cargo.length).border = thin_border
            ws.cell(row=row, column=3, value=cargo.width).border = thin_border
            ws.cell(row=row, column=4, value=cargo.height).border = thin_border
            ws.cell(row=row, column=5, value=cargo.weight).border = thin_border
            ws.cell(row=row, column=6, value=cargo.quantity).border = thin_border
            ws.cell(row=row, column=7, value="是" if cargo.stackable else "否").border = thin_border
            ws.cell(row=row, column=8, value=round(cargo.volume / 1000000, 4)).border = thin_border
            ws.cell(row=row, column=9, value=round(cargo.total_volume / 1000000, 4)).border = thin_border
            ws.cell(row=row, column=10, value=cargo.total_weight).border = thin_border
        
        # 调整列宽
        column_widths = [15, 12, 12, 12, 12, 10, 10, 14, 14, 14]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[chr(64 + col)].width = width
        
        wb.save(filename)
        QMessageBox.information(self, "成功", "货物已导出到Excel文件")
    
    def start_loading(self):
        """开始配载"""
        if not self.container:
            QMessageBox.warning(self, "警告", "请先选择集装箱")
            return
        
        if not self.cargos:
            QMessageBox.warning(self, "警告", "请先添加货物")
            return
        
        # 执行配载
        algorithm = LoadingAlgorithm(self.container)
        loaded, not_loaded = algorithm.load_all(self.cargos)
        
        self.placed_cargos = loaded
        self.gl_widget.placed_cargos = loaded
        self.gl_widget.update()
        
        # 更新统计
        stats = algorithm.get_statistics()
        
        stats_text = f"已装载: {stats['loaded_count']} 件 | "
        stats_text += f"未装载: {len(not_loaded)} 件 | "
        stats_text += f"总体积: {stats['total_volume']/1000000:.2f} m³ | "
        stats_text += f"总重量: {stats['total_weight']:.1f} kg"
        
        self.stats_label.setText(stats_text)
        self.volume_progress.setValue(int(stats['volume_utilization']))
        self.volume_label.setText(f"{stats['volume_utilization']:.1f}%")
        self.weight_progress.setValue(int(stats['weight_utilization']))
        self.weight_label.setText(f"{stats['weight_utilization']:.1f}%")
        
        if not_loaded:
            cargo_names = ", ".join(set(c.name for c in not_loaded))
            QMessageBox.information(self, "配载完成",
                f"配载完成！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%\n\n"
                f"有 {len(not_loaded)} 件货物无法装入:\n{cargo_names}")
        else:
            QMessageBox.information(self, "配载完成",
                f"所有货物已成功装载！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%")
    
    def clear_loading(self):
        """清除配载结果"""
        self.placed_cargos.clear()
        self.gl_widget.placed_cargos = []
        self.gl_widget.update()
        
        self.stats_label.setText("请先添加货物并开始配载")
        self.volume_progress.setValue(0)
        self.volume_label.setText("0%")
        self.weight_progress.setValue(0)
        self.weight_label.setText("0%")
    
    def export_loading_plan(self):
        """导出配载方案"""
        if not self.placed_cargos:
            QMessageBox.warning(self, "警告", "没有配载结果可导出")
            return
        
        filename, filter_used = QFileDialog.getSaveFileName(
            self, "导出配载方案", "", 
            "文本文件 (*.txt);;JSON文件 (*.json)")
        
        if filename:
            try:
                if filename.endswith(".json"):
                    data = {
                        "container": {
                            "name": self.container.name,
                            "length": self.container.length,
                            "width": self.container.width,
                            "height": self.container.height,
                            "max_weight": self.container.max_weight
                        },
                        "placements": [
                            {
                                "cargo_name": p.cargo.name,
                                "dimensions": {
                                    "length": p.cargo.length,
                                    "width": p.cargo.width,
                                    "height": p.cargo.height
                                },
                                "weight": p.cargo.weight,
                                "position": {"x": p.x, "y": p.y, "z": p.z},
                                "rotated": p.rotated
                            }
                            for p in self.placed_cargos
                        ]
                    }
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("=" * 70 + "\n")
                        f.write("                     集装箱配载方案\n")
                        f.write("=" * 70 + "\n\n")
                        
                        f.write(f"集装箱类型: {self.container.name}\n")
                        f.write(f"内部尺寸: {self.container.length} × {self.container.width} × {self.container.height} cm\n")
                        f.write(f"容积: {self.container.volume_cbm:.1f} m³\n")
                        f.write(f"最大载重: {self.container.max_weight:,} kg\n\n")
                        
                        f.write("-" * 70 + "\n")
                        f.write("装载明细:\n")
                        f.write("-" * 70 + "\n\n")
                        
                        for i, p in enumerate(self.placed_cargos, 1):
                            f.write(f"{i:3d}. {p.cargo.name}\n")
                            f.write(f"     尺寸: {p.cargo.length} × {p.cargo.width} × {p.cargo.height} cm\n")
                            f.write(f"     重量: {p.cargo.weight} kg\n")
                            f.write(f"     位置: X={p.x:.1f}, Y={p.y:.1f}, Z={p.z:.1f} cm\n")
                            f.write(f"     旋转: {'是' if p.rotated else '否'}\n\n")
                        
                        total_volume = sum(p.cargo.volume for p in self.placed_cargos)
                        total_weight = sum(p.cargo.weight for p in self.placed_cargos)
                        
                        f.write("-" * 70 + "\n")
                        f.write("统计信息:\n")
                        f.write(f"  装载件数: {len(self.placed_cargos)}\n")
                        f.write(f"  总体积: {total_volume/1000000:.2f} m³\n")
                        f.write(f"  空间利用率: {(total_volume/self.container.volume)*100:.1f}%\n")
                        f.write(f"  总重量: {total_weight:.1f} kg\n")
                        f.write(f"  载重利用率: {(total_weight/self.container.max_weight)*100:.1f}%\n")
                        f.write("=" * 70 + "\n")
                
                QMessageBox.information(self, "成功", "配载方案导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置深色调色板
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(33, 150, 243))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    window = ContainerLoadingApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

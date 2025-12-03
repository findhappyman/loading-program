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
    QDoubleSpinBox, QStyle, QStyleFactory, QScrollArea,
    QDialog, QGridLayout, QFormLayout, QListWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

from OpenGL.GL import *
from OpenGL.GLU import *
from PyQt6.QtOpenGLWidgets import QOpenGLWidget


@dataclass
class Cargo:
    """货物类"""
    id: str = ""  # 货物唯一ID
    name: str = ""
    length: float = 0  # 长度 (cm)
    width: float = 0   # 宽度 (cm)
    height: float = 0  # 高度 (cm)
    weight: float = 0  # 重量 (kg)
    quantity: int = 1  # 数量
    stackable: bool = True  # 是否可堆叠
    max_stack: int = 3  # 最大堆叠层数
    color: Tuple[float, float, float] = (0.3, 0.7, 0.3)  # RGB颜色
    group_id: str = ""  # 组ID，同组货物锁定在一起
    allow_rotate: bool = True  # 是否允许旋转
    bottom_only: bool = False  # 是否只能放在底层
    priority: int = 0  # 装载优先级（数字越大越优先）
    
    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]
    
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
class CargoGroup:
    """货物组 - 多个货物锁定在一起"""
    id: str
    name: str
    cargo_ids: List[str] = field(default_factory=list)
    # 组合后的整体尺寸（自动计算或手动指定）
    combined_length: float = 0
    combined_width: float = 0
    combined_height: float = 0
    combined_weight: float = 0


@dataclass
class Container:
    """容器类（集装箱/货车/托盘）"""
    name: str
    length: float  # 内部长度 (cm)
    width: float   # 内部宽度 (cm)
    height: float  # 内部高度 (cm)
    max_weight: float  # 最大载重 (kg)
    container_type: str = "container"  # container/truck/pallet
    description: str = ""
    
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
    step_number: int = 0  # 装箱步骤编号
    
    @property
    def actual_length(self) -> float:
        return self.cargo.width if self.rotated else self.cargo.length
    
    @property
    def actual_width(self) -> float:
        return self.cargo.length if self.rotated else self.cargo.width
    
    @property
    def center_x(self) -> float:
        return self.x + self.actual_length / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.actual_width / 2
    
    @property
    def center_z(self) -> float:
        return self.z + self.cargo.height / 2


# ==================== 容器预设 ====================

# 标准集装箱
CONTAINERS_SHIPPING = {
    "20英尺标准箱 (20' GP)": Container("20英尺标准箱", 589, 234, 238, 21770, "container", "标准20尺海运集装箱"),
    "40英尺标准箱 (40' GP)": Container("40英尺标准箱", 1203, 234, 238, 26680, "container", "标准40尺海运集装箱"),
    "40英尺高箱 (40' HC)": Container("40英尺高箱", 1203, 234, 269, 26460, "container", "40尺高柜海运集装箱"),
    "45英尺高箱 (45' HC)": Container("45英尺高箱", 1351, 234, 269, 25600, "container", "45尺高柜海运集装箱"),
}

# 货车类型
CONTAINERS_TRUCK = {
    "4.2米厢式货车": Container("4.2米厢式货车", 420, 180, 180, 2000, "truck", "轻型厢式货车"),
    "6.8米平板车": Container("6.8米平板车", 680, 235, 230, 10000, "truck", "中型平板货车"),
    "7.7米厢式货车": Container("7.7米厢式货车", 770, 235, 240, 12000, "truck", "中型厢式货车"),
    "9.6米厢式货车": Container("9.6米厢式货车", 960, 235, 250, 18000, "truck", "大型厢式货车"),
    "9.6米飞翼车": Container("9.6米飞翼车", 960, 235, 260, 18000, "truck", "侧开式飞翼货车"),
    "13米平板车": Container("13米平板车", 1300, 245, 260, 32000, "truck", "重型平板货车"),
    "13米厢式货车": Container("13米厢式货车", 1300, 245, 270, 32000, "truck", "重型厢式货车"),
    "17.5米高低板车": Container("17.5米高低板车", 1750, 300, 300, 35000, "truck", "超长高低板挂车"),
    "17.5米平板车": Container("17.5米平板车", 1750, 300, 280, 35000, "truck", "超长平板挂车"),
}

# 托盘类型
CONTAINERS_PALLET = {
    "标准托盘 (1200×1000)": Container("标准托盘", 120, 100, 150, 1000, "pallet", "欧标托盘1200×1000mm"),
    "标准托盘 (1200×800)": Container("标准托盘", 120, 80, 150, 800, "pallet", "欧标托盘1200×800mm"),
    "美标托盘 (1219×1016)": Container("美标托盘", 122, 102, 150, 1000, "pallet", "美标托盘48×40英寸"),
    "日标托盘 (1100×1100)": Container("日标托盘", 110, 110, 150, 1000, "pallet", "日标方形托盘"),
    "仓储笼 (1200×1000×890)": Container("仓储笼", 120, 100, 89, 1500, "pallet", "标准仓储笼箱"),
    "周转箱 (600×400×280)": Container("周转箱", 60, 40, 28, 50, "pallet", "标准物流周转箱"),
}

# 合并所有容器类型
STANDARD_CONTAINERS = {
    **CONTAINERS_SHIPPING,
    **CONTAINERS_TRUCK,
    **CONTAINERS_PALLET,
}

# 容器分类
CONTAINER_CATEGORIES = {
    "海运集装箱": list(CONTAINERS_SHIPPING.keys()),
    "公路货车": list(CONTAINERS_TRUCK.keys()),
    "托盘/周转箱": list(CONTAINERS_PALLET.keys()),
    "自定义": [],
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


# ==================== 配载规则 ====================

@dataclass
class LoadingRule:
    """配载规则"""
    id: str
    name: str
    description: str
    enabled: bool = True
    priority: int = 0  # 优先级，数字越大越优先
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        """应用规则对货物排序，子类重写"""
        return cargos


class RuleSameSizeFirst(LoadingRule):
    """相同尺寸优先配载规则"""
    def __init__(self):
        super().__init__("same_size", "相同尺寸优先", "相同或相近尺寸的货物优先放在一起", True, 50)
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        if not cargos:
            return cargos
        # 按尺寸分组排序
        def size_key(c):
            return (round(c.length / 10) * 10, round(c.width / 10) * 10, round(c.height / 10) * 10)
        return sorted(cargos, key=size_key, reverse=True)


class RuleHeavyBottom(LoadingRule):
    """重物下沉规则"""
    def __init__(self, weight_threshold: float = 100):
        super().__init__("heavy_bottom", "重物下沉", f"重量超过{weight_threshold}kg的货物优先放在底层", True, 80)
        self.weight_threshold = weight_threshold
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        heavy = [c for c in cargos if c.weight >= self.weight_threshold]
        light = [c for c in cargos if c.weight < self.weight_threshold]
        # 重物优先，按重量降序
        heavy.sort(key=lambda c: c.weight, reverse=True)
        return heavy + light


class RuleSimilarSizeStack(LoadingRule):
    """相近尺寸堆叠规则"""
    def __init__(self, tolerance: float = 50):
        super().__init__("similar_stack", "相近尺寸堆叠", f"长度差{tolerance}mm以内的货物可堆叠", True, 60)
        self.tolerance = tolerance  # mm
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        # 按长度排序，便于相近尺寸的货物放在一起
        return sorted(cargos, key=lambda c: c.length, reverse=True)


class RuleVolumeFirst(LoadingRule):
    """体积优先规则（默认）"""
    def __init__(self):
        super().__init__("volume_first", "体积优先", "按体积从大到小装载", True, 40)
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        return sorted(cargos, key=lambda c: c.volume, reverse=True)


class RulePriorityFirst(LoadingRule):
    """优先级规则"""
    def __init__(self):
        super().__init__("priority_first", "按优先级", "按货物设定的优先级装载", True, 100)
    
    def apply(self, cargos: List[Cargo], placed: List[PlacedCargo]) -> List[Cargo]:
        return sorted(cargos, key=lambda c: c.priority, reverse=True)


# 默认规则集
DEFAULT_RULES = [
    RulePriorityFirst(),
    RuleHeavyBottom(100),
    RuleSimilarSizeStack(50),
    RuleSameSizeFirst(),
    RuleVolumeFirst(),
]


class LoadingAlgorithm:
    """装载算法类"""
    
    def __init__(self, container: Container, rules: List[LoadingRule] = None, 
                 cargo_groups: List[CargoGroup] = None):
        self.container = container
        self.placed_cargos: List[PlacedCargo] = []
        self.rules = rules or DEFAULT_RULES.copy()
        self.cargo_groups = cargo_groups or []
        self.step_counter = 0
        self.similar_size_tolerance = 50  # mm，相近尺寸容差
    
    def can_place(self, cargo: Cargo, x: float, y: float, z: float, rotated: bool) -> bool:
        # 检查是否允许旋转
        if rotated and not cargo.allow_rotate:
            return False
        
        length = cargo.width if rotated else cargo.length
        width = cargo.length if rotated else cargo.width
        height = cargo.height
        
        # 检查是否只能放底层
        if cargo.bottom_only and z > 0.01:
            return False
        
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
                    
                    # 检查相近尺寸堆叠规则
                    if abs(cargo.length - placed.cargo.length) <= self.similar_size_tolerance or \
                       abs(cargo.width - placed.cargo.width) <= self.similar_size_tolerance:
                        # 允许相近尺寸堆叠
                        pass
                    
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
            if placed.cargo.stackable and not cargo.bottom_only:
                positions.append((placed.x, placed.y, placed.z + ph))
        
        rotations = [False]
        if cargo.allow_rotate:
            rotations.append(True)
        
        for x, y, z in positions:
            for rotated in rotations:
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
            self.step_counter += 1
            placed = PlacedCargo(cargo, x, y, z, rotated, self.step_counter)
            self.placed_cargos.append(placed)
            return True
        return False
    
    def apply_rules(self, cargos: List[Cargo]) -> List[Cargo]:
        """应用所有启用的规则"""
        # 按优先级排序规则
        sorted_rules = sorted([r for r in self.rules if r.enabled], 
                             key=lambda r: r.priority, reverse=True)
        
        result = cargos.copy()
        for rule in sorted_rules:
            result = rule.apply(result, self.placed_cargos)
        
        return result
    
    def expand_groups(self, cargos: List[Cargo]) -> List[Cargo]:
        """处理货物组，将组合货物合并为单个虚拟货物"""
        if not self.cargo_groups:
            return cargos
        
        result = []
        grouped_ids = set()
        
        for group in self.cargo_groups:
            group_cargos = [c for c in cargos if c.id in group.cargo_ids]
            if group_cargos:
                # 计算组合后的尺寸（取最大包围盒）
                if group.combined_length > 0:
                    combined = Cargo(
                        name=group.name,
                        length=group.combined_length,
                        width=group.combined_width,
                        height=group.combined_height,
                        weight=group.combined_weight or sum(c.weight for c in group_cargos),
                        quantity=1,
                        stackable=all(c.stackable for c in group_cargos),
                        color=group_cargos[0].color if group_cargos else (0.5, 0.5, 0.5),
                        group_id=group.id
                    )
                else:
                    # 自动计算组合尺寸
                    combined = Cargo(
                        name=group.name,
                        length=max(c.length for c in group_cargos),
                        width=max(c.width for c in group_cargos),
                        height=sum(c.height for c in group_cargos),
                        weight=sum(c.weight for c in group_cargos),
                        quantity=1,
                        stackable=all(c.stackable for c in group_cargos),
                        color=group_cargos[0].color if group_cargos else (0.5, 0.5, 0.5),
                        group_id=group.id
                    )
                result.append(combined)
                grouped_ids.update(group.cargo_ids)
        
        # 添加未分组的货物
        for cargo in cargos:
            if cargo.id not in grouped_ids:
                result.append(cargo)
        
        return result
    
    def load_all(self, cargos: List[Cargo]) -> Tuple[List[PlacedCargo], List[Cargo]]:
        """装载所有货物"""
        # 处理货物组
        processed_cargos = self.expand_groups(cargos)
        
        # 展开数量
        sorted_cargos = []
        for cargo in processed_cargos:
            for i in range(cargo.quantity):
                single_cargo = copy.copy(cargo)
                single_cargo.quantity = 1
                single_cargo.id = f"{cargo.id}_{i}"
                sorted_cargos.append(single_cargo)
        
        # 应用配载规则
        sorted_cargos = self.apply_rules(sorted_cargos)
        
        loaded = []
        not_loaded = []
        
        for cargo in sorted_cargos:
            if self.place_cargo(cargo):
                loaded.append(self.placed_cargos[-1])
            else:
                not_loaded.append(cargo)
        
        return loaded, not_loaded
    
    def calculate_center_of_gravity(self) -> Tuple[float, float, float]:
        """计算重心位置"""
        if not self.placed_cargos:
            return (0, 0, 0)
        
        total_weight = sum(p.cargo.weight for p in self.placed_cargos)
        if total_weight == 0:
            return (0, 0, 0)
        
        cx = sum(p.center_x * p.cargo.weight for p in self.placed_cargos) / total_weight
        cy = sum(p.center_y * p.cargo.weight for p in self.placed_cargos) / total_weight
        cz = sum(p.center_z * p.cargo.weight for p in self.placed_cargos) / total_weight
        
        return (cx, cy, cz)
    
    def calculate_center_offset(self) -> Tuple[float, float, float]:
        """计算重心偏移量（相对于容器中心）"""
        cx, cy, cz = self.calculate_center_of_gravity()
        container_cx = self.container.length / 2
        container_cy = self.container.width / 2
        container_cz = self.container.height / 2
        
        return (cx - container_cx, cy - container_cy, cz - container_cz)
    
    def get_loading_steps(self) -> List[dict]:
        """获取装箱步骤"""
        steps = []
        sorted_placements = sorted(self.placed_cargos, key=lambda p: p.step_number)
        
        for p in sorted_placements:
            position_desc = []
            if p.x < self.container.length * 0.33:
                position_desc.append("柜头")
            elif p.x > self.container.length * 0.66:
                position_desc.append("柜尾")
            else:
                position_desc.append("中部")
            
            if p.y < self.container.width * 0.5:
                position_desc.append("左侧")
            else:
                position_desc.append("右侧")
            
            if p.z < 1:
                position_desc.append("底层")
            elif p.z > self.container.height * 0.5:
                position_desc.append("上层")
            else:
                position_desc.append("中层")
            
            steps.append({
                "step": p.step_number,
                "cargo_name": p.cargo.name,
                "position": f"X:{p.x:.0f} Y:{p.y:.0f} Z:{p.z:.0f}",
                "position_desc": " ".join(position_desc),
                "rotated": "是" if p.rotated else "否",
                "size": f"{p.actual_length:.0f}×{p.actual_width:.0f}×{p.cargo.height:.0f}"
            })
        
        return steps
    
    def get_statistics(self) -> dict:
        total_cargo_volume = sum(p.cargo.volume for p in self.placed_cargos)
        total_cargo_weight = sum(p.cargo.weight for p in self.placed_cargos)
        
        # 计算重心偏移
        offset_x, offset_y, offset_z = self.calculate_center_offset()
        
        # 计算偏移百分比
        offset_x_pct = (offset_x / (self.container.length / 2)) * 100 if self.container.length > 0 else 0
        offset_y_pct = (offset_y / (self.container.width / 2)) * 100 if self.container.width > 0 else 0
        
        return {
            "loaded_count": len(self.placed_cargos),
            "total_volume": total_cargo_volume,
            "volume_utilization": (total_cargo_volume / self.container.volume) * 100 if self.container.volume > 0 else 0,
            "total_weight": total_cargo_weight,
            "weight_utilization": (total_cargo_weight / self.container.max_weight) * 100 if self.container.max_weight > 0 else 0,
            "center_of_gravity": self.calculate_center_of_gravity(),
            "center_offset": (offset_x, offset_y, offset_z),
            "center_offset_pct": (offset_x_pct, offset_y_pct),
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
        """绘制集装箱（半透明面+线框）"""
        l, w, h = self.container.length, self.container.width, self.container.height
        
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)  # 禁用深度写入，让透明面正确显示
        
        # 绘制半透明的所有面
        glBegin(GL_QUADS)
        
        # 底面 - 稍深一点
        glColor4f(0.5, 0.5, 0.55, 0.35)
        glVertex3f(0, 0, 0)
        glVertex3f(l, 0, 0)
        glVertex3f(l, 0, w)
        glVertex3f(0, 0, w)
        
        # 顶面 - 很透明
        glColor4f(0.4, 0.4, 0.45, 0.15)
        glVertex3f(0, h, 0)
        glVertex3f(0, h, w)
        glVertex3f(l, h, w)
        glVertex3f(l, h, 0)
        
        # 前面 (z=0) - 半透明
        glColor4f(0.45, 0.45, 0.5, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(0, h, 0)
        glVertex3f(l, h, 0)
        glVertex3f(l, 0, 0)
        
        # 后面 (z=w) - 半透明
        glColor4f(0.45, 0.45, 0.5, 0.2)
        glVertex3f(0, 0, w)
        glVertex3f(l, 0, w)
        glVertex3f(l, h, w)
        glVertex3f(0, h, w)
        
        # 左面 (x=0) - 半透明
        glColor4f(0.4, 0.4, 0.45, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, w)
        glVertex3f(0, h, w)
        glVertex3f(0, h, 0)
        
        # 右面 (x=l) - 半透明
        glColor4f(0.4, 0.4, 0.45, 0.2)
        glVertex3f(l, 0, 0)
        glVertex3f(l, h, 0)
        glVertex3f(l, h, w)
        glVertex3f(l, 0, w)
        
        glEnd()
        
        glDepthMask(GL_TRUE)  # 恢复深度写入
        
        # 绘制边框线
        glColor4f(0.8, 0.8, 0.85, 1.0)
        glLineWidth(2)
        
        # 底面边框
        glBegin(GL_LINE_LOOP)
        glVertex3f(0, 0, 0)
        glVertex3f(l, 0, 0)
        glVertex3f(l, 0, w)
        glVertex3f(0, 0, w)
        glEnd()
        
        # 顶面边框
        glBegin(GL_LINE_LOOP)
        glVertex3f(0, h, 0)
        glVertex3f(l, h, 0)
        glVertex3f(l, h, w)
        glVertex3f(0, h, w)
        glEnd()
        
        # 竖直边
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
        self.setWindowTitle("集装箱配载软件 v3.0")
        self.setMinimumSize(1500, 900)
        self.resize(1600, 1000)
        
        self.cargos: List[Cargo] = []
        self.cargo_groups: List[CargoGroup] = []
        self.container: Optional[Container] = None
        self.placed_cargos: List[PlacedCargo] = []
        self.color_index = 0
        self.loading_rules = DEFAULT_RULES.copy()
        self.custom_containers: dict = {}
        self.last_statistics: dict = {}
        
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
                padding: 4px 2px;
            }
            QTableWidget::item:selected {
                background-color: #2196F3;
            }
            QTableWidget QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #2196F3;
                padding: 2px;
                selection-background-color: #2196F3;
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
        left_panel.setMinimumWidth(520)
        left_panel.setMaximumWidth(580)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        
        # ==================== 容器选择 ====================
        container_group = QGroupBox("📦 容器选择")
        container_layout = QVBoxLayout(container_group)
        
        # 容器类别
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("类别:"))
        self.container_category = QComboBox()
        self.container_category.addItems(list(CONTAINER_CATEGORIES.keys()))
        self.container_category.currentTextChanged.connect(self.on_category_changed)
        cat_layout.addWidget(self.container_category)
        container_layout.addLayout(cat_layout)
        
        # 容器型号
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("型号:"))
        self.container_combo = QComboBox()
        self.container_combo.currentTextChanged.connect(self.on_container_selected)
        type_layout.addWidget(self.container_combo)
        container_layout.addLayout(type_layout)
        
        # 自定义容器按钮
        custom_btn_layout = QHBoxLayout()
        custom_btn = ModernButton("➕ 自定义容器")
        custom_btn.clicked.connect(self.show_custom_container_dialog)
        custom_btn_layout.addWidget(custom_btn)
        container_layout.addLayout(custom_btn_layout)
        
        # 容器信息
        self.container_info = QLabel()
        self.container_info.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        self.container_info.setWordWrap(True)
        container_layout.addWidget(self.container_info)
        
        scroll_layout.addWidget(container_group)
        
        # ==================== 货物添加 ====================
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
        
        # 货物选项
        options_layout = QHBoxLayout()
        self.cargo_stackable = QCheckBox("可堆叠")
        self.cargo_stackable.setChecked(True)
        options_layout.addWidget(self.cargo_stackable)
        self.cargo_rotatable = QCheckBox("可旋转")
        self.cargo_rotatable.setChecked(True)
        options_layout.addWidget(self.cargo_rotatable)
        self.cargo_bottom_only = QCheckBox("仅底层")
        options_layout.addWidget(self.cargo_bottom_only)
        cargo_layout.addLayout(options_layout)
        
        # 优先级
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("优先级:"))
        self.cargo_priority = QSpinBox()
        self.cargo_priority.setRange(0, 100)
        self.cargo_priority.setValue(0)
        self.cargo_priority.setToolTip("数字越大优先级越高")
        priority_layout.addWidget(self.cargo_priority)
        priority_layout.addStretch()
        cargo_layout.addLayout(priority_layout)
        
        # 添加按钮
        add_btn = ModernButton("➕ 添加货物", primary=True)
        add_btn.clicked.connect(self.add_cargo)
        cargo_layout.addWidget(add_btn)
        
        scroll_layout.addWidget(cargo_group)
        
        # ==================== 货物列表 ====================
        list_group = QGroupBox("📜 货物列表")
        list_layout = QVBoxLayout(list_group)
        
        self.cargo_table = QTableWidget()
        self.cargo_table.setColumnCount(6)
        self.cargo_table.setHorizontalHeaderLabels(["名称", "尺寸(cm)", "重量", "数量", "选项", "体积"])
        # 设置各列宽度 - 全部固定宽度
        self.cargo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.cargo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 尺寸列自动拉伸
        self.cargo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.cargo_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.cargo_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.cargo_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.cargo_table.setColumnWidth(0, 60)   # 名称
        self.cargo_table.setColumnWidth(2, 60)   # 重量
        self.cargo_table.setColumnWidth(3, 35)   # 数量
        self.cargo_table.setColumnWidth(4, 50)   # 选项
        self.cargo_table.setColumnWidth(5, 45)   # 体积
        self.cargo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cargo_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.cargo_table.setAlternatingRowColors(True)
        self.cargo_table.setMinimumHeight(180)
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
        
        # 货物组操作
        group_btn_layout = QHBoxLayout()
        create_group_btn = ModernButton("🔗 创建组")
        create_group_btn.clicked.connect(self.create_cargo_group)
        create_group_btn.setToolTip("将选中的货物组合为一组")
        group_btn_layout.addWidget(create_group_btn)
        ungroup_btn = ModernButton("解除组")
        ungroup_btn.clicked.connect(self.ungroup_cargo)
        group_btn_layout.addWidget(ungroup_btn)
        list_layout.addLayout(group_btn_layout)
        
        scroll_layout.addWidget(list_group)
        
        # ==================== 配载规则 ====================
        rules_group = QGroupBox("📐 配载规则")
        rules_layout = QVBoxLayout(rules_group)
        
        # 规则列表
        self.rules_list = QTableWidget()
        self.rules_list.setColumnCount(3)
        self.rules_list.setHorizontalHeaderLabels(["启用", "规则", "优先级"])
        self.rules_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.rules_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rules_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.rules_list.setColumnWidth(0, 50)
        self.rules_list.setColumnWidth(2, 60)
        self.rules_list.setMaximumHeight(150)
        self.setup_rules_table()
        rules_layout.addWidget(self.rules_list)
        
        scroll_layout.addWidget(rules_group)
        
        # ==================== 配载操作 ====================
        action_group = QGroupBox("⚙️ 配载操作")
        action_layout = QVBoxLayout(action_group)
        
        start_btn = ModernButton("🚀 开始配载", primary=True)
        start_btn.clicked.connect(self.start_loading)
        action_layout.addWidget(start_btn)
        
        manual_btn = ModernButton("✋ 手动调整")
        manual_btn.clicked.connect(self.enable_manual_edit)
        manual_btn.setToolTip("配载后手动调整货物位置")
        action_layout.addWidget(manual_btn)
        
        clear_result_btn = ModernButton("清除结果")
        clear_result_btn.clicked.connect(self.clear_loading)
        action_layout.addWidget(clear_result_btn)
        
        export_plan_btn = ModernButton("📋 导出详细方案")
        export_plan_btn.clicked.connect(self.export_loading_plan)
        action_layout.addWidget(export_plan_btn)
        
        scroll_layout.addWidget(action_group)
        
        # ==================== 两步装载 ====================
        twostep_group = QGroupBox("📦 两步装载（先组托再装柜）")
        twostep_layout = QVBoxLayout(twostep_group)
        
        palletize_btn = ModernButton("第一步: 货物组托")
        palletize_btn.clicked.connect(self.palletize_cargos)
        palletize_btn.setToolTip("将小箱先组到托盘上")
        twostep_layout.addWidget(palletize_btn)
        
        load_pallets_btn = ModernButton("第二步: 托盘装柜")
        load_pallets_btn.clicked.connect(self.load_pallets_to_container)
        load_pallets_btn.setToolTip("将托盘装入集装箱")
        twostep_layout.addWidget(load_pallets_btn)
        
        scroll_layout.addWidget(twostep_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)
        
        # ==================== 右侧面板 ====================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 3D视图
        view_group = QGroupBox("🎮 3D配载视图 (左键旋转 | 滚轮缩放 | 右键平移)")
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
        self.stats_label.setStyleSheet("font-size: 13px; color: #81D4FA;")
        self.stats_label.setWordWrap(True)
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
        
        # 重心偏移
        cog_layout = QHBoxLayout()
        cog_layout.addWidget(QLabel("重心偏移:"))
        self.cog_label = QLabel("X: 0% | Y: 0%")
        self.cog_label.setStyleSheet("color: #4CAF50;")
        cog_layout.addWidget(self.cog_label)
        cog_layout.addStretch()
        stats_layout.addLayout(cog_layout)
        
        right_layout.addWidget(stats_group)
        
        # ==================== 装箱步骤 ====================
        steps_group = QGroupBox("📝 装箱步骤")
        steps_layout = QVBoxLayout(steps_group)
        
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(5)
        self.steps_table.setHorizontalHeaderLabels(["步骤", "货物", "位置描述", "坐标", "旋转"])
        self.steps_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.steps_table.setMaximumHeight(150)
        steps_layout.addWidget(self.steps_table)
        
        right_layout.addWidget(steps_group)
        
        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)
    
    def setup_rules_table(self):
        """设置规则表格"""
        self.rules_list.setRowCount(len(self.loading_rules))
        for i, rule in enumerate(self.loading_rules):
            # 启用复选框
            cb = QCheckBox()
            cb.setChecked(rule.enabled)
            cb.stateChanged.connect(lambda state, r=rule: setattr(r, 'enabled', state == 2))
            self.rules_list.setCellWidget(i, 0, cb)
            
            # 规则名称
            name_item = QTableWidgetItem(rule.name)
            name_item.setToolTip(rule.description)
            self.rules_list.setItem(i, 1, name_item)
            
            # 优先级
            priority_item = QTableWidgetItem(str(rule.priority))
            self.rules_list.setItem(i, 2, priority_item)
    
    def on_category_changed(self, category):
        """容器类别变化"""
        self.container_combo.clear()
        if category == "海运集装箱":
            self.container_combo.addItems(CONTAINERS_SHIPPING.keys())
        elif category == "公路货车":
            self.container_combo.addItems(CONTAINERS_TRUCK.keys())
        elif category == "托盘/周转箱":
            self.container_combo.addItems(CONTAINERS_PALLET.keys())
        elif category == "自定义":
            self.container_combo.addItems(self.custom_containers.keys())
    
    def show_custom_container_dialog(self):
        """显示自定义容器对话框"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("自定义容器")
        dialog.setMinimumWidth(350)
        
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit("自定义容器1")
        length_spin = QDoubleSpinBox()
        length_spin.setRange(1, 50000)
        length_spin.setValue(1200)
        length_spin.setSuffix(" cm")
        
        width_spin = QDoubleSpinBox()
        width_spin.setRange(1, 10000)
        width_spin.setValue(240)
        width_spin.setSuffix(" cm")
        
        height_spin = QDoubleSpinBox()
        height_spin.setRange(1, 10000)
        height_spin.setValue(260)
        height_spin.setSuffix(" cm")
        
        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(1, 1000000)
        weight_spin.setValue(25000)
        weight_spin.setSuffix(" kg")
        
        type_combo = QComboBox()
        type_combo.addItems(["集装箱", "货车", "托盘"])
        
        layout.addRow("名称:", name_edit)
        layout.addRow("内部长度:", length_spin)
        layout.addRow("内部宽度:", width_spin)
        layout.addRow("内部高度:", height_spin)
        layout.addRow("最大载重:", weight_spin)
        layout.addRow("类型:", type_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            type_map = {"集装箱": "container", "货车": "truck", "托盘": "pallet"}
            container = Container(
                name=name_edit.text(),
                length=length_spin.value(),
                width=width_spin.value(),
                height=height_spin.value(),
                max_weight=weight_spin.value(),
                container_type=type_map[type_combo.currentText()]
            )
            self.custom_containers[name_edit.text()] = container
            STANDARD_CONTAINERS[name_edit.text()] = container
            
            # 切换到自定义类别
            self.container_category.setCurrentText("自定义")
            self.on_category_changed("自定义")
            self.container_combo.setCurrentText(name_edit.text())
            
            QMessageBox.information(self, "成功", f"已添加自定义容器: {name_edit.text()}")
    
    def setup_default_container(self):
        """设置默认集装箱"""
        self.container_category.setCurrentText("海运集装箱")
        self.on_category_changed("海运集装箱")
        if self.container_combo.count() > 1:
            self.container_combo.setCurrentIndex(1)  # 40英尺标准箱
    
    def on_container_selected(self, name):
        """容器选择事件"""
        if not name:
            return
        self.container = STANDARD_CONTAINERS.get(name) or self.custom_containers.get(name)
        if self.container:
            type_names = {"container": "集装箱", "truck": "货车", "pallet": "托盘"}
            type_name = type_names.get(self.container.container_type, "容器")
            info = f"类型: {type_name}\n"
            info += f"内部尺寸: {self.container.length} × {self.container.width} × {self.container.height} cm\n"
            info += f"容积: {self.container.volume_cbm:.1f} m³ | 最大载重: {self.container.max_weight:,} kg"
            if self.container.description:
                info += f"\n{self.container.description}"
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
            allow_rotate=self.cargo_rotatable.isChecked(),
            bottom_only=self.cargo_bottom_only.isChecked(),
            priority=self.cargo_priority.value(),
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
            # 尺寸显示为整数，更紧凑
            self.cargo_table.setItem(i, 1, QTableWidgetItem(
                f"{int(cargo.length)}×{int(cargo.width)}×{int(cargo.height)}"))
            self.cargo_table.setItem(i, 2, QTableWidgetItem(f"{cargo.weight}kg"))
            self.cargo_table.setItem(i, 3, QTableWidgetItem(str(cargo.quantity)))
            
            # 选项列 - 显示图标表示各种属性
            options = []
            if cargo.allow_rotate:
                options.append("🔄")  # 可旋转
            if cargo.bottom_only:
                options.append("⬇")  # 仅底层
            if cargo.priority > 0:
                options.append(f"P{cargo.priority}")  # 优先级
            if cargo.group_id:
                options.append(f"{cargo.group_id}")  # 分组
            self.cargo_table.setItem(i, 4, QTableWidgetItem("".join(options)))
            
            # 体积列
            self.cargo_table.setItem(i, 5, QTableWidgetItem(
                f"{cargo.total_volume/1000000:.2f}"))
    
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
                    self.cargo_groups = []
                    group_map = {}
                    
                    # 处理货物数据
                    cargo_list = data.get('cargos', data) if isinstance(data, dict) else data
                    for item in cargo_list:
                        if 'color' in item and isinstance(item['color'], list):
                            item['color'] = tuple(item['color'])
                        else:
                            item['color'] = self.get_next_color()
                        cargo = Cargo(**item)
                        self.cargos.append(cargo)
                        
                        # 记录分组
                        if cargo.group_id:
                            if cargo.group_id not in group_map:
                                group_map[cargo.group_id] = []
                            group_map[cargo.group_id].append(cargo.id)
                    
                    # 创建分组对象
                    for gid, cargo_ids in group_map.items():
                        group = CargoGroup(id=gid, name=f"分组{gid}", cargo_ids=cargo_ids)
                        self.cargo_groups.append(group)
                    
                    self.update_cargo_table()
                    group_info = f"，{len(self.cargo_groups)}个分组" if self.cargo_groups else ""
                    QMessageBox.information(self, "成功", f"成功导入 {len(self.cargos)} 种货物{group_info}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def import_from_excel(self, filename):
        """从Excel导入货物"""
        wb = load_workbook(filename)
        ws = wb.active
        
        self.cargos = []
        self.cargo_groups = []
        self.color_index = 0
        group_map = {}  # 记录分组ID到货物ID的映射
        
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
            
            # 读取分组信息 (第11列，索引10)
            group_id = None
            if len(row) > 10 and row[10]:
                group_id = str(row[10]).strip()
            
            cargo = Cargo(
                name=name,
                length=length,
                width=width,
                height=height,
                weight=weight,
                quantity=quantity,
                stackable=stackable,
                group_id=group_id,
                color=self.get_next_color()
            )
            self.cargos.append(cargo)
            
            # 记录分组
            if group_id:
                if group_id not in group_map:
                    group_map[group_id] = []
                group_map[group_id].append(cargo.id)
        
        # 创建分组对象
        for gid, cargo_ids in group_map.items():
            group = CargoGroup(
                id=gid,
                name=f"分组{gid}",
                cargo_ids=cargo_ids
            )
            self.cargo_groups.append(group)
        
        self.update_cargo_table()
        group_info = f"，{len(self.cargo_groups)}个分组" if self.cargo_groups else ""
        QMessageBox.information(self, "成功", f"成功从Excel导入 {len(self.cargos)} 种货物{group_info}")
    
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
        headers = ["货物名称", "长度(cm)", "宽度(cm)", "高度(cm)", "重量(kg)", "数量", "可堆叠", "单件体积(m³)", "总体积(m³)", "总重量(kg)", "分组"]
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
            ws.cell(row=row, column=11, value=cargo.group_id or "").border = thin_border
        
        # 调整列宽
        column_widths = [15, 12, 12, 12, 12, 10, 10, 14, 14, 14, 10]
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
        
        # 收集启用的规则
        active_rules = []
        for row in range(self.rules_list.rowCount()):
            checkbox = self.rules_list.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                rule_name = self.rules_list.item(row, 1).text()
                priority = int(self.rules_list.item(row, 2).text())
                
                if rule_name == "相同尺寸优先":
                    active_rules.append((priority, RuleSameSizeFirst()))
                elif rule_name == "重货在下":
                    active_rules.append((priority, RuleHeavyBottom()))
                elif rule_name == "相似尺寸堆叠":
                    active_rules.append((priority, RuleSimilarSizeStack()))
                elif rule_name == "体积大优先":
                    active_rules.append((priority, RuleVolumeFirst()))
                elif rule_name == "优先级排序":
                    active_rules.append((priority, RulePriorityFirst()))
        
        # 按优先级排序规则
        active_rules.sort(key=lambda x: x[0], reverse=True)
        rules = [r[1] for r in active_rules]
        
        # 执行配载
        algorithm = LoadingAlgorithm(self.container, rules=rules, cargo_groups=self.cargo_groups)
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
        
        # 更新重心显示
        cog_tuple = stats.get('center_of_gravity', (0, 0, 0))
        offset_tuple = stats.get('center_offset', (0, 0, 0))
        
        # 判断重心状态
        max_offset = min(self.container.length, self.container.width) * 0.1
        if abs(offset_tuple[0]) < max_offset and abs(offset_tuple[1]) < max_offset:
            cog_status = "良好"
        else:
            cog_status = "偏移较大"
        
        cog_text = f"重心位置: X={cog_tuple[0]:.1f}, Y={cog_tuple[1]:.1f}, Z={cog_tuple[2]:.1f} cm\n"
        cog_text += f"偏移: 横向 {offset_tuple[0]:.1f}cm, 纵向 {offset_tuple[1]:.1f}cm | 状态: {cog_status}"
        self.cog_label.setText(cog_text)
        
        # 更新装载步骤表格
        self.update_steps_table(stats.get('loading_steps', []))
        
        if not_loaded:
            cargo_names = ", ".join(set(c.name for c in not_loaded))
            QMessageBox.information(self, "配载完成",
                f"配载完成！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%\n"
                f"重心状态: {cog_status}\n\n"
                f"有 {len(not_loaded)} 件货物无法装入:\n{cargo_names}")
        else:
            QMessageBox.information(self, "配载完成",
                f"所有货物已成功装载！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%\n"
                f"重心状态: {cog_status}")
    
    def update_steps_table(self, steps: list):
        """更新装载步骤表格"""
        self.steps_table.setRowCount(len(steps))
        for i, step in enumerate(steps):
            self.steps_table.setItem(i, 0, QTableWidgetItem(str(step.get('step', i+1))))
            self.steps_table.setItem(i, 1, QTableWidgetItem(step.get('cargo_name', '')))
            self.steps_table.setItem(i, 2, QTableWidgetItem(step.get('position', '')))
            self.steps_table.setItem(i, 3, QTableWidgetItem(step.get('securing', '标准加固')))
    
    def create_cargo_group(self):
        """创建货物分组"""
        selected_rows = set()
        for item in self.cargo_table.selectedItems():
            selected_rows.add(item.row())
        
        if len(selected_rows) < 2:
            QMessageBox.warning(self, "警告", "请至少选择2个货物来创建分组")
            return
        
        # 生成新的分组ID
        group_id = f"G{len(self.cargo_groups) + 1}"
        
        # 获取选中的货物ID列表
        cargo_ids = []
        for row in selected_rows:
            cargo = self.cargos[row]
            cargo.group_id = group_id
            cargo_ids.append(cargo.id)
        
        # 创建分组对象
        group = CargoGroup(
            id=group_id,
            name=f"分组{len(self.cargo_groups) + 1}",
            cargo_ids=cargo_ids
        )
        self.cargo_groups.append(group)
        
        self.update_cargo_table()
        QMessageBox.information(self, "成功", f"已创建分组 {group_id}，包含 {len(cargo_ids)} 个货物")
    
    def ungroup_cargo(self):
        """取消货物分组"""
        selected_rows = set()
        for item in self.cargo_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请选择要取消分组的货物")
            return
        
        ungrouped_count = 0
        for row in selected_rows:
            cargo = self.cargos[row]
            if cargo.group_id:
                # 从分组中移除
                for group in self.cargo_groups:
                    if cargo.id in group.cargo_ids:
                        group.cargo_ids.remove(cargo.id)
                        if not group.cargo_ids:  # 如果分组为空，删除分组
                            self.cargo_groups.remove(group)
                        break
                cargo.group_id = None
                ungrouped_count += 1
        
        self.update_cargo_table()
        if ungrouped_count > 0:
            QMessageBox.information(self, "成功", f"已取消 {ungrouped_count} 个货物的分组")
        else:
            QMessageBox.information(self, "提示", "选中的货物没有分组")
    
    def enable_manual_edit(self):
        """启用手动编辑模式"""
        if not self.placed_cargos:
            QMessageBox.warning(self, "警告", "没有配载结果可编辑，请先执行配载")
            return
        
        # 创建手动编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("手动编辑配载")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)
        
        # 说明标签
        hint_label = QLabel("选择货物并调整其位置，可拖动滑块或直接输入坐标值")
        hint_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint_label)
        
        # 货物选择
        cargo_combo = QComboBox()
        for i, pc in enumerate(self.placed_cargos):
            cargo_combo.addItem(f"{i+1}. {pc.cargo.name} @ ({pc.x:.0f}, {pc.y:.0f}, {pc.z:.0f})")
        layout.addWidget(cargo_combo)
        
        # 位置编辑
        pos_group = QGroupBox("位置调整")
        pos_layout = QGridLayout(pos_group)
        
        x_label = QLabel("X (长度方向):")
        x_spin = QSpinBox()
        x_spin.setRange(0, int(self.container.length))
        x_spin.setSingleStep(10)
        
        y_label = QLabel("Y (宽度方向):")
        y_spin = QSpinBox()
        y_spin.setRange(0, int(self.container.width))
        y_spin.setSingleStep(10)
        
        z_label = QLabel("Z (高度方向):")
        z_spin = QSpinBox()
        z_spin.setRange(0, int(self.container.height))
        z_spin.setSingleStep(10)
        
        rotate_check = QCheckBox("旋转90度")
        
        pos_layout.addWidget(x_label, 0, 0)
        pos_layout.addWidget(x_spin, 0, 1)
        pos_layout.addWidget(y_label, 1, 0)
        pos_layout.addWidget(y_spin, 1, 1)
        pos_layout.addWidget(z_label, 2, 0)
        pos_layout.addWidget(z_spin, 2, 1)
        pos_layout.addWidget(rotate_check, 3, 0, 1, 2)
        layout.addWidget(pos_group)
        
        def on_cargo_selected(index):
            if index >= 0 and index < len(self.placed_cargos):
                pc = self.placed_cargos[index]
                x_spin.setValue(int(pc.x))
                y_spin.setValue(int(pc.y))
                z_spin.setValue(int(pc.z))
                rotate_check.setChecked(pc.rotated)
        
        def apply_position():
            index = cargo_combo.currentIndex()
            if index >= 0 and index < len(self.placed_cargos):
                pc = self.placed_cargos[index]
                pc.x = x_spin.value()
                pc.y = y_spin.value()
                pc.z = z_spin.value()
                pc.rotated = rotate_check.isChecked()
                self.gl_widget.update()
                cargo_combo.setItemText(index, 
                    f"{index+1}. {pc.cargo.name} @ ({pc.x:.0f}, {pc.y:.0f}, {pc.z:.0f})")
        
        cargo_combo.currentIndexChanged.connect(on_cargo_selected)
        on_cargo_selected(0)  # 初始化第一个
        
        # 应用按钮
        apply_btn = QPushButton("应用更改")
        apply_btn.clicked.connect(apply_position)
        apply_btn.setStyleSheet("background-color: #4CAF50; font-weight: bold;")
        layout.addWidget(apply_btn)
        
        # 删除货物按钮
        def remove_cargo():
            index = cargo_combo.currentIndex()
            if index >= 0 and index < len(self.placed_cargos):
                del self.placed_cargos[index]
                cargo_combo.removeItem(index)
                self.gl_widget.update()
                # 更新组合框中的编号
                for i in range(cargo_combo.count()):
                    pc = self.placed_cargos[i]
                    cargo_combo.setItemText(i, 
                        f"{i+1}. {pc.cargo.name} @ ({pc.x:.0f}, {pc.y:.0f}, {pc.z:.0f})")
        
        remove_btn = QPushButton("删除此货物")
        remove_btn.clicked.connect(remove_cargo)
        remove_btn.setStyleSheet("background-color: #f44336;")
        layout.addWidget(remove_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
        
        # 更新统计
        if self.placed_cargos:
            total_volume = sum(p.cargo.volume for p in self.placed_cargos)
            total_weight = sum(p.cargo.weight for p in self.placed_cargos)
            vol_util = (total_volume / self.container.volume) * 100
            wt_util = (total_weight / self.container.max_weight) * 100
            
            self.volume_progress.setValue(int(vol_util))
            self.volume_label.setText(f"{vol_util:.1f}%")
            self.weight_progress.setValue(int(wt_util))
            self.weight_label.setText(f"{wt_util:.1f}%")
    
    def palletize_cargos(self):
        """小件组托 - 将小货物组合成托盘"""
        if not self.cargos:
            QMessageBox.warning(self, "警告", "请先添加货物")
            return
        
        # 创建组托对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("小件组托")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        # 托盘尺寸选择
        pallet_group = QGroupBox("托盘规格")
        pallet_layout = QFormLayout(pallet_group)
        
        pallet_type = QComboBox()
        pallet_type.addItems(["标准托盘 (120×100×15)", "欧标托盘 (120×80×15)", "自定义"])
        pallet_layout.addRow("托盘类型:", pallet_type)
        
        pallet_length = QSpinBox()
        pallet_length.setRange(50, 200)
        pallet_length.setValue(120)
        pallet_layout.addRow("长度(cm):", pallet_length)
        
        pallet_width = QSpinBox()
        pallet_width.setRange(50, 200)
        pallet_width.setValue(100)
        pallet_layout.addRow("宽度(cm):", pallet_width)
        
        max_height = QSpinBox()
        max_height.setRange(50, 300)
        max_height.setValue(150)
        pallet_layout.addRow("最大堆叠高度(cm):", max_height)
        
        max_weight = QSpinBox()
        max_weight.setRange(100, 2000)
        max_weight.setValue(1000)
        pallet_layout.addRow("最大载重(kg):", max_weight)
        
        def on_pallet_type_changed(index):
            if index == 0:  # 标准托盘
                pallet_length.setValue(120)
                pallet_width.setValue(100)
            elif index == 1:  # 欧标托盘
                pallet_length.setValue(120)
                pallet_width.setValue(80)
        
        pallet_type.currentIndexChanged.connect(on_pallet_type_changed)
        layout.addWidget(pallet_group)
        
        # 选择要组托的货物
        cargo_group = QGroupBox("选择货物")
        cargo_layout = QVBoxLayout(cargo_group)
        
        cargo_list = QListWidget()
        cargo_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for cargo in self.cargos:
            cargo_list.addItem(f"{cargo.name} - {cargo.length}×{cargo.width}×{cargo.height}cm, {cargo.weight}kg × {cargo.quantity}")
        cargo_layout.addWidget(cargo_list)
        
        select_all_btn = QPushButton("全选小件(体积<0.1m³)")
        def select_small():
            for i, cargo in enumerate(self.cargos):
                if cargo.volume < 100000:  # 0.1m³ = 100000 cm³
                    cargo_list.item(i).setSelected(True)
        select_all_btn.clicked.connect(select_small)
        cargo_layout.addWidget(select_all_btn)
        layout.addWidget(cargo_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("开始组托")
        ok_btn.setStyleSheet("background-color: #2196F3; font-weight: bold;")
        cancel_btn = QPushButton("取消")
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_indices = [cargo_list.row(item) for item in cargo_list.selectedItems()]
            if not selected_indices:
                QMessageBox.warning(self, "警告", "请选择要组托的货物")
                return
            
            # 执行组托逻辑
            pallet_l = pallet_length.value()
            pallet_w = pallet_width.value()
            max_h = max_height.value()
            max_wt = max_weight.value()
            
            # 简化的组托算法 - 创建托盘货物
            palletized_cargos = []
            remaining_cargos = []
            
            current_pallet_cargos = []
            current_height = 15  # 托盘自身高度
            current_weight = 0
            pallet_count = 0
            
            for i, cargo in enumerate(self.cargos):
                if i in selected_indices:
                    # 检查是否能放入当前托盘
                    if (current_height + cargo.height <= max_h and 
                        current_weight + cargo.total_weight <= max_wt):
                        for _ in range(cargo.quantity):
                            current_pallet_cargos.append(cargo)
                            current_weight += cargo.weight
                            current_height = min(current_height + cargo.height, max_h)
                    else:
                        # 完成当前托盘，开始新托盘
                        if current_pallet_cargos:
                            pallet_count += 1
                            pallet_cargo = Cargo(
                                name=f"托盘{pallet_count}",
                                length=pallet_l,
                                width=pallet_w,
                                height=current_height,
                                weight=current_weight,
                                quantity=1,
                                stackable=True,
                                color=self.get_next_color()
                            )
                            palletized_cargos.append(pallet_cargo)
                        
                        # 重置
                        current_pallet_cargos = []
                        current_height = 15 + cargo.height
                        current_weight = cargo.total_weight
                        for _ in range(cargo.quantity):
                            current_pallet_cargos.append(cargo)
                else:
                    remaining_cargos.append(cargo)
            
            # 处理最后一个托盘
            if current_pallet_cargos:
                pallet_count += 1
                pallet_cargo = Cargo(
                    name=f"托盘{pallet_count}",
                    length=pallet_l,
                    width=pallet_w,
                    height=current_height,
                    weight=current_weight,
                    quantity=1,
                    stackable=True,
                    color=self.get_next_color()
                )
                palletized_cargos.append(pallet_cargo)
            
            # 更新货物列表
            self.cargos = remaining_cargos + palletized_cargos
            self.update_cargo_table()
            
            QMessageBox.information(self, "组托完成", 
                f"已将选中货物组成 {pallet_count} 个托盘\n"
                f"托盘规格: {pallet_l}×{pallet_w}cm")
    
    def load_pallets_to_container(self):
        """装载托盘到集装箱"""
        # 筛选托盘货物
        pallet_cargos = [c for c in self.cargos if c.name.startswith("托盘")]
        
        if not pallet_cargos:
            QMessageBox.warning(self, "警告", "没有托盘可装载，请先执行'小件组托'")
            return
        
        if not self.container:
            QMessageBox.warning(self, "警告", "请先选择集装箱")
            return
        
        # 直接执行配载
        self.start_loading()
        
        QMessageBox.information(self, "提示", 
            f"已将 {len(pallet_cargos)} 个托盘装入集装箱")
    
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
                # 计算重心信息
                total_volume = sum(p.cargo.volume for p in self.placed_cargos)
                total_weight = sum(p.cargo.weight for p in self.placed_cargos)
                
                # 计算重心
                if total_weight > 0:
                    cog_x = sum(p.center_x * p.cargo.weight for p in self.placed_cargos) / total_weight
                    cog_y = sum(p.center_y * p.cargo.weight for p in self.placed_cargos) / total_weight
                    cog_z = sum(p.center_z * p.cargo.weight for p in self.placed_cargos) / total_weight
                    
                    # 计算偏移
                    center_x = self.container.length / 2
                    center_y = self.container.width / 2
                    offset_x = cog_x - center_x
                    offset_y = cog_y - center_y
                else:
                    cog_x = cog_y = cog_z = 0
                    offset_x = offset_y = 0
                
                if filename.endswith(".json"):
                    data = {
                        "container": {
                            "name": self.container.name,
                            "type": self.container.container_type,
                            "length": self.container.length,
                            "width": self.container.width,
                            "height": self.container.height,
                            "max_weight": self.container.max_weight
                        },
                        "statistics": {
                            "loaded_count": len(self.placed_cargos),
                            "total_volume_m3": round(total_volume / 1000000, 3),
                            "total_weight_kg": round(total_weight, 1),
                            "volume_utilization": round((total_volume/self.container.volume)*100, 1),
                            "weight_utilization": round((total_weight/self.container.max_weight)*100, 1)
                        },
                        "center_of_gravity": {
                            "x": round(cog_x, 1),
                            "y": round(cog_y, 1),
                            "z": round(cog_z, 1),
                            "offset_x": round(offset_x, 1),
                            "offset_y": round(offset_y, 1)
                        },
                        "loading_steps": [
                            {
                                "step": i + 1,
                                "cargo_name": p.cargo.name,
                                "dimensions": f"{p.cargo.length}×{p.cargo.width}×{p.cargo.height}",
                                "weight": p.cargo.weight,
                                "position": {"x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1)},
                                "rotated": p.rotated,
                                "securing": self.get_securing_advice(p, i, len(self.placed_cargos))
                            }
                            for i, p in enumerate(self.placed_cargos)
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
                        f.write(f"容器类别: {self.container.container_type}\n")
                        f.write(f"内部尺寸: {self.container.length} × {self.container.width} × {self.container.height} cm\n")
                        f.write(f"容积: {self.container.volume_cbm:.1f} m³\n")
                        f.write(f"最大载重: {self.container.max_weight:,} kg\n\n")
                        
                        f.write("-" * 70 + "\n")
                        f.write("重心分析:\n")
                        f.write("-" * 70 + "\n")
                        f.write(f"  重心位置: X={cog_x:.1f}cm, Y={cog_y:.1f}cm, Z={cog_z:.1f}cm\n")
                        f.write(f"  横向偏移: {offset_x:.1f}cm {'(偏左)' if offset_x < 0 else '(偏右)' if offset_x > 0 else '(居中)'}\n")
                        f.write(f"  纵向偏移: {offset_y:.1f}cm {'(偏前)' if offset_y < 0 else '(偏后)' if offset_y > 0 else '(居中)'}\n")
                        
                        # 重心评估
                        max_offset = min(self.container.length, self.container.width) * 0.1
                        if abs(offset_x) < max_offset and abs(offset_y) < max_offset:
                            f.write("  评估: ✓ 重心分布良好\n\n")
                        else:
                            f.write("  评估: ⚠ 重心偏移较大，建议调整\n\n")
                        
                        f.write("-" * 70 + "\n")
                        f.write("装载步骤 (按顺序装载):\n")
                        f.write("-" * 70 + "\n\n")
                        
                        for i, p in enumerate(self.placed_cargos, 1):
                            f.write(f"步骤 {i:3d}: {p.cargo.name}\n")
                            f.write(f"  尺寸: {p.cargo.length} × {p.cargo.width} × {p.cargo.height} cm\n")
                            f.write(f"  重量: {p.cargo.weight} kg\n")
                            f.write(f"  位置: X={p.x:.1f}, Y={p.y:.1f}, Z={p.z:.1f} cm\n")
                            f.write(f"  旋转: {'是' if p.rotated else '否'}\n")
                            f.write(f"  加固: {self.get_securing_advice(p, i-1, len(self.placed_cargos))}\n\n")
                        
                        f.write("-" * 70 + "\n")
                        f.write("尾部加固建议:\n")
                        f.write("-" * 70 + "\n")
                        f.write(self.get_tail_securing_advice())
                        f.write("\n")
                        
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
    
    def get_securing_advice(self, placed_cargo, index: int, total: int) -> str:
        """获取单个货物的加固建议"""
        advice = []
        
        # 根据位置给出建议
        if placed_cargo.z == 0:  # 底层
            advice.append("底层固定")
        
        if placed_cargo.cargo.weight > 500:  # 重货
            advice.append("使用绑带固定")
        
        if index >= total - 3:  # 最后几件
            advice.append("尾部加固")
        
        # 根据是否可堆叠
        if not placed_cargo.cargo.stackable:
            advice.append("顶部勿压")
        
        return ", ".join(advice) if advice else "标准加固"
    
    def get_tail_securing_advice(self) -> str:
        """获取尾部加固建议"""
        advice = []
        advice.append("  1. 使用木方或气囊填充尾部空隙")
        advice.append("  2. 最后一排货物使用绑带横向固定")
        advice.append("  3. 如有空隙超过30cm，建议使用充气袋填充")
        advice.append("  4. 重货建议使用钢丝绳加固")
        
        # 根据容器类型添加特定建议
        if hasattr(self, 'container') and self.container:
            if self.container.container_type == "truck":
                advice.append("  5. 货车运输建议使用防滑垫")
                advice.append("  6. 注意轴重分布，重心尽量靠近车轴")
            elif self.container.container_type == "shipping":
                advice.append("  5. 海运建议预留膨胀空间")
                advice.append("  6. 注意集装箱门端加固，防止开门时货物倾倒")
        
        return "\n".join(advice)


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

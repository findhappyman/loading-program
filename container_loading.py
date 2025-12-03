# -*- coding: utf-8 -*-
"""
集装箱配载软件 (Container Loading Software)
功能：优化货物在集装箱中的装载位置，最大化空间利用率
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional
import copy


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
    color: str = "#4CAF50"  # 显示颜色
    
    @property
    def volume(self) -> float:
        """单件体积 (立方厘米)"""
        return self.length * self.width * self.height
    
    @property
    def total_volume(self) -> float:
        """总体积"""
        return self.volume * self.quantity
    
    @property
    def total_weight(self) -> float:
        """总重量"""
        return self.weight * self.quantity


@dataclass
class Container:
    """集装箱类"""
    name: str
    length: float  # 内部长度 (cm)
    width: float   # 内部宽度 (cm)
    height: float  # 内部高度 (cm)
    max_weight: float  # 最大载重 (kg)
    
    @property
    def volume(self) -> float:
        """容积 (立方厘米)"""
        return self.length * self.width * self.height
    
    @property
    def volume_cbm(self) -> float:
        """容积 (立方米)"""
        return self.volume / 1000000


@dataclass
class PlacedCargo:
    """已放置的货物"""
    cargo: Cargo
    x: float  # 放置位置 x
    y: float  # 放置位置 y
    z: float  # 放置位置 z
    rotated: bool = False  # 是否旋转(长宽互换)
    
    @property
    def actual_length(self) -> float:
        return self.cargo.width if self.rotated else self.cargo.length
    
    @property
    def actual_width(self) -> float:
        return self.cargo.length if self.rotated else self.cargo.width


# 标准集装箱尺寸 (内部尺寸，单位：cm)
STANDARD_CONTAINERS = {
    "20英尺标准箱": Container("20英尺标准箱", 589, 234, 238, 21770),
    "40英尺标准箱": Container("40英尺标准箱", 1203, 234, 238, 26680),
    "40英尺高箱": Container("40英尺高箱", 1203, 234, 269, 26460),
    "45英尺高箱": Container("45英尺高箱", 1351, 234, 269, 25600),
}

# 预设颜色
CARGO_COLORS = [
    "#4CAF50", "#2196F3", "#FF9800", "#E91E63", "#9C27B0",
    "#00BCD4", "#FFEB3B", "#795548", "#607D8B", "#F44336",
    "#8BC34A", "#03A9F4", "#FFC107", "#673AB7", "#009688"
]


class LoadingAlgorithm:
    """装载算法类"""
    
    def __init__(self, container: Container):
        self.container = container
        self.placed_cargos: List[PlacedCargo] = []
        self.spaces: List[Tuple[float, float, float, float, float, float]] = []
        # 初始空间：整个集装箱
        self.spaces.append((0, 0, 0, container.length, container.width, container.height))
    
    def can_place(self, cargo: Cargo, x: float, y: float, z: float, rotated: bool) -> bool:
        """检查货物是否可以放置在指定位置"""
        length = cargo.width if rotated else cargo.length
        width = cargo.length if rotated else cargo.width
        height = cargo.height
        
        # 检查是否超出集装箱边界
        if x + length > self.container.length + 0.01:
            return False
        if y + width > self.container.width + 0.01:
            return False
        if z + height > self.container.height + 0.01:
            return False
        
        # 检查是否与已放置的货物重叠
        for placed in self.placed_cargos:
            pl = placed.actual_length
            pw = placed.actual_width
            ph = placed.cargo.height
            
            # 检查是否重叠
            if (x < placed.x + pl and x + length > placed.x and
                y < placed.y + pw and y + width > placed.y and
                z < placed.z + ph and z + height > placed.z):
                return False
        
        # 检查底部支撑 (z > 0 时需要有支撑)
        if z > 0.01:
            support_area = 0
            required_support = length * width * 0.7  # 需要70%的底部支撑
            
            for placed in self.placed_cargos:
                if abs(placed.z + placed.cargo.height - z) < 0.01:
                    # 计算重叠面积
                    pl = placed.actual_length
                    pw = placed.actual_width
                    
                    overlap_x = max(0, min(x + length, placed.x + pl) - max(x, placed.x))
                    overlap_y = max(0, min(y + width, placed.y + pw) - max(y, placed.y))
                    support_area += overlap_x * overlap_y
            
            if support_area < required_support:
                return False
        
        return True
    
    def find_position(self, cargo: Cargo) -> Optional[Tuple[float, float, float, bool]]:
        """找到货物的最佳放置位置"""
        best_position = None
        best_score = float('inf')
        
        # 收集所有可能的放置点
        positions = [(0, 0, 0)]
        
        for placed in self.placed_cargos:
            pl = placed.actual_length
            pw = placed.actual_width
            ph = placed.cargo.height
            
            # 在已放置货物的右边
            positions.append((placed.x + pl, placed.y, placed.z))
            # 在已放置货物的前面
            positions.append((placed.x, placed.y + pw, placed.z))
            # 在已放置货物的上面
            if placed.cargo.stackable:
                positions.append((placed.x, placed.y, placed.z + ph))
        
        # 尝试每个位置和旋转状态
        for x, y, z in positions:
            for rotated in [False, True]:
                if self.can_place(cargo, x, y, z, rotated):
                    # 评分：优先选择靠近原点的位置
                    score = x + y * 2 + z * 3
                    if score < best_score:
                        best_score = score
                        best_position = (x, y, z, rotated)
        
        return best_position
    
    def place_cargo(self, cargo: Cargo) -> bool:
        """放置货物"""
        position = self.find_position(cargo)
        if position:
            x, y, z, rotated = position
            placed = PlacedCargo(cargo, x, y, z, rotated)
            self.placed_cargos.append(placed)
            return True
        return False
    
    def load_all(self, cargos: List[Cargo]) -> Tuple[List[PlacedCargo], List[Cargo]]:
        """装载所有货物"""
        # 按体积从大到小排序
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
        """获取装载统计信息"""
        total_cargo_volume = sum(
            p.cargo.volume for p in self.placed_cargos
        )
        total_cargo_weight = sum(
            p.cargo.weight for p in self.placed_cargos
        )
        
        return {
            "loaded_count": len(self.placed_cargos),
            "total_volume": total_cargo_volume,
            "volume_utilization": (total_cargo_volume / self.container.volume) * 100,
            "total_weight": total_cargo_weight,
            "weight_utilization": (total_cargo_weight / self.container.max_weight) * 100,
        }


class ContainerLoadingApp:
    """集装箱配载软件主界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("集装箱配载软件 v1.0")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # 数据
        self.cargos: List[Cargo] = []
        self.container: Optional[Container] = None
        self.placed_cargos: List[PlacedCargo] = []
        self.color_index = 0
        
        # 视图参数
        self.view_angle = 0
        self.zoom = 1.0
        
        self.setup_ui()
        self.setup_default_container()
    
    def setup_ui(self):
        """设置界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板
        left_panel = ttk.Frame(main_frame, width=400)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # 右侧面板
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # === 左侧面板内容 ===
        
        # 集装箱选择
        container_frame = ttk.LabelFrame(left_panel, text="集装箱选择", padding="10")
        container_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.container_var = tk.StringVar()
        container_combo = ttk.Combobox(
            container_frame, 
            textvariable=self.container_var,
            values=list(STANDARD_CONTAINERS.keys()),
            state="readonly",
            width=35
        )
        container_combo.pack(fill=tk.X)
        container_combo.bind("<<ComboboxSelected>>", self.on_container_selected)
        
        # 集装箱信息
        self.container_info = ttk.Label(container_frame, text="", justify=tk.LEFT)
        self.container_info.pack(fill=tk.X, pady=(5, 0))
        
        # 货物添加
        cargo_frame = ttk.LabelFrame(left_panel, text="添加货物", padding="10")
        cargo_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 货物名称
        ttk.Label(cargo_frame, text="货物名称:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cargo_name_var = tk.StringVar(value="货物1")
        ttk.Entry(cargo_frame, textvariable=self.cargo_name_var, width=20).grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=2)
        
        # 尺寸
        ttk.Label(cargo_frame, text="长度(cm):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.cargo_length_var = tk.StringVar(value="100")
        ttk.Entry(cargo_frame, textvariable=self.cargo_length_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(cargo_frame, text="宽度(cm):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.cargo_width_var = tk.StringVar(value="80")
        ttk.Entry(cargo_frame, textvariable=self.cargo_width_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(cargo_frame, text="高度(cm):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.cargo_height_var = tk.StringVar(value="60")
        ttk.Entry(cargo_frame, textvariable=self.cargo_height_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # 重量和数量
        ttk.Label(cargo_frame, text="重量(kg):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.cargo_weight_var = tk.StringVar(value="50")
        ttk.Entry(cargo_frame, textvariable=self.cargo_weight_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(cargo_frame, text="数量:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.cargo_quantity_var = tk.StringVar(value="10")
        ttk.Entry(cargo_frame, textvariable=self.cargo_quantity_var, width=10).grid(row=5, column=1, sticky=tk.W, pady=2)
        
        # 可堆叠选项
        self.cargo_stackable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cargo_frame, text="可堆叠", variable=self.cargo_stackable_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # 添加按钮
        ttk.Button(cargo_frame, text="添加货物", command=self.add_cargo).grid(row=7, column=0, columnspan=3, pady=10)
        
        cargo_frame.columnconfigure(1, weight=1)
        
        # 货物列表
        list_frame = ttk.LabelFrame(left_panel, text="货物列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建表格
        columns = ("name", "size", "weight", "qty", "volume")
        self.cargo_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self.cargo_tree.heading("name", text="名称")
        self.cargo_tree.heading("size", text="尺寸(cm)")
        self.cargo_tree.heading("weight", text="重量(kg)")
        self.cargo_tree.heading("qty", text="数量")
        self.cargo_tree.heading("volume", text="总体积(m³)")
        
        self.cargo_tree.column("name", width=80)
        self.cargo_tree.column("size", width=100)
        self.cargo_tree.column("weight", width=60)
        self.cargo_tree.column("qty", width=40)
        self.cargo_tree.column("volume", width=70)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cargo_tree.yview)
        self.cargo_tree.configure(yscrollcommand=scrollbar.set)
        
        self.cargo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 列表操作按钮
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="删除选中", command=self.delete_cargo).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_cargos).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="导入", command=self.import_cargos).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="导出", command=self.export_cargos).pack(side=tk.LEFT, padx=2)
        
        # 配载按钮
        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill=tk.X)
        
        ttk.Button(action_frame, text="开始配载", command=self.start_loading, style="Accent.TButton").pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="清除配载结果", command=self.clear_loading).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="导出配载方案", command=self.export_loading_plan).pack(fill=tk.X, pady=2)
        
        # === 右侧面板内容 ===
        
        # 3D视图
        view_frame = ttk.LabelFrame(right_panel, text="3D配载视图", padding="5")
        view_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 画布
        self.canvas = tk.Canvas(view_frame, bg="white", width=800, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 视图控制
        control_frame = ttk.Frame(view_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text="视角:").pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="◀", width=3, command=lambda: self.rotate_view(-15)).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="▶", width=3, command=lambda: self.rotate_view(15)).pack(side=tk.LEFT)
        ttk.Label(control_frame, text="缩放:").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Button(control_frame, text="+", width=3, command=lambda: self.zoom_view(1.2)).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="-", width=3, command=lambda: self.zoom_view(0.8)).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="重置视图", command=self.reset_view).pack(side=tk.LEFT, padx=20)
        
        # 统计信息
        stats_frame = ttk.LabelFrame(right_panel, text="配载统计", padding="10")
        stats_frame.pack(fill=tk.X)
        
        self.stats_label = ttk.Label(stats_frame, text="请先添加货物并开始配载", font=("Arial", 10))
        self.stats_label.pack(fill=tk.X)
        
        # 进度条
        ttk.Label(stats_frame, text="空间利用率:").pack(anchor=tk.W, pady=(10, 0))
        self.volume_progress = ttk.Progressbar(stats_frame, mode="determinate", maximum=100)
        self.volume_progress.pack(fill=tk.X, pady=2)
        
        ttk.Label(stats_frame, text="载重利用率:").pack(anchor=tk.W, pady=(5, 0))
        self.weight_progress = ttk.Progressbar(stats_frame, mode="determinate", maximum=100)
        self.weight_progress.pack(fill=tk.X, pady=2)
    
    def setup_default_container(self):
        """设置默认集装箱"""
        self.container_var.set("40英尺标准箱")
        self.on_container_selected(None)
    
    def on_container_selected(self, event):
        """集装箱选择事件"""
        name = self.container_var.get()
        self.container = STANDARD_CONTAINERS.get(name)
        if self.container:
            info = f"内部尺寸: {self.container.length}×{self.container.width}×{self.container.height} cm\n"
            info += f"容积: {self.container.volume_cbm:.1f} m³  |  最大载重: {self.container.max_weight} kg"
            self.container_info.config(text=info)
            self.draw_container()
    
    def get_next_color(self) -> str:
        """获取下一个颜色"""
        color = CARGO_COLORS[self.color_index % len(CARGO_COLORS)]
        self.color_index += 1
        return color
    
    def add_cargo(self):
        """添加货物"""
        try:
            cargo = Cargo(
                name=self.cargo_name_var.get(),
                length=float(self.cargo_length_var.get()),
                width=float(self.cargo_width_var.get()),
                height=float(self.cargo_height_var.get()),
                weight=float(self.cargo_weight_var.get()),
                quantity=int(self.cargo_quantity_var.get()),
                stackable=self.cargo_stackable_var.get(),
                color=self.get_next_color()
            )
            
            if cargo.length <= 0 or cargo.width <= 0 or cargo.height <= 0:
                raise ValueError("尺寸必须大于0")
            if cargo.weight <= 0:
                raise ValueError("重量必须大于0")
            if cargo.quantity <= 0:
                raise ValueError("数量必须大于0")
            
            self.cargos.append(cargo)
            self.update_cargo_list()
            
            # 更新默认名称
            self.cargo_name_var.set(f"货物{len(self.cargos) + 1}")
            
        except ValueError as e:
            messagebox.showerror("错误", f"输入无效: {e}")
    
    def update_cargo_list(self):
        """更新货物列表显示"""
        self.cargo_tree.delete(*self.cargo_tree.get_children())
        for cargo in self.cargos:
            size = f"{cargo.length}×{cargo.width}×{cargo.height}"
            volume = cargo.total_volume / 1000000  # 转换为立方米
            self.cargo_tree.insert("", tk.END, values=(
                cargo.name, size, cargo.weight, cargo.quantity, f"{volume:.3f}"
            ))
    
    def delete_cargo(self):
        """删除选中的货物"""
        selected = self.cargo_tree.selection()
        if selected:
            index = self.cargo_tree.index(selected[0])
            del self.cargos[index]
            self.update_cargo_list()
    
    def clear_cargos(self):
        """清空货物列表"""
        if messagebox.askyesno("确认", "确定要清空货物列表吗？"):
            self.cargos.clear()
            self.color_index = 0
            self.update_cargo_list()
    
    def import_cargos(self):
        """导入货物"""
        filename = filedialog.askopenfilename(
            title="导入货物",
            filetypes=[("JSON文件", "*.json")]
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.cargos = [Cargo(**item) for item in data]
                self.update_cargo_list()
                messagebox.showinfo("成功", f"成功导入 {len(self.cargos)} 种货物")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")
    
    def export_cargos(self):
        """导出货物"""
        if not self.cargos:
            messagebox.showwarning("警告", "没有货物可导出")
            return
        
        filename = filedialog.asksaveasfilename(
            title="导出货物",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")]
        )
        if filename:
            try:
                data = [asdict(cargo) for cargo in self.cargos]
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", "货物导出成功")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
    
    def start_loading(self):
        """开始配载"""
        if not self.container:
            messagebox.showwarning("警告", "请先选择集装箱")
            return
        
        if not self.cargos:
            messagebox.showwarning("警告", "请先添加货物")
            return
        
        # 检查总重量
        total_weight = sum(c.total_weight for c in self.cargos)
        if total_weight > self.container.max_weight:
            messagebox.showwarning("警告", 
                f"货物总重量({total_weight:.1f}kg)超过集装箱载重限制({self.container.max_weight}kg)")
        
        # 执行配载算法
        algorithm = LoadingAlgorithm(self.container)
        loaded, not_loaded = algorithm.load_all(self.cargos)
        
        self.placed_cargos = loaded
        
        # 更新统计信息
        stats = algorithm.get_statistics()
        
        stats_text = f"已装载: {stats['loaded_count']} 件  |  "
        stats_text += f"未装载: {len(not_loaded)} 件  |  "
        stats_text += f"总体积: {stats['total_volume']/1000000:.2f} m³  |  "
        stats_text += f"总重量: {stats['total_weight']:.1f} kg"
        
        self.stats_label.config(text=stats_text)
        self.volume_progress["value"] = stats["volume_utilization"]
        self.weight_progress["value"] = stats["weight_utilization"]
        
        # 绘制结果
        self.draw_container()
        
        if not_loaded:
            cargo_names = ", ".join(set(c.name for c in not_loaded))
            messagebox.showinfo("配载完成", 
                f"配载完成！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%\n\n"
                f"有 {len(not_loaded)} 件货物无法装入:\n{cargo_names}")
        else:
            messagebox.showinfo("配载完成", 
                f"所有货物已成功装载！\n\n"
                f"空间利用率: {stats['volume_utilization']:.1f}%\n"
                f"载重利用率: {stats['weight_utilization']:.1f}%")
    
    def clear_loading(self):
        """清除配载结果"""
        self.placed_cargos.clear()
        self.stats_label.config(text="请先添加货物并开始配载")
        self.volume_progress["value"] = 0
        self.weight_progress["value"] = 0
        self.draw_container()
    
    def export_loading_plan(self):
        """导出配载方案"""
        if not self.placed_cargos:
            messagebox.showwarning("警告", "没有配载结果可导出")
            return
        
        filename = filedialog.asksaveasfilename(
            title="导出配载方案",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json")]
        )
        if filename:
            try:
                if filename.endswith(".json"):
                    data = {
                        "container": asdict(self.container),
                        "placements": [
                            {
                                "cargo": asdict(p.cargo),
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
                        f.write("=" * 60 + "\n")
                        f.write("集装箱配载方案\n")
                        f.write("=" * 60 + "\n\n")
                        
                        f.write(f"集装箱: {self.container.name}\n")
                        f.write(f"内部尺寸: {self.container.length}×{self.container.width}×{self.container.height} cm\n")
                        f.write(f"容积: {self.container.volume_cbm:.1f} m³\n")
                        f.write(f"最大载重: {self.container.max_weight} kg\n\n")
                        
                        f.write("-" * 60 + "\n")
                        f.write("装载明细:\n")
                        f.write("-" * 60 + "\n\n")
                        
                        for i, p in enumerate(self.placed_cargos, 1):
                            f.write(f"{i}. {p.cargo.name}\n")
                            f.write(f"   尺寸: {p.cargo.length}×{p.cargo.width}×{p.cargo.height} cm\n")
                            f.write(f"   重量: {p.cargo.weight} kg\n")
                            f.write(f"   位置: X={p.x:.1f}, Y={p.y:.1f}, Z={p.z:.1f}\n")
                            f.write(f"   旋转: {'是' if p.rotated else '否'}\n\n")
                        
                        total_volume = sum(p.cargo.volume for p in self.placed_cargos)
                        total_weight = sum(p.cargo.weight for p in self.placed_cargos)
                        
                        f.write("-" * 60 + "\n")
                        f.write(f"统计信息:\n")
                        f.write(f"  装载件数: {len(self.placed_cargos)}\n")
                        f.write(f"  总体积: {total_volume/1000000:.2f} m³\n")
                        f.write(f"  空间利用率: {(total_volume/self.container.volume)*100:.1f}%\n")
                        f.write(f"  总重量: {total_weight:.1f} kg\n")
                        f.write(f"  载重利用率: {(total_weight/self.container.max_weight)*100:.1f}%\n")
                
                messagebox.showinfo("成功", "配载方案导出成功")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
    
    def rotate_view(self, angle):
        """旋转视图"""
        self.view_angle = (self.view_angle + angle) % 360
        self.draw_container()
    
    def zoom_view(self, factor):
        """缩放视图"""
        self.zoom = max(0.3, min(3.0, self.zoom * factor))
        self.draw_container()
    
    def reset_view(self):
        """重置视图"""
        self.view_angle = 0
        self.zoom = 1.0
        self.draw_container()
    
    def draw_container(self):
        """绘制集装箱和货物"""
        self.canvas.delete("all")
        
        if not self.container:
            return
        
        # 获取画布尺寸
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # 计算缩放比例
        import math
        angle_rad = math.radians(self.view_angle)
        
        # 等轴测投影参数
        cos_a = math.cos(angle_rad + math.pi/6)
        sin_a = math.sin(angle_rad + math.pi/6)
        
        # 计算集装箱在屏幕上的尺寸
        scale = min(
            canvas_width * 0.6 / (self.container.length + self.container.width),
            canvas_height * 0.6 / (self.container.height + self.container.width * 0.5)
        ) * self.zoom
        
        # 中心点
        cx = canvas_width / 2
        cy = canvas_height / 2 + self.container.height * scale * 0.2
        
        def project(x, y, z):
            """3D到2D投影"""
            # 旋转
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            
            # 等轴测投影
            px = cx + (rx - ry) * scale * 0.7
            py = cy - z * scale * 0.8 + (rx + ry) * scale * 0.3
            return px, py
        
        def draw_box(x, y, z, l, w, h, fill_color, outline_color="#333"):
            """绘制3D盒子"""
            # 8个顶点
            vertices = [
                (x, y, z),           # 0: 左下前
                (x + l, y, z),       # 1: 右下前
                (x + l, y + w, z),   # 2: 右下后
                (x, y + w, z),       # 3: 左下后
                (x, y, z + h),       # 4: 左上前
                (x + l, y, z + h),   # 5: 右上前
                (x + l, y + w, z + h), # 6: 右上后
                (x, y + w, z + h),   # 7: 左上后
            ]
            
            projected = [project(*v) for v in vertices]
            
            # 绘制可见面 (根据视角)
            faces = []
            
            # 顶面
            top_face = [projected[4], projected[5], projected[6], projected[7]]
            faces.append((top_face, self.lighten_color(fill_color, 1.2)))
            
            # 根据视角决定绘制哪些侧面
            if cos_a >= 0:
                # 前面
                front_face = [projected[0], projected[1], projected[5], projected[4]]
                faces.append((front_face, fill_color))
            else:
                # 后面
                back_face = [projected[2], projected[3], projected[7], projected[6]]
                faces.append((back_face, fill_color))
            
            if sin_a >= 0:
                # 右面
                right_face = [projected[1], projected[2], projected[6], projected[5]]
                faces.append((right_face, self.darken_color(fill_color, 0.8)))
            else:
                # 左面
                left_face = [projected[0], projected[3], projected[7], projected[4]]
                faces.append((left_face, self.darken_color(fill_color, 0.8)))
            
            # 绘制面
            for face, color in faces:
                points = [coord for point in face for coord in point]
                self.canvas.create_polygon(points, fill=color, outline=outline_color, width=1)
        
        # 绘制集装箱轮廓
        draw_box(0, 0, 0, self.container.length, self.container.width, self.container.height,
                "#E0E0E0", "#666")
        
        # 绘制已放置的货物 (从后往前绘制)
        sorted_cargos = sorted(self.placed_cargos, 
            key=lambda p: -(p.x * sin_a + p.y * cos_a + p.z))
        
        for placed in sorted_cargos:
            draw_box(
                placed.x, placed.y, placed.z,
                placed.actual_length, placed.actual_width, placed.cargo.height,
                placed.cargo.color
            )
        
        # 绘制坐标轴
        origin = project(0, 0, 0)
        x_end = project(100, 0, 0)
        y_end = project(0, 100, 0)
        z_end = project(0, 0, 100)
        
        self.canvas.create_line(origin[0], origin[1], x_end[0], x_end[1], fill="red", width=2, arrow=tk.LAST)
        self.canvas.create_line(origin[0], origin[1], y_end[0], y_end[1], fill="green", width=2, arrow=tk.LAST)
        self.canvas.create_line(origin[0], origin[1], z_end[0], z_end[1], fill="blue", width=2, arrow=tk.LAST)
        
        self.canvas.create_text(x_end[0] + 10, x_end[1], text="X(长)", fill="red")
        self.canvas.create_text(y_end[0] + 10, y_end[1], text="Y(宽)", fill="green")
        self.canvas.create_text(z_end[0] + 10, z_end[1], text="Z(高)", fill="blue")
        
        # 显示图例
        if self.placed_cargos:
            legend_x = 20
            legend_y = 20
            shown_cargos = {}
            
            for p in self.placed_cargos:
                if p.cargo.name not in shown_cargos:
                    shown_cargos[p.cargo.name] = p.cargo.color
            
            for name, color in shown_cargos.items():
                self.canvas.create_rectangle(legend_x, legend_y, legend_x + 20, legend_y + 15, 
                                           fill=color, outline="#333")
                self.canvas.create_text(legend_x + 25, legend_y + 7, text=name, anchor=tk.W)
                legend_y += 20
    
    def lighten_color(self, color, factor):
        """使颜色变亮"""
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def darken_color(self, color, factor):
        """使颜色变暗"""
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"


def main():
    root = tk.Tk()
    app = ContainerLoadingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

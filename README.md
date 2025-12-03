# 集装箱配载软件 (Container Loading Software)

一个现代化的集装箱货物配载优化软件，使用 PyQt6 + OpenGL 实现可交互的3D可视化界面。

## ✨ 功能特点

- 🚢 支持标准集装箱类型（20GP/40GP/40HC/45HC）
- 📦 智能3D装箱算法，优化空间利用率
- 🎮 可拖动旋转的3D视图（鼠标左键旋转，滚轮缩放，右键平移）
- 📊 实时显示空间利用率和载重利用率
- 📥 支持 Excel/JSON 格式导入导出货物数据
- 📋 导出详细的配载方案

## 🖥️ 界面预览

- 现代深色UI设计
- OpenGL 3D渲染，支持光照效果
- 多视角切换（正视/后视/左视/右视/俯视/等轴）

## 📋 系统要求

- Python 3.8+
- Windows / macOS / Linux

## 🚀 安装与运行

### 方式一：从源码运行

```bash
# 克隆仓库
git clone https://github.com/yourusername/container-loading.git
cd container-loading

# 安装依赖
pip install -r requirements.txt

# 运行程序
python container_loading_modern.py
```

### 方式二：运行可执行文件

下载 `dist/集装箱配载软件.exe` 直接运行（仅Windows）

## 📦 依赖库

- PyQt6 - 现代UI框架
- PyOpenGL - 3D渲染
- numpy - 数值计算
- openpyxl - Excel文件支持

## 📖 使用说明

1. **选择集装箱**：从下拉菜单选择集装箱类型
2. **添加货物**：输入货物尺寸、重量、数量，点击"添加货物"
3. **开始配载**：点击"开始配载"按钮，系统自动计算最优装载方案
4. **查看结果**：拖动3D视图查看装载效果，查看利用率统计
5. **导出方案**：可导出配载方案为TXT或JSON格式

### Excel导入格式

| 货物名称 | 长度(cm) | 宽度(cm) | 高度(cm) | 重量(kg) | 数量 | 可堆叠 |
|---------|---------|---------|---------|---------|------|-------|
| 货物1   | 100     | 80      | 60      | 50      | 10   | 是    |

## 🔧 打包为可执行文件

```bash
pip install pyinstaller
pyinstaller --name="集装箱配载软件" --windowed --onefile container_loading_modern.py
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

#!/bin/bash
# 集装箱配载软件 - Linux 打包脚本

echo "========================================"
echo "  集装箱配载软件 - Linux 打包脚本"
echo "========================================"
echo ""

# 检查是否存在虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "错误: 无法创建虚拟环境"
        exit 1
    fi
else
    echo "[1/4] 使用现有虚拟环境"
fi

echo ""
echo "[2/4] 激活虚拟环境..."
source venv/bin/activate

echo ""
echo "[3/4] 安装依赖..."
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt

echo ""
echo "[4/4] 开始打包..."
pyinstaller --onefile --windowed --name "ContainerLoading" --icon=assets/icon.png --clean container_loading_modern.py

echo ""
echo "========================================"
if [ -f "dist/ContainerLoading" ]; then
    echo "✓ 打包完成！"
    echo ""
    echo "可执行文件位置: dist/ContainerLoading"
    echo ""
    ls -lh dist/ContainerLoading
else
    echo "✗ 打包失败，请检查错误信息"
fi
echo "========================================"

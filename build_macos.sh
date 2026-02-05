#!/bin/bash
# 集装箱配载软件 - macOS 打包脚本

echo "========================================"
echo "  集装箱配载软件 - macOS 打包脚本"
echo "========================================"
echo ""

# 检查是否存在虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/6] 创建虚拟环境..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "错误: 无法创建虚拟环境"
        exit 1
    fi
else
    echo "[1/6] 使用现有虚拟环境"
fi

echo ""
echo "[2/6] 激活虚拟环境..."
source venv/bin/activate

echo ""
echo "[3/6] 安装依赖..."
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt

echo ""
echo "[4/6] 开始打包..."
pyinstaller --onefile --windowed --name "ContainerLoading" --icon=assets/icon.icns --clean container_loading_modern.py

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "✗ 打包失败，请检查错误信息"
    echo "========================================"
    exit 1
fi

echo ""
echo "[5/6] 创建 macOS app bundle..."

# 创建.app结构
mkdir -p ContainerLoading.app/Contents/MacOS
mkdir -p ContainerLoading.app/Contents/Resources

# 复制可执行文件
cp dist/ContainerLoading ContainerLoading.app/Contents/MacOS/

# 创建Info.plist
cat > ContainerLoading.app/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ContainerLoading</string>
    <key>CFBundleIdentifier</key>
    <string>com.containerloading.app</string>
    <key>CFBundleName</key>
    <string>ContainerLoading</string>
    <key>CFBundleDisplayName</key>
    <string>集装箱配载软件</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
EOF

# 复制图标
if [ -f "assets/icon.icns" ]; then
    cp assets/icon.icns ContainerLoading.app/Contents/Resources/AppIcon.icns
fi

echo ""
echo "[6/6] 创建 DMG 安装包..."

# 创建临时DMG目录
rm -rf dmg_temp
mkdir -p dmg_temp

# 复制.app到DMG目录
cp -R ContainerLoading.app dmg_temp/

# 创建符号链接到Applications
ln -s /Applications dmg_temp/Applications

# 复制文档
cp README.md dmg_temp/ 2>/dev/null || true
cp CHANGELOG.md dmg_temp/ 2>/dev/null || true
cp FEATURES.md dmg_temp/ 2>/dev/null || true

# 创建DMG
hdiutil create -volname "ContainerLoading" -srcfolder dmg_temp -ov -format UDZO ContainerLoading.dmg

# 清理临时目录
rm -rf dmg_temp

echo ""
echo "========================================"
if [ -f "ContainerLoading.dmg" ]; then
    echo "✓ 打包完成！"
    echo ""
    echo "生成的文件:"
    echo "  - dist/ContainerLoading (可执行文件)"
    echo "  - ContainerLoading.app (应用包)"
    echo "  - ContainerLoading.dmg (安装包)"
    echo ""
    ls -lh ContainerLoading.dmg ContainerLoading.app
else
    echo "✗ 打包失败"
fi
echo "========================================"

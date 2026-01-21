@echo off
chcp 65001 > nul
echo ========================================
echo   集装箱配载软件 - Windows 打包脚本
echo ========================================
echo.

REM 检查是否存在虚拟环境
if not exist "venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo 错误: 无法创建虚拟环境
        pause
        exit /b 1
    )
) else (
    echo [1/4] 使用现有虚拟环境
)

echo.
echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat

echo.
echo [3/4] 安装依赖...
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt

echo.
echo [4/4] 开始打包...
pyinstaller --onefile --windowed --name "ContainerLoading" --icon=assets/icon.ico --clean container_loading_modern.py

echo.
echo ========================================
if exist "dist\ContainerLoading.exe" (
    echo ✓ 打包完成！
    echo.
    echo 可执行文件位置: dist\ContainerLoading.exe
    echo.
    dir dist\ContainerLoading.exe
) else (
    echo ✗ 打包失败，请检查错误信息
)
echo ========================================
pause

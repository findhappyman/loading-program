@echo off
chcp 65001 > nul
echo ========================================
echo   集装箱配载软件 - 打包脚本
echo ========================================
echo.
echo 正在打包，请稍候...
echo.

pyinstaller --onefile --windowed --name "ContainerLoading" --clean container_loading_modern.py

echo.
echo ========================================
if exist "dist\ContainerLoading.exe" (
    echo 打包完成！
    echo 可执行文件位置: dist\ContainerLoading.exe
    echo.
    dir dist\ContainerLoading.exe
) else (
    echo 打包失败，请检查错误信息
)
echo ========================================
pause

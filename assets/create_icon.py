#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建应用图标
白色网格背景 + 箱子emoji
"""

from PIL import Image, ImageDraw, ImageFont
import os

# 创建assets目录
os.makedirs("assets", exist_ok=True)

# 图标尺寸
SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]

def create_icon(size):
    """创建指定尺寸的图标"""
    # 创建白色背景
    img = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 绘制网格
    grid_spacing = max(size // 8, 4)
    grid_color = (220, 220, 220, 255)

    # 垂直线
    for x in range(0, size, grid_spacing):
        draw.line([(x, 0), (x, size)], fill=grid_color, width=1)

    # 水平线
    for y in range(0, size, grid_spacing):
        draw.line([(0, y), (size, y)], fill=grid_color, width=1)

    # 绘制箱子 (简单的3D效果箱子)
    # 箱子的主体
    box_size = int(size * 0.5)
    box_x = (size - box_size) // 2
    box_y = (size - box_size) // 2 + int(size * 0.05)

    # 箱子正面 (棕色)
    brown_color = (205, 133, 63, 255)  # Peru brown
    dark_brown = (139, 69, 19, 255)    # Saddle brown

    # 正面
    draw.rectangle([box_x, box_y, box_x + box_size, box_y + box_size],
                   fill=brown_color, outline=dark_brown, width=max(2, size // 64))

    # 顶面 (较浅的棕色，透视效果)
    top_height = int(box_size * 0.3)
    top_points = [
        (box_x, box_y),
        (box_x + box_size, box_y),
        (box_x + box_size - int(box_size * 0.15), box_y - top_height),
        (box_x - int(box_size * 0.15), box_y - top_height)
    ]
    draw.polygon(top_points, fill=(245, 222, 179, 255), outline=dark_brown,
                 width=max(2, size // 64))

    # 侧面 (中等棕色)
    side_points = [
        (box_x + box_size, box_y),
        (box_x + box_size - int(box_size * 0.15), box_y - top_height),
        (box_x + box_size - int(box_size * 0.15), box_y + box_size - top_height),
        (box_x + box_size, box_y + box_size)
    ]
    draw.polygon(side_points, fill=(160, 82, 45, 255), outline=dark_brown,
                 width=max(2, size // 64))

    # 绘制箱子边框加强线
    # 垂直交叉线
    center_x = box_x + box_size // 2
    center_y = box_y + box_size // 2
    line_width = max(2, size // 128)

    # 垂直线
    draw.line([(box_x, box_y), (box_x, box_y + box_size)],
               fill=dark_brown, width=line_width)
    draw.line([(box_x + box_size, box_y), (box_x + box_size, box_y + box_size)],
               fill=dark_brown, width=line_width)

    # 水平线
    draw.line([(box_x, box_y), (box_x + box_size, box_y)],
               fill=dark_brown, width=line_width)
    draw.line([(box_x, box_y + box_size // 2), (box_x + box_size, box_y + box_size // 2)],
               fill=dark_brown, width=line_width)
    draw.line([(box_x, box_y + box_size), (box_x + box_size, box_y + box_size)],
               fill=dark_brown, width=line_width)

    return img

def create_ico():
    """创建Windows ICO文件"""
    print("创建 icon.ico...")
    from PIL import Image

    images = []
    for size in [16, 32, 48, 256]:
        img = create_icon(size)
        images.append(img)

    # 保存为ICO
    ico_img = images[-1]
    ico_img.save("assets/icon.ico", format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print("  -> assets/icon.ico")

def create_icns():
    """创建macOS ICNS文件"""
    print("创建 icon.icns...")

    # macOS需要的尺寸
    iconset_dir = "assets/icon.iconset"
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = {
        "icon_16x16.png": 16,
        "icon_32x16.png": 32,  # Retina
        "icon_16x32.png": 16,  # Retina
        "icon_32x32.png": 32,
        "icon_128x16.png": 128,
        "icon_256x16.png": 256,  # Retina
        "icon_128x32.png": 128,
        "icon_256x32.png": 256,  # Retina
        "icon_128x128.png": 128,
        "icon_256x256.png": 256,
        "icon_256x128.png": 256,
        "icon_512x128.png": 512,  # Retina
        "icon_256x256.png": 256,
        "icon_512x256.png": 512,  # Retina
        "icon_512x512.png": 512,
        "icon_1024x512.png": 1024,  # Retina
    }

    for filename, size in [(f"icon_{x}x{x}.png", x) for x in [16, 32, 128, 256, 512, 1024]]:
        img = create_icon(size)
        img.save(f"{iconset_dir}/{filename}", format='PNG')
        if size >= 32:
            img_2x = create_icon(size * 2)
            img_2x.save(f"{iconset_dir}/icon_{size}x{size}@2x.png", format='PNG')

    # 使用iconutil创建ICNS (仅在macOS上)
    import subprocess
    try:
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', 'assets/icon.icns'],
                       check=True, capture_output=True)
        print("  -> assets/icon.icns")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  警告: iconutil不可用，ICNS将使用PIL创建")
        # 备用方案：创建单个大尺寸PNG
        img = create_icon(1024)
        img.save("assets/icon.png", format='PNG')
        print("  -> assets/icon.png (备用)")

def create_png():
    """创建PNG图标"""
    print("创建 icon.png...")
    img = create_icon(1024)
    img.save("assets/icon.png", format='PNG')
    print("  -> assets/icon.png")

def create_favicon():
    """创建网站favicon"""
    print("创建 favicon.ico...")
    img = create_icon(32)
    img.save("assets/favicon.ico", format='ICO')
    print("  -> assets/favicon.ico")

if __name__ == "__main__":
    print("========================================")
    print("  生成应用图标")
    print("========================================")
    print()

    create_ico()
    create_icns()
    create_png()
    create_favicon()

    print()
    print("========================================")
    print("  图标生成完成！")
    print("========================================")

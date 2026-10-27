# 图名匠（PicSmith）

> 让图片命名更顺手

图名匠是一款基于 Tkinter + Pillow 的 Windows 图片重命名桌面工具。选择源文件夹和输出文件夹后，可以逐张预览图片、输入新文件名，并将重命名副本保存到输出目录。

## 功能

- 选择源文件夹和输出文件夹
- 预览 JPG、JPEG、PNG、WEBP 图片
- 大图按窗口大小自动缩放预览
- 输入文件名，可带或不带扩展名，扩展名自动保留
- 点击“下一张”或按 Enter 保存当前图片并进入下一张
- 点击“跳过”不保存当前图片，直接进入下一张
- 点击“上一张”保存当前修改并覆盖输出文件后回退
- 切回已命名的图片时自动回填已保存的文件名
- 点击图片列表切换图片时自动保存当前输入
- 同名输出文件自动覆盖

## 运行

直接运行：

```text
dist/ImageRenamer.exe
```

也可以从源码启动：

```powershell
python image_renamer.py
```

## 使用方法

1. 点击“选择...”指定源文件夹。
2. 点击“选择...”指定输出文件夹。
3. 在右侧预览图片，并在“输出文件名”输入新名称。
4. 点击“下一张”或按 Enter，保存到输出文件夹。
5. 点击“跳过”不保存当前图片，直接进入下一张。
6. 点击“上一张”会先保存当前修改，再返回上一张。

## 打包

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name ImageRenamer --icon app.ico --add-data "app.ico;." image_renamer.py
```

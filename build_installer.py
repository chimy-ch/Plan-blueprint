"""构建「蓝图 Blueprint」的独立程序与安装包。

产物按当前 Python 解释器的位数自动分目录：
    Win64\\Blueprint.exe        —— 64 位独立程序（无需安装 Python）
    Win64\\BlueprintSetup.exe   —— 64 位安装程序（多语言，内嵌上面的程序）
    Win32\\...                  —— 32 位版本（需用 32 位 Python 运行本脚本）

用法：
    python build_installer.py               # 用当前解释器的位数构建
    用 64 位 Python 跑 → 产物进 Win64\\；用 32 位 Python 跑 → 产物进 Win32\\
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IS_64BIT = sys.maxsize > 2 ** 32
ARCH = "Win64" if IS_64BIT else "Win32"

DIST_DIR = os.path.join(HERE, ARCH)
BUILD_DIR = os.path.join(HERE, "build", ARCH.lower())
PAYLOAD_DIR = os.path.join(BUILD_DIR, "payload")
ICON = os.path.join(HERE, "blueprint.ico")
ICONS_SRC = os.path.join(HERE, "icons")


def step(message: str) -> None:
    print(f"\n=== {message} ===", flush=True)


def run(args: list[str]) -> None:
    print(" ".join(args), flush=True)
    subprocess.check_call(args, cwd=HERE)


def pyinstaller(name: str, script: str, add_data: list[tuple[str, str]],
                work: str) -> str:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", name,
        "--icon", ICON,
        "--distpath", DIST_DIR,
        "--workpath", work,
        "--specpath", BUILD_DIR,
    ]
    for source, destination in add_data:
        args += ["--add-data", f"{source}{os.pathsep}{destination}"]
    args.append(script)
    run(args)
    return os.path.join(DIST_DIR, f"{name}.exe")


def build_payload(app_exe: str) -> None:
    step("组装安装包内容 (payload)")
    shutil.rmtree(PAYLOAD_DIR, ignore_errors=True)
    os.makedirs(PAYLOAD_DIR, exist_ok=True)
    shutil.copy2(app_exe, PAYLOAD_DIR)
    shutil.copy2(ICON, PAYLOAD_DIR)
    if os.path.isdir(ICONS_SRC):
        shutil.copytree(ICONS_SRC, os.path.join(PAYLOAD_DIR, "icons"))
    for name in sorted(os.listdir(PAYLOAD_DIR)):
        print("  +", name, flush=True)


def main() -> int:
    bits = "64 位" if IS_64BIT else "32 位"
    step(f"目标架构：{ARCH}（{bits}，解释器 {sys.executable}）")
    os.makedirs(DIST_DIR, exist_ok=True)

    step("打包主程序 Blueprint.exe")
    app_exe = pyinstaller(
        "Blueprint", os.path.join(HERE, "main.py"),
        [(ICON, "."), (ICONS_SRC, "icons")],
        os.path.join(BUILD_DIR, "work-app"),
    )

    build_payload(app_exe)

    step("打包安装程序 BlueprintSetup.exe")
    setup_exe = pyinstaller(
        "BlueprintSetup", os.path.join(HERE, "installer.py"),
        [(PAYLOAD_DIR, "payload")],
        os.path.join(BUILD_DIR, "work-setup"),
    )

    step(f"完成（{ARCH}）")
    for path in (app_exe, setup_exe):
        size = os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else 0
        print(f"  {path}  ({size:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""在桌面创建「蓝图 Blueprint」快捷方式。

用法：
    python install_shortcut.py          # 优先指向打包版 Win64/Win32\\Blueprint.exe
    python install_shortcut.py --dev    # 强制指向源码运行（pythonw main.py）

说明：打包版无需 Python 环境；源码版改完代码即时生效，但需要本机 Python。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "蓝图 Blueprint"
APP_DESC = "蓝图 Blueprint - 计划与记录"
PACKAGED_ARCHES = ("Win64", "Win32")


def _packaged_exe() -> str | None:
    for arch in PACKAGED_ARCHES:
        candidate = os.path.join(HERE, arch, "Blueprint.exe")
        if os.path.exists(candidate):
            return candidate
    return None


def _source_exe() -> str:
    exe = sys.executable or ""
    for name in ("pythonw.exe", "python.exe"):
        candidate = os.path.join(os.path.dirname(exe), name)
        if os.path.exists(candidate):
            return candidate
    return exe


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    script = os.path.join(HERE, "main.py")
    source_icon = os.path.join(HERE, "blueprint.ico")

    packaged = None if "--dev" in sys.argv[1:] else _packaged_exe()
    if packaged:
        target = packaged
        arguments = ""
        workdir = os.path.dirname(packaged)
        icon = packaged + ",0"
        mode = "打包版"
    else:
        if not os.path.exists(script):
            print("找不到 main.py：", script)
            return 1
        target = _source_exe()
        arguments = f'"{script}"'
        workdir = HERE
        icon = source_icon
        mode = "源码版"

    result_file = os.path.join(tempfile.gettempdir(), "blueprint_shortcut_path.txt")
    if os.path.exists(result_file):
        os.remove(result_file)

    ps = f"""$ErrorActionPreference = "Stop"
$outFile = {_ps_quote(result_file)}
$desktop = [Environment]::GetFolderPath("Desktop")
if (-not (Test-Path -LiteralPath $desktop)) {{ throw "找不到桌面目录: $desktop" }}
$lnk = Join-Path $desktop {_ps_quote(APP_NAME + ".lnk")}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = {_ps_quote(target)}
$shortcut.Arguments = {_ps_quote(arguments)}
$shortcut.WorkingDirectory = {_ps_quote(workdir)}
$shortcut.IconLocation = {_ps_quote(icon)}
$shortcut.Description = {_ps_quote(APP_DESC)}
$shortcut.WindowStyle = 1
$shortcut.Save()
if (-not (Test-Path -LiteralPath $lnk)) {{ throw "快捷方式创建失败" }}
[System.IO.File]::WriteAllText($outFile, $lnk, (New-Object System.Text.UTF8Encoding($false)))
"""

    handle, ps_path = tempfile.mkstemp(suffix=".ps1")
    os.close(handle)
    try:
        with open(ps_path, "w", encoding="utf-8-sig") as fh:
            fh.write(ps)

        for shell in ("pwsh.exe", "powershell.exe"):
            try:
                result = subprocess.run(
                    [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                path = ""
                if os.path.exists(result_file):
                    with open(result_file, encoding="utf-8") as fh:
                        path = fh.read().strip()
                    os.remove(result_file)
                print("已创建快捷方式:", path or "（桌面）")
                print("模式:", mode)
                print("目标程序:", target)
                if arguments:
                    print("启动参数:", arguments)
                print("工作目录:", workdir)
                print("图标:", icon)
                return 0
            print(f"{shell} 执行失败")
            print(result.stderr.strip() if result.stderr else "")
        return 1
    finally:
        try:
            os.remove(ps_path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

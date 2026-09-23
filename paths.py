"""统一路径管理。

应用产生的所有数据（数据库、设置、日志、导出文件）统一存放在
「Blueprint configuration file」目录中：

    <应用所在目录>\\Blueprint configuration file\\

- 开发运行：<项目目录>\\Blueprint configuration file\\
- 打包运行：<Blueprint.exe 所在目录>\\Blueprint configuration file\\
- 可用环境变量 BLUEPRINT_CONFIG_DIR 覆盖

若该目录不可写（例如安装在 Program Files 且无权限），会自动回退到
%LOCALAPPDATA%\\Blueprint Blueprint\\Blueprint configuration file\\。
"""

from __future__ import annotations

import os
import shutil
import sys

CONFIG_DIR_NAME = "Blueprint configuration file"
DB_NAME = "planflow.db"
SETTINGS_NAME = "settings.json"
LOG_NAME = "blueprint.log"
EXPORT_DIR_NAME = "导出"
BACKUP_DIR_NAME = "备份"


def app_dir() -> str:
    """可写数据所在根目录：打包后为 exe 所在目录，否则为源码目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """只读资源（图标等）所在目录：打包后为解包临时目录。"""
    return getattr(sys, "_MEIPASS", None) or app_dir()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _writable(path: str) -> bool:
    probe = os.path.join(path, ".write_probe")
    try:
        os.makedirs(path, exist_ok=True)
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_config_dir() -> str:
    override = os.environ.get("BLUEPRINT_CONFIG_DIR")
    if override:
        return os.path.abspath(override)
    primary = os.path.join(app_dir(), CONFIG_DIR_NAME)
    if _writable(primary):
        return primary
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, "Blueprint Blueprint", CONFIG_DIR_NAME)


APP_DIR = app_dir()
RESOURCE_DIR = resource_dir()
CONFIG_DIR = _resolve_config_dir()
CONFIG_DIR_IS_FALLBACK = os.path.normcase(CONFIG_DIR) != os.path.normcase(
    os.path.join(APP_DIR, CONFIG_DIR_NAME)
)

DB_PATH = os.path.join(CONFIG_DIR, DB_NAME)
SETTINGS_PATH = os.path.join(CONFIG_DIR, SETTINGS_NAME)
LOG_PATH = os.path.join(CONFIG_DIR, LOG_NAME)
EXPORT_DIR = os.path.join(CONFIG_DIR, EXPORT_DIR_NAME)
BACKUP_DIR = os.path.join(CONFIG_DIR, BACKUP_DIR_NAME)

ICON_PATH = os.path.join(RESOURCE_DIR, "blueprint.ico")
ICONS_DIR = os.path.join(RESOURCE_DIR, "icons")

# 旧版本把 planflow.db / settings.json 直接放在应用目录，需要迁移
LEGACY_NAMES = (DB_NAME, SETTINGS_NAME)


def icon_uri() -> str:
    """返回可长期引用的图标路径（供 AppUserModelID 注册）。

    冻结版的 ICON_PATH 位于 PyInstaller 的 _MEIxxxx 临时解包目录，
    该目录在进程退出后会被删除，注册到注册表会变成死链。
    绿色版直接用 exe 自身；源码版用项目里的 blueprint.ico。
    """
    return sys.executable if is_frozen() else ICON_PATH


def ensure_config_dir() -> str:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except OSError:
        pass
    return CONFIG_DIR


def _legacy_dirs() -> list[str]:
    dirs = [APP_DIR]
    for env in ("LOCALAPPDATA", "APPDATA"):
        root = os.environ.get(env)
        if not root:
            continue
        for name in ("Blueprint", "Blueprint Blueprint", "planflow", "PlanFlow"):
            dirs.append(os.path.join(root, name))
    return dirs


def migrate_legacy_data() -> list[tuple[str, str]]:
    """把旧位置的数据文件搬到配置目录，返回 [(原路径, 新路径), ...]。"""
    ensure_config_dir()
    moved: list[tuple[str, str]] = []
    for directory in _legacy_dirs():
        for name in LEGACY_NAMES:
            source = os.path.join(directory, name)
            target = os.path.join(CONFIG_DIR, name)
            if os.path.normcase(source) == os.path.normcase(target):
                continue
            if not os.path.isfile(source) or os.path.exists(target):
                continue
            try:
                shutil.move(source, target)
            except OSError:
                continue
            moved.append((source, target))
    return moved


def open_config_dir() -> None:
    ensure_config_dir()
    os.startfile(CONFIG_DIR)  # noqa: S606 - Windows 专用


def summary() -> str:
    return (
        f"配置目录: {CONFIG_DIR}\n"
        f"程序目录: {APP_DIR}\n"
        f"资源目录: {RESOURCE_DIR}\n"
        f"数据库  : {DB_PATH}"
    )


if __name__ == "__main__":
    print(summary())
    moved_items = migrate_legacy_data()
    if moved_items:
        print("已迁移:")
        for source, target in moved_items:
            print(f"  {source}  ->  {target}")
    else:
        print("无需迁移的旧文件")

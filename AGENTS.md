# 蓝图 Blueprint —— 开发说明

计划与记录桌面应用（Python 3.12 + Tkinter，纯标准库，零第三方运行依赖）。

项目根目录：`D:\APP\planflow\`

## 重要：改完应用必须同步安装包

**任何时候修改了应用代码（`app.py` / `db.py` / `theme.py` / `widgets.py` / `tray.py` /
`paths.py` / `startup.py` / `winicon.py` / `single_instance.py` / `main.py` /
`icons/` / `blueprint.ico`），都必须重新构建安装包。**

```powershell
# 0) 先结束可能占用文件的残留进程
Get-Process -Name Blueprint,pythonw,BlueprintSetup -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 800
```

### 构建 Win64（64 位）

```powershell
cd D:\APP\planflow
python build_installer.py
```

### 构建 Win32（32 位）

```powershell
cd D:\APP\planflow
& "C:\Users\babyson\AppData\Local\Programs\Python\Python312-32\python.exe" build_installer.py
```

`build_installer.py` 会按当前解释器的位数自动选择输出目录：

| 解释器 | 产物目录 | 产物 |
| --- | --- | --- |
| 64 位 `Python312` | `D:\APP\planflow\Win64\` | `Blueprint.exe`、`BlueprintSetup.exe` |
| 32 位 `Python312-32` | `D:\APP\planflow\Win32\` | `Blueprint.exe`、`BlueprintSetup.exe` |

中间产物分别位于 `build\win64\` 与 `build\win32\`（可随时删除，会自动重建）。

**两个版本都要构建**，改动才算同步完成。

## 日常运行

```powershell
python main.py            # 源码运行
python main.py --tray     # 静默启动，直接最小化到系统托盘（开机自启动用）
```

## 数据目录

所有用户数据统一位于 **`<应用目录>\Blueprint configuration file\`**：
`planflow.db`、`settings.json`、`blueprint.log`、`导出\`。

- 源码运行：`D:\APP\planflow\Blueprint configuration file\`
- 绿色版运行：对应版本目录下（如 `D:\APP\planflow\Win64\Blueprint configuration file\`）

路径逻辑集中在 `paths.py`（含旧数据自动迁移与 `BLUEPRINT_CONFIG_DIR` 环境变量覆盖）。

当前本机运行的入口是**打包版** `Win64\Blueprint.exe`，因此实际数据目录为
`D:\APP\planflow\Win64\Blueprint configuration file\`。桌面快捷方式与开机自启动
（`HKCU\...\Run\BlueprintBlueprint`）均指向该 exe。

桌面快捷方式由 `install_shortcut.py` 生成：默认优先指向 `Win64\`（其次 `Win32\`）下的
`Blueprint.exe`，加 `--dev` 参数则改为指向源码运行（`pythonw main.py`）。

## 回归测试

测试脚本在 `C:\Users\babyson\AppData\Local\Temp\opencode\`（不在项目内）：

- `pf_theme_test.py` —— 主题/设置开关/字号/日历/几何保存，期望 11/11
- `pf_tray_test.py` —— 托盘与全局热键（Ctrl+Alt+J），期望 10/10
- `pf_installer_test.py` —— 安装/卸载全流程与三语言，期望 30/30
- `pf_single_test.py` —— 源码版单实例保护，期望 5/5
- `pf_frozen_single_test.py` —— 打包版单实例保护，期望 4/4

跑测试前务必先结束残留进程（见上），否则会出现
`PermissionError: [WinError 32]`（db 被占用）或热键 `1409`（已被占用）。

## 单实例保护

`single_instance.py` 用命名互斥体 `Local\BlueprintBlueprint.SingleInstance` 保证同时只有一个副本，
避免出现“多个托盘图标”。第二个实例会调用 `app._wake_existing_instance()` 唤醒已有窗口后自行退出；
`--tray`（开机自启）方式启动则不唤醒，静默退出。

唤醒必须**带重试**：已有实例刚启动时（开机自启与手动双击几乎同时、打包版 onefile 解包需 1–2 秒）
托盘窗口可能尚未建立，此时 `FindWindowW` 会返回 0，一次性唤醒会被静默丢弃。
`app._wake_existing_instance(timeout=15.0)` 每 0.2 秒重试一次直到成功或超时。

另：`winicon.register_app_id()` 注册到 `HKCU\Software\Classes\AppUserModelId\` 的 `IconUri`
必须用 `paths.icon_uri()`（冻结版返回 `sys.executable`，源码版返回项目里的 `blueprint.ico`）。
**不可**直接用 `paths.ICON_PATH` —— 冻结版的它是 PyInstaller 的 `_MEIxxxx` 临时目录，进程退出即删除，注册表会变死链。

## 约定

- 与用户交流、总结一律使用**中文**。
- 不要添加无关注释；改动尽量跟随现有代码风格。

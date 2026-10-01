#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
应用更新：运行形态检测、升级资产选择与升级动作执行。

本模块只做纯逻辑，不依赖 Qt，便于脱离 GUI 单独验证。

四条升级路径（由 detect_install_form() 判定）：

- ``DEV``           开发运行，不下载，只打开 release 页；
- ``WIN_INSTALLED`` Windows 安装版，下载 setup.exe 后静默升级（一次 UAC）；
- ``WIN_PORTABLE``  Windows 绿色版，下载 zip 后由外部脚本原地替换；
- ``MACOS_APP``     macOS，下载 dmg 或 zip 后交给用户替换（二期再做自动替换）。

关于安全边界：用户数据（``<user_data_root>`` 下的 data/resources/templates）
与程序目录完全分离，任何升级路径都不触碰用户数据；绿色版的原地替换也只在
程序目录及其同级备份之间做目录改名。
"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.utils.file_path import get_user_data_root

# ============================ 常量 ============================

WIN_INSTALLER_SUFFIX = "-windows-setup.exe"
WIN_PORTABLE_SUFFIX = "-windows.zip"
MACOS_DMG_SUFFIX = "-macos-setup.dmg"
MACOS_ZIP_SUFFIX = "-macos.zip"

# Inno Setup 生成的卸载程序，作为「安装版」的判定标记。
INNO_UNINSTALLER_NAME = "unins000.exe"

UPDATE_STAGING_DIR_NAME = "updates"
OLD_BACKUP_SUFFIX = ".old"
NEW_STAGING_SUFFIX = ".new"
UPDATE_LOG_NAME = "update.log"
UPDATE_LOG_MAX_BYTES = 256 * 1024

# 替换脚本启动后写下的「我还活着」标记，用于把「脚本根本没执行」这类静默失败暴露出来。
STARTED_MARKER_NAME = "update_script_started"
START_HANDSHAKE_TIMEOUT_SECONDS = 5.0

# 更新脚本等待主进程退出的上限（秒），超时即中止且不动任何文件。
WAIT_EXIT_TIMEOUT_SECONDS = 180

# 目录改名重试：Windows 在主进程退出后仍可能短暂持有目录句柄，
# 一次失败就放弃是错的，必须重试（0.5s × 120 ≈ 60 秒）。
RENAME_RETRY_COUNT = 120
RENAME_RETRY_INTERVAL_MS = 500


class InstallForm(Enum):
    """当前程序的运行形态，决定走哪条升级路径。"""

    DEV = "dev"                     # 开发运行（python main.py）
    WIN_INSTALLED = "win_installed"  # Windows 安装版
    WIN_PORTABLE = "win_portable"    # Windows 绿色版（zip 解压）
    MACOS_APP = "macos_app"         # macOS .app 包
    UNKNOWN = "unknown"             # 其它平台（当前无升级能力）


class UpdateAction(Enum):
    """用户点击「立即更新」后的实际动作。"""

    NONE = "none"                       # 不做任何事（仅打开 release 页）
    WIN_SILENT_INSTALL = "win_silent_install"  # 静默运行安装器
    WIN_INPLACE_REPLACE = "win_inplace_replace"  # 绿色版原地替换
    REVEAL_FILE = "reveal_file"         # 下载后定位/打开文件，交由用户手动完成


@dataclass(frozen=True)
class UpdatePlan:
    """本次更新的执行计划。

    - ``action``：实际要做的动作；
    - ``asset``：要下载的 release 资产；None 表示无法下载（只能打开 release 页）；
    - ``degraded_reason``：非空表示未能走最优路径（如目录不可写），用于向用户解释；
    - ``auto_apply``：True 表示下载完后应用会自动完成并重启，False 表示需要用户手动收尾。
    """

    action: UpdateAction
    asset: dict | None = None
    degraded_reason: str = ""
    auto_apply: bool = False


# ============================ 形态检测 ============================


def is_frozen() -> bool:
    """是否处于 PyInstaller 打包运行态。"""
    return bool(getattr(sys, "frozen", False))


def get_app_dir() -> Path | None:
    """返回程序所在目录（仅打包态有意义）。"""
    if not is_frozen():
        return None
    try:
        return Path(sys.executable).resolve().parent
    except OSError:
        return None


def get_macos_app_path() -> Path | None:
    """从可执行文件路径回溯出 .app 包路径，非 macOS 包内运行时返回 None。"""
    if not is_frozen():
        return None
    try:
        exe = Path(sys.executable).resolve()
    except OSError:
        return None
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


def detect_install_form() -> InstallForm:
    """判定当前运行形态。"""
    if not is_frozen():
        return InstallForm.DEV

    if sys.platform == "darwin":
        return InstallForm.MACOS_APP if get_macos_app_path() else InstallForm.UNKNOWN

    if os.name == "nt":
        app_dir = get_app_dir()
        if app_dir is None:
            return InstallForm.UNKNOWN
        # Inno Setup 会在安装目录写入 unins000.exe；zip 绿色版不会有。
        if (app_dir / INNO_UNINSTALLER_NAME).exists():
            return InstallForm.WIN_INSTALLED
        return InstallForm.WIN_PORTABLE

    return InstallForm.UNKNOWN


def is_download_only_form(form: InstallForm) -> bool:
    """该形态是否只能「下载 + 交给用户手动完成」。"""
    return form in (InstallForm.DEV, InstallForm.UNKNOWN)


# ============================ 资产选择 ============================


def select_asset(assets: list[dict], form: InstallForm) -> dict | None:
    """从 release assets 中挑出当前形态需要的那个文件。

    assets 为空（走了重定向回退，或资产尚未上传完）时返回 None，
    调用方应降级为「打开 release 页面」。
    """
    if not assets:
        return None

    if form is InstallForm.WIN_INSTALLED:
        suffix = WIN_INSTALLER_SUFFIX
    elif form is InstallForm.WIN_PORTABLE:
        suffix = WIN_PORTABLE_SUFFIX
    elif form is InstallForm.MACOS_APP:
        # 已装在 Applications 的走 dmg（规范位置），其余走 zip（原地替换）。
        suffix = MACOS_DMG_SUFFIX if is_macos_app_in_applications() else MACOS_ZIP_SUFFIX
    else:
        return None

    for asset in assets:
        name = str(asset.get("name") or "")
        if name.endswith(suffix) and asset.get("url"):
            return asset
    return None


def is_macos_app_in_applications() -> bool:
    """macOS：.app 是否位于 /Applications 或 ~/Applications。"""
    app_path = get_macos_app_path()
    if app_path is None:
        return False
    candidates = [Path("/Applications"), Path.home() / "Applications"]
    for base in candidates:
        try:
            if app_path.parent.resolve() == base.resolve():
                return True
        except OSError:
            continue
    return False


def plan_action(form: InstallForm) -> UpdateAction:
    """形态 → 首选升级动作。"""
    if form is InstallForm.WIN_INSTALLED:
        return UpdateAction.WIN_SILENT_INSTALL
    if form is InstallForm.WIN_PORTABLE:
        return UpdateAction.WIN_INPLACE_REPLACE
    if form is InstallForm.MACOS_APP:
        return UpdateAction.REVEAL_FILE
    return UpdateAction.NONE


def build_update_plan(form: InstallForm, assets: list[dict]) -> UpdatePlan:
    """综合形态、资产与本地条件，给出本次更新的执行计划。

    降级规则：绿色版原地替换要求程序目录的**父目录可写**（要新建同级 .new/.old）。
    不满足（如解压在 Program Files、只读介质）则降级为下载后由用户手动替换，
    避免更新到一半失败把程序目录留在半残状态。
    """
    action = plan_action(form)
    if action is UpdateAction.NONE:
        return UpdatePlan(action)

    asset = select_asset(assets, form)
    if asset is None:
        return UpdatePlan(action)

    if action is UpdateAction.WIN_INPLACE_REPLACE:
        app_dir = get_app_dir()
        if app_dir is None:
            return UpdatePlan(UpdateAction.REVEAL_FILE, asset,
                              "无法确定程序所在目录，已改为手动替换。")
        ok, reason = can_replace_in_place(app_dir)
        if not ok:
            return UpdatePlan(UpdateAction.REVEAL_FILE, asset, reason)
        return UpdatePlan(action, asset, "", auto_apply=True)

    if action is UpdateAction.WIN_SILENT_INSTALL:
        return UpdatePlan(action, asset, "", auto_apply=True)

    return UpdatePlan(action, asset)


# ============================ 目录与校验 ============================


def get_staging_dir(version_tag: str = "") -> Path:
    """更新文件暂存目录（位于用户数据目录，必定可写）。"""
    base = get_user_data_root() / UPDATE_STAGING_DIR_NAME
    return base / sanitize_tag(version_tag) if version_tag else base


def sanitize_tag(version_tag: str) -> str:
    """把版本号转成安全的目录名（如 0.0.0-dev+20260101.abc1234 含 +）。"""
    safe = "".join(
        ch if (ch.isalnum() or ch in ".-_ ") else "_" for ch in str(version_tag)
    )
    return safe.strip() or "unknown"


# ============================ 更新日志 ============================


def get_update_log_path() -> Path:
    """更新日志路径（放在暂存根目录，不随版本子目录一起被清理）。"""
    return get_staging_dir() / UPDATE_LOG_NAME


def log_update_event(message: str) -> None:
    """把更新流程的关键节点追加到更新日志。

    这个日志是排查失败的唯一现场（更新脚本在程序退出后才跑，结果无人可见），
    所以记录动作一律不抛异常，绝不因为写日志失败而中断更新。
    """
    try:
        path = get_update_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log_if_needed(path)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except OSError:
        pass


def _rotate_log_if_needed(path: Path) -> None:
    """日志超过上限就丢掉旧内容，防止多次更新后无限增长。"""
    try:
        if path.exists() and path.stat().st_size > UPDATE_LOG_MAX_BYTES:
            path.write_text("", encoding="utf-8")
    except OSError:
        pass


@dataclass(frozen=True)
class PendingUpdateIssue:
    """上一次自动更新没能完成，需要在下次启动时告知用户。"""

    app_dir: Path
    new_dir: Path
    reason: str
    log_path: Path


def _read_last_failure_reason(log_path: Path) -> str:
    """从日志尾部找出最后一条「失败」记录，用作给用户看的原因。"""
    try:
        # PowerShell 的 Add-Content -Encoding UTF8 会带 BOM，用 utf-8-sig 吃掉
        lines = log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines[-200:]):
        if "失败" in line:
            parts = line.split(" ", 2)
            return parts[-1].strip() if parts else line.strip()
    return ""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """计算文件 sha256（分块读取，避免大安装包占内存）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> bool:
    """校验文件摘要；expected 为空表示无摘要可比（视为通过，由调用方提示）。"""
    expected = str(expected or "").strip().lower()
    if not expected:
        return True
    return sha256_file(path) == expected


def is_dir_writable(path: Path) -> bool:
    """实建临时文件探测目录可写性（比 os.access 在 Windows 上可靠）。"""
    probe = path / ".ruledone_write_probe"
    try:
        probe.write_text("", encoding="utf-8")
    except OSError:
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    return True


def can_replace_in_place(app_dir: Path) -> tuple[bool, str]:
    """绿色版原地替换的预检：父目录需可写（要新建同级 .new / .old 目录）。"""
    parent = app_dir.parent
    if not parent.exists():
        return False, "程序所在目录不存在。"
    if not is_dir_writable(parent):
        return False, f"程序所在目录没有写入权限：{parent}"
    return True, ""


def safe_rmtree(path: Path) -> None:
    """尽力删除目录，失败不抛异常（清理类操作不应打断主流程）。"""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


# ============================ 脚本生成与执行 ============================


def _ps_quote(value: str) -> str:
    """PowerShell 单引号字符串转义（串内的 ' 写成 ''）。"""
    return "'" + str(value).replace("'", "''") + "'"


def build_portable_replace_script(
    app_dir: Path,
    new_dir: Path,
    old_dir: Path,
    exe_name: str,
    process_id: int,
    log_file: Path,
    started_marker: Path,
) -> str:
    """生成绿色版原地替换用的 PowerShell 脚本。

    流程：等主进程退出 → 旧目录改名为 .old（失败则重试）→ .new 改名为正式目录 →
    启动新版本；任一步失败则回滚，绝不让程序目录处于半替换状态。

    只做目录改名（同一卷内是瞬时操作），因此要求 .new / .old 与程序目录同级。
    每一步都写 ``log_file``：脚本在程序退出后才执行，日志是唯一的失败现场。
    """
    return f"""$ErrorActionPreference = 'Continue'
$procId = {process_id}
$appDir = {_ps_quote(str(app_dir))}
$newDir = {_ps_quote(str(new_dir))}
$oldDir = {_ps_quote(str(old_dir))}
$exeName = {_ps_quote(exe_name)}
$logFile = {_ps_quote(str(log_file))}
$startedMarker = {_ps_quote(str(started_marker))}

# 第一件事就是留下「脚本确实跑起来了」的证据：调用方看不到本进程，
# 只能靠这个标记区分「脚本没执行」和「脚本执行了但失败了」。
try {{ Set-Content -LiteralPath $startedMarker -Value 'started' -Encoding ASCII }} catch {{ }}

function Write-Log([string]$message) {{
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    try {{ Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8 }} catch {{ }}
}}

Write-Log "=== 开始替换：等待主进程 $procId 退出 ==="

# 1) 等主进程退出；超时则原样退出，不动任何文件
$deadline = (Get-Date).AddSeconds({WAIT_EXIT_TIMEOUT_SECONDS})
while (Get-Process -Id $procId -ErrorAction SilentlyContinue) {{
    if ((Get-Date) -ge $deadline) {{
        Write-Log "失败：主程序在 {WAIT_EXIT_TIMEOUT_SECONDS} 秒内没有退出，已放弃（未改动任何文件）"
        exit 2
    }}
    Start-Sleep -Milliseconds 300
}}
Write-Log "主进程已退出"

# 2) 旧目录改名备份。
#    Windows 在主进程退出后仍可能短暂持有目录句柄（句柄释放、杀软扫描都有延迟），
#    所以这一步必须重试，一次失败就放弃会导致更新静默失败。
$backupOk = $false
for ($i = 0; $i -lt {RENAME_RETRY_COUNT}; $i++) {{
    if (Test-Path -LiteralPath $oldDir) {{
        Remove-Item -LiteralPath $oldDir -Recurse -Force -ErrorAction SilentlyContinue
    }}
    try {{
        Move-Item -LiteralPath $appDir -Destination $oldDir -ErrorAction Stop
        $backupOk = $true
        Write-Log "旧目录已改名为备份（第 $($i + 1) 次尝试成功）"
        break
    }} catch {{
        if ($i -eq 0 -or (($i + 1) % 20) -eq 0) {{
            Write-Log "改名重试中（第 $($i + 1) 次）：$($_.Exception.Message)"
        }}
        Start-Sleep -Milliseconds {RENAME_RETRY_INTERVAL_MS}
    }}
}}
if (-not $backupOk) {{
    Write-Log "失败：程序目录始终被占用，无法改名为备份，更新已中止（原程序未受影响）"
    exit 3
}}

# 3) 新目录就位；失败则把旧目录移回
try {{
    Move-Item -LiteralPath $newDir -Destination $appDir -ErrorAction Stop
    Write-Log "新版本已就位"
}} catch {{
    Write-Log "失败：新版本就位失败（$($_.Exception.Message)），正在回滚"
    Move-Item -LiteralPath $oldDir -Destination $appDir -ErrorAction SilentlyContinue
    exit 4
}}

# 4) 启动新版本；启动失败同样回滚
try {{
    Start-Process -FilePath (Join-Path $appDir $exeName) -ErrorAction Stop
    Write-Log "已启动新版本，更新完成"
}} catch {{
    Write-Log "失败：新版本启动失败（$($_.Exception.Message)），正在回滚"
    Move-Item -LiteralPath $appDir -Destination $newDir -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $oldDir -Destination $appDir -ErrorAction SilentlyContinue
    exit 5
}}

# 备份保留至下次启动（清理备份见 cleanup_previous_update_artifacts）
exit 0
"""


def run_detached_powershell(script: str, working_dir: Path) -> None:
    """以分离进程运行 PowerShell 脚本。

    脚本用 ``-EncodedCommand``（UTF-16LE base64）传递，彻底规避中文路径在
    命令行编码 / 代码页上的坑，也不需要落地 .bat 文件（少一个杀软敏感点）。

    working_dir 必须不在程序目录内，否则目录改名会因「目录被占用」失败。
    """
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        cwd=str(working_dir),
        creationflags=_detached_creation_flags(),
        close_fds=True,
    )


def write_update_script(script: str, staging_dir: Path) -> Path:
    """把脚本落盘一份供失败排查，返回路径。

    实际执行不用这个文件（走 ``-EncodedCommand``，编码万无一失）；
    这里带 BOM 写出，是为了 Windows PowerShell 直接双击/打开时不乱码。
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    path = staging_dir / "apply_update.ps1"
    path.write_text(script, encoding="utf-8-sig")
    return path


# ============================ 各形态的升级动作 ============================


def get_exe_name() -> str:
    """主程序可执行文件名。"""
    try:
        return Path(sys.executable).name
    except Exception:
        return "RuleDone.exe" if os.name == "nt" else "RuleDone"


def _detached_creation_flags() -> int:
    """启动「脱离父进程但仍能正常工作」的子进程所需的 flag。

    **绝对不要用 subprocess.DETACHED_PROCESS**：实测 PowerShell 在无控制台的
    脱离进程里会直接静默退出——脚本一行都不执行，而 Popen 不报任何错，
    表现为「下载完成、程序退出，但什么都没发生」。

    CREATE_NO_WINDOW 同样不分配新控制台，但不会破坏 PowerShell 初始化；
    CREATE_NEW_PROCESS_GROUP 让它不受父进程控制台事件影响。
    父进程退出后子进程不会随之终止（Windows 不会自动杀子进程）。
    """
    if os.name != "nt":
        return 0
    return subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP


def wait_for_started_marker(marker: Path, timeout: float) -> bool:
    """等替换脚本写下启动标记；超时说明脚本没跑起来。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            return True
        time.sleep(0.1)
    return False


def extract_zip_safely(archive: Path, dest: Path) -> None:
    """解压 zip 到 dest，并拒绝路径穿越条目（zip slip）。

    先校验全部条目再落地，避免解压到一半才发现恶意条目。
    """
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            target = (dest_resolved / name).resolve()
            if not str(target).startswith(str(dest_resolved) + os.sep) and target != dest_resolved:
                raise ValueError(f"压缩包内含非法路径：{name}")
        zf.extractall(dest_resolved)


def _single_exe_in(directory: Path) -> str | None:
    """目录下唯一的 .exe 文件名；没有或有多个则返回 None。"""
    try:
        names = sorted(item.name for item in directory.glob("*.exe") if item.is_file())
    except OSError:
        return None
    return names[0] if len(names) == 1 else None


def find_bundle_root(root: Path, exe_name: str) -> Path | None:
    """在解压结果中定位含主程序的目录。

    优先按当前主程序名找（兼容用户重命名过程序**文件夹**）；找不到时退回
    「唯一 exe」判定，兼容用户重命名过程序**文件**的情况。
    """
    if (root / exe_name).is_file():
        return root
    try:
        children = [child for child in root.iterdir() if child.is_dir()]
    except OSError:
        return None
    for child in children:
        if (child / exe_name).is_file():
            return child
    for child in children:
        if _single_exe_in(child) is not None:
            return child
    return root if _single_exe_in(root) is not None else None


def resolve_bundle_exe(bundle_root: Path, preferred_name: str = "") -> str | None:
    """确定更新包里要启动的主程序名。

    以包内实际内容为准：优先用与当前一致的名字，否则退回唯一的 exe。
    返回 None 表示这个包不可用。
    """
    if preferred_name and (bundle_root / preferred_name).is_file():
        return preferred_name
    return _single_exe_in(bundle_root)


def prepare_and_launch_portable_replace(
    zip_path: Path,
    app_dir: Path,
    staging_dir: Path,
) -> None:
    """绿色版原地替换：解压新版 → 启动外部替换脚本 → 清理暂存。

    本函数返回后调用方应立刻退出程序，让脚本能接管目录改名。
    所有目录改名都在同一卷内即时完成，且任一步失败都会回滚。
    """
    new_dir = app_dir.with_name(app_dir.name + NEW_STAGING_SUFFIX)
    old_dir = app_dir.with_name(app_dir.name + OLD_BACKUP_SUFFIX)

    log_update_event(f"准备原地替换：{app_dir} <- {zip_path.name}（进程 {os.getpid()}）")

    # 上一轮残留（例如上次失败留下的）先清掉，否则改名会撞名。
    if new_dir.exists():
        safe_rmtree(new_dir)

    extract_root = new_dir.with_name(new_dir.name + ".extract")
    if extract_root.exists():
        safe_rmtree(extract_root)

    try:
        extract_zip_safely(zip_path, extract_root)
        bundle_root = find_bundle_root(extract_root, get_exe_name())
        if bundle_root is None:
            raise ValueError("更新包中未找到主程序文件。")
        # 主程序名以包内实际内容为准（用户可能改过名）
        bundle_exe = resolve_bundle_exe(bundle_root, get_exe_name())
        if bundle_exe is None:
            raise ValueError("更新包中主程序文件不唯一，无法确定要启动哪个。")
        if bundle_root != extract_root:
            os.replace(bundle_root, new_dir)
            safe_rmtree(extract_root)
        else:
            os.replace(extract_root, new_dir)
    except Exception as exc:
        safe_rmtree(extract_root)
        safe_rmtree(new_dir)
        log_update_event(f"失败：解压更新包出错：{exc}")
        raise

    log_update_event(f"新版已解压到 {new_dir}，启动替换脚本（主程序 {bundle_exe}）")

    script = build_portable_replace_script(
        app_dir=app_dir,
        new_dir=new_dir,
        old_dir=old_dir,
        exe_name=bundle_exe,
        process_id=os.getpid(),
        log_file=get_update_log_path(),
        started_marker=get_started_marker_path(),
    )
    write_update_script(script, staging_dir)
    # 工作目录必须避开程序目录，否则脚本改名时会因目录被占用而失败。
    _launch_replace_script(script, staging_dir)

    # 下载包已解压完毕，删掉可以省下一份完整副本的空间。
    try:
        zip_path.unlink()
    except OSError:
        pass


def get_started_marker_path() -> Path:
    """替换脚本启动标记的路径（每次启动前先删掉，避免读到上一轮的残留）。"""
    return get_staging_dir() / STARTED_MARKER_NAME


def _launch_replace_script(script: str, staging_dir: Path) -> None:
    """启动替换脚本，并确认它真的跑起来了。

    这一步是必须的：子进程启动失败时父进程完全无感（无控制台、无异常），
    早期版本因此静默失败了很久。标记没出现就直接报错。
    """
    marker = get_started_marker_path()
    try:
        marker.unlink()
    except OSError:
        pass

    run_detached_powershell(script, working_dir=staging_dir)

    if not wait_for_started_marker(marker, START_HANDSHAKE_TIMEOUT_SECONDS):
        log_update_event("失败：替换脚本启动后没有响应（脚本未能执行）")
        raise RuntimeError("更新脚本未能启动，请重试；若反复失败请手动替换程序文件。")
    log_update_event("替换脚本已确认启动")


def retry_pending_portable_replace(issue: PendingUpdateIssue) -> bool:
    """续做上次未完成的原地替换（用当前进程的 PID 重新生成脚本）。

    返回 False 表示暂存的新版本已不可用（缺主程序），需要重新下载。
    """
    bundle_exe = resolve_bundle_exe(issue.new_dir, get_exe_name())
    if bundle_exe is None:
        return False

    staging = get_staging_dir()
    staging.mkdir(parents=True, exist_ok=True)

    old_dir = issue.app_dir.with_name(issue.app_dir.name + OLD_BACKUP_SUFFIX)
    script = build_portable_replace_script(
        app_dir=issue.app_dir,
        new_dir=issue.new_dir,
        old_dir=old_dir,
        exe_name=bundle_exe,
        process_id=os.getpid(),
        log_file=get_update_log_path(),
        started_marker=get_started_marker_path(),
    )
    log_update_event(f"用户选择续做上次未完成的更新，重新启动替换脚本（进程 {os.getpid()}）")
    try:
        _launch_replace_script(script, staging)
    except Exception as exc:
        log_update_event(f"失败：续做时替换脚本未能启动：{exc}")
        return False
    return True


def launch_windows_installer(installer_path: Path) -> None:
    """静默运行 Inno Setup 安装包。

    主程序会在调用后立即退出；安装器通过 Restart Manager 接管正在运行的实例，
    装完后自动重启（依赖 installer.iss 中的 CloseApplications / RestartApplications
    与 ``[Run]`` 段的非 skipifsilent 配置）。
    """
    subprocess.Popen(
        [str(installer_path), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
        cwd=str(installer_path.parent),
        creationflags=_detached_creation_flags(),
        close_fds=True,
    )


def reveal_in_file_manager(path: Path) -> None:
    """在文件管理器中定位到指定文件（macOS 用 open -R，Windows 用 explorer /select）。"""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(path)])
    except Exception:
        pass


def open_file_with_default_app(path: Path) -> None:
    """用系统默认程序打开文件（macOS 打开 dmg 即挂载并弹出安装窗口）。"""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        pass


def reveal_after_download(path: Path) -> None:
    """REVEAL_FILE 动作的收尾：dmg 直接打开，zip 定位到文件管理器。"""
    if path.suffix.lower() == ".dmg":
        open_file_with_default_app(path)
    else:
        reveal_in_file_manager(path)


# ============================ 启动期清理 ============================


def cleanup_previous_update_artifacts() -> PendingUpdateIssue | None:
    """清理上一次更新留下的备份与暂存文件；返回「上次更新未完成」的信息。

    能在主流程跑到这里，说明程序已经起来了。此时：

    - ``<app>.old`` 存在 → 上次替换成功过，备份可以安全删除
      （备份是整份旧程序目录，用户的档案数据一律在 ``<user_data_root>``，不在此处）；
    - ``<app>.new`` 存在 → **上次替换没能完成**（脚本超时或被占用），要如实告诉用户，
      并且不要删掉它——留在原地才能续做或手动替换。

    保留 ``*.partial``（未完成下载的断点）与 ``update.log``（失败现场）。
    """
    issue: PendingUpdateIssue | None = None

    if detect_install_form() is InstallForm.WIN_PORTABLE:
        app_dir = get_app_dir()
        if app_dir is not None:
            old_dir = app_dir.with_name(app_dir.name + OLD_BACKUP_SUFFIX)
            if old_dir.exists():
                # 新版本已经在跑，旧备份留着只是占空间
                safe_rmtree(old_dir)

            new_dir = app_dir.with_name(app_dir.name + NEW_STAGING_SUFFIX)
            if new_dir.exists():
                log_path = get_update_log_path()
                reason = _read_last_failure_reason(log_path)
                log_update_event("检测到上次更新遗留的 .new 目录，判定上次更新未完成")
                issue = PendingUpdateIssue(
                    app_dir=app_dir,
                    new_dir=new_dir,
                    reason=reason,
                    log_path=log_path,
                )

    staging = get_staging_dir()
    if not staging.exists():
        return issue

    for child in staging.iterdir():
        try:
            if child.is_dir():
                # 目录里还有断点文件就整个留着，下次接着下
                if not any(child.rglob("*.partial")):
                    safe_rmtree(child)
            elif child.name == UPDATE_LOG_NAME or child.name.endswith(".partial"):
                continue
            else:
                child.unlink()
        except OSError:
            continue

    return issue

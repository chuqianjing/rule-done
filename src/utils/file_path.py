import json
import os
import sys
from pathlib import Path

APP_DIR_NAME = "RuleDone"
BOOTSTRAP_FILE_NAME = "bootstrap_settings.json"
USER_DATA_ROOT_KEY = "user_data_root"

def get_abs_path(relative_path):
    """ 获取资源文件的绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录路径 (单文件模式)
        # 或者在单文件夹模式下，这也是程序运行的基础路径
        base_path = sys._MEIPASS
    else:
        # 普通 Python 环境下的绝对路径
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def get_builtin_resources_dir() -> Path:
    """返回程序内置（出厂默认）资源目录。

    打包模式下位于打包目录内（只读）；开发模式下为项目 resources/。
    仅用于提供出厂 schema 等默认内容；运行时一律以用户数据目录为准。
    """
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parents[2] / "resources"


def get_runtime_resources_dir(root: Path | None = None) -> Path:
    """返回运行时可写的资源目录（生效资源所在）。

    一律指向用户数据根目录下的 resources/，开发与打包行为一致；
    schema 出厂标准由首次启动从内置目录补齐，模板不预置。
    """
    base = root or get_user_data_root()
    return base / "resources"


def get_runtime_resources_sync_dir(root: Path | None = None) -> Path:
    """返回资源同步的中间目录（本机版本记录、下载缓存、备份）。"""
    return get_runtime_resources_dir(root) / "_sync"


def get_default_user_data_root() -> Path:
    """返回默认用户数据根目录（优先使用 AppData）。"""
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_DIR_NAME
    return Path.home() / ".ruledone"


def get_bootstrap_settings_path() -> Path:
    """返回 bootstrap 配置文件路径（固定可写，不随用户设置变动）。"""
    return get_default_user_data_root() / BOOTSTRAP_FILE_NAME


def load_bootstrap_settings() -> dict:
    """读取 bootstrap 设置。"""
    path = get_bootstrap_settings_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_bootstrap_settings(settings: dict) -> bool:
    """保存 bootstrap 设置。"""
    path = get_bootstrap_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    return True


def get_user_data_root() -> Path:
    """返回当前生效的用户数据根目录。"""
    settings = load_bootstrap_settings()
    configured = str(settings.get(USER_DATA_ROOT_KEY, "")).strip()
    if configured:
        return Path(configured)
    return get_default_user_data_root()


def set_user_data_root(path_value: str) -> Path:
    """设置用户数据根目录并写入 bootstrap。"""
    target = Path(path_value).expanduser().resolve()
    settings = load_bootstrap_settings()
    settings[USER_DATA_ROOT_KEY] = str(target)
    save_bootstrap_settings(settings)
    return target


def get_runtime_data_dir(root: Path | None = None) -> Path:
    """返回运行时 data 目录。"""
    base = root or get_user_data_root()
    return base / "data"


def get_runtime_exports_dir(root: Path | None = None) -> Path:
    """返回运行时 exports 目录。"""
    base = root or get_user_data_root()
    return base / "exports"


def ensure_runtime_directories(root: Path | None = None) -> tuple[Path, Path, Path]:
    """确保运行时目录存在，返回 (root, data_dir, exports_dir)。"""
    base = (root or get_user_data_root()).expanduser().resolve()
    data_dir = get_runtime_data_dir(base)
    exports_dir = get_runtime_exports_dir(base)

    base.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    # 生效资源目录一律位于用户数据目录下（开发/打包一致）
    get_runtime_resources_dir(base).mkdir(parents=True, exist_ok=True)
    return base, data_dir, exports_dir
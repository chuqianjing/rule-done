#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
字段定义加载工具

负责统一读取 resources/fields_definition.json，
供各个 UI 页面（AdminConfigPage / BasicInfoPage / TemplatePage 等）使用。

底层依赖 JSONStorage，保证 JSON 读写行为一致。
"""

from pathlib import Path
from typing import Any, Dict

from src.utils.json_storage import JSONStorage


FIELDS_DEFINITION_PATH = Path("resources/fields_definition.json")


def load_fields_definition() -> Dict[str, Any]:
    """
    读取字段定义文件 resources/fields_definition.json 并返回字典对象。

    异常约定：
    - 文件不存在时抛出 FileNotFoundError
    - JSON 解析错误时抛出 ValueError（由 JSONStorage 封装）
    - 其他 IO 错误抛出对应异常

    由调用方（通常是 UI 层）决定如何提示用户。
    """
    storage = JSONStorage()
    return storage.read_json(str(FIELDS_DEFINITION_PATH))



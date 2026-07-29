#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同步管理通用底座。"""

from __future__ import annotations

from typing import Any, Dict

import requests


class SyncManagerBase:
    """同步领域的通用底座。"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

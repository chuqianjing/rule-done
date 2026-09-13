#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2026 楚乾靖(Chu Qianjing)
# Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""
单实例守卫

同一用户数据目录下只允许存在一个程序实例：后启动的实例请求已运行实例
把窗口置前，然后自行退出。

必要性：用户的 data 目录（system_settings.json 等）由多个实例共享，
而配置写入是「读-改-写 + 直接覆盖」，多实例并发写会互相覆盖并读到半截内容。

实现方式：
- 互斥：QLockFile（原子创建锁文件；持锁进程退出/崩溃后锁自动失效）；
- 窗口置前：QLocalServer/QLocalSocket 进程间通知。

注意：不可用 QLocalServer.listen() 失败来判断「已有实例」——
Windows 命名管道允许同名多实例存在，第二个进程 listen() 同样会成功。

Author: 楚乾靖
Date: 2026-09
"""

from hashlib import sha256
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# 获取锁的最长等待时间（毫秒）：略等可覆盖「上一实例正在退出」的短暂竞争
_LOCK_WAIT_MS = 300
# 与已运行实例握手的最长等待时间（毫秒）
_CONNECT_TIMEOUT_MS = 500
# 第二实例发给首实例的唤醒消息（内容不参与逻辑判断，收到即视为唤醒请求）
_MESSAGE_ACTIVATE = b"activate"


class SingleInstanceGuard(QObject):
    """进程级单实例守卫。

    用法::

        guard = SingleInstanceGuard(get_user_data_root() / "app.lock")
        if not guard.try_acquire():
            sys.exit(0)                    # 已有实例在运行，且已请求其窗口置前
        guard.activation_requested.connect(window.bring_to_front)

    互斥范围由锁文件路径决定（同一路径的实例互斥）；置前服务名由该路径哈希得到，
    因此「不同用户 / 不同数据目录」的程序实例互不干扰。

    Signals:
        activation_requested: 收到其他实例的「窗口置前」请求时发出。
    """

    activation_requested = Signal()

    def __init__(self, lock_path: Path | str, parent: QObject | None = None):
        """初始化守卫。

        Args:
            lock_path: 锁文件路径，通常为用户数据根目录下的 app.lock；
                所在目录须已存在（由 ensure_runtime_directories 保证）。
            parent: 父对象。
        """
        super().__init__(parent)

        self.lock_path = Path(lock_path)
        digest = sha256(str(self.lock_path).encode("utf-8")).hexdigest()[:24]
        self.server_name = f"RuleDone-{digest}"

        self._lock = QLockFile(str(self.lock_path))
        # 不以时间判定残留，只凭「持锁进程是否还活着」判断，
        # 避免程序崩溃后要干等 staleLockTime 才能重新启动
        self._lock.setStaleLockTime(0)
        self._server: QLocalServer | None = None
        self._activation_pending = False
        # 被拒时是否成功通知了已运行实例（False 时调用方应给用户提示，避免静默退出）
        self.existing_instance_notified = False

    # ==================== 获取/释放 ====================

    def try_acquire(self) -> bool:
        """尝试成为唯一实例。

        Returns:
            bool: True 表示本进程是当前唯一实例；False 表示已有实例在运行
            （此时已尽力请求该实例把窗口置前）。
        """
        if self._lock.tryLock(_LOCK_WAIT_MS):
            self._start_server()
            return True

        # 拿不到锁即为已有实例在运行（Qt 文档：LockFailedError = 锁已被其他进程持有，
        # PermissionError = 锁文件因权限/只读原因无法创建）。
        # 这里不按 error() 细分原因，只认 tryLock 的返回值：该分支行为在两个平台一致。
        # 崩溃残留无需在此处理：QLockFile 会把锁文件中的 PID、进程名、hostid、bootid
        # 与当前系统比对（例如系统已重启时 bootid 不同即判为残留），确认持锁进程
        # 已消失后会自动清理，所以上一行的 tryLock 就能直接拿到锁。
        self.existing_instance_notified = self._notify_existing_instance()
        return False

    def release(self) -> None:
        """释放置前服务与单实例锁。"""
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._lock.isLocked():
            self._lock.unlock()

    def take_pending_activation(self) -> bool:
        """取出并清除「置前请求」标记。

        用于覆盖信号尚未连接时（例如首实例仍停留在启动密码框）就已到达的请求。

        Returns:
            bool: 自上次取出以来是否收到过置前请求。
        """
        pending = self._activation_pending
        self._activation_pending = False
        return pending

    # ==================== 内部实现 ====================

    def _start_server(self) -> None:
        """启动窗口置前服务（仅在已持有锁后调用）。"""
        server = QLocalServer(self)
        if server.listen(self.server_name):
            self._attach_server(server)
            return

        # Unix 下上次异常退出可能残留 socket 文件，清理后重试一次
        QLocalServer.removeServer(self.server_name)
        if server.listen(self.server_name):
            self._attach_server(server)
            return

        server.close()

    def _attach_server(self, server: QLocalServer) -> None:
        """接管已开始监听的本地服务。"""
        self._server = server
        server.newConnection.connect(self._on_new_connection)

    def _notify_existing_instance(self) -> bool:
        """连接已运行实例并请求其窗口置前。

        Returns:
            bool: True 表示连接成功（存在已运行实例）。
        """
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
            return False

        socket.write(_MESSAGE_ACTIVATE)
        socket.flush()
        socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self) -> None:
        """接受第二实例的连接。"""
        if self._server is None:
            return

        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda sock=socket: self._on_ready_read(sock))
            socket.disconnected.connect(socket.deleteLater)

    def _on_ready_read(self, socket: QLocalSocket) -> None:
        """读取唤醒消息并发出置前信号。"""
        socket.readAll()
        socket.disconnectFromServer()

        self._activation_pending = True
        self.activation_requested.emit()

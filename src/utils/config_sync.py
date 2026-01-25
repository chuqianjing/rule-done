#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置同步管理器
支持从网络 URL 自动同步管理员配置
"""

import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import json


class ConfigSync:
    """配置同步管理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.timeout = 10  # 请求超时时间（秒）
    
    def check_and_sync(self, sync_url: str, force: bool = False) -> Tuple[bool, str]:
        """
        检查并同步配置
        
        Args:
            sync_url: 配置文件的网络 URL
            force: 是否强制同步（忽略时间戳比较）
        
        Returns:
            (success: bool, message: str)
            success=True 表示同步成功，False 表示无更新或失败
        """
        try:
            # 1. 获取远程配置的元信息
            try:
                head_response = requests.head(sync_url, timeout=5, allow_redirects=True)
                head_response.raise_for_status()
            except requests.RequestException:
                # HEAD 请求失败，尝试 GET 请求
                pass
            
            # 2. 下载远程配置
            try:
                response = requests.get(sync_url, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                remote_config = response.json()
            except requests.RequestException as e:
                return False, f"无法访问配置 URL：{e}"
            except json.JSONDecodeError:
                return False, "远程配置文件格式错误（不是有效的 JSON）"
            
            # 3. 验证配置格式
            if not self._validate_config(remote_config):
                return False, "远程配置文件格式不正确，缺少必需的字段"
            
            # 4. 比较时间戳（如果不强制同步）
            if not force:
                local_config = self.config_manager.load_config()
                local_modified = local_config.get('last_modified')
                remote_modified = remote_config.get('last_modified')
                
                if local_modified and remote_modified:
                    if not self._is_remote_newer(remote_modified, local_modified):
                        return False, "本地配置已是最新版本，无需更新"
            
            # 5. 备份当前配置
            try:
                backup_path = self.config_manager.json_storage.backup_file(
                    str(self.config_manager.config_path)
                )
            except Exception as e:
                return False, f"备份当前配置失败：{e}"
            
            # 6. 合并配置（保留本地设置）
            local_config = self.config_manager.load_config()
            remote_config['locked'] = local_config.get('locked', True)  # 学生端默认锁定
            remote_config['configured'] = True
            remote_config['synced_at'] = datetime.now().isoformat()
            remote_config['sync_source'] = sync_url
            
            # 7. 保存配置
            try:
                self.config_manager.save_config(remote_config)
                return True, f"配置已成功同步（已备份到：{backup_path}）"
            except Exception as e:
                return False, f"保存同步的配置失败：{e}"
                
        except Exception as e:
            return False, f"同步过程出错：{e}"
    
    def _is_remote_newer(self, remote_time: str, local_time: str) -> bool:
        """比较远程和本地配置的时间戳"""
        if not remote_time or not local_time:
            return True
        
        try:
            from dateutil import parser
            remote_dt = parser.parse(remote_time)
            local_dt = parser.parse(local_time)
            return remote_dt > local_dt
        except Exception:
            # 解析失败时默认认为需要更新
            return True
    
    def _validate_config(self, config: dict) -> bool:
        """验证配置格式"""
        required_keys = ['branch_info', 'party_committee', 'common_fields']
        return all(key in config for key in required_keys)
    
    def get_remote_config_info(self, sync_url: str) -> Optional[dict]:
        """
        获取远程配置的元信息（不下载完整配置）
        返回配置的基本信息，如 last_modified 等
        """
        try:
            response = requests.head(sync_url, timeout=5, allow_redirects=True)
            response.raise_for_status()
            
            info = {
                'url': sync_url,
                'status_code': response.status_code,
                'last_modified': response.headers.get('Last-Modified'),
                'content_length': response.headers.get('Content-Length'),
            }
            
            # 如果 HEAD 请求没有 Last-Modified，尝试 GET 请求获取配置的 last_modified 字段
            if not info['last_modified']:
                try:
                    get_response = requests.get(sync_url, timeout=self.timeout, allow_redirects=True)
                    get_response.raise_for_status()
                    remote_config = get_response.json()
                    info['last_modified'] = remote_config.get('last_modified')
                except:
                    pass
            
            return info
        except Exception as e:
            return None


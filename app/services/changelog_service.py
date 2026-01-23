"""
Debian Changelog 解析服务
"""

import os
import re
import subprocess
from typing import Optional, Dict
import logging
import time

logger = logging.getLogger(__name__)


class ChangelogService:
    """Debian Changelog 服务"""
    
    # 简单的内存缓存，格式: {repo_path: {'version': str, 'commit': str, 'timestamp': float}}
    _cache = {}
    _cache_ttl = 60  # 缓存60秒
    
    @staticmethod
    def get_current_version(repo_path: str) -> Optional[str]:
        """
        从 debian/changelog 获取当前版本号（带缓存）
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            版本号字符串，失败返回 None
        """
        # 检查缓存
        current_time = time.time()
        if repo_path in ChangelogService._cache:
            cache_entry = ChangelogService._cache[repo_path]
            if current_time - cache_entry.get('timestamp', 0) < ChangelogService._cache_ttl:
                if 'version' in cache_entry:
                    logger.debug(f"从缓存获取版本: {cache_entry['version']}")
                    return cache_entry['version']
        
        changelog_path = os.path.join(repo_path, 'debian', 'changelog')
        
        if not os.path.exists(changelog_path):
            logger.warning(f"changelog 文件不存在: {changelog_path}")
            return None
        
        try:
            # 方法1: 使用 dpkg-parsechangelog 命令（推荐）
            result = subprocess.run(
                ['dpkg-parsechangelog', '-l', changelog_path, '-S', 'Version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"通过 dpkg-parsechangelog 获取版本: {version}")
                
                # 更新缓存
                if repo_path not in ChangelogService._cache:
                    ChangelogService._cache[repo_path] = {}
                ChangelogService._cache[repo_path]['version'] = version
                ChangelogService._cache[repo_path]['timestamp'] = current_time
                
                return version
                
        except FileNotFoundError:
            logger.info("dpkg-parsechangelog 不可用，使用手动解析")
        except Exception as e:
            logger.warning(f"dpkg-parsechangelog 失败: {e}")
        
        # 方法2: 手动解析第一行
        try:
            with open(changelog_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                # 格式: package-name (version) distribution; urgency=...
                match = re.match(r'^[^\(]+\(([^\)]+)\)', first_line)
                if match:
                    version = match.group(1)
                    logger.info(f"通过手动解析获取版本: {version}")
                    return version
        except Exception as e:
            logger.error(f"解析 changelog 失败: {e}")
        
        return None
    
    @staticmethod
    def get_changelog_info(repo_path: str) -> Dict[str, any]:
        """
        获取 changelog 完整信息
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            包含 version, package, distribution, urgency 的字典
        """
        changelog_path = os.path.join(repo_path, 'debian', 'changelog')
        
        info = {
            'version': None,
            'package': None,
            'distribution': None,
            'urgency': None
        }
        
        if not os.path.exists(changelog_path):
            return info
        
        try:
            # 使用 dpkg-parsechangelog 获取所有信息
            fields = ['Version', 'Source', 'Distribution', 'Urgency']
            for field in fields:
                result = subprocess.run(
                    ['dpkg-parsechangelog', '-l', changelog_path, '-S', field],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    value = result.stdout.strip()
                    info[field.lower()] = value
                    if field == 'Source':
                        info['package'] = value
            
            return info
            
        except Exception as e:
            logger.error(f"获取 changelog 信息失败: {e}")
            return info
    
    @staticmethod
    def get_changelog_last_commit(repo_path: str) -> Optional[str]:
        """
        获取 debian/changelog 文件最后一次修改的 commit hash（带缓存）
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            commit hash，失败返回 None
        """
        # 检查缓存
        current_time = time.time()
        if repo_path in ChangelogService._cache:
            cache_entry = ChangelogService._cache[repo_path]
            if current_time - cache_entry.get('timestamp', 0) < ChangelogService._cache_ttl:
                if 'commit' in cache_entry:
                    logger.debug(f"从缓存获取 changelog commit: {cache_entry['commit'][:8]}")
                    return cache_entry['commit']
        
        changelog_path = os.path.join(repo_path, 'debian', 'changelog')
        
        if not os.path.exists(changelog_path):
            return None
        
        try:
            # 使用 git 命令获取，比 GitPython 更快
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%H', '--', 'debian/changelog'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                commit_hash = result.stdout.strip()
                
                # 更新缓存
                if repo_path not in ChangelogService._cache:
                    ChangelogService._cache[repo_path] = {}
                ChangelogService._cache[repo_path]['commit'] = commit_hash
                ChangelogService._cache[repo_path]['timestamp'] = current_time
                
                return commit_hash
            return None
            
        except Exception as e:
            logger.error(f"获取 changelog 最后 commit 失败: {e}")
            return None
    
    @staticmethod
    def clear_cache(repo_path: str = None):
        """
        清除缓存
        
        Args:
            repo_path: 指定仓库路径清除单个缓存，None 则清除所有缓存
        """
        if repo_path:
            if repo_path in ChangelogService._cache:
                del ChangelogService._cache[repo_path]
                logger.debug(f"已清除 {repo_path} 的缓存")
        else:
            ChangelogService._cache.clear()
            logger.debug("已清除所有缓存")

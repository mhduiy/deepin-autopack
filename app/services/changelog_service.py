"""
Debian Changelog 解析服务
"""

import os
import re
import subprocess
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ChangelogService:
    """Debian Changelog 服务"""
    
    @staticmethod
    def get_current_version(repo_path: str) -> Optional[str]:
        """
        从 debian/changelog 获取当前版本号
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            版本号字符串，失败返回 None
        """
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
        获取 debian/changelog 文件最后一次修改的 commit hash
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            commit hash，失败返回 None
        """
        changelog_path = os.path.join(repo_path, 'debian', 'changelog')
        
        if not os.path.exists(changelog_path):
            return None
        
        try:
            from git import Repo
            repo = Repo(repo_path)
            
            # 获取 changelog 文件的最后修改 commit
            commits = list(repo.iter_commits(paths='debian/changelog', max_count=1))
            if commits:
                return commits[0].hexsha
            return None
            
        except Exception as e:
            logger.error(f"获取 changelog 最后 commit 失败: {e}")
            return None

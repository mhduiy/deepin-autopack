"""
GitHub Actions 执行服务
参考 git-tag.py 实现
"""

import subprocess
import logging
import os
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubActionService:
    """GitHub Actions 执行服务"""
    
    @staticmethod
    def check_gh_command():
        """检查 gh 命令是否安装"""
        try:
            result = subprocess.run(
                ['gh', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"gh 命令已安装: {result.stdout.strip()}")
                return True, None
            else:
                return False, "gh 命令执行失败"
        except FileNotFoundError:
            return False, "gh 命令未安装，请运行: sudo apt install gh"
        except Exception as e:
            return False, f"检查 gh 命令失败: {str(e)}"
    
    @staticmethod
    def check_git_command():
        """检查 git 命令是否安装"""
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"git 命令已安装: {result.stdout.strip()}")
                return True, None
            else:
                return False, "git 命令执行失败"
        except FileNotFoundError:
            return False, "git 命令未安装"
        except Exception as e:
            return False, f"检查 git 命令失败: {str(e)}"
    
    @staticmethod
    def pull_repository(repo_path: str) -> tuple[bool, str]:
        """
        拉取仓库最新代码
        
        Args:
            repo_path: 本地仓库路径
            
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(repo_path):
                return False, f"仓库路径不存在: {repo_path}"
            
            if not os.path.exists(os.path.join(repo_path, '.git')):
                return False, f"不是有效的 Git 仓库: {repo_path}"
            
            logger.info(f"拉取仓库: {repo_path}")
            
            # git pull
            result = subprocess.run(
                ['git', 'pull'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"拉取成功: {result.stdout.strip()}")
                return True, result.stdout.strip()
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"拉取失败: {error_msg}")
                return False, f"拉取失败: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "拉取超时（超过300秒）"
        except Exception as e:
            logger.exception(f"拉取仓库异常: {e}")
            return False, f"拉取仓库异常: {str(e)}"
    
    @staticmethod
    def trigger_workflow(
        repo_path: str,
        workflow_name: str,
        inputs: Dict[str, str] = None
    ) -> tuple[bool, str, Optional[str]]:
        """
        触发 GitHub Actions workflow
        
        Args:
            repo_path: 本地仓库路径
            workflow_name: workflow 文件名（如 build.yml）
            inputs: workflow 输入参数字典
            
        Returns:
            (success, message, run_url)
        """
        try:
            if not os.path.exists(repo_path):
                return False, f"仓库路径不存在: {repo_path}", None
            
            logger.info(f"触发 workflow: {workflow_name}")
            logger.info(f"输入参数: {inputs}")
            
            # 构建 gh workflow run 命令
            cmd = ['gh', 'workflow', 'run', workflow_name]
            
            # 添加输入参数
            if inputs:
                for key, value in inputs.items():
                    cmd.extend(['-f', f'{key}={value}'])
            
            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                logger.info(f"workflow 触发成功: {output}")
                
                # 尝试获取最新的 run URL
                run_url = GitHubActionService._get_latest_run_url(repo_path, workflow_name)
                
                return True, output, run_url
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"workflow 触发失败: {error_msg}")
                return False, f"workflow 触发失败: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "触发 workflow 超时（超过30秒）", None
        except Exception as e:
            logger.exception(f"触发 workflow 异常: {e}")
            return False, f"触发 workflow 异常: {str(e)}", None
    
    @staticmethod
    def _get_latest_run_url(repo_path: str, workflow_name: str) -> Optional[str]:
        """获取最新的 workflow run URL"""
        try:
            # 等待一小段时间，让 GitHub 创建 run
            import time
            time.sleep(2)
            
            # gh run list --workflow=workflow_name --limit=1 --json url
            result = subprocess.run(
                ['gh', 'run', 'list', f'--workflow={workflow_name}', '--limit=1', '--json=url,databaseId,status'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                runs = json.loads(result.stdout)
                if runs and len(runs) > 0:
                    url = runs[0].get('url')
                    run_id = runs[0].get('databaseId')
                    status = runs[0].get('status')
                    logger.info(f"获取到 run URL: {url}, ID: {run_id}, 状态: {status}")
                    return url
        except Exception as e:
            logger.warning(f"获取 run URL 失败: {e}")
        
        return None
    
    @staticmethod
    def get_workflow_status(repo_path: str, run_id: str) -> tuple[bool, str, Optional[str]]:
        """
        获取 workflow 运行状态
        
        Args:
            repo_path: 本地仓库路径
            run_id: workflow run ID
            
        Returns:
            (success, status, conclusion)
            status: queued, in_progress, completed
            conclusion: success, failure, cancelled, skipped (仅当 status=completed 时有效)
        """
        try:
            result = subprocess.run(
                ['gh', 'run', 'view', run_id, '--json=status,conclusion'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                status = data.get('status')
                conclusion = data.get('conclusion')
                return True, status, conclusion
            else:
                error_msg = result.stderr.strip()
                return False, f"获取状态失败: {error_msg}", None
                
        except Exception as e:
            logger.exception(f"获取 workflow 状态异常: {e}")
            return False, f"异常: {str(e)}", None
    
    @staticmethod
    def parse_github_url(github_url: str) -> tuple[Optional[str], Optional[str]]:
        """
        解析 GitHub URL 获取 owner 和 repo
        
        Args:
            github_url: GitHub 仓库 URL
            
        Returns:
            (owner, repo)
        """
        try:
            # https://github.com/owner/repo
            # https://github.com/owner/repo.git
            parts = github_url.rstrip('/').rstrip('.git').split('/')
            if len(parts) >= 2:
                repo = parts[-1]
                owner = parts[-2]
                return owner, repo
        except Exception as e:
            logger.error(f"解析 GitHub URL 失败: {github_url}, {e}")
        
        return None, None

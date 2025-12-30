"""
Gerrit API 服务
提供 Gerrit 仓库的所有操作接口

参考 PHP 版本实现，提供完整的 Gerrit API 封装
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from typing import Dict, List, Optional, Any
import urllib3

# 禁用 SSL 警告（内网环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GerritService:
    """Gerrit API 服务类"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        初始化 Gerrit 服务
        
        Args:
            base_url: Gerrit 服务器地址，例如：https://gerrit.uniontech.com
            username: Gerrit 用户名（LDAP账号）
            password: Gerrit 密码
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; Deepin-AutoPack/1.0)'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        执行 Gerrit API 请求
        
        Args:
            method: 请求方法（GET, POST, PUT, DELETE）
            endpoint: API 端点
            **kwargs: 其他请求参数
            
        Returns:
            包含 success、data、message 的字典
        """
        # Gerrit 认证的 API 需要使用 /a/ 前缀
        url = f"{self.base_url}/a/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=kwargs.pop('timeout', 30),
                verify=False,  # 内网环境可能需要禁用SSL验证
                **kwargs
            )

            if response.status_code not in [200, 201, 204]:
                return {
                    'success': False,
                    'message': f'Gerrit API 返回错误，HTTP 状态码: {response.status_code}',
                    'data': None,
                    'status_code': response.status_code
                }
            
            # Gerrit API 返回的JSON数据前面有 )]}'  前缀，需要去掉
            response_text = response.text.strip()
            if response_text.startswith(")]}'"):
                response_text = response_text[4:].strip()
            
            # 空响应处理
            if not response_text:
                data = {}
            else:
                data = json.loads(response_text)
            
            return {
                'success': True,
                'message': 'Gerrit API 请求成功',
                'data': data
            }
            
        except requests.RequestException as e:
            return {
                'success': False,
                'message': f'Gerrit API 请求失败: {str(e)}',
                'data': None
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': f'Gerrit API 响应格式错误: {str(e)}',
                'data': None
            }
    
    # ==================== 项目相关接口 ====================
    
    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """
        获取项目信息
        
        Args:
            project_name: 项目名称
            
        Returns:
            包含项目信息的字典
        """
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}"
        return self._request('GET', endpoint)
    
    def get_project_branches(self, project_name: str) -> Dict[str, Any]:
        """
        获取项目所有分支
        
        Args:
            project_name: 项目名称
            
        Returns:
            包含分支列表的字典
        """
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}/branches/"
        return self._request('GET', endpoint)
    
    def get_branch_info(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """
        获取指定分支信息
        
        Args:
            project_name: 项目名称
            branch_name: 分支名称
            
        Returns:
            包含分支信息的字典（包括最新 revision）
        """
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}/branches/{requests.utils.quote(branch_name, safe='')}"
        return self._request('GET', endpoint)
    
    # ==================== 提交/变更相关接口 ====================
    
    def get_change_detail(self, change_id: str) -> Dict[str, Any]:
        """
        获取变更详情
        
        Args:
            change_id: 变更ID（可以是 change number 或 commit hash）
            
        Returns:
            包含变更详情的字典
        """
        endpoint = f"changes/{change_id}/detail"
        return self._request('GET', endpoint)
    
    def get_commit_detail(self, commit_hash: str) -> Dict[str, Any]:
        """
        获取提交详情（别名，与 get_change_detail 相同）
        
        Args:
            commit_hash: 提交哈希
            
        Returns:
            包含提交详情的字典
        """
        return self.get_change_detail(commit_hash)
    
    def get_commit_from_gitiles(self, project_name: str, commit_hash: str) -> Dict[str, Any]:
        """
        通过 Gitiles API 获取 commit 信息（用于非 Gerrit review 的 commit）
        
        Args:
            project_name: 项目名称
            commit_hash: 提交哈希
            
        Returns:
            包含提交信息的字典
        """
        # Gitiles API: /plugins/gitiles/{project}/+/{commit}?format=JSON
        url = f"{self.base_url}/plugins/gitiles/{project_name}/+/{commit_hash}?format=JSON"
        
        try:
            response = self.session.get(url, verify=False, timeout=30)
            
            if response.status_code == 404:
                return {
                    'success': False,
                    'message': f'Commit {commit_hash[:12]} 不存在',
                    'data': None
                }
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Gitiles API 返回错误，HTTP 状态码: {response.status_code}',
                    'data': None
                }
            
            # Gitiles 返回可能有 )]}'  前缀
            response_text = response.text.strip()
            if response_text.startswith(")]}'"):
                response_text = response_text[4:].strip()
            
            data = json.loads(response_text)
            
            # 提取 commit message 的第一行作为 subject
            message = data.get('message', '')
            subject = message.split('\n')[0] if message else ''
            
            return {
                'success': True,
                'message': '成功获取 commit 信息',
                'data': {
                    'subject': subject,
                    'message': message,
                    'commit': commit_hash,
                    'author': data.get('author', {}),
                    'committer': data.get('committer', {}),
                    'tree': data.get('tree', '')
                }
            }
            
        except requests.RequestException as e:
            return {
                'success': False,
                'message': f'Gitiles API 请求失败: {str(e)}',
                'data': None
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': f'Gitiles API 响应格式错误: {str(e)}',
                'data': None
            }
    
    def search_changes(self, query: str, limit: int = 25, start: int = 0) -> Dict[str, Any]:
        """
        搜索变更
        
        Args:
            query: Gerrit 查询字符串，例如：
                   - "project:deepin-music branch:master"
                   - "status:merged after:2024-01-01"
                   - "project:deepin-music branch:master status:merged"
            limit: 返回结果数量限制
            start: 起始位置（用于分页）
            
        Returns:
            包含变更列表的字典
        """
        params = {
            'q': query,
            'n': limit,
            'start': start
        }
        # 将参数转换为 URL 查询字符串
        query_string = '&'.join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
        endpoint = f"changes/?{query_string}"
        return self._request('GET', endpoint)
    
    def get_commits_between(self, project_name: str, branch: str, 
                           after_commit: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        获取指定提交之后的所有提交
        
        Args:
            project_name: 项目名称
            branch: 分支名称
            after_commit: 起始提交哈希（不包含此提交），如果为None则返回所有提交
            limit: 返回结果数量限制
            
        Returns:
            包含提交列表的字典
        """
        # 构建查询条件
        query = f"project:{project_name} branch:{branch} status:merged"
        
        result = self.search_changes(query, limit=limit)
        
        if not result['success']:
            return result
        
        changes = result['data']
        
        # 如果指定了 after_commit，过滤出该提交之后的变更
        if after_commit and changes:
            filtered_changes = []
            found_after = False
            
            # 遍历变更列表，找到 after_commit 之后的所有变更
            for change in changes:
                current_rev = change.get('current_revision', '')
                
                # 如果已经找到了起始点，添加后续所有变更
                if found_after:
                    filtered_changes.append(change)
                # 检查是否是起始提交
                elif current_rev.startswith(after_commit) or after_commit.startswith(current_rev):
                    found_after = True
            
            result['data'] = filtered_changes
            result['message'] = f'找到 {len(filtered_changes)} 个新提交'
        
        return result
    
    # ==================== 分支最新提交相关 ====================
    
    def get_latest_commit(self, project_name: str, branch: str) -> Dict[str, Any]:
        """
        获取分支最新提交
        
        Args:
            project_name: 项目名称
            branch: 分支名称
            
        Returns:
            包含最新提交信息的字典
        """
        result = self.get_branch_info(project_name, branch)
        
        if not result['success']:
            return result
        
        branch_data = result['data']
        revision = branch_data.get('revision')
        
        if not revision:
            return {
                'success': False,
                'message': '未找到最新提交',
                'data': None
            }
        
        return {
            'success': True,
            'message': '成功获取最新提交',
            'data': {
                'revision': revision,
                'branch_info': branch_data
            }
        }
    
    def check_sync_status(self, project_name: str, branch: str, 
                         expected_commit: str) -> Dict[str, Any]:
        """
        检查分支是否已同步到指定提交
        
        Args:
            project_name: 项目名称
            branch: 分支名称
            expected_commit: 期望的提交哈希
            
        Returns:
            包含同步状态的字典
        """
        result = self.get_latest_commit(project_name, branch)
        
        if not result['success']:
            return result
        
        latest_revision = result['data']['revision']
        # 比较时只比较前40个字符（完整的 commit hash）
        is_synced = latest_revision[:40] == expected_commit[:40]
        
        return {
            'success': True,
            'message': '同步检查完成',
            'data': {
                'is_synced': is_synced,
                'latest_revision': latest_revision,
                'expected_commit': expected_commit
            }
        }


# ==================== 便捷函数 ====================

def create_gerrit_service(gerrit_url: str, username: str, password: str) -> GerritService:
    """
    创建 Gerrit 服务实例
    
    Args:
        gerrit_url: Gerrit 服务器地址
        username: 用户名
        password: 密码
        
    Returns:
        GerritService 实例
    """
    return GerritService(gerrit_url, username, password)


def get_commit_message_from_git(repo_path: str, commit_hash: str) -> str:
    """
    通过本地 Git 仓库获取 commit message
    
    Args:
        repo_path: 本地仓库路径
        commit_hash: commit hash
        
    Returns:
        commit message 的第一行（标题），如果失败返回空字符串
    """
    try:
        from git import Repo
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)
        # 返回第一行作为 subject
        message = commit.message.strip()
        subject = message.split('\n')[0] if message else ''
        return subject
    except Exception:
        return ''

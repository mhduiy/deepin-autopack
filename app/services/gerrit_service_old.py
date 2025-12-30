"""
Gerrit API 服务
提供 Gerrit 仓库的所有操作接口
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from typing import Dict, List, Optional, Any


class GerritService:
    """Gerrit API 服务类"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        初始化 Gerrit 服务
        
        Args:
            base_url: Gerrit 服务器地址，例如：https://gerrit.example.com
            username: Gerrit 用户名
            password: Gerrit 密码
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
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
        url = f"{self.base_url}/a/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=kwargs.pop('timeout', 30),
                verify=False,  # 如果是内网环境，可能需要禁用SSL验证
                **kwargs
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'Gerrit API 返回错误，HTTP 状态码: {response.status_code}',
                    'data': None
                }
            
            # Gerrit API 返回的数据前面有 )]}'，需要去掉
            response_text = response.text
            if response_text.startswith(")]}'"):
                response_text = response_text[4:]
            
            data = json.loads(response_text) if response_text else {}
            
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
        """获取项目信息"""
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}"
        return self._request('GET', endpoint)
    
    def get_project_branches(self, project_name: str) -> Dict[str, Any]:
        """获取项目所有分支"""
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}/branches/"
        return self._request('GET', endpoint)
    
    def get_branch_info(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """获取指定分支信息（包括最新 revision）"""
        endpoint = f"projects/{requests.utils.quote(project_name, safe='')}/branches/{requests.utils.quote(branch_name, safe='')}"
        return self._request('GET', endpoint)
    
    # ==================== 提交/变更相关接口 ====================
    
    def get_change_detail(self, change_id: str) -> Dict[str, Any]:
        """获取变更详情"""
        endpoint = f"changes/{change_id}/detail"
        return self._request('GET', endpoint)
    
    def search_changes(self, query: str, limit: int = 25) -> Dict[str, Any]:
        """搜索变更，query 示例: "project:deepin-music branch:master status:merged" """
        params = {'q': query, 'n': limit}
        endpoint = f"changes/?{requests.compat.urlencode(params)}"
        return self._request('GET', endpoint)
    
    def get_commits_between(self, project_name: str, branch: str, after_commit: Optional[str] = None) -> Dict[str, Any]:
        """获取指定提交之后的所有提交"""
        query = f"project:{project_name} branch:{branch} status:merged"
        result = self.search_changes(query, limit=100)
        
        if not result['success'] or not after_commit:
            return result
        
        # 过滤出 after_commit 之后的变更
        changes = result['data']
        filtered_changes = []
        found_after = False
        
        for change in changes:
            if found_after:
                filtered_changes.append(change)
            elif change.get('current_revision') == after_commit:
                found_after = True
        
        result['data'] = filtered_changes
        return result
    
    # ==================== 分支最新提交相关 ====================
    
    def get_latest_commit(self, project_name: str, branch: str) -> Dict[str, Any]:
        """获取分支最新提交"""
        result = self.get_branch_info(project_name, branch)
        if not result['success']:
            return result
        
        revision = result['data'].get('revision')
        if not revision:
            return {'success': False, 'message': '未找到最新提交', 'data': None}
        
        return {'success': True, 'message': '成功获取最新提交', 'data': {'revision': revision, 'branch_info': result['data']}}
    
    def check_sync_status(self, project_name: str, branch: str, expected_commit: str) -> Dict[str, Any]:
        """检查分支是否已同步到指定提交"""
        result = self.get_latest_commit(project_name, branch)
        if not result['success']:
            return result
        
        latest_revision = result['data']['revision']
        return {
            'success': True,
            'message': '同步检查完成',
            'data': {
                'is_synced': latest_revision == expected_commit,
                'latest_revision': latest_revision,
                'expected_commit': expected_commit
            }
        }


def create_gerrit_service(gerrit_url: str, username: str, password: str) -> GerritService:
    """创建 Gerrit 服务实例"""
    return GerritService(gerrit_url, username, password)

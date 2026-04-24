from flask import current_app
import requests
import logging

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self, repo_owner, repo_name, access_token):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.access_token = access_token
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

    def create_pull_request(self, title, head, base, body=""):
        url = f"{self.base_url}/pulls"
        headers = {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        }
        response = requests.post(url, json=data, headers=headers)
        return response.json()

    def get_commits(self, branch):
        url = f"{self.base_url}/commits?sha={branch}"
        response = requests.get(url)
        return response.json()

    def get_pull_requests(self):
        url = f"{self.base_url}/pulls"
        response = requests.get(url)
        return response.json()
    
    def get_pull_request(self, pull_number):
        """获取指定PR的详细信息"""
        url = f"{self.base_url}/pulls/{pull_number}"
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.access_token:
            headers["Authorization"] = f"token {self.access_token}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取PR #{pull_number} 信息失败: {e}")
            return None

    def merge_pull_request(self, pull_number):
        url = f"{self.base_url}/pulls/{pull_number}/merge"
        headers = {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.put(url, headers=headers)
        return response.json()
    
    @staticmethod
    def get_pr_info_from_url(pr_url, access_token=None):
        """从PR URL获取PR信息"""
        try:
            # 解析URL获取owner, repo, pr_number
            # https://github.com/owner/repo/pull/123
            parts = pr_url.rstrip('/').split('/')
            if len(parts) >= 4 and 'github.com' in pr_url:
                owner = parts[-4]
                repo = parts[-3]
                pr_number = parts[-1]
                
                service = GitHubService(owner, repo, access_token)
                return service.get_pull_request(pr_number)
        except Exception as e:
            logger.error(f"解析PR URL失败: {pr_url}, {e}")
        return None
from flask import current_app
import requests

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

    def merge_pull_request(self, pull_number):
        url = f"{self.base_url}/pulls/{pull_number}/merge"
        headers = {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.put(url, headers=headers)
        return response.json()
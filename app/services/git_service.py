from git import Repo
import os

class GitService:
    def __init__(self, repo_path):
        self.repo_path = repo_path

    def clone_repo(self, repo_url):
        if not os.path.exists(self.repo_path):
            Repo.clone_from(repo_url, self.repo_path)
            return True
        return False

    def pull_latest(self):
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path)
            origin = repo.remotes.origin
            origin.pull()
            return True
        return False

    def get_latest_commit(self):
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path)
            return repo.head.commit.hexsha
        return None

    def create_tag(self, tag_name, message):
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path)
            repo.create_tag(tag_name, message=message)
            return True
        return False

    def commit_changes(self, message):
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path)
            repo.git.add(A=True)
            repo.index.commit(message)
            return True
        return False

    def push_changes(self):
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path)
            origin = repo.remotes.origin
            origin.push()
            return True
        return False
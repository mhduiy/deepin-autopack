from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gerrit_url = db.Column(db.String(200), nullable=False)
    gerrit_branch = db.Column(db.String(100), nullable=False)
    gerrit_repo_url = db.Column(db.String(200), nullable=True)  # Gerrit 仓库地址（用于克隆）
    github_url = db.Column(db.String(200), nullable=False)
    github_branch = db.Column(db.String(100), nullable=False)
    last_commit_hash = db.Column(db.String(40), nullable=False)
    local_repo_path = db.Column(db.String(500), nullable=True)  # 本地仓库路径
    repo_status = db.Column(db.String(20), default='pending')  # pending/cloning/ready/error
    repo_error = db.Column(db.Text, nullable=True)  # 错误信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Project {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gerrit_url': self.gerrit_url,
            'gerrit_branch': self.gerrit_branch,
            'github_url': self.github_url,
            'github_branch': self.github_branch,
            'last_commit_hash': self.last_commit_hash,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
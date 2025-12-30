from app import db

class Project(db.Model):
    """项目配置模型"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, comment='项目名')
    gerrit_url = db.Column(db.String(500), comment='Gerrit地址')
    gerrit_branch = db.Column(db.String(100), comment='Gerrit分支')
    github_url = db.Column(db.String(500), comment='GitHub地址')
    github_branch = db.Column(db.String(100), comment='GitHub分支')
    last_commit_hash = db.Column(db.String(40), comment='上一次打包的commit hash')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'gerrit_url': self.gerrit_url,
            'gerrit_branch': self.gerrit_branch,
            'github_url': self.github_url,
            'github_branch': self.github_branch,
            'last_commit_hash': self.last_commit_hash
        }
    
    def __repr__(self):
        return f'<Project {self.name}>'

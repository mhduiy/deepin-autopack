from sqlalchemy import Column, Integer, String, Text
from app import db

class Config(db.Model):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    project_name = Column(String(100), nullable=False)
    gerrit_url = Column(String(200), nullable=False)
    gerrit_branch = Column(String(100), nullable=False)
    github_url = Column(String(200), nullable=False)
    github_branch = Column(String(100), nullable=False)
    last_commit_hash = Column(String(40), nullable=False)

    def __repr__(self):
        return f'<Config {self.project_name}>'
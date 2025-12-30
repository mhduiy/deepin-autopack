from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app import db

class BuildLog(db.Model):
    __tablename__ = 'build_logs'

    id = Column(Integer, primary_key=True)
    project_name = Column(String(100), nullable=False)
    commit_hash = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False)
    log_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<BuildLog {self.id} - {self.project_name} - {self.status}>'
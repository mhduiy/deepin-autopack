from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object('config.Config')
    
    # 初始化数据库
    db.init_app(app)
    
    # 注册路由
    from app.routes.project import project_bp
    from app.routes.config import config_bp
    from app.routes.monitor import monitor_bp
    from app.routes.crp import crp_bp
    from app.routes.build import build_bp
    app.register_blueprint(project_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(crp_bp)
    app.register_blueprint(build_bp)
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app
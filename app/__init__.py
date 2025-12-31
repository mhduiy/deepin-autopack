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
        
        # 恢复运行中的任务
        _recover_running_tasks()
    
    return app


def _recover_running_tasks():
    """恢复运行中的任务（应用重启后）"""
    try:
        from app.models.build_task import BuildTask
        from app.services.build_task_service import TaskQueue
        import logging
        
        logger = logging.getLogger(__name__)
        
        # 查找所有running状态的任务
        running_tasks = BuildTask.query.filter_by(status='running').all()
        
        if running_tasks:
            logger.info(f"发现 {len(running_tasks)} 个运行中的任务，开始恢复...")
            
            task_queue = TaskQueue()
            
            for task in running_tasks:
                try:
                    # 重新提交到队列
                    task_queue.submit_task(task.id)
                    logger.info(f"任务已恢复: task_id={task.id}, project={task.project_name}")
                except Exception as e:
                    logger.error(f"恢复任务失败: task_id={task.id}, error={e}")
            
            logger.info("任务恢复完成")
        else:
            logger.info("没有需要恢复的任务")
            
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"恢复任务时出错: {e}")
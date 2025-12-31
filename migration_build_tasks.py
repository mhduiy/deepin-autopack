"""
数据库迁移脚本 - 创建打包任务表

使用方法:
1. 确保数据库配置正确
2. 运行: python migration_build_tasks.py

注意: 此脚本会创建新表，不会修改现有表
"""

import sys
import os

# 添加项目路径到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import BuildTask, BuildTaskStep

def run_migration():
    """运行数据库迁移"""
    app = create_app()
    
    with app.app_context():
        print("开始数据库迁移...")
        
        try:
            # 创建表
            print("创建 build_tasks 表...")
            print("创建 build_task_steps 表...")
            
            # 使用 SQLAlchemy 创建表
            db.create_all()
            
            print("✓ 数据库迁移完成！")
            print("\n创建的表:")
            print("  - build_tasks (打包任务表)")
            print("  - build_task_steps (任务步骤表)")
            
        except Exception as e:
            print(f"✗ 迁移失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("数据库迁移 - 打包任务系统")
    print("=" * 60)
    
    success = run_migration()
    
    if success:
        print("\n迁移成功完成！")
        sys.exit(0)
    else:
        print("\n迁移失败！")
        sys.exit(1)

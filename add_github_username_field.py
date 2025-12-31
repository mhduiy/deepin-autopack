#!/usr/bin/env python3
"""添加github_username字段到global_config表"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def migrate():
    app = create_app()
    with app.app_context():
        try:
            # 执行SQL语句
            sql = "ALTER TABLE global_config ADD COLUMN github_username VARCHAR(100) COMMENT 'GitHub用户名' AFTER maintainer_email"
            db.session.execute(db.text(sql))
            db.session.commit()
            print("✓ 成功添加 github_username 字段")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("✓ github_username 字段已存在，跳过")
            else:
                print(f"✗ 添加字段失败: {e}")
                raise

if __name__ == '__main__':
    migrate()

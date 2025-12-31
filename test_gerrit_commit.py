#!/usr/bin/env python3
"""
测试从 Gerrit 获取指定分支的最新 commit hash
"""

from app import create_app
from app.models import GlobalConfig, Project
from app.services.gerrit_service import create_gerrit_service

def test_get_gerrit_commit():
    """测试获取 Gerrit 分支最新提交"""
    app = create_app()
    
    with app.app_context():
        # 获取全局配置
        config = GlobalConfig.query.first()
        if not config or not config.ldap_username or not config.ldap_password:
            print("❌ 未配置 LDAP 账号密码")
            return
        
        # 查找 dde-appearance 项目
        project = Project.query.filter_by(name='dde-appearance').first()
        if not project:
            print("❌ 未找到 dde-appearance 项目")
            return
        
        if not project.gerrit_url or not project.gerrit_branch:
            print("❌ 项目未配置 Gerrit 地址或分支")
            return
        
        print(f"✓ 项目信息:")
        print(f"  名称: {project.name}")
        print(f"  Gerrit URL: {project.gerrit_url}")
        print(f"  Gerrit 分支: {project.gerrit_branch}")
        
        # 提取项目名称（从 Gerrit URL）
        # URL 格式: https://gerrit.uniontech.com/plugins/gitiles/snipe/dde-appearance
        # 或: https://gerrit.uniontech.com/admin/repos/dde/dde-appearance
        if '/plugins/gitiles/' in project.gerrit_url:
            # Gitiles URL 格式
            gerrit_project_name = project.gerrit_url.split('/plugins/gitiles/')[-1]
        elif '/admin/repos/' in project.gerrit_url:
            # Admin repos URL 格式
            gerrit_project_name = project.gerrit_url.split('/admin/repos/')[-1]
        else:
            # 直接取最后一部分
            gerrit_project_name = project.gerrit_url.split('/')[-1]
        
        print(f"  Gerrit 项目名: {gerrit_project_name}")
        
        print("\n" + "="*60)
        
        # 创建 Gerrit 服务
        gerrit = create_gerrit_service(
            gerrit_url='https://gerrit.uniontech.com',
            username=config.ldap_username,
            password=config.ldap_password
        )
        
        print(f"\n🔍 获取 Gerrit 分支最新提交...")
        print(f"  项目: {gerrit_project_name}")
        print(f"  分支: {project.gerrit_branch}")
        
        # 获取最新提交
        result = gerrit.get_latest_commit(gerrit_project_name, project.gerrit_branch)
        
        if result['success']:
            revision = result['data']['revision']
            print(f"\n✓ 成功获取最新提交:")
            print(f"  Commit Hash: {revision}")
            print(f"  完整 Hash: {revision}")
            print(f"  短 Hash: {revision[:8]}")
            
            # 如果项目配置了 GitHub，也显示 GitHub 信息
            if project.github_url and project.github_branch:
                print(f"\n📊 GitHub 信息（用于对比）:")
                print(f"  GitHub URL: {project.github_url}")
                print(f"  GitHub 分支: {project.github_branch}")
                print(f"\n💡 同步检测说明:")
                print(f"  当 Gerrit 的最新 commit hash 等于 GitHub PR 的 commit hash 时，")
                print(f"  说明 GitHub→Gerrit 的同步已完成。")
        else:
            print(f"\n❌ 获取失败: {result['message']}")
            if result.get('data'):
                print(f"  详细信息: {result['data']}")

if __name__ == '__main__':
    test_get_gerrit_commit()

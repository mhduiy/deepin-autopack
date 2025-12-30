from flask import Blueprint, render_template, request, jsonify
from app.models import Project
from app.services.repo_service import RepoService
from app.services.changelog_service import ChangelogService
from app import db
import logging

monitor_bp = Blueprint('monitor', __name__)
logger = logging.getLogger(__name__)

@monitor_bp.route('/monitor')
def monitor():
    """提交监控页面"""
    # 只显示已就绪的项目
    projects = Project.query.filter_by(repo_status='ready').all()
    
    project_data = []
    for project in projects:
        # 获取当前版本
        current_version = None
        if project.local_repo_path:
            current_version = ChangelogService.get_current_version(project.local_repo_path)
        
        # 获取 changelog 最后修改的 commit（优先）
        changelog_commit = None
        if project.local_repo_path:
            changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
        
        # 获取最新 tag（降级）
        latest_tag = RepoService.get_latest_tag(project)
        
        # 确定起始点：优先使用 changelog commit，否则使用 tag
        since_point = changelog_commit or latest_tag
        since_type = 'changelog' if changelog_commit else 'tag'
        
        # 获取新增提交
        new_commits_count = 0
        new_commits = []
        if since_point:
            new_commits_count, new_commits = RepoService.get_commits_since(project, since_point)
        
        # 获取最新提交
        latest_commit = RepoService.get_latest_commit(project)
        
        project_data.append({
            'project': project,
            'current_version': current_version,
            'latest_tag': latest_tag,
            'changelog_commit': changelog_commit,
            'since_point': since_point,
            'since_type': since_type,
            'new_commits_count': new_commits_count,
            'new_commits': new_commits,
            'latest_commit': latest_commit
        })
    
    return render_template('monitor.html', projects=project_data)

@monitor_bp.route('/monitor/projects/<int:project_id>/refresh', methods=['POST'])
def refresh_project(project_id):
    """刷新单个项目的信息"""
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.repo_status != 'ready':
            return jsonify({
                'success': False,
                'message': '项目仓库未就绪'
            }), 400
        
        # 更新仓库
        RepoService.update_repo(project)
        
        # 重新获取信息
        current_version = ChangelogService.get_current_version(project.local_repo_path)
        changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
        latest_tag = RepoService.get_latest_tag(project)
        
        # 确定起始点
        since_point = changelog_commit or latest_tag
        new_commits_count = 0
        if since_point:
            new_commits_count, _ = RepoService.get_commits_since(project, since_point)
        
        latest_commit = RepoService.get_latest_commit(project)
        
        # 更新数据库中的 last_commit_hash
        if latest_commit:
            project.last_commit_hash = latest_commit['full_hash']
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '刷新成功',
            'data': {
                'current_version': current_version,
                'latest_tag': latest_tag,
                'new_commits_count': new_commits_count,
                'latest_commit': latest_commit
            }
        })
        
    except Exception as e:
        logger.error(f"刷新项目失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@monitor_bp.route('/monitor/refresh-all', methods=['POST'])
def refresh_all():
    """刷新所有项目"""
    try:
        projects = Project.query.filter_by(repo_status='ready').all()
        
        success_count = 0
        failed_count = 0
        
        for project in projects:
            try:
                # 更新仓库
                result = RepoService.update_repo(project)
                if result:
                    # 更新 last_commit_hash
                    latest_commit = RepoService.get_latest_commit(project)
                    if latest_commit:
                        project.last_commit_hash = latest_commit['full_hash']
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"刷新项目 {project.name} 失败: {e}")
                failed_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'刷新完成！成功: {success_count}, 失败: {failed_count}',
            'data': {
                'success_count': success_count,
                'failed_count': failed_count
            }
        })
        
    except Exception as e:
        logger.error(f"批量刷新失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

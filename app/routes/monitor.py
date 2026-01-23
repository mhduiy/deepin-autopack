from flask import Blueprint, render_template, request, jsonify
from app.models import Project
from app.services.repo_service import RepoService
from app.services.changelog_service import ChangelogService
from app import db
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

monitor_bp = Blueprint('monitor', __name__)
logger = logging.getLogger(__name__)

def process_single_project(project):
    """处理单个项目的数据获取（用于并行处理）"""
    try:
        # 获取当前版本
        current_version = None
        if project.local_repo_path:
            current_version = ChangelogService.get_current_version(project.local_repo_path)
        
        # 获取 changelog 最后修改的 commit
        changelog_commit = None
        if project.local_repo_path:
            changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
        
        # 使用 changelog commit 作为起始点
        since_point = changelog_commit
        
        # 获取新增提交
        new_commits_count = 0
        new_commits = []
        if since_point:
            new_commits_count, new_commits = RepoService.get_commits_since(project, since_point)
        
        # 获取最新提交
        latest_commit = RepoService.get_latest_commit(project)
        
        return {
            'success': True,
            'data': {
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'github_url': project.github_url,
                    'github_branch': project.github_branch,
                    'gerrit_branch': project.gerrit_branch
                },
                'current_version': current_version,
                'changelog_commit': changelog_commit,
                'since_point': since_point,
                'new_commits_count': new_commits_count,
                'new_commits': new_commits,
                'latest_commit': latest_commit
            }
        }
    except Exception as e:
        logger.error(f"处理项目 {project.name} 失败: {str(e)}", exc_info=True)
        return {
            'success': False,
            'project_name': project.name,
            'error': str(e)
        }

@monitor_bp.route('/monitor')
def monitor():
    """提交监控页面"""
    # 只返回空页面，数据通过API异步加载
    return render_template('monitor.html')

@monitor_bp.route('/api/monitor/data', methods=['GET'])
def monitor_data():
    """获取监控数据的API（串行版本，带性能日志）"""
def monitor_data():
    """获取监控数据的API"""
    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status='ready').all()
        
        project_data = []
        for project in projects:
            # 获取当前版本
            current_version = None
            if project.local_repo_path:
                current_version = ChangelogService.get_current_version(project.local_repo_path)
            
            # 获取 changelog 最后修改的 commit
            changelog_commit = None
            if project.local_repo_path:
                changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
            
            # 使用 changelog commit 作为起始点
            since_point = changelog_commit
            
            # 获取新增提交
            new_commits_count = 0
            new_commits = []
            if since_point:
                new_commits_count, new_commits = RepoService.get_commits_since(project, since_point)
            
            # 获取最新提交
            latest_commit = RepoService.get_latest_commit(project)

            
            project_data.append({
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'github_url': project.github_url,
                    'github_branch': project.github_branch,
                    'gerrit_branch': project.gerrit_branch
                },
                'current_version': current_version,
                'changelog_commit': changelog_commit,
                'since_point': since_point,
                'new_commits_count': new_commits_count,
                'new_commits': new_commits,
                'latest_commit': latest_commit
            })
        
        return jsonify({
            'success': True,
            'data': project_data
        })
    except Exception as e:
        logger.error(f"获取监控数据失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@monitor_bp.route('/api/monitor/data-parallel', methods=['GET'])
def monitor_data_parallel():
    """获取监控数据的API（并行版本，推荐使用）"""
    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status='ready').all()
        
        if not projects:
            return jsonify({
                'success': True,
                'data': []
            })
        
        # 使用线程池并行处理所有项目
        project_data = []
        max_workers = min(len(projects), 5)  # 最多5个并发线程
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_project = {executor.submit(process_single_project, project): project 
                                for project in projects}
            
            # 收集结果
            for future in as_completed(future_to_project):
                result = future.result()
                if result['success']:
                    project_data.append(result['data'])
                else:
                    logger.warning(f"项目 {result.get('project_name')} 处理失败: {result.get('error')}")
        
        return jsonify({
            'success': True,
            'data': project_data
        })
    except Exception as e:
        logger.error(f"获取监控数据失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

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
        
        # 清除缓存
        if project.local_repo_path:
            ChangelogService.clear_cache(project.local_repo_path)
        
        # 更新仓库
        RepoService.update_repo(project)
        
        # 重新获取信息
        current_version = ChangelogService.get_current_version(project.local_repo_path)
        changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
        
        # 使用 changelog commit 作为起始点
        since_point = changelog_commit
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
        
        # 清除所有缓存
        ChangelogService.clear_cache()
        
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

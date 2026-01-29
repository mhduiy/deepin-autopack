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
        
        # 排序：1. 有新增提交的优先 2. 最新提交时间最新的优先
        project_data.sort(key=lambda x: (
            -x['new_commits_count'],  # 新增提交数降序（负号表示降序）
            -(x['latest_commit']['timestamp'] if x['latest_commit'] and 'timestamp' in x['latest_commit'] else 0)  # 时间戳降序
        ))
        
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
        
        # 排序：1. 有新增提交的优先 2. 最新提交时间最新的优先
        project_data.sort(key=lambda x: (
            -x['new_commits_count'],  # 新增提交数降序（负号表示降序）
            -(x['latest_commit']['timestamp'] if x['latest_commit'] and 'timestamp' in x['latest_commit'] else 0)  # 时间戳降序
        ))
        
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

@monitor_bp.route('/monitor/refresh-all', methods=['GET'])
def refresh_all():
    """刷新所有项目 - 使用流式响应返回进度"""
    from flask import Response, current_app
    import json
    
    # 获取应用实例
    app = current_app._get_current_object()
    
    # 在应用上下文中先查询数据
    try:
        projects = Project.query.filter_by(repo_status='ready').all()
        total = len(projects)
        
        if total == 0:
            def empty_generate():
                yield f"data: {json.dumps({'type': 'complete', 'message': '没有需要刷新的项目', 'success_count': 0, 'failed_count': 0})}\n\n"
            return Response(empty_generate(), mimetype='text/event-stream')
        
        # 转换为简单的数据结构，避免在生成器中访问数据库对象
        project_list = [{
            'id': p.id,
            'name': p.name,
            'local_repo_path': p.local_repo_path
        } for p in projects]
        
    except Exception as e:
        logger.error(f"查询项目失败: {str(e)}", exc_info=True)
        def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return Response(error_generate(), mimetype='text/event-stream')
    
    def generate():
        # 在生成器中手动推送应用上下文
        with app.app_context():
            try:
                # 清除所有缓存
                ChangelogService.clear_cache()
                
                success_count = 0
                failed_count = 0
                
                # 发送开始事件
                yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"
                
                for index, project_data in enumerate(project_list, 1):
                    try:
                        project_name = project_data['name']
                        
                        # 发送进度更新
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'project_name': project_name, 'status': 'processing'})}\n\n"
                        
                        # 重新获取项目对象
                        project = Project.query.get(project_data['id'])
                        if not project:
                            raise Exception(f"项目不存在: {project_name}")
                        
                        # 更新仓库
                        result = RepoService.update_repo(project)
                        if result:
                            # 更新 last_commit_hash
                            latest_commit = RepoService.get_latest_commit(project)
                            if latest_commit:
                                project.last_commit_hash = latest_commit['full_hash']
                            db.session.commit()
                            success_count += 1
                            status = 'success'
                        else:
                            failed_count += 1
                            status = 'failed'
                        
                        # 发送项目完成状态
                        yield f"data: {json.dumps({'type': 'project_complete', 'current': index, 'total': total, 'project_name': project_name, 'status': status})}\n\n"
                        
                    except Exception as e:
                        logger.error(f"刷新项目 {project_name} 失败: {e}")
                        failed_count += 1
                        yield f"data: {json.dumps({'type': 'project_complete', 'current': index, 'total': total, 'project_name': project_name, 'status': 'failed', 'error': str(e)})}\n\n"
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'complete', 'success_count': success_count, 'failed_count': failed_count, 'message': f'刷新完成！成功: {success_count}, 失败: {failed_count}'})}\n\n"
                
            except Exception as e:
                logger.error(f"批量刷新失败: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@monitor_bp.route('/api/monitor/export-new-commits', methods=['GET'])
def export_new_commits():
    """导出有新增提交的项目列表"""
    from flask import Response
    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status='ready').all()
        
        export_lines = []
        
        for project in projects:
            try:
                # 获取当前版本
                current_version = None
                if project.local_repo_path:
                    current_version = ChangelogService.get_current_version(project.local_repo_path)
                
                # 获取 changelog 最后修改的 commit
                changelog_commit = None
                if project.local_repo_path:
                    changelog_commit = ChangelogService.get_changelog_last_commit(project.local_repo_path)
                
                # 获取新增提交数
                new_commits_count = 0
                if changelog_commit:
                    new_commits_count, _ = RepoService.get_commits_since(project, changelog_commit)
                
                # 只导出有新增提交的项目
                if new_commits_count > 0:
                    version_str = current_version if current_version else '未知版本'
                    export_lines.append(f"{project.name} {version_str}")
            
            except Exception as e:
                logger.error(f"处理项目 {project.name} 失败: {e}")
                continue
        
        # 生成纯文本内容
        content = '\n'.join(export_lines)
        
        # 返回文本文件
        return Response(
            content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': 'attachment; filename=projects_with_new_commits.txt'
            }
        )
        
    except Exception as e:
        logger.error(f"导出失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

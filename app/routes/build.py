"""
打包任务路由
"""

import json
from flask import Blueprint, render_template, jsonify, request
from app.services.build_task_service import BuildTaskService
from app.models.build_task import BuildTask
from app.services.github_service import GitHubService
from app.services.workflow_service import WorkflowService
from app.models import GlobalConfig
from app.models.project import Project
import logging
import os

logger = logging.getLogger(__name__)

build_bp = Blueprint('build', __name__)


@build_bp.route('/tasks')
def tasks():
    """打包任务列表页面"""
    return render_template('build.html')


@build_bp.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """获取任务列表API"""
    try:
        # 从数据库读取任务列表
        tasks = BuildTaskService.get_all_tasks(limit=100)
        
        # 如果没有数据，返回空列表
        if not tasks:
            return jsonify({
                'success': True,
                'data': []
            })
        
        # 格式化任务数据以匹配前端需求
        formatted_tasks = []
        for task in tasks:
            # 格式化步骤数据
            steps = []
            for step in task.get('steps', []):
                steps.append({
                    'name': step['step_name'],
                    'status': step['status'],
                    'time': step['completed_at'] or step['started_at'],
                    'log_message': step['log_message'],
                    'error_message': step.get('error_message')
                })
            
            formatted_task = {
                'id': task['id'],
                'project_name': task['project_name'],
                'version': task['version'],
                'mode': task['package_mode'],
                'status': task['status'],
                'current_step': task['current_step'],
                'architectures': task['architectures'] or [],
                'steps': steps,
                'created_at': task['created_at'],
                'started_at': task['started_at'],
                'updated_at': task['updated_at'],
                'completed_at': task['completed_at'],
                'github_pr_url': task['github_pr_url'],
                'github_pr_number': task['github_pr_number'],
                'crp_build_url': task['crp_build_url'],
                'error': task['error_message']
            }
            formatted_tasks.append(formatted_task)
        
        return jsonify({
            'success': True,
            'data': formatted_tasks
        })
        
    except Exception as e:
        logger.exception(f"获取任务列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取任务列表失败: {str(e)}'
        }), 500

# ==================== 新增任务控制API ====================

@build_bp.route('/api/tasks/create', methods=['POST'])
def api_create_task():
    """创建打包任务"""
    try:
        data = request.get_json()
        
        # 验证必填参数
        required = ['project_id', 'mode', 'version']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'缺少必填参数: {field}'
                }), 400
        
        # 创建任务
        task = BuildTaskService.create_task(
            project_id=data['project_id'],
            package_config={
                'mode': data['mode'],
                'version': data['version'],
                'architectures': data.get('architectures', []),
                'crp_topic_id': data.get('crp_topic_id'),
                'crp_topic_name': data.get('crp_topic_name'),
                'start_commit_hash': data.get('start_commit_hash', ''),
                'github_action_name': data.get('github_action_name'),
                'github_action_params': data.get('github_action_params'),
            }
        )
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': '任务创建成功'
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"创建任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'创建任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>/start', methods=['POST'])
def api_start_task(task_id):
    """启动任务"""
    try:
        task = BuildTaskService.start_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已启动'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"启动任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'启动任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>', methods=['GET'])
def api_get_task(task_id):
    """获取任务详情"""
    try:
        task_data = BuildTaskService.get_task_status(task_id)
        return jsonify({
            'success': True,
            'data': task_data
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 404
    except Exception as e:
        logger.exception(f"获取任务详情失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取任务详情失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>/pause', methods=['POST'])
def api_pause_task(task_id):
    """暂停任务"""
    try:
        task = BuildTaskService.pause_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已暂停'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"暂停任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'暂停任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>/resume', methods=['POST'])
def api_resume_task(task_id):
    """恢复任务"""
    try:
        task = BuildTaskService.resume_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已恢复'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"恢复任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'恢复任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>/cancel', methods=['POST'])
def api_cancel_task(task_id):
    """取消任务"""
    try:
        task = BuildTaskService.cancel_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已取消'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"取消任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'取消任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>/retry', methods=['POST'])
def api_retry_task(task_id):
    """重试任务"""
    try:
        # 尝试获取JSON数据，如果失败则使用空字典
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}
        
        # 从查询参数或请求体获取from_step
        from_step = request.args.get('from_step', None)
        if from_step is None:
            from_step = data.get('from_step', None)
        
        # 转换为整数
        if from_step is not None:
            try:
                from_step = int(from_step)
            except (ValueError, TypeError):
                from_step = None
        
        task = BuildTaskService.retry_task(task_id, from_step)
        return jsonify({
            'success': True,
            'message': '任务已重试'
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.exception(f"重试任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'重试任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    """删除任务"""
    try:
        # 直接查询任务对象
        task = BuildTask.query.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        # 检查任务状态，运行中的任务不允许删除
        if task.status == 'running':
            return jsonify({
                'success': False,
                'message': '运行中的任务不能删除'
            }), 400
        
        BuildTaskService.delete_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已删除'
        })
    except Exception as e:
        logger.exception(f"删除任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'删除任务失败: {str(e)}'
        }), 500


@build_bp.route('/api/tasks/cleanup-completed', methods=['POST'])
def api_cleanup_completed_tasks():
    """清理所有已完成的任务"""
    try:
        deleted_count = BuildTaskService.cleanup_completed_tasks()
        return jsonify({
            'success': True,
            'message': f'已清理 {deleted_count} 个已完成的任务',
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.exception(f"清理任务失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清理任务失败: {str(e)}'
        }), 500

@build_bp.route('/api/tasks/unmerged-prs', methods=['GET'])
def api_get_unmerged_prs():
    """获取所有未合并的PR列表"""
    try:
        # 获取所有任务
        tasks = BuildTaskService.get_all_tasks(limit=1000)
        
        # 获取GitHub token（用于API调用）
        config = GlobalConfig.get_config()
        github_token = config.github_token if config else None
        
        # 只筛选未完成的任务（排除success和cancelled状态）
        # 未完成的状态包括: pending, running, paused, failed
        incomplete_statuses = ['pending', 'running', 'paused', 'failed']
        unmerged_prs = []
        
        for task in tasks:
            # 只处理未完成的任务
            if task.get('status') not in incomplete_statuses:
                continue
                
            # 检查是否有GitHub PR信息
            if not task.get('github_pr_url') or not task.get('github_pr_number'):
                continue
            
            pr_url = task.get('github_pr_url')
            pr_number = task.get('github_pr_number')
            
            # 实时从GitHub API获取PR状态
            pr_state = 'open'  # 默认状态
            pr_merged = False
            
            try:
                pr_info = GitHubService.get_pr_info_from_url(pr_url, github_token)
                if pr_info:
                    pr_state = pr_info.get('state', 'open')  # open, closed
                    pr_merged = pr_info.get('merged', False)  # True/False
                    
                    logger.info(f"PR #{pr_number}: state={pr_state}, merged={pr_merged}")
            except Exception as e:
                logger.warning(f"无法获取PR #{pr_number} 的实时状态: {e}")
            
            # 只添加未合并的PR（open状态或closed但未merged）
            if not pr_merged:
                unmerged_prs.append({
                    'task_id': task['id'],
                    'project_name': task['project_name'],
                    'version': task['version'],
                    'pr_number': pr_number,
                    'pr_url': pr_url,
                    'pr_status': 'merged' if pr_merged else pr_state,
                    'pr_merged': pr_merged,
                    'created_at': task['created_at'],
                    'task_status': task['status']
                })
        
        # 按创建时间倒序排序
        unmerged_prs.sort(key=lambda x: x['created_at'], reverse=True)
        
        logger.info(f"找到 {len(unmerged_prs)} 个未合并的PR（从 {len([t for t in tasks if t.get('status') in incomplete_statuses])} 个未完成任务中）")
        
        return jsonify({
            'success': True,
            'data': unmerged_prs,
            'total': len(unmerged_prs)
        })
        
    except Exception as e:
        logger.exception(f"获取未合并PR列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取未合并PR列表失败: {str(e)}'
        }), 500


@build_bp.route('/api/workflows/<project_name>', methods=['GET'])
def api_get_workflows(project_name):
    """获取项目的 GitHub Actions workflows"""
    logger.info(f"[DEBUG] api_get_workflows 被调用, project_name: {project_name}")
    try:
        # 查找项目
        project = Project.query.filter_by(name=project_name).first()
        logger.info(f"[DEBUG] 查询到的项目: {project}")
        if not project:
            logger.warning(f"[DEBUG] 项目不存在: {project_name}")
            return jsonify({
                'success': False,
                'message': f'项目 {project_name} 不存在'
            }), 404
        
        # 使用项目的本地仓库路径
        repo_path = project.local_repo_path
        logger.info(f"[DEBUG] 项目仓库路径: {repo_path}")
        
        # 检查仓库是否存在
        if not repo_path or not os.path.exists(repo_path):
            return jsonify({
                'success': False,
                'message': f'仓库未克隆或路径不存在，请先在项目管理页面克隆仓库'
            }), 404
        
        # 获取 workflows
        workflows = WorkflowService.get_workflows(repo_path)
        
        if not workflows:
            return jsonify({
                'success': True,
                'data': [],
                'message': '该项目没有可手动触发的 workflow'
            })
        
        logger.info(f"项目 {project_name} 找到 {len(workflows)} 个可手动触发的 workflow")
        
        return jsonify({
            'success': True,
            'data': workflows
        })
        
    except Exception as e:
        logger.exception(f"获取 workflows 失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取 workflows 失败: {str(e)}'
        }), 500


# ==================== Shuttle 构建日志 ====================

@build_bp.route('/api/shuttle/log/<int:job_id>', methods=['GET'])
def api_shuttle_log(job_id):
    """获取 Shuttle 构建日志"""
    from app.services.shuttle_service import ShuttleService

    try:
        log = ShuttleService.get_job_log(job_id)
        if log is None:
            return jsonify({
                'success': False,
                'message': '获取构建日志失败，请检查权限或稍后重试',
                'shuttle_url': ShuttleService.get_build_url(job_id),
            }), 502

        return jsonify({
            'success': True,
            'data': log,
            'shuttle_url': ShuttleService.get_build_url(job_id),
        })

    except Exception as e:
        logger.exception(f"获取 shuttle 日志失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取构建日志失败: {str(e)}'
        }), 500


@build_bp.route('/api/shuttle/log/<int:job_id>/analyze', methods=['POST'])
def api_shuttle_log_analyze(job_id):
    """AI 分析 Shuttle 构建日志（支持流式输出）"""
    from flask import Response, stream_with_context
    from app.services.shuttle_service import ShuttleService
    from app.services.ai_service import AIService

    try:
        log = ShuttleService.get_job_log(job_id)
        if log is None:
            return jsonify({
                'success': False,
                'message': '获取构建日志失败，无法分析',
            }), 502

        data = request.get_json(silent=True) or {}
        arch = data.get('arch', '')
        project_name = data.get('project_name', '')
        use_stream = request.args.get('stream', '1') == '1'

        if not use_stream:
            analysis = AIService.analyze(log, arch=arch, project_name=project_name)
            if analysis is None:
                return jsonify({
                    'success': False,
                    'message': 'AI 分析失败，请检查 AI 配置或稍后重试',
                }), 502
            return jsonify({
                'success': True,
                'data': analysis,
            })

        def generate():
            for chunk in AIService.analyze_stream(log, arch=arch, project_name=project_name):
                yield f"data: {json.dumps({'c': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )

    except Exception as e:
        logger.exception(f"AI 分析失败: {e}")
        return jsonify({
            'success': False,
            'message': f'AI 分析失败: {str(e)}'
        }), 500

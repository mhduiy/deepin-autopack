"""
打包任务路由
"""

from flask import Blueprint, render_template, jsonify, request
from app.services.build_task_service import BuildTaskService
import logging

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
                'start_commit_hash': data.get('start_commit_hash', '')
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


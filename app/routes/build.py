"""
打包任务路由
"""

from flask import Blueprint, render_template, jsonify
import logging

logger = logging.getLogger(__name__)

build_bp = Blueprint('build', __name__)


@build_bp.route('/tasks')
def tasks():
    """打包任务列表页面"""
    return render_template('build.html')


@build_bp.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """获取任务列表API（示例数据）"""
    # 示例数据
    tasks = [
        {
            'id': 1,
            'project_name': 'dde-control-center',
            'version': '6.0.52',
            'status': 'running',
            'current_step': 2,
            'steps': [
                {'name': '克隆仓库', 'status': 'completed', 'time': '2024-12-30 10:23:15'},
                {'name': '生成Tag', 'status': 'completed', 'time': '2024-12-30 10:23:45'},
                {'name': '提交PR', 'status': 'running', 'time': '2024-12-30 10:24:10'},
                {'name': '监控打包', 'status': 'pending', 'time': None},
                {'name': '完成', 'status': 'pending', 'time': None},
            ],
            'created_at': '2024-12-30 10:23:10',
            'updated_at': '2024-12-30 10:24:15'
        },
        {
            'id': 2,
            'project_name': 'deepin-music',
            'version': '7.0.8',
            'status': 'success',
            'current_step': 4,
            'steps': [
                {'name': '克隆仓库', 'status': 'completed', 'time': '2024-12-30 09:15:20'},
                {'name': '生成Tag', 'status': 'completed', 'time': '2024-12-30 09:15:50'},
                {'name': '提交PR', 'status': 'completed', 'time': '2024-12-30 09:16:20'},
                {'name': '监控打包', 'status': 'completed', 'time': '2024-12-30 09:25:40'},
                {'name': '完成', 'status': 'completed', 'time': '2024-12-30 09:25:45'},
            ],
            'created_at': '2024-12-30 09:15:10',
            'updated_at': '2024-12-30 09:25:45'
        },
        {
            'id': 3,
            'project_name': 'dde-appearance',
            'version': '6.1.15',
            'status': 'failed',
            'current_step': 1,
            'error': 'GitHub PR创建失败: API rate limit exceeded',
            'steps': [
                {'name': '克隆仓库', 'status': 'completed', 'time': '2024-12-30 08:30:15'},
                {'name': '生成Tag', 'status': 'completed', 'time': '2024-12-30 08:30:45'},
                {'name': '提交PR', 'status': 'failed', 'time': '2024-12-30 08:31:05'},
                {'name': '监控打包', 'status': 'pending', 'time': None},
                {'name': '完成', 'status': 'pending', 'time': None},
            ],
            'created_at': '2024-12-30 08:30:10',
            'updated_at': '2024-12-30 08:31:05'
        },
        {
            'id': 4,
            'project_name': 'deepin-calculator',
            'version': '6.5.2',
            'status': 'paused',
            'current_step': 3,
            'steps': [
                {'name': '克隆仓库', 'status': 'completed', 'time': '2024-12-30 07:20:10'},
                {'name': '生成Tag', 'status': 'completed', 'time': '2024-12-30 07:20:35'},
                {'name': '提交PR', 'status': 'completed', 'time': '2024-12-30 07:21:00'},
                {'name': '监控打包', 'status': 'paused', 'time': '2024-12-30 07:21:20'},
                {'name': '完成', 'status': 'pending', 'time': None},
            ],
            'created_at': '2024-12-30 07:20:05',
            'updated_at': '2024-12-30 07:25:15'
        },
    ]
    
    return jsonify({
        'success': True,
        'data': tasks
    })
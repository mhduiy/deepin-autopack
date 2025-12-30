"""
CRP主题管理路由
"""

from flask import Blueprint, render_template, jsonify, request
from app.services.crp_service import CRPService
from app.models import GlobalConfig
import logging

logger = logging.getLogger(__name__)

crp_bp = Blueprint('crp', __name__)


@crp_bp.route('/topics')
def topics():
    """CRP主题列表页面"""
    return render_template('crp_topics.html')


@crp_bp.route('/topics/<int:topic_id>')
def topic_detail(topic_id):
    """CRP主题详情页面"""
    return render_template('crp_topic_detail.html', topic_id=topic_id)


@crp_bp.route('/api/topics', methods=['GET'])
def api_get_topics():
    """获取主题列表API"""
    try:
        # 获取配置
        config = GlobalConfig.get_config()
        
        if not config.crp_branch_id:
            return jsonify({
                'success': False,
                'message': 'CRP分支ID未配置，请先在全局配置中设置'
            }), 400
        
        # 获取token
        token = CRPService.get_token()
        if not token:
            return jsonify({
                'success': False,
                'message': 'CRP登录失败，请检查LDAP账号密码'
            }), 401
        
        # 获取用户名
        username = CRPService.fetch_user(token)
        if not username:
            return jsonify({
                'success': False,
                'message': '获取用户信息失败'
            }), 500
        
        # 获取主题列表
        topic_type = config.crp_topic_type or 'test'
        topics = CRPService.list_topics(token, username, config.crp_branch_id, topic_type)
        
        return jsonify({
            'success': True,
            'data': topics
        })
        
    except Exception as e:
        logger.error(f"获取主题列表失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'获取主题列表失败: {str(e)}'
        }), 500


@crp_bp.route('/api/topics/<int:topic_id>/releases', methods=['GET'])
def api_get_topic_releases(topic_id):
    """获取主题下的包列表API"""
    try:
        # 获取token
        token = CRPService.get_token()
        if not token:
            return jsonify({
                'success': False,
                'message': 'CRP登录失败，请检查LDAP账号密码'
            }), 401
        
        # 获取包列表
        releases = CRPService.list_topic_releases(token, topic_id)
        
        # 添加状态显示信息
        for release in releases:
            state_info = CRPService.get_build_state_info(release['build_state'])
            release['state_label'] = state_info['label']
            release['state_badge_class'] = state_info['badge_class']
        
        return jsonify({
            'success': True,
            'data': releases
        })
        
    except Exception as e:
        logger.error(f"获取包列表失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'获取包列表失败: {str(e)}'
        }), 500


@crp_bp.route('/api/releases/<int:release_id>', methods=['DELETE'])
def api_delete_release(release_id):
    """放弃包API"""
    try:
        # 获取token
        token = CRPService.get_token()
        if not token:
            return jsonify({
                'success': False,
                'message': 'CRP登录失败，请检查LDAP账号密码'
            }), 401
        
        # 删除release
        success = CRPService.delete_release(token, release_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '已成功放弃该包'
            })
        else:
            return jsonify({
                'success': False,
                'message': '放弃包失败'
            }), 500
        
    except Exception as e:
        logger.error(f"放弃包失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'放弃包失败: {str(e)}'
        }), 500

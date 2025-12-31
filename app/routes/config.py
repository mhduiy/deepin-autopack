from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import GlobalConfig

config_bp = Blueprint('config', __name__, url_prefix='/config')

@config_bp.route('/', methods=['GET', 'POST'])
def global_config():
    """全局配置页面"""
    config = GlobalConfig.get_config()
    
    if request.method == 'POST':
        try:
            # 更新配置
            config.ldap_username = request.form.get('ldap_username')
            config.gerrit_url = request.form.get('gerrit_url')
            config.maintainer_name = request.form.get('maintainer_name')
            config.maintainer_email = request.form.get('maintainer_email')
            config.local_repos_dir = request.form.get('local_repos_dir') or '/tmp/deepin-autopack-repos'
            config.https_proxy = request.form.get('https_proxy') or None
            
            # CRP配置
            crp_branch_id = request.form.get('crp_branch_id')
            if crp_branch_id:
                config.crp_branch_id = int(crp_branch_id)
            config.crp_topic_type = request.form.get('crp_topic_type') or 'test'
            
            # 只有当密码字段不为空时才更新密码
            ldap_password = request.form.get('ldap_password')
            if ldap_password:
                config.ldap_password = ldap_password
            
            # GitHub配置
            config.github_username = request.form.get('github_username')
            github_token = request.form.get('github_token')
            if github_token:
                config.github_token = github_token
            
            crp_token = request.form.get('crp_token')
            if crp_token:
                config.crp_token = crp_token
            
            db.session.commit()
            flash('全局配置已保存！', 'success')
            return redirect(url_for('config.global_config'))
        except Exception as e:
            db.session.rollback()
            flash(f'保存失败: {str(e)}', 'danger')
    
    return render_template('config.html', config=config)

@config_bp.route('/test-gerrit', methods=['POST'])
def test_gerrit():
    """测试 Gerrit 连接（JSON API）"""
    from app.services.gerrit_service import create_gerrit_service
    
    config = GlobalConfig.get_config()
    
    # 检查是否是JSON请求
    is_json = request.is_json or request.headers.get('Content-Type') == 'application/x-www-form-urlencoded'
    
    if not config.ldap_username or not config.ldap_password or not config.gerrit_url:
        if is_json:
            return jsonify({'success': False, 'message': '请先配置 LDAP 账号和 Gerrit 地址'}), 400
        flash('请先配置 LDAP 账号和 Gerrit 地址', 'warning')
        return redirect(url_for('config.global_config'))
    
    try:
        # 创建 Gerrit 服务
        gerrit = create_gerrit_service(
            config.gerrit_url,
            config.ldap_username,
            config.ldap_password
        )
        
        # 测试项目名称（从表单获取）
        test_project = request.form.get('test_project', 'deepin-music')
        
        # 测试 API 调用
        result = gerrit.get_project_info(test_project)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'项目 {test_project} 连接成功'})
        else:
            return jsonify({'success': False, 'message': result.get('message', '连接失败')})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试出错: {str(e)}'})

@config_bp.route('/test-crp', methods=['POST'])
def test_crp():
    """测试 CRP 连接（JSON API）"""
    from app.services.crp_service import CRPService
    
    config = GlobalConfig.get_config()
    
    if not config.ldap_username or not config.ldap_password or not config.crp_token:
        return jsonify({'success': False, 'message': '请先配置 LDAP 账号和 CRP Token'}), 400
    
    try:
        # 创建 CRP 服务
        crp = CRPService(config.crp_token)
        
        # 测试 API 调用 - 获取主题列表
        topics = crp.get_topics()
        
        if topics:
            return jsonify({'success': True, 'message': f'CRP 连接成功，找到 {len(topics)} 个主题'})
        else:
            return jsonify({'success': False, 'message': 'CRP Token 可能无效或已过期'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试出错: {str(e)}'})

@config_bp.route('/refresh-crp-token', methods=['POST'])
def refresh_crp_token():
    """刷新 CRP Token"""
    import subprocess
    import os
    
    config = GlobalConfig.get_config()
    
    if not config.ldap_username or not config.ldap_password:
        return jsonify({'success': False, 'message': '请先配置 LDAP 账号和密码'}), 400
    
    try:
        # 查找刷新脚本
        script_path = os.path.expanduser('~/Dev/dev-tool/gen_pwd.py')
        if not os.path.exists(script_path):
            # 尝试其他可能的路径
            alt_paths = [
                os.path.expanduser('~/Dev/dev-tool/gen_pwd'),
                os.path.expanduser('~/Dev/dev-tool/gen_token.py'),
                os.path.expanduser('~/Dev/dev-tool/refresh_token.py'),
            ]
            for path in alt_paths:
                if os.path.exists(path):
                    script_path = path
                    break
            else:
                return jsonify({'success': False, 'message': '未找到刷新脚本，请检查 ~/Dev/dev-tool/ 目录'})
        
        # 执行脚本刷新token
        result = subprocess.run(
            ['python3', script_path, config.ldap_username, config.ldap_password],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            # 假设脚本输出的是新token
            new_token = result.stdout.strip()
            config.crp_token = new_token
            db.session.commit()
            return jsonify({'success': True, 'message': 'Token 刷新成功'})
        else:
            error_msg = result.stderr if result.stderr else '脚本执行失败'
            return jsonify({'success': False, 'message': error_msg})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '刷新超时，请稍后重试'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'刷新失败: {str(e)}'})

from flask import Blueprint, render_template, request, redirect, url_for, flash
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
    """测试 Gerrit 连接"""
    from app.services.gerrit_service import create_gerrit_service
    
    config = GlobalConfig.get_config()
    
    if not config.ldap_username or not config.ldap_password or not config.gerrit_url:
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
            flash(f'Gerrit 连接测试成功！项目 {test_project} 信息获取成功。', 'success')
        else:
            flash(f'Gerrit 连接失败: {result["message"]}', 'danger')
    except Exception as e:
        flash(f'测试出错: {str(e)}', 'danger')
    
    return redirect(url_for('config.global_config'))

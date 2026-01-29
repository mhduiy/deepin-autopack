from flask import Blueprint, render_template

group_bp = Blueprint('group', __name__)

@group_bp.route('/groups')
def group_list():
    """分组管理页面"""
    return render_template('group_list.html')

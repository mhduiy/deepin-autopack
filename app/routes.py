from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Project

project_bp = Blueprint('project', __name__)

@project_bp.route('/')
def index():
    """首页 - 重定向到项目列表"""
    return redirect(url_for('project.project_list'))

@project_bp.route('/projects')
def project_list():
    """项目列表页"""
    projects = Project.query.all()
    return render_template('project_list.html', projects=projects)

@project_bp.route('/projects/new', methods=['GET', 'POST'])
def project_create():
    """创建项目"""
    if request.method == 'POST':
        try:
            project = Project(
                name=request.form.get('name'),
                gerrit_url=request.form.get('gerrit_url'),
                gerrit_branch=request.form.get('gerrit_branch'),
                github_url=request.form.get('github_url'),
                github_branch=request.form.get('github_branch'),
                last_commit_hash=request.form.get('last_commit_hash')
            )
            db.session.add(project)
            db.session.commit()
            flash(f'项目 {project.name} 创建成功！', 'success')
            return redirect(url_for('project.project_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')
    
    return render_template('project_form.html', project=None)

@project_bp.route('/projects/<int:id>/edit', methods=['GET', 'POST'])
def project_edit(id):
    """编辑项目"""
    project = Project.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            project.name = request.form.get('name')
            project.gerrit_url = request.form.get('gerrit_url')
            project.gerrit_branch = request.form.get('gerrit_branch')
            project.github_url = request.form.get('github_url')
            project.github_branch = request.form.get('github_branch')
            project.last_commit_hash = request.form.get('last_commit_hash')
            
            db.session.commit()
            flash(f'项目 {project.name} 更新成功！', 'success')
            return redirect(url_for('project.project_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')
    
    return render_template('project_form.html', project=project)

@project_bp.route('/projects/<int:id>/delete', methods=['POST'])
def project_delete(id):
    """删除项目"""
    try:
        project = Project.query.get_or_404(id)
        name = project.name
        db.session.delete(project)
        db.session.commit()
        flash(f'项目 {name} 已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    
    return redirect(url_for('project.project_list'))

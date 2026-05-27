"""
API v1 路由 - 为 OpenClaw 等外部工具提供 REST API

监控组:
  GET  /api/v1/monitor/status   - 系统概览
  GET  /api/v1/monitor/projects - 项目列表（含提交信息）
  POST /api/v1/monitor/refresh  - 刷新所有项目

打包组:
  POST /api/v1/packages/create      - 创建打包任务
  GET  /api/v1/packages/<id>/status - 任务状态
  POST /api/v1/packages/<id>/retry  - 重试失败任务
  GET  /api/v1/packages/list        - 打包任务列表
"""

from flask import Blueprint, jsonify, request
from app.models import Project, GlobalConfig
from app.models.build_task import BuildTask
from app.services.repo_service import RepoService
from app.services.changelog_service import ChangelogService
from app.services.build_task_service import BuildTaskService
from app.services.crp_service import CRPService
from app import db
from datetime import datetime
import logging

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)


# ============================================================
# 监控组
# ============================================================

@api_v1_bp.route("/monitor/status", methods=["GET"])
def monitor_status():
    """系统概览：项目总数、就绪数、有新增提交的项目数"""
    try:
        total = Project.query.count()
        ready = Project.query.filter_by(repo_status="ready").count()
        projects = Project.query.filter_by(repo_status="ready").all()

        projects_with_commits = []
        for p in projects:
            try:
                since = None
                if p.local_repo_path:
                    since = ChangelogService.get_changelog_last_commit(p.local_repo_path)
                count = 0
                if since:
                    count, _ = RepoService.get_commits_since(p, since)
                if count > 0:
                    projects_with_commits.append({"id": p.id, "name": p.name, "new_commits": count})
            except Exception:
                pass

        return jsonify({
            "success": True,
            "data": {
                "total_projects": total,
                "ready_projects": ready,
                "projects_with_new_commits": len(projects_with_commits),
                "details": projects_with_commits,
            }
        })
    except Exception as e:
        logger.exception(f"获取监控状态失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/monitor/projects", methods=["GET"])
def monitor_projects():
    """获取所有已就绪项目及其提交信息"""
    try:
        projects = Project.query.filter_by(repo_status="ready").all()
        result = []
        for p in projects:
            item = {
                "id": p.id,
                "name": p.name,
                "github_url": p.github_url,
                "github_branch": p.github_branch,
                "gerrit_branch": p.gerrit_branch,
                "current_version": None,
                "new_commits_count": 0,
                "new_commits": [],
                "latest_commit": None,
            }
            try:
                if p.local_repo_path:
                    item["current_version"] = ChangelogService.get_current_version(p.local_repo_path)
                    since = ChangelogService.get_changelog_last_commit(p.local_repo_path)
                    if since:
                        item["new_commits_count"], item["new_commits"] = RepoService.get_commits_since(p, since)
                item["latest_commit"] = RepoService.get_latest_commit(p)
            except Exception as e:
                logger.warning(f"处理项目 {p.name} 失败: {e}")
            result.append(item)

        result.sort(key=lambda x: (-x["new_commits_count"], -(x["latest_commit"]["timestamp"] if x["latest_commit"] and "timestamp" in x["latest_commit"] else 0)))

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception(f"获取项目列表失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/monitor/refresh", methods=["POST"])
def monitor_refresh():
    """触发刷新所有项目（异步执行，立即返回）"""
    import threading
    from flask import current_app

    app_ctx = current_app._get_current_object()

    def _refresh_all():
        with app_ctx.app_context():
            ChangelogService.clear_cache()
            projects = Project.query.filter_by(repo_status="ready").all()
            success = 0
            failed = 0
            for p in projects:
                try:
                    RepoService.update_repo(p)
                    latest = RepoService.get_latest_commit(p)
                    if latest:
                        p.last_commit_hash = latest["full_hash"]
                    db.session.commit()
                    success += 1
                except Exception as e:
                    logger.error(f"刷新 {p.name} 失败: {e}")
                    failed += 1
            logger.info(f"刷新完成: 成功 {success}, 失败 {failed}")

    thread = threading.Thread(target=_refresh_all, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "message": "刷新任务已触发，正在后台执行",
    })


# ============================================================
# 打包组
# ============================================================

@api_v1_bp.route("/packages/create", methods=["POST"])
def packages_create():
    """创建打包任务"""
    try:
        data = request.get_json(silent=True) or {}

        project_name = data.get("project_name", "").strip()
        if not project_name:
            return jsonify({"success": False, "message": "缺少 project_name"}), 400

        project = Project.query.filter_by(name=project_name).first()
        if not project:
            return jsonify({"success": False, "message": f"项目不存在: {project_name}"}), 404

        if project.repo_status != "ready":
            return jsonify({"success": False, "message": f"项目仓库未就绪: {project.repo_status}"}), 400

        mode = data.get("mode", "normal")
        version = data.get("version") or datetime.now().strftime("%Y%m%d%H%M%S")
        architectures = data.get("architectures", ["amd64", "arm64", "loongarch64"])

        # 获取 CRP 主题
        crp_topic_id = data.get("crp_topic_id")
        crp_topic_name = data.get("crp_topic_name")
        if not crp_topic_id:
            try:
                config = GlobalConfig.get_config()
                token = CRPService.get_token()
                if token and config.crp_branch_id:
                    username = CRPService.fetch_user(token)
                    topics = CRPService.list_topics(token, username, config.crp_branch_id, config.crp_topic_type or "test")
                    if topics:
                        crp_topic_id = topics[0].get("ID") or topics[0].get("id")
                        crp_topic_name = topics[0].get("Name") or topics[0].get("name", "最新CRP仓库")
            except Exception:
                pass

        task = BuildTaskService.create_task(
            project_id=project.id,
            package_config={
                "mode": mode,
                "version": version,
                "architectures": architectures,
                "crp_topic_id": crp_topic_id,
                "crp_topic_name": crp_topic_name,
                "start_commit_hash": data.get("start_commit_hash", ""),
            },
        )

        BuildTaskService.start_task(task.id)

        return jsonify({
            "success": True,
            "data": {
                "task_id": task.id,
                "project_name": project.name,
                "version": version,
                "mode": mode,
                "architectures": architectures,
                "crp_topic_name": crp_topic_name,
                "status": "running",
            },
            "message": f"打包任务已创建并启动: {project.name} v{version}",
        })
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.exception(f"创建打包任务失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/packages/<int:task_id>/status", methods=["GET"])
def packages_status(task_id):
    """获取打包任务状态"""
    try:
        task_data = BuildTaskService.get_task_status(task_id)
        return jsonify({"success": True, "data": task_data})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        logger.exception(f"获取任务状态失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/packages/<int:task_id>/retry", methods=["POST"])
def packages_retry(task_id):
    """重试失败的打包任务"""
    try:
        data = request.get_json(silent=True) or {}
        from_step = data.get("from_step")

        task = BuildTaskService.retry_task(task_id, from_step)
        return jsonify({
            "success": True,
            "message": f"任务 {task_id} 已重新提交",
            "data": {"task_id": task_id, "status": task.status},
        })
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.exception(f"重试任务失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/packages/list", methods=["GET"])
def packages_list():
    """获取打包任务列表"""
    try:
        status = request.args.get("status")
        limit = request.args.get("limit", 20, type=int)
        tasks = BuildTaskService.get_all_tasks(status=status, limit=limit)

        summary = []
        for t in tasks:
            summary.append({
                "id": t["id"],
                "project_name": t["project_name"],
                "version": t["version"],
                "mode": t["package_mode"],
                "status": t["status"],
                "current_step": t.get("current_step"),
                "error_message": t.get("error_message"),
                "github_pr_url": t.get("github_pr_url"),
                "crp_build_url": t.get("crp_build_url"),
                "created_at": t.get("created_at"),
                "completed_at": t.get("completed_at"),
            })

        return jsonify({"success": True, "data": summary})
    except Exception as e:
        logger.exception(f"获取任务列表失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# 工具组
# ============================================================

@api_v1_bp.route("/projects", methods=["GET"])
def list_projects():
    """获取可用项目列表"""
    try:
        projects = Project.query.filter_by(repo_status="ready").all()
        result = []
        for p in projects:
            result.append({
                "id": p.id,
                "name": p.name,
                "github_url": p.github_url,
                "gerrit_branch": p.gerrit_branch,
                "github_branch": p.github_branch,
                "crp_project_name": p.crp_project_name or f"{p.name}-v25",
            })
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception(f"获取项目列表失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/crp-topics", methods=["GET"])
def list_crp_topics():
    """获取 CRP 主题列表"""
    try:
        config = GlobalConfig.get_config()
        if not config.crp_branch_id:
            return jsonify({"success": False, "message": "CRP分支ID未配置"}), 400

        token = CRPService.get_token()
        if not token:
            return jsonify({"success": False, "message": "CRP登录失败，请检查LDAP配置"}), 401

        username = CRPService.fetch_user(token)
        if not username:
            return jsonify({"success": False, "message": "获取用户信息失败"}), 500

        topics = CRPService.list_topics(token, username, config.crp_branch_id, config.crp_topic_type or "test")
        return jsonify({
            "success": True,
            "data": [
                {"topic_id": t.get("ID") or t.get("id"), "topic_name": t.get("Name") or t.get("name", "")}
                for t in topics
            ]
        })
    except Exception as e:
        logger.exception(f"获取 CRP 主题失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/ai/analyze-commits", methods=["POST"])
def ai_analyze_commits():
    """AI 分析提交信息（非流式，返回完整结果）"""
    from app.services.ai_service import AIService
    import hashlib

    try:
        data = request.get_json(silent=True) or {}
        projects = data.get("projects", [])
        force = data.get("force", False)

        if not projects:
            return jsonify({"success": False, "message": "缺少 projects 参数"}), 400

        lines = []
        hashes = []
        for p in projects:
            name = p.get("name", "")
            commits = p.get("commits", [])
            for c in commits:
                hashes.append(c.get("hash", ""))
                lines.append(f"[{name}] {c.get('hash','')} | {c.get('author','')} | {c.get('date','')} | {c.get('message','')}")

        fingerprint = hashlib.md5("|".join(sorted(hashes)).encode()).hexdigest()
        commit_text = "\n".join(lines)

        config = GlobalConfig.get_config()
        if not force and config.ai_analysis_fingerprint == fingerprint and config.ai_analysis_result:
            return jsonify({"success": True, "data": {"analysis": config.ai_analysis_result, "cached": True}})

        prompt = (
            "你是 Deepin 软件包维护者。下面是项目的新增提交信息（格式：项目名 | hash | 作者 | 日期 | 提交信息），请做以下分析：\n"
            "1. 关联单据：提取 BUG-xxxx、TASK-xxxx、STORY-xxx 编号，按项目分组\n"
            "2. 变更概述：每个项目用 1-2 句话概括\n"
            "3. 打包建议：判断哪些项目适合打包，哪些可以跳过\n"
            "直接输出，不要寒暄。"
        )
        # 使用 analyze_stream 收集完整结果
        analysis_parts = []
        for chunk in AIService.analyze_stream(commit_text, arch="", project_name="提交监控批量分析", system_prompt=prompt):
            analysis_parts.append(chunk)
        analysis = "".join(analysis_parts) if analysis_parts else None

        if analysis:
            try:
                config.ai_analysis_fingerprint = fingerprint
                config.ai_analysis_result = analysis
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({"success": True, "data": {"analysis": analysis, "cached": False}})
    except Exception as e:
        logger.exception(f"AI 分析提交失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# CRP 主题组
# ============================================================

@api_v1_bp.route("/crp/topics", methods=["GET"])
def crp_topics():
    """获取 CRP 主题列表（详细字段）"""
    try:
        config = GlobalConfig.get_config()
        if not config.crp_branch_id:
            return jsonify({"success": False, "message": "CRP分支ID未配置"}), 400

        token = CRPService.get_token()
        if not token:
            return jsonify({"success": False, "message": "CRP登录失败，请检查LDAP配置"}), 401

        username = CRPService.fetch_user(token)
        if not username:
            return jsonify({"success": False, "message": "获取用户信息失败"}), 500

        topics = CRPService.list_topics(token, username, config.crp_branch_id, config.crp_topic_type or "test")
        result = []
        for t in topics:
            result.append({
                "id": t.get("ID") or t.get("id"),
                "name": t.get("Name") or t.get("name", ""),
                "description": t.get("Description") or t.get("description", ""),
                "create_time": t.get("CreateTime") or t.get("create_time", ""),
                "creator_name": t.get("CreatorName") or t.get("creator_name", ""),
            })
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception(f"获取 CRP 主题列表失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/crp/topics/<int:topic_id>", methods=["GET"])
def crp_topic_detail(topic_id):
    """获取 CRP 主题详情（含包列表）"""
    try:
        config = GlobalConfig.get_config()
        token = CRPService.get_token()
        if not token:
            return jsonify({"success": False, "message": "CRP登录失败，请检查LDAP配置"}), 401

        username = CRPService.fetch_user(token)
        topic_type = config.crp_topic_type or "test"
        topics = CRPService.list_topics(token, username, config.crp_branch_id, topic_type)

        topic = None
        for t in topics:
            t_id = t.get("ID") or t.get("id")
            if t_id == topic_id:
                topic = {
                    "id": t_id,
                    "name": t.get("Name") or t.get("name", ""),
                    "description": t.get("Description") or t.get("description", ""),
                    "create_time": t.get("CreateTime") or t.get("create_time", ""),
                    "creator_name": t.get("CreatorName") or t.get("creator_name", ""),
                }
                break

        if not topic:
            return jsonify({"success": False, "message": "主题未找到"}), 404

        releases = CRPService.list_topic_releases(token, topic_id)
        for r in releases:
            state_info = CRPService.get_build_state_info(r.get("build_state", ""))
            r["state_label"] = state_info["label"]

        return jsonify({"success": True, "data": {"topic": topic, "releases": releases}})
    except Exception as e:
        logger.exception(f"获取主题详情失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/crp/releases/<int:release_id>/retry", methods=["POST"])
def crp_retry_release(release_id):
    """重试 CRP 构建"""
    try:
        token = CRPService.get_token()
        if not token:
            return jsonify({"success": False, "message": "CRP登录失败"}), 401

        success = CRPService.retry_build(token, release_id)
        if success:
            return jsonify({"success": True, "message": "已触发重新构建"})
        return jsonify({"success": False, "message": "重试构建失败"}), 500
    except Exception as e:
        logger.exception(f"重试构建失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_v1_bp.route("/crp/releases/<int:release_id>", methods=["DELETE"])
def crp_abandon_release(release_id):
    """放弃 CRP 包"""
    try:
        token = CRPService.get_token()
        if not token:
            return jsonify({"success": False, "message": "CRP登录失败"}), 401

        success = CRPService.delete_release(token, release_id)
        if success:
            return jsonify({"success": True, "message": "已放弃该包"})
        return jsonify({"success": False, "message": "放弃包失败"}), 500
    except Exception as e:
        logger.exception(f"放弃包失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# CRP 构建日志 & AI 分析
# ============================================================

SHUTTLE_BASE = "https://shuttle.uniontech.com/api/shuttle"


def _shuttle_request(method, path, **kwargs):
    """通用 Shuttle API 请求"""
    import requests as req
    token = CRPService.get_token()
    if not token:
        return None
    url = f"{SHUTTLE_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if method == "GET":
            resp = req.get(url, headers=headers, timeout=30, **kwargs)
        else:
            resp = req.post(url, headers=headers, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Shuttle API 请求失败 {url}: {e}")
        return None


@api_v1_bp.route("/crp/builds/<int:build_id>/jobs", methods=["GET"])
def crp_build_jobs(build_id):
    """获取构建任务的所有 job（按架构拆分）"""
    result = _shuttle_request("POST", "/task/list",
        json={"params": {"taskid": str(build_id)}, "pageSize": 20, "current": 1})
    if not result:
        return jsonify({"success": False, "message": "获取 Shuttle 构建信息失败"}), 502

    tasks = result.get("tasks", [])
    if not tasks:
        return jsonify({"success": True, "data": []})

    jobs = []
    for job in tasks[0].get("jobs", []):
        jobs.append({
            "job_id": job.get("id"),
            "arch": job.get("arch", ""),
            "status": job.get("status", "UNKNOWN"),
        })

    return jsonify({"success": True, "data": jobs})


@api_v1_bp.route("/crp/builds/<int:build_id>/logs/<int:job_id>", methods=["GET"])
def crp_build_log(build_id, job_id):
    """获取单个 job 的构建日志"""
    result = _shuttle_request("GET", "/job/log", params={"jobid": job_id})
    if result is None:
        return jsonify({"success": False, "message": "获取构建日志失败"}), 502
    log_text = result.get("data", "") if isinstance(result, dict) else str(result)
    return jsonify({
        "success": True,
        "data": {
            "job_id": job_id,
            "build_id": build_id,
            "log": log_text,
            "shuttle_url": f"https://shuttle.uniontech.com/#/details/build?jobId={job_id}",
        }
    })


@api_v1_bp.route("/crp/builds/<int:build_id>/analyze", methods=["POST"])
def crp_build_analyze(build_id):
    """AI 分析构建中所有失败的 job 日志"""
    from app.services.ai_service import AIService
    from flask import Response, stream_with_context

    # 获取 jobs
    result = _shuttle_request("POST", "/task/list",
        json={"params": {"taskid": str(build_id)}, "pageSize": 20, "current": 1})
    if not result:
        return jsonify({"success": False, "message": "获取 Shuttle 构建信息失败"}), 502

    tasks = result.get("tasks", [])
    if not tasks:
        return jsonify({"success": False, "message": "构建任务未找到"}), 404

    failed_jobs = []
    all_jobs = []
    for job in tasks[0].get("jobs", []):
        all_jobs.append(job)
        if job.get("status") == "FAILED":
            failed_jobs.append(job)

    if not failed_jobs:
        statuses = {j.get("arch"): j.get("status") for j in all_jobs}
        return jsonify({
            "success": True,
            "message": "没有失败的 job，无需分析",
            "data": {"build_id": build_id, "job_statuses": statuses, "analysis": None}
        })

    # 获取失败 job 的日志并分析
    analyses = []
    for job in failed_jobs:
        job_id = job.get("id")
        arch = job.get("arch", "")
        log_result = _shuttle_request("GET", "/job/log", params={"jobid": job_id})
        if not log_result:
            analyses.append({"arch": arch, "job_id": job_id, "error": "获取日志失败"})
            continue

        log_text = log_result.get("data", "") if isinstance(log_result, dict) else str(log_result)
        if not log_text:
            analyses.append({"arch": arch, "job_id": job_id, "error": "日志为空"})
            continue

        analysis_parts = []
        for chunk in AIService.analyze_stream(log_text, arch=arch):
            analysis_parts.append(chunk)
        analyses.append({
            "arch": arch,
            "job_id": job_id,
            "analysis": "".join(analysis_parts),
        })

    return jsonify({
        "success": True,
        "data": {
            "build_id": build_id,
            "failed_count": len(failed_jobs),
            "total_jobs": len(all_jobs),
            "analyses": analyses,
        }
    })


@api_v1_bp.route("/crp/builds/<int:build_id>/logs/<int:job_id>/analyze", methods=["POST"])
def crp_build_log_analyze(build_id, job_id):
    """AI 分析单个 job 的构建日志"""
    from app.services.ai_service import AIService

    log_result = _shuttle_request("GET", "/job/log", params={"jobid": job_id})
    if not log_result:
        return jsonify({"success": False, "message": "获取构建日志失败"}), 502

    log_text = log_result.get("data", "") if isinstance(log_result, dict) else str(log_result)
    if not log_text:
        return jsonify({"success": False, "message": "日志为空"}), 404

    analysis_parts = []
    for chunk in AIService.analyze_stream(log_text, arch=""):
        analysis_parts.append(chunk)

    return jsonify({
        "success": True,
        "data": {
            "build_id": build_id,
            "job_id": job_id,
            "analysis": "".join(analysis_parts),
        }
    })

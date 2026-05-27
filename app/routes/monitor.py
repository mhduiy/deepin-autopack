from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
from app.models import Project
from app.services.repo_service import RepoService
from app.services.changelog_service import ChangelogService
from app import db
import logging
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

monitor_bp = Blueprint("monitor", __name__)
logger = logging.getLogger(__name__)


def process_single_project(project):
    """处理单个项目的数据获取（用于并行处理）"""
    try:
        # 获取当前版本
        current_version = None
        if project.local_repo_path:
            current_version = ChangelogService.get_current_version(
                project.local_repo_path
            )

        # 获取 changelog 最后修改的 commit
        changelog_commit = None
        if project.local_repo_path:
            changelog_commit = ChangelogService.get_changelog_last_commit(
                project.local_repo_path
            )

        # 使用 changelog commit 作为起始点
        since_point = changelog_commit

        # 获取新增提交
        new_commits_count = 0
        new_commits = []
        if since_point:
            new_commits_count, new_commits = RepoService.get_commits_since(
                project, since_point
            )

        # 获取最新提交
        latest_commit = RepoService.get_latest_commit(project)

        return {
            "success": True,
            "data": {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "github_url": project.github_url,
                    "github_branch": project.github_branch,
                    "gerrit_branch": project.gerrit_branch,
                },
                "current_version": current_version,
                "changelog_commit": changelog_commit,
                "since_point": since_point,
                "new_commits_count": new_commits_count,
                "new_commits": new_commits,
                "latest_commit": latest_commit,
            },
        }
    except Exception as e:
        logger.error(f"处理项目 {project.name} 失败: {str(e)}", exc_info=True)
        return {"success": False, "project_name": project.name, "error": str(e)}


@monitor_bp.route("/monitor")
def monitor():
    """提交监控页面"""
    # 只返回空页面，数据通过API异步加载
    return render_template("monitor.html")


@monitor_bp.route("/api/monitor/data", methods=["GET"])
def monitor_data():
    """获取监控数据的API"""
    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status="ready").all()

        project_data = []
        for project in projects:
            # 获取当前版本
            current_version = None
            if project.local_repo_path:
                current_version = ChangelogService.get_current_version(
                    project.local_repo_path
                )

            # 获取 changelog 最后修改的 commit
            changelog_commit = None
            if project.local_repo_path:
                changelog_commit = ChangelogService.get_changelog_last_commit(
                    project.local_repo_path
                )

            # 使用 changelog commit 作为起始点
            since_point = changelog_commit

            # 获取新增提交
            new_commits_count = 0
            new_commits = []
            if since_point:
                new_commits_count, new_commits = RepoService.get_commits_since(
                    project, since_point
                )

            # 获取最新提交
            latest_commit = RepoService.get_latest_commit(project)

            project_data.append(
                {
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "github_url": project.github_url,
                        "github_branch": project.github_branch,
                        "gerrit_branch": project.gerrit_branch,
                    },
                    "current_version": current_version,
                    "changelog_commit": changelog_commit,
                    "since_point": since_point,
                    "new_commits_count": new_commits_count,
                    "new_commits": new_commits,
                    "latest_commit": latest_commit,
                }
            )

        # 排序：1. 有新增提交的优先 2. 最新提交时间最新的优先
        project_data.sort(
            key=lambda x: (
                -x["new_commits_count"],  # 新增提交数降序（负号表示降序）
                -(
                    x["latest_commit"]["timestamp"]
                    if x["latest_commit"] and "timestamp" in x["latest_commit"]
                    else 0
                ),  # 时间戳降序
            )
        )

        return jsonify({"success": True, "data": project_data})
    except Exception as e:
        logger.error(f"获取监控数据失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route("/api/monitor/data-parallel", methods=["GET"])
def monitor_data_parallel():
    """获取监控数据的API（并行版本，推荐使用）"""
    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status="ready").all()

        if not projects:
            return jsonify({"success": True, "data": []})

        # 使用线程池并行处理所有项目
        project_data = []
        max_workers = min(len(projects), 5)  # 最多5个并发线程

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_project = {
                executor.submit(process_single_project, project): project
                for project in projects
            }

            # 收集结果
            for future in as_completed(future_to_project):
                result = future.result()
                if result["success"]:
                    project_data.append(result["data"])
                else:
                    logger.warning(
                        f"项目 {result.get('project_name')} 处理失败: {result.get('error')}"
                    )

        # 排序：1. 有新增提交的优先 2. 最新提交时间最新的优先
        project_data.sort(
            key=lambda x: (
                -x["new_commits_count"],  # 新增提交数降序（负号表示降序）
                -(
                    x["latest_commit"]["timestamp"]
                    if x["latest_commit"] and "timestamp" in x["latest_commit"]
                    else 0
                ),  # 时间戳降序
            )
        )

        return jsonify({"success": True, "data": project_data})
    except Exception as e:
        logger.error(f"获取监控数据失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route("/monitor/projects/<int:project_id>/refresh", methods=["POST"])
def refresh_project(project_id):
    """刷新单个项目的信息"""
    try:
        project = Project.query.get_or_404(project_id)

        if project.repo_status != "ready":
            return jsonify({"success": False, "message": "项目仓库未就绪"}), 400

        # 清除缓存
        if project.local_repo_path:
            ChangelogService.clear_cache(project.local_repo_path)

        # 更新仓库
        RepoService.update_repo(project)

        # 重新获取信息
        current_version = ChangelogService.get_current_version(project.local_repo_path)
        changelog_commit = ChangelogService.get_changelog_last_commit(
            project.local_repo_path
        )

        # 使用 changelog commit 作为起始点
        since_point = changelog_commit
        new_commits_count = 0
        if since_point:
            new_commits_count, _ = RepoService.get_commits_since(project, since_point)

        latest_commit = RepoService.get_latest_commit(project)

        # 更新数据库中的 last_commit_hash
        if latest_commit:
            project.last_commit_hash = latest_commit["full_hash"]
            db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "刷新成功",
                "data": {
                    "current_version": current_version,
                    "new_commits_count": new_commits_count,
                    "latest_commit": latest_commit,
                },
            }
        )

    except Exception as e:
        logger.error(f"刷新项目失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route("/monitor/refresh-all", methods=["GET"])
def refresh_all():
    """刷新所有项目 - 使用多线程并行处理，流式响应返回进度"""
    from flask import Response, current_app
    import json
    import queue
    import threading

    app = current_app._get_current_object()

    try:
        projects = Project.query.filter_by(repo_status="ready").all()
        total = len(projects)

        if total == 0:

            def empty_generate():
                yield f"data: {json.dumps({'type': 'complete', 'message': '没有需要刷新的项目', 'success_count': 0, 'failed_count': 0, 'failed_projects': []})}\n\n"

            return Response(empty_generate(), mimetype="text/event-stream")

        project_list = [
            {"id": p.id, "name": p.name, "local_repo_path": p.local_repo_path}
            for p in projects
        ]

    except Exception as e:
        logger.error(f"查询项目失败: {str(e)}", exc_info=True)

        def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(error_generate(), mimetype="text/event-stream")

    def generate():
        with app.app_context():
            try:
                ChangelogService.clear_cache()

                success_count = 0
                failed_count = 0
                failed_projects = []

                yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

                completed_count = 0
                lock = threading.Lock()

                def refresh_single_project(project_data):
                    nonlocal success_count, failed_count, completed_count
                    project_name = project_data["name"]
                    try:
                        with app.app_context():
                            project = Project.query.get(project_data["id"])
                            if not project:
                                raise Exception(f"项目不存在: {project_name}")

                            result = RepoService.update_repo(project)
                            if result:
                                latest_commit = RepoService.get_latest_commit(project)
                                if latest_commit:
                                    project.last_commit_hash = latest_commit[
                                        "full_hash"
                                    ]
                                db.session.commit()
                                return {"success": True, "project_name": project_name}
                            else:
                                raise Exception("更新仓库失败")
                    except Exception as e:
                        logger.error(f"刷新项目 {project_name} 失败: {e}")
                        return {
                            "success": False,
                            "project_name": project_name,
                            "error": str(e),
                        }

                max_workers = min(len(project_list), 5)

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_project = {
                        executor.submit(refresh_single_project, p): p
                        for p in project_list
                    }

                    for future in as_completed(future_to_project):
                        result = future.result()

                        with lock:
                            completed_count += 1

                            if result["success"]:
                                success_count += 1
                                status = "success"
                            else:
                                failed_count += 1
                                status = "failed"
                                failed_projects.append(
                                    {
                                        "name": result["project_name"],
                                        "error": result.get("error", "未知错误"),
                                    }
                                )

                            progress_data = {
                                "type": "progress",
                                "current": completed_count,
                                "total": total,
                                "percent": int((completed_count / total) * 100),
                                "project_name": result["project_name"],
                                "status": status,
                            }
                            if not result["success"]:
                                progress_data["error"] = result.get("error", "未知错误")

                            yield f"data: {json.dumps(progress_data)}\n\n"

                complete_data = {
                    "type": "complete",
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "failed_projects": failed_projects,
                    "message": f"刷新完成！成功: {success_count}, 失败: {failed_count}",
                }
                yield f"data: {json.dumps(complete_data)}\n\n"

            except Exception as e:
                logger.error(f"批量刷新失败: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@monitor_bp.route("/api/monitor/export-new-commits", methods=["GET"])
def export_new_commits():
    """导出有新增提交的项目列表"""
    from flask import Response

    try:
        # 只显示已就绪的项目
        projects = Project.query.filter_by(repo_status="ready").all()

        export_lines = []

        for project in projects:
            try:
                # 获取当前版本
                current_version = None
                if project.local_repo_path:
                    current_version = ChangelogService.get_current_version(
                        project.local_repo_path
                    )

                # 获取 changelog 最后修改的 commit
                changelog_commit = None
                if project.local_repo_path:
                    changelog_commit = ChangelogService.get_changelog_last_commit(
                        project.local_repo_path
                    )

                # 获取新增提交数
                new_commits_count = 0
                if changelog_commit:
                    new_commits_count, _ = RepoService.get_commits_since(
                        project, changelog_commit
                    )

                # 只导出有新增提交的项目
                if new_commits_count > 0:
                    version_str = current_version if current_version else "未知版本"
                    export_lines.append(f"{project.name} {version_str}")

            except Exception as e:
                logger.error(f"处理项目 {project.name} 失败: {e}")
                continue

        # 生成纯文本内容
        content = "\n".join(export_lines)

        # 返回文本文件
        return Response(
            content,
            mimetype="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=projects_with_new_commits.txt"
            },
        )

    except Exception as e:
        logger.error(f"导出失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


COMMIT_ANALYSIS_PROMPT = """你是 Deepin 软件包维护者。下面是一批项目的新增提交信息（格式：项目名 | hash | 作者 | 日期 | 提交信息），请做以下分析：

1. **关联单据**：从所有提交信息中提取 BUG-xxxx、TASK-xxxx、STORY-xxx 编号，按项目分组列出，没有就写"无"

2. **变更概述**：每个项目用 1-2 句话概括这批提交做了什么改动

3. **打包建议**：判断哪些项目适合打包（有实质代码变更、bug修复、功能新增），哪些可以跳过（仅文档、CI配置、格式化等）

请直接输出，不要寒暄。格式：
## 关联单据
- projectA: STORY-001, BUG-002
- projectB: 无

## 变更概述
- projectA: 修复了xxx，新增了xxx
- projectB: 更新了翻译文件

## 打包建议
建议打包: projectA (有bug修复)
可跳过: projectB (仅翻译更新)"""


@monitor_bp.route("/api/monitor/ai-analyze-commits", methods=["POST"])
def ai_analyze_commits():
    """AI 分析所有有新增提交的项目（流式输出，带指纹缓存）"""
    from app.services.ai_service import AIService
    from app.models import GlobalConfig
    import hashlib

    try:
        data = request.get_json(silent=True) or {}
        projects = data.get("projects", [])
        force = data.get("force", False)

        if not projects:
            return jsonify({"success": False, "message": "没有提交数据"}), 400

        # 构建紧凑文本 + 计算指纹
        lines = []
        hashes = []
        for p in projects:
            name = p.get("name", "")
            commits = p.get("commits", [])
            if not commits:
                continue
            for c in commits:
                hashes.append(c.get("hash", ""))
                lines.append(
                    f"[{name}] {c.get('hash','')} | {c.get('author','')} | {c.get('date','')} | {c.get('message','')}"
                )

        fingerprint = hashlib.md5("|".join(sorted(hashes)).encode()).hexdigest()
        commit_text = "\n".join(lines)

        # 检查缓存
        config = GlobalConfig.get_config()
        if not force and config.ai_analysis_fingerprint == fingerprint and config.ai_analysis_result:
            logger.info("AI 提交分析命中缓存，直接返回")
            result = config.ai_analysis_result

            def cached_generate():
                # 模拟流式输出，每 50 个字符一块
                for i in range(0, len(result), 50):
                    yield f"data: {json.dumps({'c': result[i:i+50]})}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                stream_with_context(cached_generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # 缓存未命中，调用 AI 分析
        logger.info(f"AI 提交分析指纹不匹配 ({fingerprint[:8]}...)，开始分析")

        def generate():
            full_result = []
            for chunk in AIService.analyze_stream(
                commit_text, arch="", project_name="提交监控批量分析",
                system_prompt=COMMIT_ANALYSIS_PROMPT
            ):
                full_result.append(chunk)
                yield f"data: {json.dumps({'c': chunk})}\n\n"

            # 分析完成，存入缓存
            try:
                result_text = "".join(full_result)
                config.ai_analysis_fingerprint = fingerprint
                config.ai_analysis_result = result_text
                db.session.commit()
                logger.info(f"AI 提交分析结果已缓存 (指纹: {fingerprint[:8]}...)")
            except Exception as e:
                logger.error(f"缓存 AI 分析结果失败: {e}")
                db.session.rollback()

            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        logger.exception(f"AI 分析提交失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route("/api/monitor/ai-analysis-cache", methods=["GET"])
def ai_analysis_cache():
    """检查 AI 分析缓存状态"""
    from app.models import GlobalConfig
    config = GlobalConfig.get_config()
    return jsonify({
        "success": True,
        "fingerprint": config.ai_analysis_fingerprint or "",
        "has_result": bool(config.ai_analysis_result),
        "result": config.ai_analysis_result or "",
    })

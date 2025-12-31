"""打包任务服务层"""
import logging
import threading
import queue
import time
import os
import shutil
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from app import db
from app.models import Project
from app.models.build_task import BuildTask, BuildTaskStep
from git import Repo

logger = logging.getLogger(__name__)


# 步骤定义
NORMAL_MODE_STEPS = [
    {'order': 0, 'name': '检查环境', 'description': '检查仓库状态和工具'},
    {'order': 1, 'name': '拉取最新代码', 'description': '更新本地仓库'},
    {'order': 2, 'name': '生成Changelog', 'description': '使用dch生成changelog'},
    {'order': 3, 'name': '提交Commit', 'description': '提交changelog变更'},
    {'order': 4, 'name': '推送到远程', 'description': '推送到GitHub/Gerrit'},
    {'order': 5, 'name': '创建PR', 'description': '创建Pull Request（GitHub）'},
    {'order': 6, 'name': '监控PR状态', 'description': '等待PR合并'},
    {'order': 7, 'name': '等待同步', 'description': '等待GitHub同步到Gerrit（GitHub项目）'},
    {'order': 8, 'name': 'CRP打包', 'description': '提交CRP打包任务'},
    {'order': 9, 'name': '监控打包', 'description': '监控CRP打包状态'},
]

CHANGELOG_ONLY_STEPS = [
    {'order': 0, 'name': '检查环境', 'description': '检查仓库状态和工具'},
    {'order': 1, 'name': '拉取最新代码', 'description': '更新本地仓库'},
    {'order': 2, 'name': '生成Changelog', 'description': '使用dch生成changelog'},
    {'order': 3, 'name': '提交Commit', 'description': '提交changelog变更'},
    {'order': 4, 'name': '推送到远程', 'description': '推送到GitHub/Gerrit'},
    {'order': 5, 'name': '创建PR', 'description': '创建Pull Request（GitHub）'},
    {'order': 6, 'name': '监控PR状态', 'description': '等待PR合并'},
]

CRP_ONLY_STEPS = [
    {'order': 0, 'name': '检查环境', 'description': '检查配置和权限'},
    {'order': 1, 'name': 'CRP打包', 'description': '提交CRP打包任务'},
    {'order': 2, 'name': '监控打包', 'description': '监控CRP打包状态'},
]


class BuildTaskService:
    """打包任务管理服务"""
    
    @staticmethod
    def create_task(project_id, package_config):
        """创建打包任务
        
        Args:
            project_id: 项目ID
            package_config: {
                'mode': 'normal'|'changelog_only'|'crp_only',
                'version': '6.0.52',
                'architectures': ['amd64', 'arm64'],
                'crp_topic_id': 'xxx',
                'crp_topic_name': 'topic_name',
                'start_commit_hash': 'abc123'
            }
            
        Returns:
            BuildTask: 创建的任务对象
        """
        try:
            # 获取项目信息
            project = Project.query.get(project_id)
            if not project:
                raise ValueError(f"项目不存在: {project_id}")
            
            # 创建任务
            task = BuildTask(
                project_id=project_id,
                project_name=project.name,
                package_mode=package_config['mode'],
                version=package_config['version'],
                architectures=package_config.get('architectures', []),
                crp_topic_id=package_config.get('crp_topic_id'),
                crp_topic_name=package_config.get('crp_topic_name'),
                start_commit_hash=package_config.get('start_commit_hash', ''),
                status='pending'
            )
            
            db.session.add(task)
            db.session.flush()  # 获取task.id
            
            # 根据模式创建步骤
            steps = BuildTaskService._get_steps_for_mode(package_config['mode'])
            for step_def in steps:
                step = BuildTaskStep(
                    task_id=task.id,
                    step_order=step_def['order'],
                    step_name=step_def['name'],
                    step_description=step_def['description'],
                    status='pending'
                )
                db.session.add(step)
            
            db.session.commit()
            logger.info(f"创建打包任务成功: task_id={task.id}, project={project.name}, mode={package_config['mode']}")
            
            return task
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"创建打包任务失败: {e}")
            raise
    
    @staticmethod
    def _get_steps_for_mode(mode):
        """根据模式获取步骤列表"""
        if mode == 'normal':
            return NORMAL_MODE_STEPS
        elif mode == 'changelog_only':
            return CHANGELOG_ONLY_STEPS
        elif mode == 'crp_only':
            return CRP_ONLY_STEPS
        else:
            raise ValueError(f"不支持的打包模式: {mode}")
    
    @staticmethod
    def start_task(task_id):
        """启动任务（后台异步执行）"""
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        if task.status != 'pending' and task.status != 'paused':
            raise ValueError(f"任务状态不允许启动: {task.status}")
        
        # 提交到任务队列
        TaskQueue().submit_task(task_id)
        logger.info(f"任务已提交到队列: task_id={task_id}")
        
        return task
    
    @staticmethod
    def pause_task(task_id):
        """暂停任务"""
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        if task.status != 'running':
            raise ValueError(f"只能暂停运行中的任务，当前状态: {task.status}")
        
        # 设置停止标志
        TaskQueue().stop_task(task_id)
        
        task.status = 'paused'
        db.session.commit()
        logger.info(f"任务已暂停: task_id={task_id}")
        
        return task
    
    @staticmethod
    def resume_task(task_id):
        """恢复任务"""
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        if task.status != 'paused':
            raise ValueError(f"只能恢复暂停的任务，当前状态: {task.status}")
        
        # 重新提交到队列
        TaskQueue().submit_task(task_id)
        logger.info(f"任务已恢复: task_id={task_id}")
        
        return task
    
    @staticmethod
    def cancel_task(task_id):
        """取消任务"""
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        if task.status in ['success', 'cancelled']:
            raise ValueError(f"任务已结束，无法取消: {task.status}")
        
        # 设置停止标志
        TaskQueue().stop_task(task_id)
        
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        
        # 将所有未完成的步骤标记为取消
        for step in task.steps:
            if step.status in ['pending', 'running']:
                step.status = 'cancelled'
                if not step.log_message:
                    step.log_message = '任务被取消'
        
        db.session.commit()
        logger.info(f"任务已取消（保留在列表中可重试）: task_id={task_id}")
        
        return task
    
    @staticmethod
    def retry_task(task_id, from_step=None):
        """重试任务
        
        Args:
            task_id: 任务ID
            from_step: 从第几步开始重试（None或0=从第一步开始，1+=从指定步骤）
        """
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        if task.status == 'running':
            raise ValueError("任务正在运行中，无法重试")
        
        # 重置任务状态（默认从第一步开始）
        if from_step is None or from_step == 0:
            # 从第一步开始重试
            task.status = 'pending'
            task.current_step = 0
            task.error_message = None
            task.started_at = None
            task.completed_at = None
            
            # 重置所有步骤
            for step in task.steps:
                step.status = 'pending'
                step.log_message = None
                step.error_message = None
                step.started_at = None
                step.completed_at = None
                step.retry_count += 1
        else:
            # 从指定步骤重试
            task.status = 'pending'
            task.current_step = from_step
            task.error_message = None
            
            # 重置指定步骤及之后的步骤
            for step in task.steps:
                if step.step_order >= from_step:
                    step.status = 'pending'
                    step.log_message = None
                    step.error_message = None
                    step.started_at = None
                    step.completed_at = None
                    step.retry_count += 1
        
        db.session.commit()
        
        # 提交到队列
        TaskQueue().submit_task(task_id)
        logger.info(f"任务重试（从第{'一' if not from_step else from_step}步开始）: task_id={task_id}")
        
        return task
    
    @staticmethod
    def get_task_status(task_id):
        """获取任务状态"""
        task = BuildTask.query.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        return task.to_dict()
    
    @staticmethod
    def get_all_tasks(status=None, limit=100, offset=0):
        """获取任务列表"""
        query = BuildTask.query
        
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(BuildTask.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        tasks = query.all()
        return [task.to_dict() for task in tasks]


class BuildExecutor:
    """打包任务执行器（核心逻辑框架）"""
    
    def __init__(self, task_id):
        self.task_id = task_id
        self.task = None
        self.project = None
        self.stopped = False  # 停止标志
        self._stop_event = threading.Event()
    
    def _setup_github_proxy(self, repo):
        """
        为GitHub仓库设置代理（仅GitHub需要）
        
        Args:
            repo: GitPython的Repo对象
        """
        # 检查是否是GitHub仓库
        if not self.project.github_url:
            return
        
        try:
            from app.models import GlobalConfig
            config = GlobalConfig.query.first()
            
            if config and config.https_proxy:
                # 设置Git的HTTP/HTTPS代理
                with repo.config_writer() as git_config:
                    git_config.set_value('http', 'proxy', config.https_proxy)
                    git_config.set_value('https', 'proxy', config.https_proxy)
                logger.info(f"已为GitHub仓库设置代理: {config.https_proxy}")
        except Exception as e:
            logger.warning(f"设置代理失败: {e}，将尝试直接连接")
    
    def _clear_github_proxy(self, repo):
        """
        清除GitHub仓库的代理设置
        
        Args:
            repo: GitPython的Repo对象
        """
        try:
            with repo.config_writer() as git_config:
                try:
                    git_config.remove_option('http', 'proxy')
                except:
                    pass
                try:
                    git_config.remove_option('https', 'proxy')
                except:
                    pass
        except Exception as e:
            logger.warning(f"清除代理失败: {e}")
    
    def execute(self):
        """执行任务主流程"""
        try:
            # 重新获取任务对象（新线程需要新session）
            self.task = BuildTask.query.get(self.task_id)
            if not self.task:
                raise Exception(f"任务不存在: {self.task_id}")
            
            self.project = Project.query.get(self.task.project_id)
            if not self.project:
                raise Exception(f"项目不存在: {self.task.project_id}")
            
            # 更新任务状态
            self.task.status = 'running'
            if not self.task.started_at:
                self.task.started_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"开始执行任务: task_id={self.task_id}, project={self.project.name}")
            
            # 执行步骤
            for step in self.task.steps:
                if self._stop_event.is_set():
                    logger.info(f"任务被停止: task_id={self.task_id}")
                    break
                
                # 跳过已完成的步骤（用于重试场景）
                if step.status == 'completed':
                    continue
                
                self._execute_step(step)
            
            # 检查是否所有步骤都完成
            if all(step.status in ['completed', 'skipped'] for step in self.task.steps):
                self.task.status = 'success'
                self.task.completed_at = datetime.utcnow()
                logger.info(f"任务执行成功: task_id={self.task_id}")
            
            db.session.commit()
            
        except Exception as e:
            logger.exception(f"任务执行失败: task_id={self.task_id}, error={e}")
            if self.task:
                self.task.status = 'failed'
                self.task.error_message = str(e)
                self.task.completed_at = datetime.utcnow()
                db.session.commit()
    
    def _execute_step(self, step):
        """执行单个步骤"""
        try:
            logger.info(f"执行步骤: task_id={self.task_id}, step={step.step_name}")
            
            step.status = 'running'
            step.started_at = datetime.utcnow()
            self.task.current_step = step.step_order
            db.session.commit()
            
            # 调用对应的步骤处理方法
            handler_name = f'_step_{step.step_order}_{self._normalize_step_name(step.step_name)}'
            handler = getattr(self, handler_name, None)
            
            if handler:
                handler(step)
            else:
                # 默认处理：标记为待实现
                step.log_message = f"步骤 {step.step_name} 待实现"
                logger.warning(f"步骤处理方法未实现: {handler_name}")
            
            step.status = 'completed'
            step.completed_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"步骤执行成功: task_id={self.task_id}, step={step.step_name}")
            
        except Exception as e:
            logger.exception(f"步骤执行失败: task_id={self.task_id}, step={step.step_name}, error={e}")
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = datetime.utcnow()
            db.session.commit()
            raise
    
    def _normalize_step_name(self, step_name):
        """标准化步骤名称为方法名"""
        # 将中文步骤名转换为拼音或英文标识
        name_map = {
            '检查环境': 'check_env',
            '拉取最新代码': 'pull_code',
            '生成Changelog': 'generate_changelog',
            '提交Commit': 'commit',
            '推送到远程': 'push',
            '创建PR': 'create_pr',
            '监控PR状态': 'monitor_pr',
            '等待同步': 'wait_sync',
            'CRP打包': 'crp_build',
            '监控打包': 'monitor_build',
        }
        return name_map.get(step_name, step_name.lower().replace(' ', '_'))
    
    def stop(self):
        """停止执行"""
        self.stopped = True
        self._stop_event.set()
    
    def _find_last_changelog_version(self, repo):
        """
        查找最新的已打包版本，优先使用changelog中的版本
        
        Returns:
            str: 版本号或commit hash，用于git log范围查询
        """
        try:
            # 方法1: 尝试从changelog获取上一个版本
            changelog_path = os.path.join(self.project.local_repo_path, 'debian', 'changelog')
            if os.path.exists(changelog_path):
                try:
                    # 解析changelog获取前两个版本（当前版本和上一个版本）
                    with open(changelog_path, 'r') as f:
                        content = f.read()
                    
                    import re
                    # 匹配版本行: package (version) distribution; urgency=level
                    version_pattern = r'\w+\s+\(([^)]+)\)\s+(?:unstable|stable)'
                    matches = re.findall(version_pattern, content)
                    
                    if len(matches) >= 2:
                        # 取倒数第二个版本（上一个版本）
                        prev_version = matches[0]
                        logger.info(f"从changelog找到上一个版本: {prev_version}")
                        
                        # 尝试找到这个版本对应的commit
                        commit_hash = self._find_commit_by_changelog_version(repo, prev_version)
                        if commit_hash:
                            logger.warn(f"找到版本 {prev_version} 对应的commit: {commit_hash[:8]}")
                            return commit_hash
                        else:
                            # 如果找不到commit，直接使用版本号
                            logger.info(f"未找到commit，使用版本号: {prev_version}")
                            return prev_version
                    elif len(matches) == 1:
                        # 只有一个版本，说明是首次发布，尝试使用git的第一个commit
                        logger.info("changelog只有一个版本，使用git历史的初始commit")
                        try:
                            first_commit = repo.git.rev_list('--max-parents=0', 'HEAD')
                            return first_commit
                        except:
                            return None
                    
                except Exception as e:
                    logger.warning(f"解析changelog失败: {e}")
            
            # 方法2: 回退到git tag
            try:
                last_tag = repo.git.describe('--tags', '--abbrev=0')
                logger.info(f"使用git tag作为回退: {last_tag}")
                return last_tag
            except Exception as e:
                logger.warning(f"获取git tag失败: {e}")
            
            # 方法3: 使用第一个commit
            try:
                first_commit = repo.git.rev_list('--max-parents=0', 'HEAD')
                logger.info(f"使用首次commit: {first_commit[:8]}")
                return first_commit
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.warning(f"查找上一个版本失败: {e}")
            return None
    
    def _find_commit_by_changelog_version(self, repo, version):
        """
        通过git blame查找changelog版本对应的commit
        参考: git-tag.py中的findCommitByChangelogBlame方法
        
        Args:
            repo: GitPython的Repo对象
            version: changelog版本号
            
        Returns:
            str: commit hash，如果未找到则返回None
        """
        try:
            changelog_path = os.path.join(self.project.local_repo_path, 'debian', 'changelog')
            
            # 使用git blame查找包含该版本的行
            blame_output = repo.git.blame('--porcelain', 'debian/changelog')
            
            lines = blame_output.split('\n')
            current_commit = None
            
            for i, line in enumerate(lines):
                # 解析commit hash行
                if line and not line.startswith('\t') and ' ' in line:
                    parts = line.split(' ')
                    # 检查是否是40位的commit hash
                    if len(parts) >= 1 and len(parts[0]) == 40:
                        try:
                            # 验证是否全是十六进制字符
                            int(parts[0], 16)
                            current_commit = parts[0]
                        except ValueError:
                            continue
                # 解析内容行（以\t开头）
                elif line.startswith('\t') and current_commit:
                    content = line[1:]  # 去掉开头的\t
                    # 检查是否是目标版本的行
                    if f"({version})" in content and ('unstable' in content or 'stable' in content):
                        logger.info(f"通过git blame找到版本 {version} 对应的commit: {current_commit[:8]}")
                        return current_commit
            
            # 如果git blame未找到，尝试通过git log搜索
            try:
                # 搜索提交信息中包含版本号的commit
                log_output = repo.git.log(
                    '--grep', f'bump version to {version}',
                    '--format=%H',
                    '-n', '1'
                )
                if log_output.strip():
                    commit_hash = log_output.strip()
                    logger.info(f"通过git log找到版本 {version} 对应的commit: {commit_hash[:8]}")
                    return commit_hash
            except Exception as e:
                logger.debug(f"git log搜索失败: {e}")
            
            logger.warning(f"未找到版本 {version} 对应的commit")
            return None
            
        except Exception as e:
            logger.warning(f"查找commit失败: {e}")
            return None
    
    # ==================== 步骤处理方法（框架，待实现具体逻辑） ====================
    
    def _step_0_check_env(self, step):
        """步骤0: 检查环境"""
        check_results = []
        
        # 检查本地仓库是否存在
        if not os.path.exists(self.project.local_repo_path):
            raise Exception(f"本地仓库不存在: {self.project.local_repo_path}")
        check_results.append("✓ 仓库路径正常")
        
        # 检查dch工具
        if not shutil.which('dch'):
            raise Exception("未安装dch工具，请安装: sudo apt install devscripts")
        check_results.append("✓ dch工具已安装")
        
        # 检查gh命令（GitHub项目）
        if self.project.github_url:
            if not shutil.which('gh'):
                raise Exception("未安装gh工具，请安装: sudo apt install gh")
            check_results.append("✓ gh工具已安装")
        
        # 检查git-review工具（Gerrit项目）
        if self.project.gerrit_url:
            if not shutil.which('git-review'):
                raise Exception("未安装git-review工具，请安装: sudo apt install git-review")
            check_results.append("✓ git-review工具已安装")
        
        # 检查debian/changelog文件是否存在
        changelog_path = os.path.join(self.project.local_repo_path, 'debian', 'changelog')
        if not os.path.exists(changelog_path):
            raise Exception(f"debian/changelog文件不存在: {changelog_path}")
        check_results.append("✓ debian/changelog文件存在")
        
        step.log_message = "环境检查通过:\n" + "\n".join(check_results)
        logger.info(f"环境检查通过: task_id={self.task_id}")
    
    def _step_1_pull_code(self, step):
        """步骤1: 拉取最新代码"""
        try:
            repo = Repo(self.project.local_repo_path)
            
            # 为GitHub仓库设置代理
            self._setup_github_proxy(repo)
            
            # 确定要拉取的分支
            target_branch = self.project.github_branch if self.project.github_url else self.project.gerrit_branch
            if not target_branch:
                raise Exception("未配置项目分支")
            
            # Fetch最新代码
            logger.info(f"Fetching from origin: task_id={self.task_id}")
            origin = repo.remotes.origin
            origin.fetch()
            
            # Checkout到目标分支
            logger.info(f"Checking out branch: {target_branch}")
            repo.git.checkout(target_branch)
            
            # Pull最新代码
            logger.info(f"Pulling latest changes: task_id={self.task_id}")
            origin.pull(target_branch)
            
            # 获取最新commit信息
            latest_commit = repo.head.commit
            commit_hash = latest_commit.hexsha[:8]
            commit_msg = latest_commit.message.strip().split('\n')[0]
            
            step.log_message = (
                f"代码拉取成功\n"
                f"分支: {target_branch}\n"
                f"最新提交: {commit_hash}\n"
                f"提交信息: {commit_msg}"
            )
            
            # 保存当前commit hash
            self.task.start_commit_hash = latest_commit.hexsha
            db.session.commit()
            
            logger.info(f"代码拉取成功: task_id={self.task_id}, commit={commit_hash}")
            
        except Exception as e:
            logger.exception(f"拉取代码失败: task_id={self.task_id}, error={e}")
            raise Exception(f"拉取代码失败: {str(e)}")
    
    def _step_2_generate_changelog(self, step):
        """步骤2: 生成Changelog"""
        try:
            repo = Repo(self.project.local_repo_path)
            
            # 创建打包分支（GitHub项目需要）
            if self.project.github_url:
                branch_name = f"dev-changelog-{self.task.version}"
                self.task.github_branch = branch_name
                db.session.commit()
                
                # 获取基础分支
                base_branch = self.project.github_branch
                
                logger.info(f"创建打包分支: {branch_name} from origin/{base_branch}")
                try:
                    # 为GitHub仓库设置代理
                    self._setup_github_proxy(repo)
                    
                    # 获取最新的远程分支状态
                    origin = repo.remotes.origin
                    logger.info(f"拉取最新的远程分支: {base_branch}")
                    origin.fetch()
                    
                    # 先删除本地分支（如果存在）
                    try:
                        repo.git.branch('-D', branch_name)
                    except:
                        pass
                    
                    # 从远程基础分支创建新分支（-B强制创建/重置）
                    repo.git.checkout('-B', branch_name, f'origin/{base_branch}')
                    
                    # 重置到干净状态，清除任何冲突或未提交的更改
                    repo.git.clean('-fd')  # 删除未跟踪的文件和目录
                    repo.git.reset('--hard', f'origin/{base_branch}')  # 硬重置到远程分支
                    
                    logger.info(f"✓ 分支已重置到干净状态: origin/{base_branch}")
                    
                except Exception as e:
                    raise Exception(f"创建分支失败: {str(e)}")
            
            # 设置DEBEMAIL环境变量（从全局配置读取）
            from app.models import GlobalConfig
            config = GlobalConfig.query.first()
            if config and config.maintainer_email:
                os.environ['DEBEMAIL'] = config.maintainer_email
                logger.info(f"设置DEBEMAIL: {config.maintainer_email}")
            
            # 获取上一个版本（优先使用changelog版本）
            last_version = self._find_last_changelog_version(repo)
            if not last_version:
                logger.warning(f"未找到上一个changelog版本，将使用默认消息")
            else:
                logger.info(f"上一个版本: {last_version}")
            
            # 获取commit信息（从上一个版本到HEAD）
            commit_info = None
            if last_version:
                try:
                    commit_log = repo.git.log(
                        '--pretty=format:%s',
                        '--no-merges',
                        f'{last_version}..HEAD'
                    )
                    if commit_log:
                        commit_info = commit_log
                        logger.info(f"获取到 {len(commit_log.split(chr(10)))} 条提交记录")
                except Exception as e:
                    logger.warning(f"获取commit日志失败: {e}")
            
            if not commit_info:
                commit_info = f"Release {self.task.version}"
            
            # 切换到仓库目录
            os.chdir(self.project.local_repo_path)
            
            # 使用dch生成changelog
            logger.info(f"生成changelog: version={self.task.version}")
            try:
                # 将commit信息按行分割，逐行添加到changelog
                commits = commit_info.strip().split('\n')
                for commit_msg in commits:
                    if commit_msg.strip():
                        subprocess.run(
                            ['dch', '-v', self.task.version, commit_msg.strip()],
                            check=True,
                            capture_output=True,
                            text=True
                        )

                        logger.warning(f"添加到changelog: {commit_msg.strip()}")
                
                step.log_message = (
                    f"Changelog已生成\n"
                    f"版本: {self.task.version}\n"
                    f"基于版本: {last_version if last_version else '首次发布'}\n"
                    f"包含 {len(commits)} 条变更记录"
                )
                
                logger.info(f"Changelog生成成功: task_id={self.task_id}, version={self.task.version}")
                
            except subprocess.CalledProcessError as e:
                logger.exception(f"dch命令执行失败: {e.stderr}")
                raise Exception(f"生成changelog失败: {e.stderr}")
            
        except Exception as e:
            logger.exception(f"生成changelog失败: task_id={self.task_id}, error={e}")
            raise
    
    def _step_3_commit(self, step):
        """步骤3: 提交Commit"""
        try:
            repo = Repo(self.project.local_repo_path)
            
            # 为GitHub仓库设置代理
            self._setup_github_proxy(repo)
            
            # 获取当前分支
            current_branch = repo.active_branch.name
            logger.info(f"当前分支: {current_branch}, task_id={self.task_id}")
            
            # 在提交前，确保分支是最新的（避免冲突）
            logger.info(f"同步远程最新代码: task_id={self.task_id}")
            try:
                # 检查是否有未提交的修改
                has_changes = repo.is_dirty()
                
                if has_changes:
                    # 暂存当前的修改（changelog）
                    logger.info("暂存当前修改")
                    repo.git.stash('push', '-m', f'temp-stash-{self.task.version}')
                
                # 从远程获取最新代码
                origin = repo.remotes.origin
                origin.fetch()
                
                # 重置到远程分支最新状态
                try:
                    repo.git.reset('--hard', f'origin/{current_branch}')
                    logger.info(f"已重置到 origin/{current_branch} 最新状态")
                except Exception as e:
                    logger.warning(f"远程分支不存在: {e}，保持当前状态")
                
                if has_changes:
                    # 恢复暂存的修改
                    try:
                        repo.git.stash('pop')
                        logger.info("已恢复暂存的修改")
                    except Exception as e:
                        # 如果pop失败，可能是因为有冲突，尝试drop stash
                        logger.warning(f"恢复暂存时出现问题: {e}")
                        try:
                            repo.git.stash('drop')
                        except:
                            pass
                        # 继续，因为修改可能已经应用了
                        
            except Exception as e:
                logger.warning(f"同步远程代码时出错: {e}，继续提交流程")
            
            # 检查是否有需要提交的修改
            if not repo.is_dirty():
                step.log_message = "没有需要提交的修改"
                logger.info(f"工作区干净，无需提交: task_id={self.task_id}")
                return
            
            # 添加debian/changelog到暂存区
            changelog_path = 'debian/changelog'
            repo.index.add([changelog_path])
            logger.info(f"已添加文件到暂存区: {changelog_path}")
            
            # 获取暂存区的diff信息
            try:
                diff_stat = repo.git.diff('--cached', '--stat')
                logger.info(f"暂存区变更:\n{diff_stat}")
            except:
                pass
            
            # 创建commit（多行格式：标题 + 空行 + 内容 + 空行 + Log）
            commit_title = f"chore: bump version to {self.task.version}"
            commit_body = f"update changelog to {self.task.version}"
            commit_log = f"Log: update changelog to {self.task.version}"
            commit_message = f"{commit_title}\n\n{commit_body}\n\n{commit_log}"
            
            commit = repo.index.commit(commit_message)
            
            step.log_message = (
                f"提交成功\n"
                f"分支: {current_branch}\n"
                f"Commit: {commit.hexsha[:8]}\n"
                f"标题: {commit_title}\n"
                f"修改文件: debian/changelog"
            )
            
            # 保存commit hash
            self.task.github_commit_hash = commit.hexsha
            db.session.commit()
            
            logger.info(f"提交成功: task_id={self.task_id}, commit={commit.hexsha[:8]}")
            
        except Exception as e:
            logger.exception(f"提交失败: task_id={self.task_id}, error={e}")
            raise Exception(f"提交失败: {str(e)}")
    
    def _step_4_push(self, step):
        """步骤4: 推送到远程"""
        try:
            repo = Repo(self.project.local_repo_path)
            current_branch = repo.active_branch.name
            
            # 获取全局配置
            from app.models import GlobalConfig
            config = GlobalConfig.query.first()
            
            if self.project.github_url:
                # 为GitHub仓库设置代理
                self._setup_github_proxy(repo)
                
                # GitHub项目：推送到用户自己的fork仓库
                if not config or not config.github_username:
                    raise Exception("未配置GitHub用户名，请在全局配置中设置github_username")
                
                # 获取上游仓库信息
                # GitHub URL格式: https://github.com/owner/repo.git
                upstream_url = self.project.github_url
                if upstream_url.endswith('.git'):
                    upstream_url = upstream_url[:-4]
                
                # 构建fork仓库URL
                # 从 https://github.com/linuxdeepin/dde-shell.git 提取 repo名
                repo_name = upstream_url.split('/')[-1]
                fork_url = f"https://github.com/{config.github_username}/{repo_name}.git"
                
                logger.info(f"推送到fork仓库: {fork_url}")
                
                # 检查是否已有fork remote
                try:
                    fork_remote = repo.remotes['fork']
                    logger.info("使用已存在的fork remote")
                except:
                    # 添加fork remote
                    logger.info(f"添加fork remote: {fork_url}")
                    fork_remote = repo.create_remote('fork', fork_url)
                
                # 推送到fork仓库
                logger.info(f"推送分支 {current_branch} 到 fork/{current_branch}")
                try:
                    push_info = fork_remote.push(f"{current_branch}:{current_branch}", force=True)
                    logger.info(f"推送结果: {push_info}")
                except Exception as e:
                    raise Exception(f"推送到fork仓库失败: {str(e)}")
                
                step.log_message = (
                    f"推送成功\n"
                    f"目标: fork仓库\n"
                    f"分支: {current_branch}\n"
                    f"仓库: {config.github_username}/{repo_name}"
                )
                
            elif self.project.gerrit_url:
                # Gerrit项目：使用git-review推送
                target_branch = self.project.gerrit_branch
                
                logger.info(f"使用git-review推送到Gerrit: {target_branch}")
                
                # 切换到仓库目录
                os.chdir(self.project.local_repo_path)
                
                # 使用git-review推送
                try:
                    result = subprocess.run(
                        ['git', 'review', '-R', target_branch, '-r', 'origin'],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    
                    logger.info(f"git-review输出: {result.stdout}")
                    
                    step.log_message = (
                        f"推送成功\n"
                        f"目标: Gerrit\n"
                        f"分支: {target_branch}\n"
                        f"方式: git-review"
                    )
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"git-review失败: {e.stderr}")
                    raise Exception(f"git-review推送失败: {e.stderr}")
            else:
                raise Exception("项目未配置GitHub或Gerrit URL")
            
            logger.info(f"推送成功: task_id={self.task_id}")
            
        except Exception as e:
            logger.exception(f"推送失败: task_id={self.task_id}, error={e}")
            raise Exception(f"推送失败: {str(e)}")
    
    def _step_5_create_pr(self, step):
        """步骤5: 创建PR（仅GitHub）"""
        if not self.project.github_url:
            step.status = 'skipped'
            step.log_message = "非GitHub项目，跳过PR创建"
            return
        
        try:
            repo = Repo(self.project.local_repo_path)
            current_branch = repo.active_branch.name
            
            # 获取全局配置
            from app.models import GlobalConfig
            config = GlobalConfig.query.first()
            
            if not config or not config.github_username:
                raise Exception("未配置GitHub用户名")
            
            # 解析上游仓库信息
            # 从 https://github.com/linuxdeepin/dde-shell.git 提取 owner/repo
            upstream_url = self.project.github_url
            if upstream_url.endswith('.git'):
                upstream_url = upstream_url[:-4]
            
            parts = upstream_url.replace('https://github.com/', '').split('/')
            upstream_owner = parts[0]
            repo_name = parts[1]
            
            # 目标分支（通常是master或main）
            base_branch = self.project.github_branch
            
            # PR标题和描述
            pr_title = f"chore: update changelog to {self.task.version}"
            pr_body = f"""## 更新说明

自动更新 changelog 到版本 {self.task.version}

### 变更内容
- 更新 debian/changelog

### 版本信息
- 新版本: {self.task.version}
- 目标分支: {base_branch}
"""
            
            # 切换到仓库目录
            os.chdir(self.project.local_repo_path)
            
            # 使用gh命令创建PR
            logger.info(f"创建PR: {config.github_username}:{current_branch} -> {upstream_owner}:{base_branch}")
            
            try:
                # gh pr create --repo OWNER/REPO --head USER:BRANCH --base BASE --title TITLE --body BODY
                cmd = [
                    'gh', 'pr', 'create',
                    '--repo', f'{upstream_owner}/{repo_name}',
                    '--head', f'{config.github_username}:{current_branch}',
                    '--base', base_branch,
                    '--title', pr_title,
                    '--body', pr_body
                ]
                
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # 从输出中提取PR URL
                pr_url = result.stdout.strip()
                logger.info(f"PR创建成功: {pr_url}")
                
                # 提取PR编号
                # URL格式: https://github.com/owner/repo/pull/123
                pr_number = pr_url.split('/')[-1]
                
                # 保存PR信息到任务
                self.task.github_pr_url = pr_url
                self.task.github_pr_number = int(pr_number) if pr_number.isdigit() else None
                db.session.commit()
                
                step.log_message = (
                    f"PR创建成功\n"
                    f"PR链接: {pr_url}\n"
                    f"标题: {pr_title}\n"
                    f"源分支: {config.github_username}:{current_branch}\n"
                    f"目标分支: {upstream_owner}:{base_branch}"
                )
                
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                logger.warning(f"gh命令执行失败: {error_msg}")
                
                # 检查是否是PR已存在的错误
                if "already exists" in error_msg:
                    # 从错误信息中提取PR URL
                    # 错误格式: a pull request for branch "..." into branch "..." already exists:\nhttps://github.com/...
                    import re
                    pr_url_match = re.search(r'(https://github\.com/[^\s]+)', error_msg)
                    
                    if pr_url_match:
                        pr_url = pr_url_match.group(1).strip()
                        pr_number = pr_url.split('/')[-1]
                        
                        # 保存已存在的PR信息
                        self.task.github_pr_url = pr_url
                        self.task.github_pr_number = int(pr_number) if pr_number.isdigit() else None
                        db.session.commit()
                        
                        step.log_message = (
                            f"⚠️ PR已存在，使用现有PR\n"
                            f"PR链接: {pr_url}\n"
                            f"PR编号: #{pr_number}\n"
                            f"源分支: {config.github_username}:{current_branch}\n"
                            f"目标分支: {upstream_owner}:{base_branch}\n"
                            f"\n提示: 该PR在之前的任务中已创建，将继续使用此PR"
                        )
                        
                        logger.info(f"PR已存在，使用现有PR: {pr_url}, task_id={self.task_id}")
                        return  # 不抛出异常，继续执行
                
                # 其他错误则抛出异常
                logger.error(f"创建PR失败: {error_msg}")
                raise Exception(f"创建PR失败: {error_msg}")
            
            logger.info(f"PR创建成功: task_id={self.task_id}")
            
        except Exception as e:
            logger.exception(f"创建PR失败: task_id={self.task_id}, error={e}")
            raise Exception(f"创建PR失败: {str(e)}")
    
    def _step_6_monitor_pr(self, step):
        """步骤6: 监控PR状态"""
        if not self.project.github_url:
            step.status = 'skipped'
            step.log_message = "非GitHub项目，跳过PR监控"
            return
        
        try:
            # 获取全局配置
            from app.models import GlobalConfig
            config = GlobalConfig.query.first()
            
            if not config or not config.github_token:
                raise Exception("未配置GitHub Token，无法监控PR状态")
            
            if not self.task.github_pr_number:
                raise Exception("未找到PR编号，无法监控")
            
            # 解析仓库信息
            upstream_url = self.project.github_url
            if upstream_url.endswith('.git'):
                upstream_url = upstream_url[:-4]
            
            parts = upstream_url.replace('https://github.com/', '').split('/')
            owner = parts[0]
            repo = parts[1]
            pr_number = self.task.github_pr_number
            
            # GitHub API URL
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            
            # 设置请求头
            headers = {
                'Authorization': f'token {config.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'deepin-autopack'
            }
            
            logger.info(f"开始监控PR状态: {owner}/{repo}#{pr_number}")
            
            # 轮询检查PR状态（最多30分钟，每30秒检查一次）
            max_attempts = 60  # 30分钟 / 30秒
            check_interval = 30  # 30秒
            
            for attempt in range(max_attempts):
                # 检查是否被停止
                if self._stop_event.is_set():
                    step.log_message = "监控被中断"
                    logger.info(f"PR监控被停止: task_id={self.task_id}")
                    return
                
                # 调用GitHub API
                import requests
                try:
                    response = requests.get(api_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        pr_data = response.json()
                        
                        state = pr_data.get('state')  # open, closed
                        merged = pr_data.get('merged', False)
                        mergeable_state = pr_data.get('mergeable_state', 'unknown')
                        
                        # 获取PR的review状态
                        reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
                        try:
                            reviews_response = requests.get(reviews_url, headers=headers, timeout=10)
                            reviews_data = reviews_response.json() if reviews_response.status_code == 200 else []
                            
                            # 统计review状态
                            approved_count = 0
                            changes_requested_count = 0
                            commented_count = 0
                            reviewers = set()
                            
                            for review in reviews_data:
                                reviewer = review.get('user', {}).get('login', 'unknown')
                                reviewers.add(reviewer)
                                review_state = review.get('state', '')
                                
                                if review_state == 'APPROVED':
                                    approved_count += 1
                                elif review_state == 'CHANGES_REQUESTED':
                                    changes_requested_count += 1
                                elif review_state == 'COMMENTED':
                                    commented_count += 1
                            
                            review_summary = f"✓ {approved_count}个批准"
                            if changes_requested_count > 0:
                                review_summary += f" / ✗ {changes_requested_count}个请求修改"
                            if commented_count > 0:
                                review_summary += f" / 💬 {commented_count}个评论"
                            
                            reviewer_list = ", ".join(list(reviewers)[:5])  # 最多显示5个
                            if len(reviewers) > 5:
                                reviewer_list += "..."
                                
                        except Exception as e:
                            logger.warning(f"获取review状态失败: {e}")
                            review_summary = "review状态未知"
                            reviewer_list = ""
                        
                        logger.info(f"PR状态: state={state}, merged={merged}, mergeable_state={mergeable_state}, reviews={review_summary}")
                        
                        if merged:
                            # PR已合并
                            merged_at = pr_data.get('merged_at', '')
                            merged_by = pr_data.get('merged_by', {}).get('login', 'unknown')
                            
                            step.log_message = (
                                f"PR已合并\n"
                                f"PR编号: #{pr_number}\n"
                                f"合并者: {merged_by}\n"
                                f"合并时间: {merged_at}\n"
                                f"检查次数: {attempt + 1}"
                            )
                            
                            logger.info(f"PR已合并: task_id={self.task_id}, pr={pr_number}")
                            return
                        
                        elif state == 'closed' and not merged:
                            # PR被关闭但未合并
                            raise Exception(f"PR#{pr_number}已关闭但未合并，请检查PR状态")
                        
                        # PR仍在打开状态，继续等待
                        logger.info(f"PR#{pr_number}仍在等待合并 (attempt {attempt + 1}/{max_attempts})")
                        
                        # 更新步骤日志显示进度
                        elapsed_time = (attempt + 1) * check_interval
                        step.log_message = (
                            f"等待PR合并中...\n"
                            f"PR编号: #{pr_number}\n"
                            f"状态: {state}\n"
                            f"Review状态: {review_summary}\n"
                        )
                        
                        if reviewer_list:
                            step.log_message += f"评审者: {reviewer_list}\n"
                        
                        step.log_message += (
                            f"已等待: {elapsed_time}秒\n"
                            f"检查次数: {attempt + 1}/{max_attempts}"
                        )
                        db.session.commit()
                        
                    elif response.status_code == 404:
                        raise Exception(f"PR不存在: {owner}/{repo}#{pr_number}")
                    elif response.status_code == 401:
                        raise Exception("GitHub Token无效或已过期")
                    elif response.status_code == 403:
                        # 可能是API速率限制
                        rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                        raise Exception(f"GitHub API访问受限 (剩余: {rate_limit_remaining})")
                    else:
                        raise Exception(f"GitHub API请求失败: HTTP {response.status_code}")
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"GitHub API请求超时，继续重试")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"GitHub API请求异常: {e}，继续重试")
                
                # 等待下一次检查（使用可中断的sleep）
                for _ in range(check_interval):
                    if self._stop_event.is_set():
                        return
                    time.sleep(1)
            
            # 超时未合并
            raise Exception(f"PR监控超时（{max_attempts * check_interval / 60}分钟），PR仍未合并")
            
        except Exception as e:
            logger.exception(f"PR监控失败: task_id={self.task_id}, error={e}")
            raise Exception(f"PR监控失败: {str(e)}")
    
    def _step_7_wait_sync(self, step):
        """步骤7: 等待GitHub同步到Gerrit"""
        # 检查是否需要等待同步
        if not self.project.github_url or not self.project.gerrit_url:
            step.status = 'skipped'
            step.log_message = "项目未同时配置GitHub和Gerrit，跳过同步等待"
            return
        
        if not self.task.github_commit_hash:
            raise Exception("未找到GitHub commit hash，无法监控同步状态")
        
        try:
            # 获取全局配置
            from app.models import GlobalConfig
            from app.services.gerrit_service import create_gerrit_service
            
            config = GlobalConfig.query.first()
            if not config or not config.ldap_username or not config.ldap_password:
                raise Exception("未配置LDAP账号密码，无法访问Gerrit")
            
            # 提取Gerrit项目名称
            gerrit_url = self.project.gerrit_url
            if '/plugins/gitiles/' in gerrit_url:
                # Gitiles URL格式: https://gerrit.uniontech.com/plugins/gitiles/snipe/dde-appearance
                gerrit_project_name = gerrit_url.split('/plugins/gitiles/')[-1]
            elif '/admin/repos/' in gerrit_url:
                # Admin repos URL格式: https://gerrit.uniontech.com/admin/repos/dde/dde-appearance
                gerrit_project_name = gerrit_url.split('/admin/repos/')[-1]
            else:
                # 直接取最后部分
                gerrit_project_name = gerrit_url.split('/')[-1]
            
            gerrit_branch = self.project.gerrit_branch
            if not gerrit_branch:
                raise Exception("未配置Gerrit分支")
            
            # 期望的commit hash（GitHub PR的commit）
            expected_commit = self.task.github_commit_hash
            
            logger.info(f"开始监控GitHub→Gerrit同步: project={gerrit_project_name}, branch={gerrit_branch}, expected={expected_commit[:8]}")
            
            # 创建Gerrit服务
            gerrit = create_gerrit_service(
                gerrit_url='https://gerrit.uniontech.com',
                username=config.ldap_username,
                password=config.ldap_password
            )
            
            # 轮询检查同步状态（最多10分钟，每30秒检查一次）
            max_attempts = 20  # 10分钟 / 30秒
            check_interval = 30  # 30秒
            
            for attempt in range(max_attempts):
                # 检查是否被停止
                if self._stop_event.is_set():
                    step.log_message = "监控被中断"
                    logger.info(f"同步监控被停止: task_id={self.task_id}")
                    return
                
                # 获取Gerrit最新commit
                logger.info(f"检查Gerrit同步状态 (attempt {attempt + 1}/{max_attempts})")
                
                result = gerrit.get_latest_commit(gerrit_project_name, gerrit_branch)
                
                if result['success']:
                    gerrit_commit = result['data']['revision']
                    
                    logger.info(f"Gerrit最新commit: {gerrit_commit[:8]}, 期望commit: {expected_commit[:8]}")
                    
                    # 检查是否同步完成
                    if gerrit_commit == expected_commit:
                        # 同步完成
                        step.log_message = (
                            f"GitHub→Gerrit同步完成\n"
                            f"Gerrit项目: {gerrit_project_name}\n"
                            f"分支: {gerrit_branch}\n"
                            f"Commit: {gerrit_commit[:8]}\n"
                            f"检查次数: {attempt + 1}"
                        )
                        
                        logger.info(f"同步完成: task_id={self.task_id}, commit={gerrit_commit[:8]}")
                        return
                    
                    # 尚未同步，继续等待
                    elapsed_time = (attempt + 1) * check_interval
                    step.log_message = (
                        f"等待GitHub→Gerrit同步中...\n"
                        f"Gerrit项目: {gerrit_project_name}\n"
                        f"分支: {gerrit_branch}\n"
                        f"期望Commit: {expected_commit[:8]}\n"
                        f"当前Commit: {gerrit_commit[:8]}\n"
                        f"已等待: {elapsed_time}秒\n"
                        f"检查次数: {attempt + 1}/{max_attempts}"
                    )
                    db.session.commit()
                    
                else:
                    # API调用失败，记录警告并继续重试
                    logger.warning(f"获取Gerrit commit失败: {result['message']}")
                    
                    elapsed_time = (attempt + 1) * check_interval
                    step.log_message = (
                        f"等待GitHub→Gerrit同步中...\n"
                        f"Gerrit项目: {gerrit_project_name}\n"
                        f"分支: {gerrit_branch}\n"
                        f"状态: 正在重试获取Gerrit状态...\n"
                        f"已等待: {elapsed_time}秒\n"
                        f"检查次数: {attempt + 1}/{max_attempts}"
                    )
                    db.session.commit()
                
                # 等待下一次检查（使用可中断的sleep）
                for _ in range(check_interval):
                    if self._stop_event.is_set():
                        return
                    time.sleep(1)
            
            # 超时未同步
            raise Exception(f"同步监控超时（{max_attempts * check_interval / 60}分钟），GitHub代码尚未同步到Gerrit")
            
        except Exception as e:
            logger.exception(f"同步监控失败: task_id={self.task_id}, error={e}")
            raise Exception(f"同步监控失败: {str(e)}")
    
    def _step_8_crp_build(self, step):
        """步骤8: CRP打包"""
        try:
            from app.models import GlobalConfig
            from app.services.crp_service import CRPService
            
            config = GlobalConfig.query.first()
            if not config:
                raise Exception("未找到全局配置")
            
            if not config.crp_branch_id:
                raise Exception("未配置CRP分支ID")
            
            if not self.task.crp_topic_id:
                raise Exception("未指定CRP主题ID")
            
            # 获取CRP Token
            logger.info(f"获取CRP Token: task_id={self.task_id}")
            token = CRPService.get_token()
            if not token:
                raise Exception("获取CRP Token失败，请检查LDAP账号密码配置")
            
            # 确定commit hash
            if self.task.package_mode == 'crp_only':
                # 仅CRP模式，使用指定的commit
                commit_hash = self.task.start_commit_hash
                logger.info(f"使用指定commit: {commit_hash[:8]}")
            elif self.project.github_url and self.task.gerrit_commit_hash:
                # GitHub项目，使用同步后的gerrit commit
                commit_hash = self.task.gerrit_commit_hash
                logger.info(f"使用Gerrit同步commit: {commit_hash[:8]}")
            else:
                # Gerrit项目或其他情况，使用最新commit
                repo = Repo(self.project.local_repo_path)
                commit_hash = repo.head.commit.hexsha
                logger.info(f"使用当前commit: {commit_hash[:8]}")
            
            # 确定分支
            branch = self.project.gerrit_branch if self.project.gerrit_branch else self.project.github_branch
            if not branch:
                raise Exception("未配置项目分支")
            
            # 格式化架构列表
            if self.task.architectures:
                # 转换架构名称映射
                arch_map = {
                    'amd64': 'amd64',
                    'arm64': 'arm64',
                    'loongarch64': 'loong64',
                    'riscv64': 'riscv64'
                }
                arches = ';'.join([arch_map.get(arch, arch) for arch in self.task.architectures])
            else:
                # 默认架构
                arches = 'amd64;arm64;loong64'
            
            logger.info(f"提交CRP打包: project={self.project.name}, topic_id={self.task.crp_topic_id}, "
                       f"branch={branch}, commit={commit_hash[:8]}, arches={arches}")
            
            # 调用CRP API提交打包任务
            result = CRPService.submit_build(
                token=token,
                topic_id=int(self.task.crp_topic_id),
                project_id=0,  # 项目ID可以为0，CRP会自动匹配
                project_name=self.project.name,
                branch=branch,
                commit=commit_hash,
                tag=self.task.version,
                arches=arches,
                branch_id=config.crp_branch_id,
                changelog=f"Release {self.task.version}"
            )
            
            if not result or not result.get('success'):
                raise Exception("CRP打包任务提交失败，请检查配置或查看日志")
            
            # 保存CRP打包信息
            self.task.crp_build_id = str(result.get('build_id', 0))
            self.task.crp_build_url = result.get('url', '')
            self.task.crp_build_status = 'building'
            db.session.commit()
            
            step.log_message = (
                f"CRP打包任务已提交\n"
                f"主题ID: {self.task.crp_topic_id}\n"
                f"项目: {self.project.name}\n"
                f"分支: {branch}\n"
                f"Commit: {commit_hash[:8]}\n"
                f"版本: {self.task.version}\n"
                f"架构: {arches}\n"
                f"Build ID: {self.task.crp_build_id}\n"
                f"URL: {self.task.crp_build_url}"
            )
            
            logger.info(f"CRP打包任务提交成功: task_id={self.task_id}, build_id={self.task.crp_build_id}")
            
        except Exception as e:
            logger.exception(f"CRP打包失败: task_id={self.task_id}, error={e}")
            raise Exception(f"CRP打包失败: {str(e)}")
    
    def _step_9_monitor_build(self, step):
        """步骤9: 监控打包状态"""
        # 目前不监控打包状态，直接标记为待实现
        step.log_message = (
            "CRP打包监控功能待实现\n"
            "打包任务已提交到CRP平台，请前往CRP平台查看打包状态\n"
            f"URL: {self.task.crp_build_url if self.task.crp_build_url else 'N/A'}"
        )
        logger.info(f"跳过CRP打包监控: task_id={self.task_id}")
        time.sleep(1)
    
    def _step_1_crp_build(self, step):
        """步骤1: CRP打包（仅CRP模式）"""
        self._step_8_crp_build(step)
    
    def _step_2_monitor_build(self, step):
        """步骤2: 监控打包（仅CRP模式）"""
        self._step_9_monitor_build(step)


class TaskQueue:
    """任务队列管理器（单例）"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=3)  # 最多3个并发任务
        self.running_tasks = {}  # task_id -> (Future, BuildExecutor)
        
        # 保存Flask应用实例用于在线程中创建上下文
        from flask import current_app
        self.app = current_app._get_current_object()
        
        self._initialized = True
        logger.info("任务队列管理器初始化完成")
    
    def submit_task(self, task_id):
        """提交任务到队列"""
        if task_id in self.running_tasks:
            logger.warning(f"任务已在运行中: task_id={task_id}")
            return
        
        executor_instance = BuildExecutor(task_id)
        future = self.executor.submit(self._run_task, task_id, executor_instance)
        self.running_tasks[task_id] = (future, executor_instance)
        
        logger.info(f"任务已提交到执行器: task_id={task_id}")
        return future
    
    def _run_task(self, task_id, executor_instance):
        """执行任务"""
        try:
            # 在新线程中需要创建应用上下文
            with self.app.app_context():
                executor_instance.execute()
        except Exception as e:
            logger.exception(f"任务执行异常: task_id={task_id}, error={e}")
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
                logger.info(f"任务已从队列移除: task_id={task_id}")
    
    def stop_task(self, task_id):
        """停止任务"""
        if task_id in self.running_tasks:
            future, executor_instance = self.running_tasks[task_id]
            executor_instance.stop()
            logger.info(f"已发送停止信号: task_id={task_id}")
    
    def is_running(self, task_id):
        """检查任务是否在运行"""
        return task_id in self.running_tasks
    
    def get_running_tasks(self):
        """获取正在运行的任务列表"""
        return list(self.running_tasks.keys())

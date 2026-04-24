"""
GitHub Workflow 文件解析服务
从仓库的 .github/workflows 目录读取并解析 workflow 文件
"""
import os
import yaml
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowService:
    """Workflow 文件解析服务"""
    
    @staticmethod
    def get_workflows(repo_path: str) -> List[Dict]:
        """
        获取仓库中所有的 workflow 文件
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            workflow 列表，每个 workflow 包含：
            - name: workflow 名称
            - file: workflow 文件名
            - inputs: 输入参数列表
        """
        logger.info(f"[DEBUG] get_workflows 开始, repo_path: {repo_path}")
        workflows_dir = os.path.join(repo_path, '.github', 'workflows')
        logger.info(f"[DEBUG] workflows_dir: {workflows_dir}")
        
        if not os.path.exists(workflows_dir):
            logger.warning(f"Workflows directory not found: {workflows_dir}")
            return []
        
        workflows = []
        
        try:
            for filename in os.listdir(workflows_dir):
                if not (filename.endswith('.yml') or filename.endswith('.yaml')):
                    continue
                
                file_path = os.path.join(workflows_dir, filename)
                workflow_info = WorkflowService._parse_workflow_file(file_path, filename)
                
                if workflow_info:
                    workflows.append(workflow_info)
        
        except Exception as e:
            logger.error(f"Failed to read workflows directory: {e}")
        
        return workflows
    
    @staticmethod
    def _parse_workflow_file(file_path: str, filename: str) -> Optional[Dict]:
        """
        解析单个 workflow 文件
        
        Args:
            file_path: workflow 文件路径
            filename: 文件名
            
        Returns:
            workflow 信息字典，包含 name, file, inputs
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            if not content:
                return None
            
            # 检查是否支持 workflow_dispatch
            on_events = content.get('on', {})
            if isinstance(on_events, list):
                has_dispatch = 'workflow_dispatch' in on_events
                workflow_dispatch = {}
            elif isinstance(on_events, dict):
                has_dispatch = 'workflow_dispatch' in on_events
                workflow_dispatch = on_events.get('workflow_dispatch', {})
            else:
                has_dispatch = False
                workflow_dispatch = {}
            
            # 如果不支持手动触发，跳过
            if not has_dispatch:
                logger.debug(f"Workflow {filename} does not support workflow_dispatch")
                return None
            
            # 获取 workflow 名称
            workflow_name = content.get('name', filename.replace('.yml', '').replace('.yaml', ''))
            
            # 解析输入参数
            inputs = []
            inputs_config = workflow_dispatch.get('inputs', {})
            
            for input_name, input_config in inputs_config.items():
                if not isinstance(input_config, dict):
                    continue
                
                input_info = {
                    'name': input_name,
                    'description': input_config.get('description', ''),
                    'required': input_config.get('required', False),
                    'default': input_config.get('default', ''),
                    'type': input_config.get('type', 'string'),
                }
                
                # 如果有选项（choice 类型）
                if 'options' in input_config:
                    input_info['options'] = input_config['options']
                
                inputs.append(input_info)
            
            return {
                'name': workflow_name,
                'file': filename,
                'inputs': inputs
            }
        
        except Exception as e:
            logger.error(f"Failed to parse workflow file {filename}: {e}")
            return None

"""
CRP平台服务
处理与CRP平台的API交互
"""

import requests
import logging
import rsa
import base64
from typing import List, Dict, Optional
from app.models import GlobalConfig

logger = logging.getLogger(__name__)


class CRPService:
    """CRP平台服务类"""
    
    # CRP公钥用于密码加密
    CRP_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCkA9WqirWQII3D8/M9UG8X8ybQ
Ou+cPSNTgR9b4HenJ7A5zSfkXZnetb5q6MmKTJLGCl9MSsHveQPHmLGDG+xw2MlB
w3Yefd/jJ1Cg8pP69wlHRX+wiyh5p8KY55ehFNsQLm3kDGXgVJdtrZn/MiBOlCtE
fe9YvvT0lqy2BtBpaQIDAQAB
-----END PUBLIC KEY-----"""
    
    BASE_URL = "https://crp.uniontech.com/api"
    
    @staticmethod
    def encrypt_password(password: str) -> str:
        """
        使用RSA公钥加密密码
        
        Args:
            password: 明文密码
            
        Returns:
            Base64编码的加密密码
        """
        try:
            pub_key = rsa.PublicKey.load_pkcs1_openssl_pem(
                CRPService.CRP_PUBLIC_KEY.encode()
            )
            cipher = rsa.encrypt(password.encode(), pub_key)
            return base64.b64encode(cipher).decode()
        except Exception as e:
            logger.error(f"密码加密失败: {str(e)}")
            raise
    
    @staticmethod
    def fetch_token(username: str, password: str) -> Optional[str]:
        """
        登录CRP平台获取Token
        
        Args:
            username: LDAP用户名
            password: LDAP密码（加密后）
            
        Returns:
            Token字符串，失败返回None
        """
        try:
            url = f"{CRPService.BASE_URL}/login"
            headers = {"Content-Type": "application/json"}
            data = {
                "userName": username,
                "password": password
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            token = result.get("Token", "")
            if not token:
                logger.error("Token not found in response")
                return None
            
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"CRP登录失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应内容: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"获取Token异常: {str(e)}")
            return None
    
    @staticmethod
    def get_token() -> Optional[str]:
        """
        从全局配置获取或刷新Token
        
        Returns:
            Token字符串，失败返回None
        """
        config = GlobalConfig.get_config()
        if not config.ldap_username or not config.ldap_password:
            logger.error("LDAP账号密码未配置")
            return None
        
        # 加密密码
        encrypted_pwd = CRPService.encrypt_password(config.ldap_password)
        
        # 获取token
        return CRPService.fetch_token(config.ldap_username, encrypted_pwd)
    
    @staticmethod
    def fetch_user(token: str) -> Optional[str]:
        """
        获取当前登录用户信息
        
        Args:
            token: CRP Token
            
        Returns:
            用户名，失败返回None
        """
        try:
            url = f"{CRPService.BASE_URL}/user"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get("Name", "")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    @staticmethod
    def list_topics(token: str, username: str, branch_id: int, topic_type: str = "test") -> List[Dict]:
        """
        获取主题列表
        
        Args:
            token: CRP Token
            username: 用户名（过滤）
            branch_id: 分支ID
            topic_type: 主题类型（test/release等）
            
        Returns:
            主题列表
        """
        try:
            url = f"{CRPService.BASE_URL}/topics/search"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            data = {
                "TopicType": topic_type,
                "UserName": username,
                "BranchID": branch_id
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取主题列表失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应内容: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"获取主题列表异常: {str(e)}")
            return []
    
    @staticmethod
    def list_topic_releases(token: str, topic_id: int) -> List[Dict]:
        """
        获取主题下的所有包（releases）
        
        Args:
            token: CRP Token
            topic_id: 主题ID
            
        Returns:
            包列表
        """
        try:
            url = f"{CRPService.BASE_URL}/topics/{topic_id}/releases"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # 格式化返回数据
            releases = []
            for item in result:
                build_state = item.get("BuildState", {})
                releases.append({
                    'id': item.get("ID", 0),
                    'project_id': item.get("ProjectID", 0),
                    'project_name': item.get("ProjectName", ""),
                    'source_pkg_name': item.get("SourcePkgName", ""),
                    'branch': item.get("Branch", ""),
                    'tag': item.get("Tag", ""),
                    'commit': item.get("Commit", ""),
                    'build_id': item.get("BuildID", 0),
                    'build_state': build_state.get("state", "UNKNOWN"),
                    'arches': item.get("Arches", ""),
                })
            
            return releases
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取主题包列表失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应内容: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"获取主题包列表异常: {str(e)}")
            return []
    
    @staticmethod
    def delete_release(token: str, release_id: int) -> bool:
        """
        放弃一个包（删除release）
        
        Args:
            token: CRP Token
            release_id: Release ID
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            url = f"{CRPService.BASE_URL}/topic_releases/{release_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.delete(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            logger.info(f"成功删除release: {release_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"删除release失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应内容: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"删除release异常: {str(e)}")
            return False
    
    @staticmethod
    def retry_build(token: str, release_id: int) -> bool:
        """
        重试构建一个包
        
        Args:
            token: CRP Token
            release_id: Release ID
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            url = f"{CRPService.BASE_URL}/topic_releases/{release_id}/retry"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            logger.info(f"成功触发重试构建: {release_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"重试构建失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应内容: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"重试构建异常: {str(e)}")
            return False
    
    @staticmethod
    def get_build_state_info(state: str) -> Dict[str, str]:
        """
        获取构建状态的显示信息
        
        Args:
            state: 构建状态
            
        Returns:
            包含label(显示文本)和badge_class(Bootstrap类名)的字典
        """
        state_upper = str(state).upper()
        
        state_map = {
            'UPLOAD_OK': {'label': '构建成功', 'badge_class': 'bg-success'},
            'SUCCESS': {'label': '成功', 'badge_class': 'bg-success'},
            'OK': {'label': '成功', 'badge_class': 'bg-success'},
            'UPLOAD_GIVEUP': {'label': '已放弃', 'badge_class': 'bg-danger'},
            'APPLY_FAILED': {'label': '申请失败', 'badge_class': 'bg-danger'},
            'APPLYING': {'label': '申请中', 'badge_class': 'bg-warning'},
            'UPLOADING': {'label': '上传中', 'badge_class': 'bg-warning'},
            'UNKNOWN': {'label': '未知', 'badge_class': 'bg-secondary'},
        }
        
        return state_map.get(state_upper, {
            'label': state,
            'badge_class': 'bg-secondary'
        })

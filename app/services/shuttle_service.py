"""Shuttle 构建平台服务 - 获取构建日志"""
import requests
import logging
from typing import Optional, Dict
from app.models import GlobalConfig
from app.services.crp_service import CRPService

logger = logging.getLogger(__name__)

SHUTTLE_BASE_URL = "https://shuttle.uniontech.com/api/shuttle"


class ShuttleService:
    """Shuttle 构建平台服务"""

    _token = None

    @classmethod
    def get_token(cls) -> Optional[str]:
        """获取 shuttle token，复用 CRP 的加密密码"""
        if cls._token:
            return cls._token

        config = GlobalConfig.get_config()
        if not config.ldap_username or not config.ldap_password:
            logger.error("LDAP 账号密码未配置")
            return None

        try:
            encrypted_pwd = CRPService.encrypt_password(config.ldap_password)
            url = f"{SHUTTLE_BASE_URL}/user/login"
            resp = requests.post(
                url,
                json={"userName": config.ldap_username, "password": encrypted_pwd},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.error(f"Shuttle 登录失败: {result.get('message')}")
                return None

            cls._token = result["data"]["token"]
            logger.info("Shuttle 登录成功")
            return cls._token

        except Exception as e:
            logger.exception(f"Shuttle 登录异常: {e}")
            return None

    @classmethod
    def clear_token(cls):
        """清除缓存的 token"""
        cls._token = None

    @classmethod
    def get_job_info(cls, job_id: int) -> Optional[Dict]:
        """获取构建任务详情"""
        token = cls.get_token()
        if not token:
            return None

        try:
            url = f"{SHUTTLE_BASE_URL}/job/info"
            resp = requests.get(
                url,
                params={"jobid": job_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.warning(f"获取 job 信息失败: {result.get('message')}")
                cls._token = None
                return None

            return result["data"]

        except Exception as e:
            logger.exception(f"获取 job 信息异常: {e}")
            return None

    @classmethod
    def get_job_log(cls, job_id: int) -> Optional[str]:
        """获取构建任务完整日志"""
        token = cls.get_token()
        if not token:
            return None

        try:
            url = f"{SHUTTLE_BASE_URL}/job/log"
            resp = requests.get(
                url,
                params={"jobid": job_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.warning(f"获取 job 日志失败: {result.get('message')}")
                cls._token = None
                return None

            return result.get("data", "")

        except Exception as e:
            logger.exception(f"获取 job 日志异常: {e}")
            return None

    @classmethod
    def get_build_url(cls, job_id: int) -> str:
        """生成 shuttle 构建详情页面链接"""
        return f"https://shuttle.uniontech.com/#/details/build?jobId={job_id}"

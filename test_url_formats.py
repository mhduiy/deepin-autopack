#!/usr/bin/env python3
"""测试各种 Gitiles URL 格式"""

import sys
sys.path.insert(0, '/home/uos/Dev/deepin-autopack-1')

import requests
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app import create_app
from app.models import GlobalConfig

app = create_app()
with app.app_context():
    config = GlobalConfig.get_config()
    
    session = requests.Session()
    session.auth = HTTPBasicAuth(config.ldap_username, config.ldap_password)
    
    base = "https://gerrit.uniontech.com"
    project = "snipe/dde-control-center"
    commit = "7208010ff6bde2894ac669e90731edbf135855be"
    
    urls_to_test = [
        f"{base}/plugins/gitiles/{project}/+/{commit}?format=JSON",
        f"{base}/plugins/gitiles/{project}/+/{commit}",
        f"{base}/gitweb?p={project}.git;a=commitdiff;h={commit}",
        f"{base}/projects/{project}/commits/{commit}",
        # 直接用 gitiles 浏览器的 URL
        f"https://gerrit.uniontech.com/plugins/gitiles/snipe/dde-control-center/+/refs/heads/upstream/master",
    ]
    
    for url in urls_to_test:
        print(f"\n测试: {url}")
        try:
            resp = session.get(url, verify=False, timeout=5)
            print(f"  状态码: {resp.status_code}")
            if resp.status_code == 200:
                print(f"  ✓ 成功! 内容长度: {len(resp.text)}")
                print(f"  前200字符: {resp.text[:200]}")
        except Exception as e:
            print(f"  ✗ 异常: {e}")

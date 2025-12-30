#!/usr/bin/env python3
"""直接测试 Gitiles API"""

import sys
sys.path.insert(0, '/home/uos/Dev/deepin-autopack-1')

import requests
from requests.auth import HTTPBasicAuth
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 从数据库读取配置
from app import create_app
from app.models import GlobalConfig, Project

app = create_app()
with app.app_context():
    config = GlobalConfig.get_config()
    project = Project.query.first()
    
    if not config:
        print("错误: 未找到全局配置")
        sys.exit(1)
    
    # 配置
    base_url = "https://gerrit.uniontech.com"
    project_name = "snipe/dde-control-center"
    commit_hash = project.last_commit_hash if project else "7208010ff6bde2894ac669e90731edbf135855be"
    username = config.ldap_username
    password = config.ldap_password

    # 创建 session
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)

    # 创建 session
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)

    # 测试 Gitiles API
    url = f"{base_url}/plugins/gitiles/{project_name}/+/{commit_hash}?format=JSON"
    print(f"测试 URL: {url}\n")

    try:
        resp = session.get(url, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            text = resp.text.strip()
            print(f"\n原始响应 (前500字符):\n{text[:500]}\n")
            
            # 去除 )]}'  前缀
            if text.startswith(")]}'"):
                text = text[4:].strip()
            
            data = json.loads(text)
            
            print(f"✓ 成功获取 commit 信息!")
            print(f"\nCommit Message:")
            print(f"{data.get('message', 'N/A')}")
            print(f"\nAuthor: {data.get('author', {}).get('name', 'N/A')} <{data.get('author', {}).get('email', 'N/A')}>")
            print(f"Date: {data.get('committer', {}).get('time', 'N/A')}")
            
            # 提取第一行作为 subject
            message = data.get('message', '')
            subject = message.split('\n')[0] if message else ''
            print(f"\nSubject (第一行): {subject}")
        else:
            print(f"✗ 失败")
            print(f"响应内容: {resp.text[:500]}")
            
    except Exception as e:
        print(f"✗ 异常: {e}")
        import traceback
        traceback.print_exc()

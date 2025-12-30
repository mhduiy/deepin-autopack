#!/usr/bin/env python3
"""测试 Gerrit API 调用"""

import requests
from requests.auth import HTTPBasicAuth
import json
import sys

# 禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_gerrit_api(base_url, username, password, project_name, commit_hash):
    """测试 Gerrit API"""
    
    print(f"\n{'='*60}")
    print(f"测试配置:")
    print(f"  Base URL: {base_url}")
    print(f"  Project: {project_name}")
    print(f"  Commit: {commit_hash}")
    print(f"  Username: {username}")
    print(f"{'='*60}\n")
    
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    
    # 测试1: 直接用 commit hash 查询 change detail
    print("测试 1: GET /a/changes/{commit}/detail")
    url1 = f"{base_url}/a/changes/{commit_hash}/detail"
    print(f"URL: {url1}")
    try:
        resp = session.get(url1, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 成功!")
            print(f"Subject: {data.get('subject', 'N/A')}")
            return
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")
    
    # 测试2: 搜索该 commit
    print(f"\n测试 2: GET /a/changes/?q=commit:{commit_hash}")
    url2 = f"{base_url}/a/changes/?q=commit:{commit_hash}"
    print(f"URL: {url2}")
    try:
        resp = session.get(url2, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 成功! 找到 {len(data)} 条结果")
            if data:
                print(f"第一条: {data[0].get('subject', 'N/A')}")
                print(f"完整数据: {json.dumps(data[0], indent=2, ensure_ascii=False)}")
            return
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")
    
    # 测试3: 搜索项目+分支的最新提交
    print(f"\n测试 3: GET /a/changes/?q=project:{project_name}")
    url3 = f"{base_url}/a/changes/?q=project:{requests.utils.quote(project_name)}"
    print(f"URL: {url3}")
    try:
        resp = session.get(url3, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 成功! 找到 {len(data)} 条结果")
            if data:
                print(f"最近的几条提交:")
                for i, change in enumerate(data[:3], 1):
                    print(f"  {i}. {change.get('subject', 'N/A')}")
                    print(f"     Commit: {change.get('current_revision', 'N/A')[:12]}")
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")
    
    # 测试4: 获取项目信息
    print(f"\n测试 4: GET /a/projects/{project_name}")
    url4 = f"{base_url}/a/projects/{requests.utils.quote(project_name, safe='')}"
    print(f"URL: {url4}")
    try:
        resp = session.get(url4, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 项目存在!")
            print(f"项目信息: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")
    
    # 测试5: 通过 Gitiles 直接获取 commit 信息
    print(f"\n测试 5: 通过 Gitiles API 获取 commit 信息")
    # Gitiles API: /projects/{project}/+/{commit}
    url5 = f"{base_url}/plugins/gitiles/{project_name}/+/{commit_hash}?format=JSON"
    print(f"URL: {url5}")
    try:
        resp = session.get(url5, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            # Gitiles 返回可能有 )]}' 前缀
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 成功! 通过 Gitiles 获取到 commit 信息")
            print(f"Commit message: {data.get('message', 'N/A').split('\\n')[0]}")
            print(f"Author: {data.get('author', {}).get('name', 'N/A')}")
            print(f"Date: {data.get('committer', {}).get('time', 'N/A')}")
            return
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")
    
    # 测试6: 获取分支信息
    print(f"\n测试 6: GET /a/projects/{project_name}/branches/upstream%2Fmaster")
    url6 = f"{base_url}/a/projects/{requests.utils.quote(project_name, safe='')}/branches/upstream%2Fmaster"
    print(f"URL: {url6}")
    try:
        resp = session.get(url6, verify=False, timeout=10)
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            if text.startswith(")]}'"):
                text = text[4:].strip()
            data = json.loads(text)
            print(f"✓ 分支信息获取成功!")
            print(f"最新 revision: {data.get('revision', 'N/A')}")
        else:
            print(f"✗ 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"✗ 异常: {e}")


if __name__ == '__main__':
    # 从数据库读取配置
    import sys
    sys.path.insert(0, '/home/uos/Dev/deepin-autopack-1')
    
    from app import create_app, db
    from app.models import GlobalConfig, Project
    
    app = create_app()
    with app.app_context():
        config = GlobalConfig.get_config()
        project = Project.query.first()
        
        if not config or not config.ldap_username or not config.ldap_password:
            print("错误: 请先配置全局配置（LDAP账号密码）")
            sys.exit(1)
        
        if not project:
            print("错误: 没有找到项目")
            sys.exit(1)
        
        # 从URL中提取base_url和project_name
        gerrit_full_url = project.gerrit_url
        print(f"原始 Gerrit URL: {gerrit_full_url}")
        
        # 处理URL: https://gerrit.uniontech.com/plugins/gitiles/snipe/dde-control-center
        if '/plugins/gitiles/' in gerrit_full_url:
            parts = gerrit_full_url.split('/plugins/gitiles/')
            base_url = parts[0]
            project_name = parts[1] if len(parts) > 1 else ''
            print(f"解析后:")
            print(f"  Base URL: {base_url}")
            print(f"  Project: {project_name}")
        else:
            base_url = gerrit_full_url
            project_name = project.name
        
        test_gerrit_api(
            base_url=base_url,
            username=config.ldap_username,
            password=config.ldap_password,
            project_name=project_name,
            commit_hash=project.last_commit_hash
        )

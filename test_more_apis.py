#!/usr/bin/env python3
"""测试更多获取 commit 信息的方法"""

import sys
sys.path.insert(0, '/home/uos/Dev/deepin-autopack-1')

import requests
from requests.auth import HTTPBasicAuth
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app import create_app
from app.models import GlobalConfig, Project

app = create_app()
with app.app_context():
    config = GlobalConfig.get_config()
    project = Project.query.first()
    
    session = requests.Session()
    session.auth = HTTPBasicAuth(config.ldap_username, config.ldap_password)
    
    base = "https://gerrit.uniontech.com"
    proj = "snipe/dde-control-center"
    commit = "7208010ff6bde2894ac669e90731edbf135855be"
    branch = "upstream/master"
    
    tests = [
        # 1. Git REST API - 获取 commit
        ("Git REST API", f"{base}/projects/{requests.utils.quote(proj, safe='')}/commits/{commit}"),
        
        # 2. Gitiles log 格式
        ("Gitiles log", f"{base}/plugins/gitiles/{proj}/+log/{commit}?format=JSON"),
        
        # 3. Gitiles 指定分支的 commit
        ("Gitiles branch commit", f"{base}/plugins/gitiles/{proj}/+/{branch}/{commit}?format=JSON"),
        
        # 4. Gitiles 单个 commit diff
        ("Gitiles commit diff", f"{base}/plugins/gitiles/{proj}/+/{commit}^!/?format=JSON"),
        
        # 5. 使用短 hash
        ("Short hash", f"{base}/plugins/gitiles/{proj}/+/{commit[:12]}?format=JSON"),
        
        # 6. 分支的 commits 列表，然后找对应的
        ("Branch commits", f"{base}/projects/{requests.utils.quote(proj, safe='')}/branches/{requests.utils.quote(branch, safe='')}/commits/{commit}"),
        
        # 7. 直接访问分支 log
        ("Branch log", f"{base}/projects/{requests.utils.quote(proj, safe='')}/+log/{requests.utils.quote(branch, safe='')}?format=JSON&n=10"),
        
        # 8. Gitiles 路径格式测试
        ("Gitiles alt path", f"{base}/plugins/gitiles/{proj}/+show/{commit}?format=JSON"),
    ]
    
    for name, url in tests:
        print(f"\n{'='*70}")
        print(f"测试: {name}")
        print(f"URL: {url}")
        print("="*70)
        
        try:
            resp = session.get(url, verify=False, timeout=10)
            print(f"状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                text = resp.text.strip()
                
                # 去除 Gerrit/Gitiles 前缀
                if text.startswith(")]}'"):
                    text = text[4:].strip()
                
                # 尝试解析 JSON
                try:
                    data = json.loads(text)
                    print(f"✓ 成功获取 JSON 数据!")
                    
                    # 查找可能的 message/subject 字段
                    if 'message' in data:
                        print(f"Message: {data['message'].split(chr(10))[0]}")
                    elif 'subject' in data:
                        print(f"Subject: {data['subject']}")
                    elif 'log' in data and len(data['log']) > 0:
                        print(f"Log 中第一条: {data['log'][0].get('message', '').split(chr(10))[0]}")
                    else:
                        print(f"数据 keys: {list(data.keys())[:10]}")
                        print(f"数据预览: {str(data)[:300]}")
                    
                except json.JSONDecodeError:
                    # 可能是 HTML
                    if '<html' in text.lower():
                        print("返回的是 HTML 页面")
                        if 'commit' in text.lower():
                            print("页面中包含 commit 信息")
                    else:
                        print(f"非 JSON 响应，前300字符: {text[:300]}")
            
            elif resp.status_code == 404:
                print("✗ 404 Not Found")
            else:
                print(f"✗ 状态码 {resp.status_code}")
                print(f"响应: {resp.text[:200]}")
                
        except Exception as e:
            print(f"✗ 异常: {e}")
    
    print(f"\n\n{'='*70}")
    print("总结：寻找能返回 200 且包含 commit message 的 API")
    print("="*70)

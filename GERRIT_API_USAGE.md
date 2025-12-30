# Gerrit API 服务使用文档

## 认证方式

Gerrit 使用 **HTTP Basic Authentication** 进行认证：

```python
from app.services.gerrit_service import create_gerrit_service

# 创建服务实例
gerrit = create_gerrit_service(
    gerrit_url='https://gerrit.uniontech.com',  # Gerrit 服务器地址
    username='your_ldap_username',               # LDAP 账号
    password='your_ldap_password'                # LDAP 密码
)
```

## API 使用示例

### 1. 获取项目信息

```python
# 获取项目基本信息
result = gerrit.get_project_info('deepin-music')
if result['success']:
    project_info = result['data']
    print(f"项目ID: {project_info['id']}")
    print(f"项目状态: {project_info['state']}")
```

### 2. 获取分支列表

```python
# 获取项目所有分支
result = gerrit.get_project_branches('deepin-music')
if result['success']:
    branches = result['data']
    for branch in branches:
        print(f"分支: {branch['ref']}, 最新提交: {branch['revision']}")
```

### 3. 获取分支最新提交

```python
# 获取指定分支的最新提交
result = gerrit.get_latest_commit('deepin-music', 'master')
if result['success']:
    revision = result['data']['revision']
    print(f"最新提交哈希: {revision}")
```

### 4. 搜索提交

```python
# 搜索已合并的提交
result = gerrit.search_changes(
    query='project:deepin-music branch:master status:merged',
    limit=10
)
if result['success']:
    changes = result['data']
    for change in changes:
        print(f"提交: {change['subject']}")
        print(f"作者: {change['owner']['name']}")
        print(f"时间: {change['updated']}")
```

### 5. 获取指定提交之后的所有新提交

```python
# 获取自上次打包以来的所有新提交
result = gerrit.get_commits_between(
    project_name='deepin-music',
    branch='master',
    after_commit='abc123def456'  # 上一次打包的 commit hash
)
if result['success']:
    new_commits = result['data']
    print(f"找到 {len(new_commits)} 个新提交")
    for commit in new_commits:
        print(f"- {commit['subject']}")
```

### 6. 检查代码同步状态

```python
# 检查 Gerrit 是否已同步到指定提交（用于检查 GitHub->Gerrit 的自动同步）
result = gerrit.check_sync_status(
    project_name='deepin-music',
    branch='master',
    expected_commit='xyz789abc123'  # GitHub 的 commit hash
)
if result['success']:
    if result['data']['is_synced']:
        print("代码已同步！")
    else:
        print(f"代码未同步")
        print(f"Gerrit 最新: {result['data']['latest_revision']}")
        print(f"期望提交: {result['data']['expected_commit']}")
```

### 7. 获取提交详情

```python
# 获取单个提交的详细信息
result = gerrit.get_commit_detail('abc123def456')
if result['success']:
    detail = result['data']
    print(f"标题: {detail['subject']}")
    print(f"分支: {detail['branch']}")
    print(f"状态: {detail['status']}")
    print(f"作者: {detail['owner']['name']}")
```

## 返回值格式

所有 API 方法都返回统一格式的字典：

```python
{
    'success': True/False,      # 请求是否成功
    'message': '描述信息',       # 成功或失败的描述
    'data': {...}               # 返回的数据（失败时为 None）
}
```

## 注意事项

1. **认证信息来源**：
   - 使用 LDAP 账号密码
   - 可以从全局配置表中读取

2. **API 端点**：
   - 所有需要认证的 API 都使用 `/a/` 前缀
   - 例如：`https://gerrit.uniontech.com/a/projects/deepin-music`

3. **响应格式**：
   - Gerrit API 返回的 JSON 前面会有 `)]}'` 前缀
   - 服务已自动处理，无需手动去除

4. **SSL 验证**：
   - 内网环境已禁用 SSL 验证（`verify=False`）
   - 生产环境建议启用

5. **查询语法**：
   - Gerrit 使用特殊的查询语法
   - 常用操作符：`project:`, `branch:`, `status:`, `after:`, `before:`
   - 示例：`"project:deepin-music branch:master status:merged"`

## 集成到项目中

在路由中使用：

```python
from app.services.gerrit_service import create_gerrit_service
from app.models import Project

@app.route('/projects/<int:id>/commits')
def get_project_commits(id):
    # 获取项目配置
    project = Project.query.get_or_404(id)
    
    # TODO: 从全局配置获取 LDAP 账号密码
    gerrit = create_gerrit_service(
        project.gerrit_url,
        'username',
        'password'
    )
    
    # 获取新提交
    result = gerrit.get_commits_between(
        project_name=project.name,
        branch=project.gerrit_branch,
        after_commit=project.last_commit_hash
    )
    
    if result['success']:
        return jsonify({
            'commits': result['data']
        })
    else:
        return jsonify({
            'error': result['message']
        }), 500
```

## PHP 对比

该 Python 实现完全基于您提供的 PHP 版本，主要函数对照：

| PHP 函数 | Python 方法 |
|---------|------------|
| `executeGerritRequest()` | `_request()` |
| `getProjectInfo()` | `get_project_info()` |
| `getProjectBranches()` | `get_project_branches()` |
| `getBranchLatestCommit()` | `get_latest_commit()` |
| `searchChanges()` | `search_changes()` |
| `getCommitDetail()` | `get_commit_detail()` |
| `getChangeDetail()` | `get_change_detail()` |

## 其他发现

从 PHP 代码中看到，该文件**只包含 Gerrit API 请求**，没有其他服务的请求（如 GitHub、CRP 等），这些应该在其他文件中实现。

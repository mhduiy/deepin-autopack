# Deepin Autopack OpenClaw Skill 使用指南

## 概述

这是一个为 Deepin Autopack 系统创建的 OpenClaw Skill，让你可以通过自然语言对话来打包 Deepin 项目。

## 安装

### 1. 将 Skill 放到 OpenClaw 的 workspace

```bash
# 复制整个 skills 目录到 OpenClaw workspace
cp -r /home/uos/Dev/deepin-autopack/skills/deepin-autopack ~/.openclaw/workspace/skills/

# 或者创建符号链接
ln -s /home/uos/Dev/deepin-autopack/skills/deepin-autopack ~/.openclaw/workspace/skills/deepin-autopack
```

### 2. 重启 OpenClaw 或刷新 Skills

```bash
# 重启 OpenClaw Gateway
openclaw gateway --restart

# 或者让 AI 刷新 skills
# 在对话中说："刷新 skills" 或 "refresh skills"
```

### 3. 验证 Skill 已加载

```bash
# 列出所有 skills
openclaw skills list

# 查看 deepin-autopack skill 的详情
openclaw skills info deepin-autopack
```

## 使用方法

一旦 Skill 加载成功，你就可以直接通过对话来使用它。以下是一些示例：

### 基础打包

**对话示例：**

```
你: 我要打包 dde-shell

AI: 好的，我来为你打包 dde-shell 项目。

[执行打包...]

✅ 打包任务已创建并启动

📦 项目：dde-shell
🔖 版本：20260307120000
🗂️  CRP仓库：最新CRP仓库
🏗️  架构：amd64, arm64, loong64, sw64, mips64el

🔗 查看进度：http://localhost:5000/build/tasks#123
```

### 带参数打包

```
你: 打包 deepin-music，版本号 6.0.30

AI: 好的，为 deepin-music 打包版本 6.0.30...

[执行打包...]

✅ 打包任务已创建并启动
📦 项目：deepin-music
🔖 版本：6.0.30
...
```

```
你: 打包 dde-control-center，只打 amd64 和 arm64 架构

AI: 好的，为 dde-control-center 打包，架构限定为 amd64 和 arm64...
```

### 查询状态

```
你: 查询任务 123 的状态

AI: 好的，查询任务 123 的状态...

📊 任务状态

🆔 任务ID：123
📦 项目：dde-shell
🔖 版本：20260307120000
📈 状态：running
🔄 当前步骤：创建PR

🔗 GitHub PR：https://github.com/linuxdeepin/dde-shell/pull/456
🌐 查看详情：http://localhost:5000/build/tasks#123
```

### 查看可用项目

```
你: 有哪些项目可以打包？

AI: 让我查看一下可用的项目...

📦 可打包的项目列表：

• dde-shell
  仓库：https://github.com/linuxdeepin/dde-shell
  分支：master

• deepin-music
  仓库：https://github.com/linuxdeepin/deepin-music
  分支：master

• dde-control-center
  仓库：https://github.com/linuxdeepin/dde-control-center
  分支：master
```

### 查看 CRP 仓库

```
你: 有哪些 CRP 仓库可用？

AI: 让我查看 CRP 仓库列表...

🗂️  可用的CRP仓库：

1. V26开发仓库
   ID：topic_123
   ⭐ （默认使用）

2. V25稳定仓库
   ID：topic_456

3. 测试仓库
   ID：topic_789
```

### 查看打包历史

```
你: 最近的打包任务有哪些？

AI: 让我查看最近的打包任务...

📋 最近的打包任务：

🆔 125 - dde-shell (20260307150000)
   状态：completed | 完成
   PR：https://github.com/linuxdeepin/dde-shell/pull/458
   详情：http://localhost:5000/build/tasks#125

🆔 124 - deepin-music (6.0.30)
   状态：running | CRP打包
   详情：http://localhost:5000/build/tasks#124

🆔 123 - dde-control-center (6.1.0)
   状态：failed | 创建PR
   详情：http://localhost:5000/build/tasks#123
```

## 对话模式的优势

1. **自然语言**：不需要记忆命令和参数，直接说你的需求
2. **智能理解**：AI 会理解你的意图，自动填充默认值
3. **实时反馈**：即时获得结果和链接
4. **上下文感知**：可以在对话中引用之前的任务

### 示例对话流程

```
你: 我要打包 dde-shell

AI: 好的，已为 dde-shell 创建打包任务 #123
    查看进度：http://localhost:5000/build/tasks#123

你: 这个任务现在怎么样了？

AI: [查询任务 123]
    任务正在执行，当前步骤：创建PR
    状态：running

你: GitHub PR 链接是什么？

AI: [再次查询任务 123]
    GitHub PR：https://github.com/linuxdeepin/dde-shell/pull/456
```

## 技术细节

### Skill 文件结构

```
skills/deepin-autopack/
└── SKILL.md                 # Skill 定义和指令
```

### Skill 的工作原理

1. **触发**：当用户提及"打包"、"dde-shell"等关键词时，AI 会加载这个 skill
2. **执行**：Skill 使用 `curl` 调用 Autopack REST API（`http://localhost:5000/api/v1/`）
3. **响应**：API 返回 JSON，AI 解析并格式化后呈现给用户

### API 端点清单

```
监控组:
  GET  /api/v1/monitor/status    - 系统概览
  GET  /api/v1/monitor/projects  - 项目列表（含提交）
  POST /api/v1/monitor/refresh   - 刷新所有仓库

打包组:
  POST /api/v1/packages/create       - 创建打包任务
  GET  /api/v1/packages/<id>/status  - 查询任务状态
  POST /api/v1/packages/<id>/retry   - 重试失败任务
  GET  /api/v1/packages/list         - 任务列表

工具组:
  GET  /api/v1/projects              - 可用项目
  GET  /api/v1/crp-topics            - CRP 仓库列表
  POST /api/v1/ai/analyze-commits    - AI 分析提交
```

### 自定义配置

如果需要修改 Skill 行为，编辑 `SKILL.md` 文件：

```bash
vim ~/.openclaw/workspace/skills/deepin-autopack/SKILL.md
```

修改后无需重启，AI 会在下次使用时重新加载。

## 常见问题

### Q: Skill 没有被加载？

A: 检查以下几点：
1. 文件路径是否正确：`~/.openclaw/workspace/skills/deepin-autopack/SKILL.md`
2. YAML frontmatter 格式是否正确
3. 尝试重启 OpenClaw：`openclaw gateway --restart`
4. 运行 `openclaw skills list` 查看 skill 是否在列表中

### Q: API 调用失败（Connection Refused）？

A: 确保 Autopack Flask 服务在运行：
```bash
cd /home/uos/Dev/deepin-autopack
/home/uos/.local/venv/bin/python app.py
```

### Q: 如何调试 API？

A: 直接 curl 测试即可：
```bash
curl -s http://localhost:5000/api/v1/monitor/status | python3 -m json.tool
curl -s http://localhost:5000/api/v1/projects | python3 -m json.tool
```

### Q: 可以添加更多 API 吗？

A: 编辑 `app/routes/api_v1.py` 添加新端点，Skill 会自动通过 API 调用。例如:
- 取消打包任务
- 批量打包多个项目
- 导出构建日志

## 高级用法

### 在其他渠道使用

如果你的 OpenClaw 连接了 Telegram、Slack 或其他平台，你可以在任何地方使用这个 skill：

**Telegram 示例：**
```
你: @molty 我要打包 dde-shell
Molty: 好的，已创建打包任务...
```

**Slack 示例：**
```
你: /molty 打包 deepin-music 版本 6.0.30
Molty: ✅ 任务已创建...
```

### 结合其他 Skills

可以和其他 skills 组合使用：

```
你: 打包 dde-shell，完成后发送邮件通知我

AI: [使用 deepin-autopack skill 打包]
    [使用 email skill 发送通知]
```

## 贡献

如果你想改进这个 Skill，欢迎：

1. Fork 项目
2. 修改 `skills/deepin-autopack/SKILL.md`
3. 测试你的修改
4. 提交 Pull Request

## 许可证

与 Deepin Autopack 项目相同

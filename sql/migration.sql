-- 数据库迁移脚本：添加本地仓库相关字段

-- 1. 为 projects 表添加新字段
ALTER TABLE projects ADD COLUMN gerrit_repo_url VARCHAR(200) COMMENT 'Gerrit仓库地址（用于克隆）';
ALTER TABLE projects ADD COLUMN local_repo_path VARCHAR(500) COMMENT '本地仓库路径';
ALTER TABLE projects ADD COLUMN repo_status VARCHAR(20) DEFAULT 'pending' COMMENT '仓库状态: pending/cloning/ready/error';
ALTER TABLE projects ADD COLUMN repo_error TEXT COMMENT '错误信息';

-- 2. 为 global_config 表添加新字段
ALTER TABLE global_config ADD COLUMN https_proxy VARCHAR(200) COMMENT 'HTTPS代理配置';
ALTER TABLE global_config ADD COLUMN local_repos_dir VARCHAR(500) DEFAULT '/tmp/deepin-autopack-repos' COMMENT '本地仓库存储目录';

-- 3. 更新现有项目的状态为 pending
UPDATE projects SET repo_status = 'pending' WHERE repo_status IS NULL;

-- 添加CRP相关配置字段
ALTER TABLE global_config ADD COLUMN crp_branch_id INT COMMENT 'CRP项目分支ID';
ALTER TABLE global_config ADD COLUMN crp_topic_type VARCHAR(50) DEFAULT 'test' COMMENT 'CRP主题类型';

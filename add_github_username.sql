-- 为global_config表添加github_username字段
ALTER TABLE global_config 
ADD COLUMN github_username VARCHAR(100) COMMENT 'GitHub用户名' AFTER maintainer_email;

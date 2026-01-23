-- 添加 crp_topic_name 字段到 build_tasks 表

ALTER TABLE build_tasks ADD COLUMN crp_topic_name VARCHAR(255) COMMENT 'CRP主题名称' AFTER crp_topic_id;

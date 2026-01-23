-- 添加 crp_project_name 字段到 projects 表
ALTER TABLE projects ADD COLUMN crp_project_name VARCHAR(100);

-- 添加注释
COMMENT ON COLUMN projects.crp_project_name IS 'CRP平台上的项目名称，默认为 项目名-v25';

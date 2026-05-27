-- Add AI analysis cache fields to global_config table
ALTER TABLE global_config ADD COLUMN ai_analysis_fingerprint VARCHAR(64) COMMENT '提交分析指纹';
ALTER TABLE global_config ADD COLUMN ai_analysis_result TEXT COMMENT '缓存的AI提交分析结果';

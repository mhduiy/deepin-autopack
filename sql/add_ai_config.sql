-- Add AI config fields to global_config table
ALTER TABLE global_config ADD COLUMN ai_api_url VARCHAR(500) COMMENT 'AI API地址 (OpenAI兼容)';
ALTER TABLE global_config ADD COLUMN ai_api_key VARCHAR(255) COMMENT 'AI API密钥';
ALTER TABLE global_config ADD COLUMN ai_model VARCHAR(100) COMMENT 'AI模型名称';

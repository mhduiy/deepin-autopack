#!/bin/bash
# AI 配置迁移脚本
# 用法: bash sql/migrate_ai_config.sh

DB_NAME="${DB_NAME:-deepin_autopack}"
DB_USER="${DB_USER:-root}"

echo "=== AI 配置字段迁移 ==="
echo "数据库: ${DB_NAME}"
echo "用户: ${DB_USER}"
echo ""

mysql -u "${DB_USER}" "${DB_NAME}" <<SQL
ALTER TABLE global_config ADD COLUMN IF NOT EXISTS ai_api_url VARCHAR(500) COMMENT 'AI API地址 (OpenAI兼容)';
ALTER TABLE global_config ADD COLUMN IF NOT EXISTS ai_api_key VARCHAR(255) COMMENT 'AI API密钥';
ALTER TABLE global_config ADD COLUMN IF NOT EXISTS ai_model VARCHAR(100) COMMENT 'AI模型名称';
SQL

if [ $? -eq 0 ]; then
    echo "迁移完成"
else
    echo "迁移失败，请检查数据库连接"
    exit 1
fi

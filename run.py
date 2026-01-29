from app import create_app
import logging
import os

# 启动时自动取消代理设置
proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]
        print(f"已取消环境变量: {var}")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 设置第三方库的日志级别为WARNING，避免过多输出
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('git').setLevel(logging.WARNING)

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
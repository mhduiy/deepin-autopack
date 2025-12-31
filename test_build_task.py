"""
测试打包任务系统 - 前三个步骤
"""
import requests
import json
import time

BASE_URL = 'http://localhost:5000'

def test_create_and_run_task():
    """测试创建并运行任务"""
    
    # 1. 创建任务
    print("=" * 60)
    print("步骤1: 创建打包任务")
    print("=" * 60)
    
    task_data = {
        'project_id': 1,  # 假设项目ID为1，请根据实际情况修改
        'mode': 'normal',
        'version': '1.0.test',
        'architectures': ['amd64'],
        'start_commit_hash': ''
    }
    
    response = requests.post(f'{BASE_URL}/api/tasks/create', json=task_data)
    result = response.json()
    
    if not result['success']:
        print(f"❌ 创建任务失败: {result.get('message')}")
        return
    
    task_id = result['task_id']
    print(f"✓ 任务创建成功! ID: {task_id}")
    
    # 2. 启动任务
    print("\n" + "=" * 60)
    print("步骤2: 启动任务")
    print("=" * 60)
    
    response = requests.post(f'{BASE_URL}/api/tasks/{task_id}/start')
    result = response.json()
    
    if not result['success']:
        print(f"❌ 启动任务失败: {result.get('message')}")
        return
    
    print(f"✓ 任务已启动!")
    
    # 3. 监控任务执行
    print("\n" + "=" * 60)
    print("步骤3: 监控任务执行")
    print("=" * 60)
    
    max_wait = 120  # 最多等待2分钟
    elapsed = 0
    interval = 2  # 每2秒检查一次
    
    while elapsed < max_wait:
        response = requests.get(f'{BASE_URL}/api/tasks/{task_id}')
        result = response.json()
        
        if not result['success']:
            print(f"❌ 获取任务状态失败: {result.get('message')}")
            break
        
        task = result['data']
        print(f"\n当前状态: {task['status']}, 当前步骤: {task['current_step']}")
        
        # 显示步骤信息
        for step in task['steps']:
            status_icon = {
                'pending': '⏱️',
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'skipped': '⏭️'
            }.get(step['status'], '❓')
            
            print(f"  {status_icon} {step['step_name']} - {step['status']}")
            if step['log_message']:
                # 只显示第一行日志
                first_line = step['log_message'].split('\n')[0]
                print(f"     └─ {first_line}")
            if step.get('error_message'):
                print(f"     ⚠️  错误: {step['error_message']}")
        
        # 检查是否完成
        if task['status'] in ['success', 'failed', 'cancelled']:
            print(f"\n{'='*60}")
            print(f"任务已结束: {task['status']}")
            if task['error_message']:
                print(f"错误信息: {task['error_message']}")
            print(f"{'='*60}")
            break
        
        time.sleep(interval)
        elapsed += interval
    
    if elapsed >= max_wait:
        print(f"\n⏱️  监控超时（{max_wait}秒）")

if __name__ == '__main__':
    print("\n🚀 开始测试打包任务系统\n")
    test_create_and_run_task()
    print("\n✨ 测试完成!\n")

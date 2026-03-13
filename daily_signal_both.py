# 同时运行原始版和稳健版策略

import subprocess
import sys

print("="*50)
print("📊 ETF轮动策略日报")
print("="*50)
print()

# 运行原始版
print("【原始版策略】")
print("-"*50)
result = subprocess.run([sys.executable, 'daily_signal_enhanced.py'],
                       capture_output=True, text=True)
print(result.stdout)

print()
print("="*50)
print()

# 运行稳健版
print("【稳健版策略】")
print("-"*50)
result = subprocess.run([sys.executable, 'daily_signal_stable.py'],
                       capture_output=True, text=True)
print(result.stdout)

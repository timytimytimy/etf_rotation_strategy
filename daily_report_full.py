# 每日财经早报 + ETF轮动信号
# 整合新闻和策略信号

import subprocess
import sys
from datetime import datetime

def print_header(title):
    print("="*50)
    print(title)
    print("="*50)
    print()

print_header(f"📈 ETF轮动策略日报 [{datetime.now().strftime('%Y-%m-%d')}]")

# 早间财经快报
print("📰 **早间财经快报**")
print("-"*50)

# 获取美股昨晚表现
try:
    import akshare as ak
    # 纳指期货
    print("【外盘表现】")
    print("• 纳斯达克: 请查看东方财富/同花顺APP获取最新数据")
    print("• 标普500: 请查看东方财富/同花顺APP获取最新数据")
    print("• 黄金: 请查看东方财富/同花顺APP获取最新数据")
except Exception as e:
    print(f"获取外盘数据失败: {e}")

print()

# 重要财经日历提醒
print("【今日关注】")
today = datetime.now()
weekday = today.weekday()
if weekday == 0:  # 周一
    print("• 周一开盘，关注周末消息面影响")
elif weekday == 1:  # 周二
    print("• 关注美联储官员讲话")
elif weekday == 2:  # 周三
    print("• 关注美国ADP就业数据(如有)")
elif weekday == 3:  # 周四
    print("• 关注美国初请失业金人数")
elif weekday == 4:  # 周五
    print("• 周末前注意仓位控制")
    print("• 关注非农数据(每月第一个周五)")

print()

# ETF相关新闻提醒
print("【ETF相关提醒】")
print("• 红利ETF: 关注银行、煤炭等高分红板块走势")
print("• 创业板ETF: 关注新能源、医药板块走势")
print("• 纳指ETF: 关注美股科技股、AI板块走势")
print("• 黄金ETF: 关注美元指数、美联储政策、地缘政治")

print()
print("="*50)
print()

# 原始版策略
print("【原始版策略】激进型")
print("-"*50)
result = subprocess.run([sys.executable, 'daily_signal_enhanced.py'],
                       capture_output=True, text=True)
print(result.stdout)

print("="*50)
print()

# 稳健版策略
print("【稳健版策略】推荐")
print("-"*50)
result = subprocess.run([sys.executable, 'daily_signal_stable.py'],
                       capture_output=True, text=True)
print(result.stdout)

# 操作建议
print()
print("="*50)
print("💡 **今日操作建议**")
print("-"*50)
print("1. 建议主要参考【稳健版】信号")
print("2. 14:50左右根据信号调仓")
print("3. 如有重大新闻，请先评估影响再操作")
print("4. 仓位控制: 稳健版已预留20%现金")

# 每日完整ETF轮动日报（三版本）
# 原始版 + 稳健版 + 进阶稳健版

import subprocess
import sys
from datetime import datetime

def run_script(script_name):
    result = subprocess.run([sys.executable, script_name],
                           capture_output=True, text=True)
    return result.stdout

print("="*60)
print(f"📈 ETF轮动策略日报 [{datetime.now().strftime('%Y-%m-%d')}]")
print("="*60)
print()

# 早间财经快报
print("📰 **早间财经快报**")
print("-"*60)
print()

# 今日关注
weekday = datetime.now().weekday()
focus_items = {
    0: ["周一开盘，关注周末消息面影响", "注意可能的方向性选择"],
    1: ["关注美联储官员讲话", "关注通胀预期数据"],
    2: ["关注美国ADP就业数据(如有)", "关注周三小非农"],
    3: ["关注美国初请失业金人数", "关注欧央行政策动向"],
    4: ["周末前注意仓位控制", "关注非农数据(每月第一个周五)"]
}

print("【今日关注】")
for item in focus_items.get(weekday, []):
    print(f"• {item}")

print()
print("【ETF相关关注】")
print("• 红利ETF → 关注银行、煤炭、电力板块")
print("• 创业板ETF → 关注新能源、医药、科技")
print("• 纳指ETF → 关注美股科技、AI板块")
print("• 黄金ETF → 关注美元、美联储政策、地缘政治")
print()

print("="*60)
print()

# 进阶稳健版（推荐）
print("🚀 【进阶稳健版】★★★ 推荐")
print("-"*60)
print(run_script('daily_signal_advanced.py'))

print()
print("="*60)
print()

# 稳健版
print("🛡️ 【稳健版】")
print("-"*60)
print(run_script('daily_signal_stable.py'))

print()
print("="*60)
print()

# 原始版
print("📊 【原始版】激进型")
print("-"*60)
print(run_script('daily_signal_enhanced.py'))

# 操作建议
print()
print("="*60)
print("💡 **今日操作建议**")
print("-"*60)
print("1. ⭐ 推荐使用【进阶稳健版】信号")
print("2. 该版本增加了择时模块，可自动规避大熊市")
print("3. 14:50左右根据信号调仓")
print("4. 严格执行止损纪律")
print("5. 保持20%现金应对突发情况")
print()
print("="*60)

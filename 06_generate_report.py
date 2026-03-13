# 生成完整回测报告和可视化
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import quantstats as qs
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载三个策略的结果
v1 = pd.read_csv('strategy_v1_result.csv', index_col=0, parse_dates=True)
v2 = pd.read_csv('strategy_v2_result.csv', index_col=0, parse_dates=True)
v3 = pd.read_csv('strategy_v3_result.csv', index_col=0, parse_dates=True)

# 计算绩效指标
def calc_metrics(data, col='轮动策略净值'):
    returns = data['轮动策略日收益率']
    nav = data[col]
    
    # 年化收益率
    years = len(data) / 252
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1/years) - 1
    
    # 年化波动率
    ann_vol = returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe = (cagr - 0.02) / ann_vol  # 假设无风险利率2%
    
    # 最大回撤
    cummax = nav.cummax()
    drawdown = (nav - cummax) / cummax
    max_dd = drawdown.min()
    
    # 卡尔玛比率
    calmar = cagr / abs(max_dd)
    
    # 胜率
    win_rate = (returns > 0).sum() / len(returns)
    
    return {
        '累计收益': f'{(nav.iloc[-1]-1)*100:.2f}%',
        '年化收益': f'{cagr*100:.2f}%',
        '年化波动': f'{ann_vol*100:.2f}%',
        '夏普比率': f'{sharpe:.2f}',
        '最大回撤': f'{max_dd*100:.2f}%',
        '卡尔玛': f'{calmar:.2f}',
        '胜率': f'{win_rate*100:.2f}%'
    }

print('='*60)
print('ETF轮动策略回测报告')
print('='*60)

print('\n【原始策略】候选池：沪深300+中证500+红利+创业板')
m1 = calc_metrics(v1)
for k, v in m1.items():
    print(f'  {k}: {v}')

print('\n【改进策略1】候选池：红利+创业板+纳指+黄金')
m2 = calc_metrics(v2)
for k, v in m2.items():
    print(f'  {k}: {v}')

print('\n【改进策略2】强弱排序：斜率×R²')
m3 = calc_metrics(v3)
for k, v in m3.items():
    print(f'  {k}: {v}')

# 绘制对比图
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. 净值曲线对比
ax1 = axes[0, 0]
ax1.plot(v1.index, v1['轮动策略净值'], label='原始策略', linewidth=1.5)
ax1.plot(v2.index, v2['轮动策略净值'], label='改进策略1', linewidth=1.5)
ax1.plot(v3.index, v3['轮动策略净值'], label='改进策略2', linewidth=2, color='red')
ax1.set_title('三个策略净值对比', fontsize=14)
ax1.set_xlabel('日期')
ax1.set_ylabel('净值')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. 改进策略2与各ETF对比
ax2 = axes[0, 1]
ax2.plot(v3.index, v3['轮动策略净值'], label='轮动策略', linewidth=2, color='red')
for code in ['510880', '159915', '513100', '518880']:
    ax2.plot(v3.index, v3[code+'净值'], '--', label=code, alpha=0.7)
ax2.set_title('改进策略2 vs 各ETF', fontsize=14)
ax2.set_xlabel('日期')
ax2.set_ylabel('净值')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. 回撤曲线
ax3 = axes[1, 0]
for data, name in [(v1, '原始策略'), (v2, '改进策略1'), (v3, '改进策略2')]:
    nav = data['轮动策略净值']
    cummax = nav.cummax()
    dd = (nav - cummax) / cummax * 100
    ax3.fill_between(data.index, dd, 0, label=name, alpha=0.5)
ax3.set_title('回撤曲线对比', fontsize=14)
ax3.set_xlabel('日期')
ax3.set_ylabel('回撤(%)')
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. 年度收益对比
ax4 = axes[1, 1]
def calc_annual_returns(data):
    data['year'] = data.index.year
    annual = data.groupby('year')['轮动策略日收益率'].apply(lambda x: (1+x).prod()-1)
    return annual

years = list(range(2015, 2027))
x = np.arange(len(years))
width = 0.25

a1 = calc_annual_returns(v1)
a2 = calc_annual_returns(v2)
a3 = calc_annual_returns(v3)

ax4.bar(x - width, [a1.get(y, 0)*100 for y in years], width, label='原始策略')
ax4.bar(x, [a2.get(y, 0)*100 for y in years], width, label='改进策略1')
ax4.bar(x + width, [a3.get(y, 0)*100 for y in years], width, label='改进策略2')
ax4.set_xticks(x)
ax4.set_xticklabels(years, rotation=45)
ax4.set_title('年度收益对比', fontsize=14)
ax4.set_xlabel('年份')
ax4.set_ylabel('收益率(%)')
ax4.legend()
ax4.grid(True, alpha=0.3)
ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

plt.tight_layout()
plt.savefig('etf_rotation_report.png', dpi=150, bbox_inches='tight')
print('\n\n图表已保存到 etf_rotation_report.png')

# 生成HTML报告
print('\n正在生成详细HTML报告...')
qs.reports.html(v3['轮动策略日收益率'], 
                benchmark=v3['513100净值'].pct_change().dropna(),
                title='ETF轮动策略改进版回测报告',
                output='etf_rotation_quantstats.html')
print('详细报告已保存到 etf_rotation_quantstats.html')

# 保存汇总表
summary = pd.DataFrame({
    '原始策略': m1,
    '改进策略1': m2,
    '改进策略2': m3
}).T
summary.to_csv('performance_summary.csv')
print('\n绩效汇总表已保存到 performance_summary.csv')
print('\n' + '='*60)
print('回测完成！')
print('='*60)

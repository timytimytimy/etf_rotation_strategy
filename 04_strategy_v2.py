# 改进策略1回测：修改候选池
# 候选池：红利ETF（510880），创业板ETF（159915），纳指ETF（513100），黄金ETF（518880）

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

data = pd.read_csv('etf_prices_v2.csv', index_col=0, parse_dates=True)
code_list = ['510880', '159915', '513100', '518880']

N = 10

for code in code_list:
    data['日收益率_'+code] = data[code] / data[code].shift(1) - 1.0
    data['涨幅_'+code] = data[code] / data[code].shift(N+1) - 1.0

data = data.dropna()

data['信号'] = data[['涨幅_'+v for v in code_list]].idxmax(axis=1).str.replace('涨幅_', '')
data['信号'] = data['信号'].shift(1)
data = data.dropna()

data['轮动策略日收益率'] = data.apply(lambda x: x['日收益率_'+x['信号']], axis=1)
data.loc[data.index[0],'轮动策略日收益率'] = 0.0
data['轮动策略净值'] = (1.0 + data['轮动策略日收益率']).cumprod()

for code in code_list:
    data[code+'净值'] = data[code] / data[code].iloc[0]

print('改进策略1回测完成！')
print(f'回测区间：{data.index[0].strftime("%Y-%m-%d")} 至 {data.index[-1].strftime("%Y-%m-%d")}')
print(f'策略最终净值：{data["轮动策略净值"].iloc[-1]:.4f}')
print(f'累计收益率：{(data["轮动策略净值"].iloc[-1]-1)*100:.2f}%')

# 统计各ETF持有天数
print('\n各ETF持有天数统计：')
signal_counts = data['信号'].value_counts()
for code in code_list:
    if code in signal_counts.index:
        print(f'  {code}: {signal_counts[code]}天 ({signal_counts[code]/len(data)*100:.1f}%)')

data.to_csv('strategy_v2_result.csv')
print('\n结果已保存到 strategy_v2_result.csv')

# 改进策略2：修改强弱排序方式
# 使用斜率×R²作为趋势得分

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

data = pd.read_csv('etf_prices_v2.csv', index_col=0, parse_dates=True)
code_list = ['510880', '159915', '513100', '518880']

# 计算强弱得分
def calculate_score(srs, N=25):
    if srs.shape[0] < N:
        return np.nan
    x = np.arange(1, N+1)
    y = srs.values / srs.values[0]  # 归一化
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    slope = lr.coef_[0]
    r_squared = lr.score(x.reshape(-1, 1), y)
    score = 10000 * slope * r_squared
    return score

N = 25  # 斜率计算长度

for code in code_list:
    data['日收益率_'+code] = data[code] / data[code].shift(1) - 1.0
    data['得分_'+code] = data[code].rolling(N).apply(lambda x: calculate_score(x, N))

data = data.dropna()

# 信号生成（用得分替代涨幅）
data['信号'] = data[['得分_'+v for v in code_list]].idxmax(axis=1).str.replace('得分_', '')
data['信号'] = data['信号'].shift(1)
data = data.dropna()

data['轮动策略日收益率'] = data.apply(lambda x: x['日收益率_'+x['信号']], axis=1)
data.loc[data.index[0],'轮动策略日收益率'] = 0.0
data['轮动策略净值'] = (1.0 + data['轮动策略日收益率']).cumprod()

for code in code_list:
    data[code+'净值'] = data[code] / data[code].iloc[0]

print('改进策略2回测完成！')
print(f'回测区间：{data.index[0].strftime("%Y-%m-%d")} 至 {data.index[-1].strftime("%Y-%m-%d")}')
print(f'策略最终净值：{data["轮动策略净值"].iloc[-1]:.4f}')
print(f'累计收益率：{(data["轮动策略净值"].iloc[-1]-1)*100:.2f}%')

print('\n各ETF持有天数统计：')
signal_counts = data['信号'].value_counts()
for code in code_list:
    if code in signal_counts.index:
        print(f'  {code}: {signal_counts[code]}天 ({signal_counts[code]/len(data)*100:.1f}%)')

data.to_csv('strategy_v3_result.csv')
print('\n结果已保存到 strategy_v3_result.csv')

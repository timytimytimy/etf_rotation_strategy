# 原始策略回测
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 读取数据
data = pd.read_csv('etf_prices.csv', index_col=0, parse_dates=True)
code_list = ['510300', '510500', '510880', '159915']

# 动量长度
N = 10

# 计算每日涨跌幅和N日涨跌幅
for code in code_list:
    data['日收益率_'+code] = data[code] / data[code].shift(1) - 1.0
    data['涨幅_'+code] = data[code] / data[code].shift(N+1) - 1.0

# 去掉缺失值
data = data.dropna()

# 信号生成
data['信号'] = data[['涨幅_'+v for v in code_list]].idxmax(axis=1).str.replace('涨幅_', '')
data['信号'] = data['信号'].shift(1)
data = data.dropna()

# 计算策略收益率
data['轮动策略日收益率'] = data.apply(lambda x: x['日收益率_'+x['信号']], axis=1)
data.loc[data.index[0],'轮动策略日收益率'] = 0.0
data['轮动策略净值'] = (1.0 + data['轮动策略日收益率']).cumprod()

# 计算各ETF净值
for code in code_list:
    data[code+'净值'] = data[code] / data[code].iloc[0]

print('原始策略回测完成！')
print(f'回测区间：{data.index[0].strftime("%Y-%m-%d")} 至 {data.index[-1].strftime("%Y-%m-%d")}')
print(f'总交易日：{len(data)}')
print(f'策略最终净值：{data["轮动策略净值"].iloc[-1]:.4f}')
print(f'累计收益率：{(data["轮动策略净值"].iloc[-1]-1)*100:.2f}%')

# 保存结果
data.to_csv('strategy_v1_result.csv')
print('\n结果已保存到 strategy_v1_result.csv')

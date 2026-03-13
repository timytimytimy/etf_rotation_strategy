# 改进策略1：修改候选池
# 候选池：红利ETF（510880），创业板ETF（159915），纳指ETF（513100），黄金ETF（518880）

import akshare as ak
import pandas as pd
import time

code_list = ['510880', '159915', '513100', '518880']
start_date = '20150101'
end_date = '20260313'

df_list = []
for code in code_list:
    print(f'正在获取[{code}]行情数据...')
    df = ak.fund_etf_hist_em(symbol=code, period='daily', 
        start_date=start_date, end_date=end_date, adjust='hfq')
    df.insert(0, 'code', code)
    df_list.append(df)
    time.sleep(3)

print('数据获取完毕！')

all_df = pd.concat(df_list, ignore_index=True)
data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
data.index = pd.to_datetime(data.index)
data = data.sort_index()

data.to_csv('etf_prices_v2.csv')
print(f'数据已保存，共{len(data)}个交易日')
print(data.head(10))

# 510300：沪深300ETF，代表大盘
# 510500：中证500ETF，代表小盘
# 510880：红利ETF，代表价值
# 159915：创业板ETF，代表成长

code_list = ['510300', '510500', '510880', '159915']
start_date = '20150101'
end_date = '20260313'

# 数据获取
import akshare as ak
import pandas as pd
import time

df_list = []
for code in code_list:
    print(f'正在获取[{code}]行情数据...')
    # adjust：""-不复权、qfq-前复权、hfq-后复权
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

# 保存数据
data.to_csv('etf_prices.csv')
print(f'数据已保存，共{len(data)}个交易日')
print(data.head(10))

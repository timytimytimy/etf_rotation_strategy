# 每日ETF轮动信号计算脚本
# 用于定时任务，每天14:30运行

import akshare as ak
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import time
from datetime import datetime

# 候选池
code_list = ['510880', '159915', '513100', '518880']
code_names = {
    '510880': '红利ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '518880': '黄金ETF'
}

def calculate_score(srs, N=25):
    """计算斜率×R²得分"""
    if srs.shape[0] < N:
        return np.nan
    x = np.arange(1, N+1)
    y = srs.values / srs.values[0]
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    slope = lr.coef_[0]
    r_squared = lr.score(x.reshape(-1, 1), y)
    score = 10000 * slope * r_squared
    return score

def get_latest_signal():
    """获取最新信号"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始获取数据...")

    # 获取最近30天的数据（足够计算25日斜率）
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - pd.Timedelta(days=60)).strftime('%Y%m%d')

    df_list = []
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date=start_date, end_date=end_date, adjust='hfq')
            df.insert(0, 'code', code)
            df_list.append(df)
            time.sleep(1)
        except Exception as e:
            print(f"获取{code}失败: {e}")
            return None

    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    # 计算得分
    N = 25
    scores = {}
    for code in code_list:
        recent = data[code].tail(N)
        if len(recent) == N:
            scores[code] = calculate_score(recent, N)

    if not scores:
        return None

    # 选出得分最高的
    best_code = max(scores, key=scores.get)

    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'signal': best_code,
        'signal_name': code_names[best_code],
        'scores': scores
    }

if __name__ == '__main__':
    result = get_latest_signal()
    if result:
        print(f"\n📊 ETF轮动信号 [{result['date']}]")
        print(f"✅ 今日买入：{result['signal_name']}（{result['signal']}）")
        print(f"\n各ETF得分：")
        for code, score in sorted(result['scores'].items(), key=lambda x: -x[1]):
            print(f"  {code_names[code]}: {score:.2f}")

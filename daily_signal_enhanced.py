# 增强版每日ETF轮动信号
# 包含：信号、涨跌幅、持仓追踪

import akshare as ak
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import time
from datetime import datetime
import json
import os

# 候选池
code_list = ['510880', '159915', '513100', '518880']
code_names = {
    '510880': '红利ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '518880': '黄金ETF'
}

# 持仓追踪文件
TRACK_FILE = 'track_record.json'

def calculate_score(srs, N=25):
    if srs.shape[0] < N:
        return np.nan
    x = np.arange(1, N+1)
    y = srs.values / srs.values[0]
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    slope = lr.coef_[0]
    r_squared = lr.score(x.reshape(-1, 1), y)
    return 10000 * slope * r_squared

def load_track():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r') as f:
            return json.load(f)
    return {
        'start_date': None,
        'current_holding': None,
        'signals': [],
        'simulated_nav': 1.0,
        'daily_returns': []
    }

def save_track(track):
    with open(TRACK_FILE, 'w') as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

def get_latest_signal():
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

    # 计算涨跌幅
    returns = {}
    prices = {}
    for code in code_list:
        prices[code] = float(data[code].iloc[-1])
        if len(data) > 1:
            returns[code] = (data[code].iloc[-1] / data[code].iloc[-2] - 1) * 100
        else:
            returns[code] = 0

    # 计算得分
    N = 25
    scores = {}
    for code in code_list:
        recent = data[code].tail(N)
        if len(recent) == N:
            scores[code] = calculate_score(recent, N)

    best_code = max(scores, key=scores.get)

    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'signal': best_code,
        'signal_name': code_names[best_code],
        'scores': scores,
        'prices': prices,
        'returns': returns
    }

def format_message(result, track):
    msg = f"📊 **ETF轮动信号** [{result['date']}]\n\n"
    msg += f"✅ **今日买入：{result['signal_name']}（{result['signal']}）**\n\n"

    # 涨跌幅表
    msg += "**各ETF今日表现：**\n"
    msg += "| ETF | 代码 | 涨跌 | 得分 |\n"
    msg += "|-----|------|------|------|\n"
    sorted_codes = sorted(result['scores'].items(), key=lambda x: -x[1])
    for code, score in sorted_codes:
        ret = result['returns'][code]
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        marker = " 🔥" if code == result['signal'] else ""
        msg += f"| {code_names[code]}{marker} | {code} | {ret_str} | {score:.1f} |\n"

    # 持仓追踪
    if track['start_date']:
        msg += f"\n---\n📈 **模拟持仓追踪**\n"
        msg += f"- 起始日期：{track['start_date']}\n"
        msg += f"- 当前持有：{code_names.get(track['current_holding'], track['current_holding'])}\n"
        msg += f"- 累计收益：{(track['simulated_nav']-1)*100:.2f}%\n"

        # 最近信号变化
        if len(track['signals']) >= 2:
            recent = track['signals'][-3:]
            msg += f"\n**近期调仓记录：**\n"
            for s in recent:
                msg += f"- {s['date']}: 买入{s['name']}\n"

    msg += "\n💡 *数据仅供参考，不构成投资建议*"

    return msg

if __name__ == '__main__':
    result = get_latest_signal()
    if result:
        track = load_track()

        # 更新追踪记录
        today = result['date']

        if track['start_date'] is None:
            track['start_date'] = today
            track['current_holding'] = result['signal']
            track['signals'].append({
                'date': today,
                'code': result['signal'],
                'name': result['signal_name']
            })
        else:
            # 计算今日收益（用昨天的持仓）
            if track['current_holding'] and track['current_holding'] in result['returns']:
                today_return = result['returns'][track['current_holding']] / 100
                track['simulated_nav'] *= (1 + today_return)
                track['daily_returns'].append({
                    'date': today,
                    'return': today_return
                })

            # 检查是否需要调仓
            if result['signal'] != track['current_holding']:
                track['current_holding'] = result['signal']
                track['signals'].append({
                    'date': today,
                    'code': result['signal'],
                    'name': result['signal_name']
                })

        save_track(track)
        print(format_message(result, track))

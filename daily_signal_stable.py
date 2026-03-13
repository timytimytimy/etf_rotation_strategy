# 稳健版ETF轮动策略
# 特点：双持仓、20%现金、换仓阈值、止损机制

import akshare as ak
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import time
from datetime import datetime
import json
import os

# 候选池（增加货币基金ETF作为避险）
code_list = ['510880', '159915', '513100', '518880', '511880']  # 新增银华日利(货币基金)
code_names = {
    '510880': '红利ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '518880': '黄金ETF',
    '511880': '银华日利(货币)'
}

# 稳健版参数
CASH_RATIO = 0.20          # 现金比例20%
POSITION_RATIO = 0.40      # 每个ETF仓位40%
SWITCH_THRESHOLD = 0.20    # 换仓阈值：新ETF得分需高出20%
STOP_LOSS = 0.08           # 止损线：8%

TRACK_FILE = 'track_record_stable.json'

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
        'holdings': [],  # 当前持有[{'code': xxx, 'buy_price': xxx}]
        'signals': [],
        'simulated_nav': 1.0,
        'daily_returns': [],
        'cash': 0.20  # 初始现金比例
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
            continue

    if not df_list:
        return None

    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')
    # 只保留存在的代码
    available_codes = [c for c in code_list if c in data.columns]
    data = data[available_codes]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    # 计算涨跌幅
    returns = {}
    prices = {}
    for code in available_codes:
        prices[code] = float(data[code].iloc[-1])
        if len(data) > 1:
            returns[code] = (data[code].iloc[-1] / data[code].iloc[-2] - 1) * 100
        else:
            returns[code] = 0

    # 计算得分
    N = 25
    scores = {}
    for code in available_codes:
        recent = data[code].tail(N)
        if len(recent) == N:
            scores[code] = calculate_score(recent, N)

    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'available_codes': available_codes,
        'scores': scores,
        'prices': prices,
        'returns': returns
    }

def decide_holdings(scores, current_holdings, prices):
    """
    稳健版持仓决策：
    1. 选择得分最高的2个ETF
    2. 换仓需要新ETF得分高出20%
    3. 检查止损
    """
    if not scores:
        return current_holdings, []

    sorted_etfs = sorted(scores.items(), key=lambda x: -x[1])
    top2_codes = [sorted_etfs[0][0], sorted_etfs[1][0]] if len(sorted_etfs) >= 2 else [sorted_etfs[0][0]]

    changes = []

    if not current_holdings:
        # 首次建仓
        new_holdings = []
        for code in top2_codes:
            new_holdings.append({
                'code': code,
                'buy_price': prices.get(code, 1),
                'buy_date': datetime.now().strftime('%Y-%m-%d')
            })
        changes.append({'action': '建仓', 'codes': top2_codes})
        return new_holdings, changes

    # 检查止损
    final_holdings = []
    for h in current_holdings:
        code = h['code']
        if code in prices:
            loss = (prices[code] - h['buy_price']) / h['buy_price']
            if loss < -STOP_LOSS:
                # 触发止损
                changes.append({'action': '止损', 'code': code, 'loss': f'{loss*100:.2f}%'})
                continue
        final_holdings.append(h)

    # 检查是否需要换仓
    current_codes = [h['code'] for h in final_holdings]

    for i, (new_code, new_score) in enumerate(sorted_etfs[:2]):
        if new_code not in current_codes:
            # 检查是否有需要替换的持仓
            if len(final_holdings) < 2:
                # 还有空位，直接加入
                final_holdings.append({
                    'code': new_code,
                    'buy_price': prices.get(new_code, 1),
                    'buy_date': datetime.now().strftime('%Y-%m-%d')
                })
                changes.append({'action': '加仓', 'code': new_code})
            else:
                # 检查是否值得换仓
                for j, h in enumerate(final_holdings):
                    old_code = h['code']
                    old_score = scores.get(old_code, 0)

                    # 换仓条件：新ETF得分高出20%
                    if new_score > old_score * (1 + SWITCH_THRESHOLD):
                        changes.append({
                            'action': '换仓',
                            'from': old_code,
                            'to': new_code,
                            'reason': f'得分提升{(new_score/old_score-1)*100:.1f}%'
                        })
                        final_holdings[j] = {
                            'code': new_code,
                            'buy_price': prices.get(new_code, 1),
                            'buy_date': datetime.now().strftime('%Y-%m-%d')
                        }
                        break

    return final_holdings, changes

def format_message(result, track, changes):
    scores = result['scores']
    prices = result['prices']
    returns = result['returns']

    # 持仓代码
    holding_codes = [h['code'] for h in track['holdings']] if track['holdings'] else []

    msg = f"🛡️ **稳健版ETF轮动信号** [{result['date']}]\n\n"

    # 今日持仓
    if holding_codes:
        msg += f"**今日持仓（各40%仓位 + 20%现金）：**\n"
        for code in holding_codes:
            msg += f"- {code_names.get(code, code)}（{code}）\n"
    else:
        msg += f"**今日持仓：等待建仓**\n"

    # 换仓记录
    if changes:
        msg += f"\n**今日调仓：**\n"
        for c in changes:
            if c['action'] == '建仓':
                msg += f"- 📌 {c['action']}：{', '.join([code_names.get(x, x) for x in c['codes']])}\n"
            elif c['action'] == '止损':
                msg += f"- 🛑 {c['action']}：{code_names.get(c['code'], c['code'])}（{c['loss']}）\n"
            elif c['action'] == '换仓':
                msg += f"- 🔄 {c['action']}：{code_names.get(c['from'], c['from'])} → {code_names.get(c['to'], c['to'])}（{c['reason']}）\n"
            else:
                msg += f"- ➕ {c['action']}：{code_names.get(c['code'], c['code'])}\n"

    # 得分排名
    msg += f"\n**各ETF得分排名：**\n"
    msg += "| 排名 | ETF | 得分 | 涨跌 | 状态 |\n"
    msg += "|------|-----|------|------|------|\n"
    sorted_codes = sorted(scores.items(), key=lambda x: -x[1])
    for rank, (code, score) in enumerate(sorted_codes, 1):
        ret = returns.get(code, 0)
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        status = "✅持有" if code in holding_codes else ""
        msg += f"| {rank} | {code_names.get(code, code)} | {score:.1f} | {ret_str} | {status} |\n"

    # 持仓追踪
    if track['start_date']:
        msg += f"\n---\n📈 **模拟持仓追踪**\n"
        msg += f"- 起始日期：{track['start_date']}\n"
        msg += f"- 累计收益：{(track['simulated_nav']-1)*100:.2f}%\n"
        msg += f"- 现金比例：{track['cash']*100:.0f}%\n"

    msg += "\n💡 *稳健版：双持仓+止损+换仓阈值，适合风险厌恶型投资者*"

    return msg

if __name__ == '__main__':
    result = get_latest_signal()
    if result:
        track = load_track()

        # 决策持仓
        current_holdings = track.get('holdings', [])
        new_holdings, changes = decide_holdings(
            result['scores'],
            current_holdings,
            result['prices']
        )

        # 更新追踪
        today = result['date']

        if track['start_date'] is None:
            track['start_date'] = today
            track['holdings'] = new_holdings
            track['signals'].append({
                'date': today,
                'holdings': [{'code': h['code'], 'name': code_names.get(h['code'], h['code'])} for h in new_holdings],
                'changes': changes
            })
        else:
            # 计算今日收益
            daily_return = 0
            for h in track['holdings']:
                if h['code'] in result['returns']:
                    daily_return += result['returns'][h['code']] / 100 * POSITION_RATIO

            track['simulated_nav'] *= (1 + daily_return)
            track['daily_returns'].append({
                'date': today,
                'return': daily_return
            })

            # 更新持仓
            track['holdings'] = new_holdings
            if changes:
                track['signals'].append({
                    'date': today,
                    'holdings': [{'code': h['code'], 'name': code_names.get(h['code'], h['code'])} for h in new_holdings],
                    'changes': changes
                })

        save_track(track)
        print(format_message(result, track, changes))

# v1涨跌幅版 - ETF轮动策略（扩充版）
# 支持14只ETF，覆盖宽基、红利、行业、海外、商品、现金管理

import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime
import json
import os

# =====================📊 候选ETF池====================
# 分类：宽基红利 | 行业成长 | 海外商品 | 现金管理
code_list = [
    # 宽基 & 红利（底仓）
    '510300',  # 沪深300ETF
    '512510',  # 中证500ETF
    '510880',  # 上证红利ETF
    '515080',  # 中证红利ETF
    '159915',  # 创业板ETF
    '588000',  # 科创50ETF
    # 行业 & 成长（定投）
    '515070',  # 人工智能ETF
    '512480',  # 半导体ETF
    '512010',  # 医药ETF
    '513130',  # 恒生科技ETF
    # 海外 & 商品
    '513100',  # 纳指ETF
    '518880',  # 黄金ETF
    # 现金管理（稳）
    '511360',  # 中短债ETF
    '511990',  # 货币ETF
]

code_names = {
    # 宽基 & 红利
    '510300': '沪深300ETF',
    '512510': '中证500ETF',
    '510880': '上证红利ETF',
    '515080': '中证红利ETF',
    '159915': '创业板ETF',
    '588000': '科创50ETF',
    # 行业 & 成长
    '515070': '人工智能ETF',
    '512480': '半导体ETF',
    '512010': '医药ETF',
    '513130': '恒生科技ETF',
    # 海外 & 商品
    '513100': '纳指ETF',
    '518880': '黄金ETF',
    # 现金管理
    '511360': '中短债ETF',
    '511990': '货币ETF',
}

code_category = {
    # 宽基 & 红利
    '510300': '宽基',
    '512510': '宽基',
    '510880': '红利',
    '515080': '红利',
    '159915': '成长',
    '588000': '成长',
    # 行业 & 成长
    '515070': '行业',
    '512480': '行业',
    '512010': '行业',
    '513130': '海外',
    # 海外 & 商品
    '513100': '海外',
    '518880': '商品',
    # 现金管理
    '511360': '现金',
    '511990': '现金',
}

# =====================⚙️ 参数设置====================
N = 25  # 回看天数
TRACK_FILE = 'track_record_expanded.json'

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
    """获取最新信号"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - pd.Timedelta(days=60)).strftime('%Y%m%d')

    df_list = []
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date=start_date, end_date=end_date, adjust='hfq')
            df.insert(0, 'code', code)
            df_list.append(df)
            time.sleep(0.5)
        except Exception as e:
            print(f"获取{code}失败: {e}")
            continue

    if not df_list:
        return None

    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    # 计算今日涨跌
    returns = {}
    prices = {}
    for code in code_list:
        if code in data.columns:
            prices[code] = float(data[code].iloc[-1])
            if len(data) > 1:
                returns[code] = (data[code].iloc[-1] / data[code].iloc[-2] - 1) * 100
            else:
                returns[code] = 0

    # 计算N日涨跌幅（核心因子）
    momentum = {}
    for code in code_list:
        if code in data.columns and len(data) >= N:
            momentum[code] = (data[code].iloc[-1] / data[code].iloc[-N] - 1) * 100
        else:
            momentum[code] = 0

    # 过滤现金管理类（只做参考，不买入）
    investable_codes = [c for c in code_list if code_category.get(c) not in ['现金']]
    
    # 选择涨幅最大的（排除现金类）
    investable_momentum = {k: v for k, v in momentum.items() if k in investable_codes}
    if not investable_momentum:
        return None
        
    best_code = max(investable_momentum, key=investable_momentum.get)

    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'signal': best_code,
        'signal_name': code_names[best_code],
        'category': code_category[best_code],
        'momentum': momentum,
        'prices': prices,
        'returns': returns
    }

def format_message(result, track):
    """格式化输出消息"""
    msg = f"📊 **ETF轮动信号（扩充版）** [{result['date']}]\n\n"
    msg += f"✅ **{result['category']}推荐：{result['signal_name']}（{result['signal']}）**\n\n"

    # 按分类展示
    categories = ['宽基', '红利', '成长', '行业', '海外', '商品', '现金']
    
    for cat in categories:
        cat_codes = [c for c, c_cat in code_category.items() if c_cat == cat and c in result['momentum']]
        if not cat_codes:
            continue
            
        msg += f"**{cat}：**\n"
        sorted_codes = sorted(cat_codes, key=lambda x: -result['momentum'].get(x, 0))
        
        for code in sorted_codes:
            momentum_val = result['momentum'].get(code, 0)
            ret = result['returns'].get(code, 0)
            ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
            momentum_str = f"+{momentum_val:.1f}%" if momentum_val >= 0 else f"{momentum_val:.1f}%"
            
            marker = " 🔥" if code == result['signal'] else ""
            if code_category.get(code) == '现金':
                marker = " 💰"
                
            msg += f"- {code_names[code]}{marker}: 今日{ret_str} / 25日{momentum_str}\n"
        
        msg += "\n"

    # 持仓追踪
    if track['start_date']:
        msg += f"---\n📈 **模拟持仓追踪**\n"
        msg += f"- 起始日期：{track['start_date']}\n"
        msg += f"- 当前持有：{code_names.get(track['current_holding'], track['current_holding'])}\n"
        msg += f"- 累计收益：{(track['simulated_nav']-1)*100:.2f}%\n"

        if len(track['signals']) >= 2:
            recent = track['signals'][-3:]
            msg += f"\n**近期调仓：**\n"
            for s in recent:
                msg += f"- {s['date']}: → {s['name']}\n"

    msg += "\n💡 *现金管理类仅供参考，不参与轮动*"
    msg += "\n💡 *数据仅供参考，不构成投资建议*"

    return msg

if __name__ == '__main__':
    result = get_latest_signal()
    if result:
        track = load_track()
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
            if track['current_holding'] and track['current_holding'] in result['returns']:
                today_return = result['returns'][track['current_holding']] / 100
                track['simulated_nav'] *= (1 + today_return)
                track['daily_returns'].append({
                    'date': today,
                    'return': today_return
                })

            if result['signal'] != track['current_holding']:
                track['current_holding'] = result['signal']
                track['signals'].append({
                    'date': today,
                    'code': result['signal'],
                    'name': result['signal_name']
                })

        save_track(track)
        print(format_message(result, track))
    else:
        print("❌ 获取数据失败")

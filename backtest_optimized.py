# ETF轮动策略 - 优化版
# 优化点：每周调仓 + 止损 + 类别分散

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import json
import time

# 加载配置
CONFIG_FILE = 'etf_config.json'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_backtest(code_list, code_names, code_category, start_date='20210101', end_date='20251231', N=25):
    """运行优化版回测"""
    print(f"📊 ETF轮动策略 - 优化版回测")
    print("="*70)
    print("优化策略：")
    print("  1. 每周调仓（周一），降低交易成本")
    print("  2. 单只止损-5%")
    print("  3. 单类别上限50%")
    print()
    
    # 获取数据
    df_list = []
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date=start_date, end_date=end_date, adjust='hfq')
            df.insert(0, 'code', code)
            df_list.append(df)
            time.sleep(0.3)
        except:
            continue
    
    if not df_list:
        return None
    
    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    
    print(f"数据区间: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"交易日数: {len(data)}")
    print()
    
    # 优化版策略回测
    nav = 1.0
    holdings = []
    last_rebalance = None
    stop_loss_codes = set()
    
    results = []
    
    for i in range(N+1, len(data)):
        date = data.index[i]
        
        # 计算涨跌幅
        momentum = {}
        for code in code_list:
            if code in data.columns:
                momentum[code] = (data[code].iloc[i-1] / data[code].iloc[i-N-1] - 1) * 100
        
        # 判断是否调仓
        should_rebalance = False
        
        # 优化1：每周一调仓
        if date.weekday() == 0:  # 周一
            should_rebalance = True
            stop_loss_codes = set()  # 清空止损标记
        
        # 优化2：止损检查
        if holdings:
            for code in holdings:
                if code in data.columns:
                    daily_ret = data[code].iloc[i] / data[code].iloc[i-1] - 1
                    if daily_ret < -0.05:  # 单日跌超5%
                        stop_loss_codes.add(code)
                        should_rebalance = True
        
        # 执行调仓
        if should_rebalance:
            # 排除止损的ETF
            available = {k: v for k, v in momentum.items() if k not in stop_loss_codes}
            if available:
                sorted_codes = sorted(available.items(), key=lambda x: -x[1])
                
                # 优化3：单类别上限（Top3中每类最多1只）
                holdings = []
                cat_used = {}
                for code, mom in sorted_codes:
                    cat = code_category.get(code, '其他')
                    if cat not in cat_used or cat_used[cat] == 0:
                        holdings.append(code)
                        cat_used[cat] = cat_used.get(cat, 0) + 1
                    if len(holdings) >= 3:
                        break
        
        # 计算收益
        if holdings:
            daily_ret = 0
            for code in holdings:
                if code in data.columns:
                    daily_ret += (data[code].iloc[i] / data[code].iloc[i-1] - 1) / 3
            nav *= (1 + daily_ret)
        
        results.append({'date': date, 'nav': nav, 'holdings': holdings.copy()})
    
    nav_series = pd.DataFrame(results).set_index('date')['nav']
    
    # 计算指标
    total_return = (nav_series.iloc[-1] - 1) * 100
    years = (data.index[-1] - data.index[N]).days / 365
    annual_return = ((nav_series.iloc[-1]) ** (1/years) - 1) * 100
    daily_returns = nav_series.pct_change(fill_method=None).dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    max_dd = ((nav_series / nav_series.cummax()) - 1).min() * 100
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'nav_series': nav_series
    }

if __name__ == '__main__':
    config = load_config()
    code_list = [etf['code'] for etf in config['etf_pool'] if etf.get('enabled', True)]
    code_names = {etf['code']: etf['name'] for etf in config['etf_pool']}
    code_category = {etf['code']: etf['category'] for etf in config['etf_pool']}
    
    result = run_backtest(code_list, code_names, code_category)
    
    if result:
        print("📈 优化版回测结果")
        print("="*70)
        print(f"累计收益率: {result['total_return']:.1f}%")
        print(f"年化收益率: {result['annual_return']:.1f}%")
        print(f"夏普比率: {result['sharpe']:.2f}")
        print(f"最大回撤: {result['max_drawdown']:.1f}%")
        print()
        
        # 年度收益
        print("📅 年度收益")
        print("="*70)
        for year in [2021, 2022, 2023, 2024, 2025]:
            year_data = result['nav_series'][result['nav_series'].index.year == year]
            if len(year_data) > 1:
                year_ret = (year_data.iloc[-1] / year_data.iloc[0] - 1) * 100
                print(f"{year}年: {'+' if year_ret >= 0 else ''}{year_ret:.1f}%")
        
        print()
        print("📊 与原版对比")
        print("="*70)
        print("| 指标 | 原版 | 优化版 |")
        print("|------|------|--------|")
        print(f"| 累计收益 | +78.9% | {'+' if result['total_return'] >= 0 else ''}{result['total_return']:.1f}% |")
        print(f"| 年化收益 | 12.6% | {result['annual_return']:.1f}% |")
        print(f"| 夏普比率 | 0.64 | {result['sharpe']:.2f} |")
        print(f"| 最大回撤 | -25.8% | {result['max_drawdown']:.1f}% |")

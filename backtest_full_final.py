# ETF轮动策略 - 全面优化版
# 优化：凯利仓位 + 多因子排序 + 相关性过滤

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import json
import time

def run_backtest_full(code_list, code_names, code_category, 
                      start_date='20210101', end_date='20260313', N=25):
    """全面优化版回测"""
    print("📊 ETF轮动策略 - 全面优化版回测")
    print("="*70)
    print("优化内容：")
    print("  1. 凯利公式仓位管理")
    print("  2. 多因子排序（动量+波动率+夏普）")
    print("  3. 相关性过滤（相关性<0.7）")
    print("  4. 每周调仓+止损")
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
    
    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    
    print(f"数据区间: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"交易日数: {len(data)}")
    print()
    
    # ===== 计算各ETF历史统计 =====
    print("📈 计算各ETF历史表现...")
    etf_stats = {}
    
    for code in code_list:
        if code not in data.columns:
            continue
        prices = data[code].dropna()
        if len(prices) < 100:
            continue
        
        hold_returns = prices.pct_change(N).dropna()
        wins = hold_returns[hold_returns > 0]
        losses = hold_returns[hold_returns <= 0]
        
        if len(wins) > 5 and len(losses) > 5:
            win_rate = len(wins) / len(hold_returns)
            avg_win = wins.mean() if len(wins) > 0 else 0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 1
            win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1
            
            kelly = (win_rate * win_loss_ratio - (1-win_rate)) / win_loss_ratio
            kelly = max(0.1, min(kelly * 0.5, 0.5))
            
            etf_stats[code] = {
                'win_rate': win_rate,
                'win_loss_ratio': win_loss_ratio,
                'kelly_position': kelly,
                'volatility': prices.pct_change().std() * np.sqrt(252),
                'sharpe': prices.pct_change().mean() / prices.pct_change().std() * np.sqrt(252) if prices.pct_change().std() > 0 else 0
            }
    
    print(f"成功计算 {len(etf_stats)} 只ETF")
    print()
    
    # ===== 回测 =====
    nav = 1.0
    holdings = {}
    stop_loss_codes = set()
    
    results = []
    
    for i in range(N+1, len(data)):
        date = data.index[i]
        
        # 多因子评分
        scores = {}
        for code in code_list:
            if code not in data.columns or code not in etf_stats:
                continue
            
            prices = data[code].iloc[max(0,i-60):i]
            if len(prices) < N:
                continue
            
            momentum = (prices.iloc[-1] / prices.iloc[-N] - 1) * 100
            vol = etf_stats[code]['volatility']
            sharpe = etf_stats[code]['sharpe']
            
            scores[code] = 0.5 * momentum - 0.25 * vol * 5 + 0.25 * sharpe * 10
        
        # 调仓判断
        should_rebalance = False
        
        if date.weekday() == 0:  # 周一
            should_rebalance = True
            stop_loss_codes = set()
        
        # 止损检查
        for code in list(holdings.keys()):
            if code in data.columns:
                daily_ret = data[code].iloc[i] / data[code].iloc[i-1] - 1
                if daily_ret < -0.05:
                    stop_loss_codes.add(code)
                    should_rebalance = True
        
        # 执行调仓
        if should_rebalance or len(holdings) == 0:
            available = {k: v for k, v in scores.items() if k not in stop_loss_codes}
            
            if len(available) > 0:
                sorted_codes = sorted(available.items(), key=lambda x: -x[1])
                
                # 相关性过滤
                selected = []
                for code, score in sorted_codes:
                    if len(selected) >= 3:
                        break
                    
                    if len(selected) == 0:
                        selected.append(code)
                    else:
                        # 检查相关性
                        try:
                            corr_ok = True
                            for sel_code in selected:
                                corr = data[sel_code].iloc[max(0,i-60):i].corr(
                                    data[code].iloc[max(0,i-60):i]
                                )
                                if abs(corr) > 0.7:
                                    corr_ok = False
                                    break
                            
                            if corr_ok:
                                selected.append(code)
                        except:
                            pass
                
                # 凯利仓位
                if len(selected) > 0:
                    holdings = {}
                    total_kelly = sum([etf_stats[c]['kelly_position'] for c in selected if c in etf_stats])
                    
                    for code in selected:
                        if code in etf_stats and total_kelly > 0:
                            w = etf_stats[code]['kelly_position'] / total_kelly
                            holdings[code] = min(w, 0.5)
                    
                    # 归一化
                    total_w = sum(holdings.values())
                    if total_w > 0:
                        holdings = {k: v/total_w for k, v in holdings.items()}
        
        # 计算收益
        daily_ret = 0
        if len(holdings) > 0:
            for code, weight in holdings.items():
                if code in data.columns:
                    try:
                        daily_ret += (data[code].iloc[i] / data[code].iloc[i-1] - 1) * weight
                    except:
                        pass
            nav *= (1 + daily_ret)
        
        results.append({'date': date, 'nav': nav})
    
    nav_series = pd.DataFrame(results).set_index('date')['nav']
    
    # 指标
    total_return = (nav_series.iloc[-1] - 1) * 100
    years = (data.index[-1] - data.index[N]).days / 365
    annual_return = ((nav_series.iloc[-1]) ** (1/years) - 1) * 100
    daily_returns = nav_series.pct_change().dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    max_dd = ((nav_series / nav_series.cummax()) - 1).min() * 100
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'nav_series': nav_series,
        'etf_stats': etf_stats
    }

if __name__ == '__main__':
    with open('etf_config.json', 'r') as f:
        config = json.load(f)
    
    code_list = [etf['code'] for etf in config['etf_pool'] if etf.get('enabled', True)]
    code_names = {etf['code']: etf['name'] for etf in config['etf_pool']}
    code_category = {etf['code']: etf['category'] for etf in config['etf_pool']}
    
    result = run_backtest_full(code_list, code_names, code_category)
    
    print("="*70)
    print("📈 全面优化版回测结果")
    print("="*70)
    print(f"累计收益率: {result['total_return']:.1f}%")
    print(f"年化收益率: {result['annual_return']:.1f}%")
    print(f"夏普比率: {result['sharpe']:.2f}")
    print(f"最大回撤: {result['max_drawdown']:.1f}%")
    print()
    
    print("📅 年度收益")
    print("="*70)
    for year in [2021, 2022, 2023, 2024, 2025, 2026]:
        year_data = result['nav_series'][result['nav_series'].index.year == year]
        if len(year_data) > 1:
            year_ret = (year_data.iloc[-1] / year_data.iloc[0] - 1) * 100
            print(f"{year}年: {'+' if year_ret >= 0 else ''}{year_ret:.1f}%")
    
    print()
    print("📊 ETF凯利仓位")
    print("="*70)
    sorted_stats = sorted(result['etf_stats'].items(), 
                         key=lambda x: -x[1]['kelly_position'])
    for code, stats in sorted_stats[:10]:
        name = code_names.get(code, code)
        print(f"{name}: 胜率{stats['win_rate']*100:.0f}% "
              f"盈亏比{stats['win_loss_ratio']:.2f} "
              f"凯利仓位{stats['kelly_position']*100:.1f}%")
    
    result['nav_series'].to_csv('backtest_full_final.csv')
    print()
    print("✅ 完成")

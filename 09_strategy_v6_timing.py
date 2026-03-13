# 策略v6：斜率×R²核心 + 择时增强
# 保持v3的核心因子不变，增加：
# 1. 市场择时（沪深300均线）
# 2. 动态仓位管理
# 3. 波动率调节

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

code_list = ['510880', '159915', '513100', '518880']
code_names = {
    '510880': '红利ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '518880': '黄金ETF'
}

def calculate_slope_r2(srs, N=25):
    """核心因子：斜率×R²"""
    if len(srs) < N:
        return np.nan
    x = np.arange(1, N+1)
    y = srs.values / srs.values[0]
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    slope = lr.coef_[0]
    r_squared = lr.score(x.reshape(-1, 1), y)
    return 10000 * slope * r_squared

def calculate_market_timing(benchmark_prices):
    """
    市场择时信号
    基于沪深300的均线系统
    返回：1=多头, 0.5=减仓, 0=空仓
    """
    if len(benchmark_prices) < 60:
        return 1.0
    
    ma20 = benchmark_prices.rolling(20).mean().iloc[-1]
    ma60 = benchmark_prices.rolling(60).mean().iloc[-1]
    current = benchmark_prices.iloc[-1]
    
    # 完全多头
    if current > ma20 > ma60:
        return 1.0
    # 减仓信号
    elif current > ma60:
        return 0.7
    # 清仓信号
    elif current < ma60:
        return 0.3  # 保留30%仓位（避免踏空）
    
    return 1.0

def calculate_vol_adjustment(prices, N=20):
    """
    波动率调整
    低波动时期可以加仓，高波动时期减仓
    """
    returns = prices.pct_change().tail(N)
    avg_vol = returns.std().mean() * np.sqrt(252)
    
    if avg_vol < 0.15:
        return 1.2  # 低波动，加仓20%
    elif avg_vol > 0.30:
        return 0.8  # 高波动，减仓20%
    else:
        return 1.0

def run_strategy_v6():
    """运行增强策略v6"""
    print("正在获取数据...")
    
    # 获取ETF数据
    df_list = []
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date='20150101', end_date='20260313', adjust='hfq')
            df = df[['日期', '收盘']].copy()
            df.columns = ['日期', code]
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.set_index('日期')
            df_list.append(df)
        except Exception as e:
            print(f"  {code}获取失败: {e}")
    
    prices = pd.concat(df_list, axis=1).dropna().sort_index()
    
    # 获取沪深300作为择时基准
    try:
        hs300 = ak.fund_etf_hist_em(symbol='510300', period='daily',
            start_date='20150101', end_date='20260313', adjust='hfq')
        hs300 = hs300[['日期', '收盘']].copy()
        hs300['日期'] = pd.to_datetime(hs300['日期'])
        hs300 = hs300.set_index('日期')['收盘']
    except:
        print("无法获取沪深300，使用创业板作为基准")
        hs300 = prices['159915']
    
    print(f"数据区间: {prices.index[0].strftime('%Y-%m-%d')} 至 {prices.index[-1].strftime('%Y-%m-%d')}")
    
    N = 25
    
    # 回测
    results = {
        'v3_base': [],
        'v6_timing': []
    }
    
    print("\n开始回测...")
    
    for i in range(max(N, 60), len(prices) - 1):
        date = prices.index[i]
        hist = prices.iloc[:i+1]
        hist_hs300 = hs300.iloc[:i+1]
        
        # 计算斜率×R²得分
        scores = {}
        for code in code_list:
            srs = hist[code].tail(N)
            scores[code] = calculate_slope_r2(srs, N)
        
        best_code = max(scores.items(), key=lambda x: x[1] if not np.isnan(x[1]) else -np.inf)[0]
        
        # v3: 基础策略
        next_return_v3 = prices[best_code].iloc[i+1] / prices[best_code].iloc[i] - 1
        
        # v6: 择时增强
        timing = calculate_market_timing(hist_hs300)
        vol_adj = calculate_vol_adjustment(hist)
        position = timing * vol_adj
        position = min(max(position, 0), 1.5)  # 限制仓位范围
        
        # 如果择时信号减仓，部分持有现金（收益为0）
        next_return_v6 = next_return_v3 * position
        
        results['v3_base'].append({
            'date': date,
            'signal': best_code,
            'return': next_return_v3,
            'position': 1.0
        })
        
        results['v6_timing'].append({
            'date': date,
            'signal': best_code,
            'return': next_return_v6,
            'position': position
        })
    
    # 计算绩效
    def calc_metrics(result_list, name):
        df = pd.DataFrame(result_list)
        df['cum_return'] = (1 + df['return']).cumprod()
        
        total = df['cum_return'].iloc[-1] - 1
        years = len(df) / 252
        annual = (1 + total) ** (1/years) - 1
        sharpe = df['return'].mean() / df['return'].std() * np.sqrt(252)
        
        running_max = df['cum_return'].cummax()
        drawdown = (df['cum_return'] - running_max) / running_max
        max_dd = drawdown.min()
        
        win_rate = (df['return'] > 0).mean()
        avg_position = df['position'].mean()
        
        return {
            'name': name,
            'total_return': total,
            'annual_return': annual,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'avg_position': avg_position
        }
    
    metrics_v3 = calc_metrics(results['v3_base'], 'v3_基础')
    metrics_v6 = calc_metrics(results['v6_timing'], 'v6_择时增强')
    
    # 输出
    print("\n" + "="*70)
    print("策略对比：v3基础 vs v6择时增强")
    print("="*70)
    print(f"{'指标':<15} {'v3基础':<18} {'v6择时增强':<18} {'变化':<15}")
    print("-"*70)
    
    metric_names = {
        'total_return': '累计收益',
        'annual_return': '年化收益', 
        'sharpe': '夏普比率',
        'max_drawdown': '最大回撤',
        'win_rate': '胜率',
        'avg_position': '平均仓位'
    }
    
    for metric in ['total_return', 'annual_return', 'sharpe', 'max_drawdown', 'win_rate', 'avg_position']:
        v3_val = metrics_v3[metric]
        v6_val = metrics_v6[metric]
        
        if metric in ['total_return', 'annual_return', 'max_drawdown', 'win_rate', 'avg_position']:
            v3_str = f"{v3_val*100:.2f}%"
            v6_str = f"{v6_val*100:.2f}%"
            change = f"{(v6_val-v3_val)*100:+.2f}%"
        else:
            v3_str = f"{v3_val:.2f}"
            v6_str = f"{v6_val:.2f}"
            change = f"{v6_val-v3_val:+.2f}"
        
        print(f"{metric_names[metric]:<15} {v3_str:<18} {v6_str:<18} {change:<15}")
    
    # 保存
    df_v6 = pd.DataFrame(results['v6_timing'])
    df_v6.to_csv('strategy_v6_result.csv', index=False)
    print("\nv6结果已保存到 strategy_v6_result.csv")
    
    return metrics_v3, metrics_v6

if __name__ == '__main__':
    run_strategy_v6()

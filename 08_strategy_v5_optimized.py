# 策略v5：优化版多因子策略
# 专注于技术因子优化：斜率×R² + RSI + MACD + 动量加速
# 调整因子权重，添加自适应机制

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

# ============ 因子计算函数 ============

def calculate_slope_r2(srs, N=25):
    """斜率×R²因子（动量核心）"""
    if len(srs) < N:
        return np.nan
    x = np.arange(1, N+1)
    y = srs.values / srs.values[0]
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    slope = lr.coef_[0]
    r_squared = lr.score(x.reshape(-1, 1), y)
    return 10000 * slope * r_squared

def calculate_rsi(srs, period=14):
    """RSI相对强弱指标"""
    delta = srs.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

def calculate_rsi_score(rsi):
    """RSI得分转换"""
    # RSI 30-70区间：中间值最优，过热/过冷扣分
    if rsi > 70:
        return -(rsi - 70) * 2  # 超买，负分
    elif rsi < 30:
        return -(30 - rsi) * 2  # 超卖，负分
    else:
        return (rsi - 50) * 1.5  # 正常区间，偏离中性得分

def calculate_macd(srs, fast=12, slow=26, signal=9):
    """MACD因子"""
    ema_fast = srs.ewm(span=fast, adjust=False).mean()
    ema_slow = srs.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    # 归一化MACD
    current_price = srs.iloc[-1]
    normalized_macd = (histogram.iloc[-1] / current_price) * 1000 if current_price else 0
    
    # 趋势加速（MACD斜率）
    if len(histogram) >= 5:
        macd_slope = histogram.diff().tail(5).mean()
        momentum = macd_slope / current_price * 10000 if current_price else 0
    else:
        momentum = 0
    
    return normalized_macd, momentum

def calculate_volatility_adjustment(srs, N=20):
    """波动率调整因子"""
    rets = srs.pct_change().tail(N)
    vol = rets.std() * np.sqrt(252)
    # 低波动加分，高波动扣分
    if vol < 0.15:
        return 20  # 低波动，加分
    elif vol > 0.30:
        return -20  # 高波动，扣分
    else:
        return 0

def calculate_momentum_acceleration(srs, short=5, long=20):
    """动量加速因子"""
    ret_short = srs.pct_change(short).iloc[-1]
    ret_long = srs.pct_change(long).iloc[-1]
    
    # 短期动量 vs 长期动量
    acceleration = (ret_short / short) - (ret_long / long)
    return acceleration * 1000

# ============ 多因子综合得分 v2 ============

def calculate_multifactor_score_v2(prices):
    """
    优化版多因子综合得分
    
    因子权重（根据历史表现调整）：
    - 斜率×R²: 50%（核心动量因子，权重最高）
    - RSI: 15%（超买超卖调节）
    - MACD: 20%（趋势确认）
    - 动量加速: 10%（趋势加速信号）
    - 波动率调整: 5%（风险调节）
    """
    N = 25
    scores = {}
    
    for code in prices.columns:
        srs = prices[code]
        
        # 1. 斜率×R²因子 (核心)
        slope_score = calculate_slope_r2(srs.tail(N), N)
        slope_norm = min(max(slope_score / 10, -100), 100) if not np.isnan(slope_score) else 0
        
        # 2. RSI因子
        rsi = calculate_rsi(srs)
        rsi_score = calculate_rsi_score(rsi)
        
        # 3. MACD因子
        macd_score, macd_momentum = calculate_macd(srs)
        macd_norm = min(max(macd_score * 5, -100), 100)
        macd_mom_norm = min(max(macd_momentum * 5, -100), 100)
        
        # 4. 动量加速因子
        accel_score = calculate_momentum_acceleration(srs)
        accel_norm = min(max(accel_score, -100), 100)
        
        # 5. 波动率调整
        vol_adj = calculate_volatility_adjustment(srs)
        
        # 综合得分（加权）
        total_score = (
            slope_norm * 0.50 +
            rsi_score * 0.15 +
            macd_norm * 0.15 +
            macd_mom_norm * 0.05 +
            accel_norm * 0.10 +
            vol_adj * 0.05
        )
        
        scores[code] = {
            'total': total_score,
            'slope': slope_norm,
            'rsi': rsi,
            'macd': macd_norm,
            'accel': accel_norm,
            'vol_adj': vol_adj
        }
    
    return scores

# ============ 对比策略 ============

def run_comparison():
    """运行策略对比"""
    print("正在获取ETF数据...")
    
    code_list = ['510880', '159915', '513100', '518880']
    code_names = {
        '510880': '红利ETF',
        '159915': '创业板ETF',
        '513100': '纳指ETF',
        '518880': '黄金ETF'
    }
    
    # 获取数据
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
    print(f"数据区间: {prices.index[0].strftime('%Y-%m-%d')} 至 {prices.index[-1].strftime('%Y-%m-%d')}")
    
    N = 25
    
    # 策略对比
    results = {
        'v3_slope': [],  # 原始斜率×R²
        'v5_multifactor': []  # 优化多因子
    }
    
    print("\n开始回测对比...")
    
    for i in range(N, len(prices) - 1):
        date = prices.index[i]
        hist = prices.iloc[:i+1]
        
        # v3: 纯斜率×R²
        scores_v3 = {}
        for code in code_list:
            srs = hist[code].tail(N)
            scores_v3[code] = calculate_slope_r2(srs, N)
        best_v3 = max(scores_v3.items(), key=lambda x: x[1] if not np.isnan(x[1]) else -np.inf)[0]
        
        # v5: 优化多因子
        scores_v5 = calculate_multifactor_score_v2(hist.tail(N))
        best_v5 = max(scores_v5.items(), key=lambda x: x[1]['total'])[0]
        
        # 次日收益
        next_return_v3 = prices[best_v3].iloc[i+1] / prices[best_v3].iloc[i] - 1
        next_return_v5 = prices[best_v5].iloc[i+1] / prices[best_v5].iloc[i] - 1
        
        results['v3_slope'].append({
            'date': date,
            'signal': best_v3,
            'return': next_return_v3
        })
        results['v5_multifactor'].append({
            'date': date,
            'signal': best_v5,
            'return': next_return_v5
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
        
        return {
            'name': name,
            'total_return': total,
            'annual_return': annual,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate
        }
    
    metrics_v3 = calc_metrics(results['v3_slope'], 'v3_斜率R²')
    metrics_v5 = calc_metrics(results['v5_multifactor'], 'v5_优化多因子')
    
    # 输出结果
    print("\n" + "="*60)
    print("策略对比结果")
    print("="*60)
    print(f"{'指标':<15} {'v3斜率R²':<15} {'v5优化多因子':<15} {'变化':<15}")
    print("-"*60)
    
    for metric in ['total_return', 'annual_return', 'sharpe', 'max_drawdown', 'win_rate']:
        v3_val = metrics_v3[metric]
        v5_val = metrics_v5[metric]
        
        if metric in ['total_return', 'annual_return']:
            v3_str = f"{v3_val*100:.2f}%"
            v5_str = f"{v5_val*100:.2f}%"
            change = f"{(v5_val-v3_val)*100:+.2f}%"
        elif metric == 'sharpe':
            v3_str = f"{v3_val:.2f}"
            v5_str = f"{v5_val:.2f}"
            change = f"{v5_val-v3_val:+.2f}"
        elif metric == 'max_drawdown':
            v3_str = f"{v3_val*100:.2f}%"
            v5_str = f"{v5_val*100:.2f}%"
            change = f"{(v5_val-v3_val)*100:+.2f}%"
        else:
            v3_str = f"{v3_val*100:.2f}%"
            v5_str = f"{v5_val*100:.2f}%"
            change = f"{(v5_val-v3_val)*100:+.2f}%"
        
        metric_name = {'total_return': '累计收益', 'annual_return': '年化收益', 
                       'sharpe': '夏普比率', 'max_drawdown': '最大回撤', 'win_rate': '胜率'}
        print(f"{metric_name[metric]:<15} {v3_str:<15} {v5_str:<15} {change:<15}")
    
    # v5各ETF持有统计
    print("\nv5各ETF持有天数:")
    df_v5 = pd.DataFrame(results['v5_multifactor'])
    signal_counts = df_v5['signal'].value_counts()
    for code in code_list:
        if code in signal_counts.index:
            pct = signal_counts[code] / len(df_v5) * 100
            print(f"  {code_names[code]}: {signal_counts[code]}天 ({pct:.1f}%)")
    
    # 保存详细结果
    df_v5.to_csv('strategy_v5_result.csv', index=False)
    print("\nv5结果已保存到 strategy_v5_result.csv")
    
    return metrics_v3, metrics_v5

if __name__ == '__main__':
    run_comparison()

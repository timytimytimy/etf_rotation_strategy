# 策略v4：多因子优化版
# 新增因子：RSI + MACD + 北向资金 + 融资余额
# 多因子加权得分系统

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

# ============ 因子计算函数 ============

def calculate_slope_r2(srs, N=25):
    """斜率×R²因子"""
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
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

def calculate_macd(srs, fast=12, slow=26, signal=9):
    """MACD因子：返回MACD柱状图值和趋势信号"""
    ema_fast = srs.ewm(span=fast, adjust=False).mean()
    ema_slow = srs.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    # 归一化MACD（相对于价格）
    current_price = srs.iloc[-1]
    normalized_macd = (histogram.iloc[-1] / current_price) * 1000 if current_price else 0
    
    # 趋势信号：MACD金叉/死叉
    if len(histogram) >= 2:
        trend = 1 if histogram.iloc[-1] > histogram.iloc[-2] else -1
    else:
        trend = 0
    
    return normalized_macd, trend

def get_north_money():
    """获取北向资金数据"""
    try:
        df = ak.stock_hsgt_hist_em(symbol='北向资金')
        if df is not None and len(df) > 0:
            # 使用当日成交净买额
            df = df.tail(30).copy()
            df['净买额'] = pd.to_numeric(df['当日成交净买额'], errors='coerce')
            df = df.dropna(subset=['净买额'])
            if len(df) >= 5:
                recent_5d = df['净买额'].tail(5).sum()
                recent_20d = df['净买额'].tail(20).sum()
                return {
                    'net_5d': recent_5d,
                    'net_20d': recent_20d,
                    'signal': 1 if recent_5d > 0 and recent_20d > 0 else -1 if recent_5d < 0 else 0
                }
    except Exception as e:
        print(f"获取北向资金失败: {e}")
    return {'net_5d': 0, 'net_20d': 0, 'signal': 0}

def get_margin_balance():
    """获取融资余额数据"""
    try:
        # 上交所融资余额
        df = ak.stock_margin_sse(start_date='20250101')
        if df is not None and len(df) > 0:
            recent = df.tail(10)
            if len(recent) >= 5 and '融资余额' in recent.columns:
                trend = recent['融资余额'].diff().tail(5).mean()
                return {
                    'balance': recent['融资余额'].iloc[-1],
                    'trend': trend,
                    'signal': 1 if trend > 0 else -1
                }
    except Exception as e:
        print(f"获取融资余额失败: {e}")
    return {'balance': 0, 'trend': 0, 'signal': 0}

# ============ 多因子综合得分 ============

def calculate_multifactor_score(prices, north_money=None, margin=None):
    """
    多因子综合得分
    
    因子权重：
    - 斜率×R²: 40%
    - RSI: 20%
    - MACD: 20%
    - 资金流向: 20%（北向+融资）
    """
    N = 25
    scores = {}
    
    for code in prices.columns:
        srs = prices[code]
        
        # 1. 斜率×R²因子 (基础动量)
        slope_score = calculate_slope_r2(srs.tail(N), N)
        
        # 2. RSI因子 (超买超卖)
        rsi = calculate_rsi(srs)
        # RSI归一化：50为中性，>50看多，<50看空
        rsi_score = (rsi - 50) * 2  # 范围约-100到+100
        
        # 3. MACD因子 (趋势确认)
        macd_score, macd_trend = calculate_macd(srs)
        
        # 4. 资金流向因子 (仅对A股有效)
        money_score = 0
        if code in ['510880', '159915']:  # 红利ETF、创业板ETF
            if north_money and north_money['signal'] != 0:
                money_score += north_money['signal'] * 50
            if margin and margin['signal'] != 0:
                money_score += margin['signal'] * 50
        
        # 综合得分（加权平均）
        # 先归一化各因子到0-100范围
        slope_norm = min(max(slope_score / 10, -100), 100) if not np.isnan(slope_score) else 0
        rsi_norm = min(max(rsi_score, -100), 100)
        macd_norm = min(max(macd_score * 10, -100), 100)
        
        total_score = (
            slope_norm * 0.4 +
            rsi_norm * 0.2 +
            macd_norm * 0.2 +
            money_score * 0.2
        )
        
        scores[code] = {
            'total': total_score,
            'slope': slope_norm,
            'rsi': rsi_norm,
            'macd': macd_norm,
            'money': money_score,
            'rsi_raw': rsi,
            'macd_trend': macd_trend
        }
    
    return scores

# ============ 主策略 ============

def run_strategy_v4():
    """运行多因子策略v4"""
    print("正在获取ETF数据...")
    
    code_list = ['510880', '159915', '513100', '518880']
    code_names = {
        '510880': '红利ETF',
        '159915': '创业板ETF',
        '513100': '纳指ETF',
        '518880': '黄金ETF'
    }
    
    # 获取ETF价格数据
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
            print(f"  {code_names[code]}: {len(df)}条记录")
        except Exception as e:
            print(f"  {code}获取失败: {e}")
    
    if not df_list:
        print("数据获取失败！")
        return
    
    # 合并数据
    prices = pd.concat(df_list, axis=1).dropna()
    prices = prices.sort_index()
    print(f"\n数据区间: {prices.index[0].strftime('%Y-%m-%d')} 至 {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"共 {len(prices)} 个交易日")
    
    # 获取资金数据
    print("\n正在获取资金流向数据...")
    north_money = get_north_money()
    print(f"  北向资金近5日净流入: {north_money['net_5d']/1e8:.2f}亿")
    print(f"  北向资金近20日净流入: {north_money['net_20d']/1e8:.2f}亿")
    
    margin = get_margin_balance()
    print(f"  融资余额趋势: {margin['trend']/1e8:.2f}亿/日")
    
    # 回测
    print("\n开始回测...")
    N = 25
    results = []
    
    for i in range(N, len(prices) - 1):
        date = prices.index[i]
        hist_prices = prices.iloc[:i+1]
        
        # 计算多因子得分
        scores = calculate_multifactor_score(hist_prices.tail(N), north_money, margin)
        
        # 选择得分最高的ETF
        best_code = max(scores.items(), key=lambda x: x[1]['total'])[0]
        
        # 计算次日收益
        next_date = prices.index[i+1]
        next_return = prices[best_code].iloc[i+1] / prices[best_code].iloc[i] - 1
        
        results.append({
            'date': date,
            'signal': best_code,
            'next_return': next_return,
            'scores': scores
        })
    
    # 计算累计收益
    results_df = pd.DataFrame(results)
    results_df['cum_return'] = (1 + results_df['next_return']).cumprod()
    
    # 统计
    print("\n" + "="*50)
    print("多因子策略v4回测结果")
    print("="*50)
    
    # 年化收益
    total_return = results_df['cum_return'].iloc[-1] - 1
    years = (prices.index[-1] - prices.index[N]).days / 365
    annual_return = (1 + total_return) ** (1/years) - 1
    
    # 夏普比率
    daily_returns = results_df['next_return']
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
    
    # 最大回撤
    cum_returns = results_df['cum_return']
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # 胜率
    win_rate = (results_df['next_return'] > 0).mean()
    
    print(f"累计收益: {total_return*100:.2f}%")
    print(f"年化收益: {annual_return*100:.2f}%")
    print(f"夏普比率: {sharpe:.2f}")
    print(f"最大回撤: {max_drawdown*100:.2f}%")
    print(f"胜率: {win_rate*100:.2f}%")
    
    # 各ETF持有统计
    print("\n各ETF持有天数:")
    signal_counts = results_df['signal'].value_counts()
    for code in code_list:
        if code in signal_counts.index:
            pct = signal_counts[code] / len(results_df) * 100
            print(f"  {code_names[code]}: {signal_counts[code]}天 ({pct:.1f}%)")
    
    # 保存结果
    results_df.to_csv('strategy_v4_result.csv', index=False)
    print("\n结果已保存到 strategy_v4_result.csv")
    
    return results_df

if __name__ == '__main__':
    run_strategy_v4()

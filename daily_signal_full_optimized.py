# ETF轮动策略 - 全面优化版每日信号
# 优化：凯利仓位 + ATR止损 + 多因子排序 + 相关性过滤

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import time

CONFIG_FILE = 'etf_config.json'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_etf_list(config):
    etf_pool = config['etf_pool']
    code_list = []
    code_names = {}
    code_category = {}
    
    for etf in etf_pool:
        if etf.get('enabled', True):
            code_list.append(etf['code'])
            code_names[etf['code']] = etf['name']
            code_category[etf['code']] = etf['category']
    
    return code_list, code_names, code_category

def load_track():
    track_file = 'track_record_full_optimized.json'
    if os.path.exists(track_file):
        with open(track_file, 'r') as f:
            return json.load(f)
    return {
        'start_date': None,
        'holdings': {},
        'signals': [],
        'nav': 1.0,
        'stop_loss_codes': [],
        'etf_stats': {}
    }

def save_track(track):
    with open('track_record_full_optimized.json', 'w') as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

def calculate_atr(high, low, close, window=14):
    """计算ATR"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()
    return atr

def calculate_kelly(win_rate, win_loss_ratio, fraction=0.5):
    """凯利公式"""
    loss_rate = 1 - win_rate
    kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
    kelly = max(0, min(kelly, 1))
    return kelly * fraction

def get_signal(code_list, code_names, code_category, config):
    """获取最新信号"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - pd.Timedelta(days=100)).strftime('%Y%m%d')
    N = config['settings'].get('lookback_days', 25)
    
    # 获取数据
    df_list = []
    ohlc_dict = {}
    
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date=start_date, end_date=end_date, adjust='hfq')
            df.insert(0, 'code', code)
            df_list.append(df)
            
            # OHLC数据
            ohlc_dict[code] = df.copy()
            
            time.sleep(0.5)
        except:
            continue
    
    if not df_list:
        return None
    
    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    
    # 计算ETF统计
    etf_stats = {}
    for code in code_list:
        if code not in data.columns:
            continue
        
        prices = data[code].dropna()
        if len(prices) < N + 20:
            continue
        
        hold_returns = prices.pct_change(N).dropna()
        wins = hold_returns[hold_returns > 0]
        losses = hold_returns[hold_returns <= 0]
        
        if len(wins) > 0 and len(losses) > 0:
            win_rate = len(wins) / len(hold_returns)
            avg_win = wins.mean()
            avg_loss = abs(losses.mean())
            win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1
            kelly_pos = calculate_kelly(win_rate, win_loss_ratio, 0.5)
            
            etf_stats[code] = {
                'win_rate': win_rate,
                'win_loss_ratio': win_loss_ratio,
                'kelly_position': kelly_pos,
                'volatility': prices.pct_change().std() * np.sqrt(252),
                'sharpe': prices.pct_change().mean() / prices.pct_change().std() * np.sqrt(252) if prices.pct_change().std() > 0 else 0
            }
    
    # 计算多因子得分
    scores = {}
    momentum = {}
    returns = {}
    
    for code in code_list:
        if code not in data.columns or code not in etf_stats:
            continue
        
        prices = data[code]
        if len(prices) < N:
            continue
        
        # 动量
        mom = (prices.iloc[-1] / prices.iloc[-N] - 1) * 100
        momentum[code] = mom
        
        # 今日涨跌
        if len(prices) > 1:
            returns[code] = (prices.iloc[-1] / prices.iloc[-2] - 1) * 100
        else:
            returns[code] = 0
        
        # 波动率
        volatility = prices.pct_change().iloc[-20:].std() * np.sqrt(252)
        
        # 夏普
        sharpe = etf_stats[code]['sharpe']
        
        # 综合得分
        scores[code] = 0.4 * mom - 0.3 * volatility * 10 + 0.3 * sharpe * 10
    
    # 加载止损名单
    track = load_track()
    stop_loss_codes = track.get('stop_loss_codes', [])
    
    # 周一重置止损
    if datetime.now().weekday() == 0:
        stop_loss_codes = []
        track['stop_loss_codes'] = []
        save_track(track)
    
    # ATR止损检查
    for code in list(track.get('holdings', {}).keys()):
        if code in ohlc_dict and code in data.columns:
            try:
                ohlc = ohlc_dict[code]
                if len(ohlc) >= 14:
                    atr = calculate_atr(ohlc['最高'], ohlc['最低'], ohlc['收盘'], 14).iloc[-1]
                    current_price = data[code].iloc[-1]
                    prev_price = data[code].iloc[-2]
                    
                    if current_price < prev_price - 2 * atr:
                        stop_loss_codes.append(code)
                        track['stop_loss_codes'] = list(set(stop_loss_codes))
                        save_track(track)
            except:
                pass
    
    # 排除止损ETF
    available = {k: v for k, v in scores.items() if k not in stop_loss_codes}
    
    if not available:
        available = scores
    
    # 排序
    sorted_codes = sorted(available.items(), key=lambda x: -x[1])
    
    # 相关性过滤
    selected = []
    for code, score in sorted_codes:
        if len(selected) == 0:
            selected.append(code)
        else:
            is_low_corr = True
            for sel_code in selected:
                if sel_code in data.columns and code in data.columns:
                    try:
                        corr = data[sel_code].iloc[-N:].corr(data[code].iloc[-N:])
                        if pd.notna(corr) and abs(corr) > 0.7:
                            is_low_corr = False
                            break
                    except:
                        pass
            
            if is_low_corr:
                selected.append(code)
            
            if len(selected) >= 3:
                break
    
    # 凯利仓位
    holdings = {}
    total_kelly = sum([etf_stats[c]['kelly_position'] for c in selected if c in etf_stats])
    
    for code in selected:
        if code in etf_stats:
            kelly_w = etf_stats[code]['kelly_position'] / total_kelly if total_kelly > 0 else 1/3
            kelly_w = min(kelly_w, 0.5)
            holdings[code] = kelly_w
    
    # 归一化
    total_w = sum(holdings.values())
    if total_w > 0:
        holdings = {k: v/total_w for k, v in holdings.items()}
    
    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'weekday': datetime.now().weekday(),
        'holdings': holdings,
        'scores': scores,
        'momentum': momentum,
        'returns': returns,
        'etf_stats': etf_stats,
        'stop_loss_codes': stop_loss_codes,
        'code_names': code_names,
        'code_category': code_category
    }

def format_message(result, track):
    """格式化输出"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekday_names[result['weekday']]
    
    lines = []
    lines.append(f"# 📊 ETF轮动信号（全面优化版）[{result['date']} {weekday}]")
    lines.append("")
    lines.append("## ✅ 今日推荐持仓")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 25日涨跌 | 凯利仓位 |")
    lines.append("|:---:|---------|:----:|---------:|--------:|")
    
    for i, (code, weight) in enumerate(result['holdings'].items(), 1):
        name = result['code_names'].get(code, code)
        cat = result['code_category'].get(code, '其他')
        mom = result['momentum'].get(code, 0)
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        weight_pct = weight * 100
        marker = "🔥" if i == 1 else ""
        lines.append(f"| {i} | {marker}{name} | {cat} | {mom_str} | {weight_pct:.1f}% |")
    
    lines.append("")
    lines.append("## 📈 完整排名")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 今日涨跌 | 25日涨跌 | 综合得分 |")
    lines.append("|:---:|---------|:----:|---------:|---------:|---------:|")
    
    sorted_all = sorted(result['scores'].items(), key=lambda x: -x[1])
    for i, (code, score) in enumerate(sorted_all, 1):
        name = result['code_names'].get(code, code)
        cat = result['code_category'].get(code, '其他')
        ret = result['returns'].get(code, 0)
        mom = result['momentum'].get(code, 0)
        
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        
        marker = ""
        if code in result['holdings']:
            marker = "🔥"
        if code in result['stop_loss_codes']:
            marker = "⚠️止损"
        
        lines.append(f"| {i} | {marker}{name} | {cat} | {ret_str} | {mom_str} | {score:.1f} |")
    
    lines.append("")
    
    # 优化说明
    lines.append("## 🔧 今日优化")
    lines.append("")
    
    if result['weekday'] == 0:
        lines.append("- ✅ **周一调仓日**：重新评估所有ETF，重置止损名单")
    else:
        lines.append("- 📅 非调仓日：维持持仓（除非触发ATR止损）")
    
    if result['stop_loss_codes']:
        stop_names = [result['code_names'].get(c, c) for c in result['stop_loss_codes']]
        lines.append(f"- ⚠️ **止损ETF**：{', '.join(stop_names)}")
    
    lines.append("")
    
    # 持仓追踪
    if track['start_date']:
        lines.append("## 📊 模拟持仓追踪")
        lines.append("")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| 起始日期 | {track['start_date']} |")
        
        holding_strs = []
        for code, weight in track.get('holdings', {}).items():
            name = result['code_names'].get(code, code)
            holding_strs.append(f"{name}({weight*100:.1f}%)")
        lines.append(f"| 当前持有 | {', '.join(holding_strs)} |")
        
        nav_return = (track['nav'] - 1) * 100
        nav_str = f"+{nav_return:.2f}%" if nav_return >= 0 else f"{nav_return:.2f}%"
        lines.append(f"| 累计收益 | **{nav_str}** |")
        lines.append("")
        
        if track['signals']:
            lines.append("**近期调仓：**")
            recent = track['signals'][-3:]
            for s in recent:
                holdings_str = ", ".join([f"{n}({w*100:.0f}%)" for n, w in zip(s.get('names', []), s.get('weights', []))])
                lines.append(f"- {s['date']} → {holdings_str}")
        lines.append("")
    
    lines.append("## 💡 全面优化策略")
    lines.append("")
    lines.append("- **凯利仓位**：根据胜率和盈亏比动态分配仓位")
    lines.append("- **ATR止损**：基于波动率动态止损，避免被震出")
    lines.append("- **多因子排序**：动量(40%) + 低波动(30%) + 夏普(30%)")
    lines.append("- **相关性过滤**：相关性>0.7排除，真正分散风险")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("⚠️ *数据仅供参考，不构成投资建议*")
    
    return "\n".join(lines)

if __name__ == '__main__':
    config = load_config()
    code_list, code_names, code_category = get_etf_list(config)
    
    result = get_signal(code_list, code_names, code_category, config)
    
    if result:
        track = load_track()
        today = result['date']
        
        if track['start_date'] is None:
            track['start_date'] = today
            track['holdings'] = result['holdings']
            track['signals'].append({
                'date': today,
                'names': [code_names.get(c, c) for c in result['holdings'].keys()],
                'weights': list(result['holdings'].values())
            })
        else:
            # 计算收益
            if track.get('holdings'):
                total_ret = 0
                for code, weight in track['holdings'].items():
                    ret = result['returns'].get(code, 0) / 100
                    total_ret += ret * weight
                track['nav'] *= (1 + total_ret)
            
            # 周一调仓
            if result['weekday'] == 0:
                track['holdings'] = result['holdings']
                track['signals'].append({
                    'date': today,
                    'names': [code_names.get(c, c) for c in result['holdings'].keys()],
                    'weights': list(result['holdings'].values())
                })
        
        save_track(track)
        print(format_message(result, track))
    else:
        print("❌ 获取数据失败")

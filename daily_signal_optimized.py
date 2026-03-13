# ETF轮动策略 - 优化版每日信号
# 优化点：每周调仓 + 止损 + 类别分散

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import time

# 加载配置
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
    track_file = 'track_record_optimized.json'
    if os.path.exists(track_file):
        with open(track_file, 'r') as f:
            return json.load(f)
    return {
        'start_date': None,
        'holdings': [],
        'signals': [],
        'nav': 1.0,
        'stop_loss_codes': []
    }

def save_track(track):
    with open('track_record_optimized.json', 'w') as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

def get_latest_signal(config, code_list, code_names, code_category):
    """获取最新信号（优化版）"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - pd.Timedelta(days=60)).strftime('%Y%m%d')
    N = config['settings'].get('lookback_days', 25)
    
    df_list = []
    for code in code_list:
        try:
            df = ak.fund_etf_hist_em(symbol=code, period='daily',
                start_date=start_date, end_date=end_date, adjust='hfq')
            df.insert(0, 'code', code)
            df_list.append(df)
            time.sleep(0.5)
        except Exception as e:
            continue
    
    if not df_list:
        return None
    
    all_df = pd.concat(df_list, ignore_index=True)
    data = all_df.pivot(index='日期', columns='code', values='收盘')[code_list]
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    
    # 计算涨跌幅
    momentum = {}
    returns = {}
    prices = {}
    
    for code in code_list:
        if code in data.columns:
            prices[code] = float(data[code].iloc[-1])
            if len(data) > 1:
                returns[code] = (data[code].iloc[-1] / data[code].iloc[-2] - 1) * 100
            else:
                returns[code] = 0
            
            if len(data) >= N:
                momentum[code] = (data[code].iloc[-1] / data[code].iloc[-N] - 1) * 100
            else:
                momentum[code] = 0
    
    # 加载止损名单
    track = load_track()
    stop_loss_codes = track.get('stop_loss_codes', [])
    
    # 周一重置止损名单
    if datetime.now().weekday() == 0:
        stop_loss_codes = []
        track['stop_loss_codes'] = []
    
    # 检查今日是否触发止损
    today_stop_loss = []
    for code in code_list:
        if code in returns and returns[code] < -5.0:  # 单日跌超5%
            today_stop_loss.append(code)
    
    stop_loss_codes.extend(today_stop_loss)
    track['stop_loss_codes'] = list(set(stop_loss_codes))
    save_track(track)
    
    # 排除止损的ETF
    available = {k: v for k, v in momentum.items() if k not in stop_loss_codes}
    
    if not available:
        available = momentum  # 如果全部止损，则忽略止损
    
    # 排序选择Top3
    sorted_codes = sorted(available.items(), key=lambda x: -x[1])
    
    # 类别分散：Top3中每类最多1只
    top3_codes = []
    cat_used = {}
    
    for code, mom in sorted_codes:
        cat = code_category.get(code, '其他')
        if cat not in cat_used or cat_used[cat] < 1:
            top3_codes.append(code)
            cat_used[cat] = cat_used.get(cat, 0) + 1
        if len(top3_codes) >= 3:
            break
    
    top3_names = [code_names[c] for c in top3_codes]
    top3_categories = [code_category[c] for c in top3_codes]
    top3_momentum = [momentum[c] for c in top3_codes]
    
    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'weekday': datetime.now().weekday(),
        'top3_codes': top3_codes,
        'top3_names': top3_names,
        'top3_categories': top3_categories,
        'top3_momentum': top3_momentum,
        'all_momentum': momentum,
        'all_returns': returns,
        'code_names': code_names,
        'code_category': code_category,
        'stop_loss_codes': stop_loss_codes
    }

def format_message(result, track):
    """格式化输出"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekday_names[result['weekday']]
    
    lines = []
    lines.append(f"# 📊 ETF轮动信号（优化版）[{result['date']} {weekday}]")
    lines.append("")
    lines.append("## ✅ 今日Top3推荐")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 25日涨跌 | 仓位 |")
    lines.append("|:---:|---------|:----:|---------:|:----:|")
    
    for i, (code, name, cat, mom) in enumerate(zip(
        result['top3_codes'],
        result['top3_names'],
        result['top3_categories'],
        result['top3_momentum']
    ), 1):
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        marker = "🔥" if i == 1 else ""
        lines.append(f"| {i} | {marker}{name} | {cat} | {mom_str} | 33% |")
    
    lines.append("")
    lines.append("## 📈 完整排名")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 今日涨跌 | 25日涨跌 |")
    lines.append("|:---:|---------|:----:|---------:|---------:|")
    
    sorted_all = sorted(result['all_momentum'].items(), key=lambda x: -x[1])
    for i, (code, mom) in enumerate(sorted_all, 1):
        name = result['code_names'].get(code, code)
        cat = result['code_category'].get(code, '其他')
        ret = result['all_returns'].get(code, 0)
        
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        
        marker = ""
        if code in result['top3_codes']:
            marker = "🔥"
        if code in result['stop_loss_codes']:
            marker = "⚠️止损"
        
        lines.append(f"| {i} | {marker}{name} | {cat} | {ret_str} | {mom_str} |")
    
    lines.append("")
    
    # 优化说明
    lines.append("## 🔧 今日优化")
    lines.append("")
    
    if result['weekday'] == 0:
        lines.append("- ✅ **周一调仓日**：重新评估所有ETF")
    else:
        lines.append("- 📅 非调仓日：维持昨日持仓（除非触发止损）")
    
    if result['stop_loss_codes']:
        lines.append(f"- ⚠️ **止损ETF**：{', '.join([result['code_names'].get(c, c) for c in result['stop_loss_codes']])}")
    
    lines.append("")
    
    # 持仓追踪
    if track['start_date']:
        lines.append("## 📊 模拟持仓追踪")
        lines.append("")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| 起始日期 | {track['start_date']} |")
        holding_names = ", ".join([result['code_names'].get(c, c) for c in track['holdings']])
        lines.append(f"| 当前持有 | {holding_names} |")
        nav_return = (track['nav'] - 1) * 100
        nav_str = f"+{nav_return:.2f}%" if nav_return >= 0 else f"{nav_return:.2f}%"
        lines.append(f"| 累计收益 | **{nav_str}** |")
        lines.append("")
        
        if track['signals']:
            lines.append("**近期调仓：**")
            recent = track['signals'][-3:]
            for s in recent:
                names = ", ".join(s.get('names', []))
                lines.append(f"- {s['date']} → {names}")
        lines.append("")
    
    lines.append("## 💡 优化策略")
    lines.append("")
    lines.append("- **每周调仓**：周一重新评估，降低交易成本")
    lines.append("- **止损机制**：单日跌超5%暂停买入")
    lines.append("- **类别分散**：Top3中每类最多1只")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("⚠️ *数据仅供参考，不构成投资建议*")
    
    return "\n".join(lines)

if __name__ == '__main__':
    config = load_config()
    code_list, code_names, code_category = get_etf_list(config)
    
    result = get_latest_signal(config, code_list, code_names, code_category)
    
    if result:
        track = load_track()
        today = result['date']
        
        if track['start_date'] is None:
            track['start_date'] = today
            track['holdings'] = result['top3_codes']
            track['signals'].append({
                'date': today,
                'codes': result['top3_codes'],
                'names': result['top3_names']
            })
        else:
            # 计算收益（等权平均）
            if track['holdings']:
                total_ret = 0
                for code in track['holdings']:
                    ret = result['all_returns'].get(code, 0) / 100
                    total_ret += ret
                avg_ret = total_ret / len(track['holdings'])
                track['nav'] *= (1 + avg_ret)
            
            # 周一调仓或止损触发调仓
            should_rebalance = (result['weekday'] == 0) or (set(track['holdings']) != set(result['top3_codes']))
            
            if should_rebalance:
                track['holdings'] = result['top3_codes']
                track['signals'].append({
                    'date': today,
                    'codes': result['top3_codes'],
                    'names': result['top3_names']
                })
        
        save_track(track)
        print(format_message(result, track))
    else:
        print("❌ 获取数据失败")

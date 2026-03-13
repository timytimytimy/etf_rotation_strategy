# ETF轮动策略 - Top3轮动版
# 持有涨幅最高的3只ETF，等权配置

import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime
import json
import os

# =====================加载配置=====================
CONFIG_FILE = 'etf_config.json'

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_etf_list(config):
    etf_pool = config['etf_pool']
    code_list = []
    code_names = {}
    code_category = {}
    exclude_categories = config['settings'].get('exclude_categories', ['现金'])
    
    for etf in etf_pool:
        if etf.get('enabled', True):
            code_list.append(etf['code'])
            code_names[etf['code']] = etf['name']
            code_category[etf['code']] = etf['category']
    
    return code_list, code_names, code_category, exclude_categories

def load_track():
    track_file = 'track_record_top3.json'
    if os.path.exists(track_file):
        with open(track_file, 'r') as f:
            return json.load(f)
    return {'start_date': None, 'holdings': [], 'signals': [], 'nav': 1.0}

def save_track(track):
    with open('track_record_top3.json', 'w') as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

def get_data(config, code_list, code_names, code_category, exclude_categories):
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
    returns = {}
    momentum = {}
    for code in code_list:
        if code in data.columns:
            if len(data) > 1:
                returns[code] = (data[code].iloc[-1] / data[code].iloc[-2] - 1) * 100
            else:
                returns[code] = 0
            if len(data) >= N:
                momentum[code] = (data[code].iloc[-1] / data[code].iloc[-N] - 1) * 100
            else:
                momentum[code] = 0
    
    # Top3
    investable = {k: v for k, v in momentum.items() if code_category.get(k) not in exclude_categories}
    if not investable:
        return None
    
    sorted_etfs = sorted(investable.items(), key=lambda x: -x[1])
    top3 = sorted_etfs[:3]
    
    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'top3_codes': [x[0] for x in top3],
        'top3_names': [code_names[x[0]] for x in top3],
        'top3_cats': [code_category[x[0]] for x in top3],
        'top3_mom': [x[1] for x in top3],
        'all_momentum': momentum,
        'all_returns': returns,
        'code_names': code_names,
        'code_category': code_category,
        'exclude_cats': exclude_categories
    }

def format_msg(result, track):
    lines = []
    lines.append(f"# 📊 ETF轮动信号（Top3）[{result['date']}]")
    lines.append("")
    lines.append("## ✅ 今日Top3推荐")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 25日涨跌 | 仓位 |")
    lines.append("|:---:|---------|:----:|---------:|:----:|")
    
    for i, (code, name, cat, mom) in enumerate(zip(
        result['top3_codes'], result['top3_names'], 
        result['top3_cats'], result['top3_mom']), 1):
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        marker = "🔥" if i == 1 else ""
        lines.append(f"| {i} | {marker}{name} | {cat} | {mom_str} | 33% |")
    
    lines.append("")
    
    # 完整排名
    lines.append("## 📈 完整排名")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 今日涨跌 | 25日涨跌 |")
    lines.append("|:---:|---------|:----:|---------:|---------:|")
    
    all_sorted = sorted(result['all_momentum'].items(), key=lambda x: -x[1])
    for rank, (code, mom) in enumerate(all_sorted, 1):
        name = result['code_names'].get(code, code)
        cat = result['code_category'].get(code, '其他')
        ret = result['all_returns'].get(code, 0)
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        marker = "🔥" if code in result['top3_codes'] else ""
        lines.append(f"| {rank} | {marker}{name} | {cat} | {ret_str} | {mom_str} |")
    
    lines.append("")
    
    # 分类表现
    lines.append("## 📂 分类表现")
    lines.append("")
    categories = ['宽基', '红利', '稳健', '成长', '行业', '海外', '商品']
    for cat in categories:
        cat_codes = [(c, m) for c, m in result['all_momentum'].items() 
                     if result['code_category'].get(c) == cat]
        if not cat_codes:
            continue
        avg = sum([m for _, m in cat_codes]) / len(cat_codes)
        avg_str = f"+{avg:.1f}%" if avg >= 0 else f"{avg:.1f}%"
        best = max(cat_codes, key=lambda x: x[1])
        best_name = result['code_names'].get(best[0], best[0])
        fire = "🔥" if any(c in result['top3_codes'] for c, _ in cat_codes) else ""
        lines.append(f"- **{cat}**{fire}: 平均{avg_str}，最佳{best_name}")
    
    lines.append("")
    
    # 持仓追踪
    if track['start_date']:
        lines.append("## 📊 模拟持仓追踪")
        lines.append("")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| 起始日期 | {track['start_date']} |")
        if track['holdings']:
            holding_names = ", ".join([result['code_names'].get(c, c) for c in track['holdings']])
            lines.append(f"| 当前持有 | {holding_names} |")
        nav_ret = (track['nav'] - 1) * 100
        nav_str = f"+{nav_ret:.2f}%" if nav_ret >= 0 else f"{nav_ret:.2f}%"
        lines.append(f"| 累计收益 | **{nav_str}** |")
        lines.append("")
        
        if track['signals']:
            lines.append("**近期调仓：**")
            for s in track['signals'][-5:]:
                names = ", ".join(s.get('names', []))
                lines.append(f"- {s['date']} → {names}")
            lines.append("")
    
    # 策略说明
    lines.append("## 💡 策略逻辑")
    lines.append("")
    lines.append("- **核心思路**：持有近25日涨幅最高的Top3 ETF")
    lines.append("- **仓位分配**：每只33.3%，等权配置")
    lines.append("- **调仓频率**：每日收盘后计算，次日开盘调仓")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("⚠️ *数据仅供参考，不构成投资建议*")
    
    return "\n".join(lines)

if __name__ == '__main__':
    config = load_config()
    code_list, code_names, code_category, exclude_categories = get_etf_list(config)
    
    result = get_data(config, code_list, code_names, code_category, exclude_categories)
    
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
            
            # 检查调仓
            if set(track['holdings']) != set(result['top3_codes']):
                track['holdings'] = result['top3_codes']
                track['signals'].append({
                    'date': today,
                    'codes': result['top3_codes'],
                    'names': result['top3_names']
                })
        
        save_track(track)
        print(format_msg(result, track))
    else:
        print("❌ 获取数据失败")

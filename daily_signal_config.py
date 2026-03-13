# ETF轮动策略 - 配置驱动版（美观格式）
# 只需修改 etf_config.json 即可增删ETF

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
    """加载ETF配置"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_etf_list(config):
    """获取启用的ETF列表"""
    etf_pool = config['etf_pool']
    
    code_list = []
    code_names = {}
    code_category = {}
    exclude_categories = config['settings'].get('exclude_categories', ['现金'])
    
    for etf in etf_pool:
        if etf.get('enabled', True):
            category = etf['category']
            if category in exclude_categories:
                etf['note'] = '仅供参考'
            
            code_list.append(etf['code'])
            code_names[etf['code']] = etf['name']
            code_category[etf['code']] = category
    
    return code_list, code_names, code_category

def load_track(config):
    """加载持仓追踪"""
    track_file = config['settings'].get('track_file', 'track_record.json')
    if os.path.exists(track_file):
        with open(track_file, 'r') as f:
            return json.load(f)
    return {
        'start_date': None,
        'current_holding': None,
        'signals': [],
        'simulated_nav': 1.0,
        'daily_returns': []
    }

def save_track(track, config):
    """保存持仓追踪"""
    track_file = config['settings'].get('track_file', 'track_record.json')
    with open(track_file, 'w') as f:
        json.dump(track, f, ensure_ascii=False, indent=2)

def get_latest_signal(config, code_list, code_names, code_category):
    """获取最新信号"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - pd.Timedelta(days=60)).strftime('%Y%m%d')
    
    exclude_categories = config['settings'].get('exclude_categories', ['现金'])
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

    # 计算N日涨跌幅
    momentum = {}
    for code in code_list:
        if code in data.columns and len(data) >= N:
            momentum[code] = (data[code].iloc[-1] / data[code].iloc[-N] - 1) * 100
        else:
            momentum[code] = 0

    # 过滤不参与轮动的类别
    investable_codes = [c for c in code_list if code_category.get(c) not in exclude_categories]
    
    investable_momentum = {k: v for k, v in momentum.items() if k in investable_codes}
    if not investable_momentum:
        return None
        
    # 选择Top3
    sorted_codes = sorted(investable_momentum.items(), key=lambda x: -x[1])
    top3_codes = [c[0] for c in sorted_codes[:3]]
    top3_names = [code_names[c] for c in top3_codes]
    top3_categories = [code_category[c] for c in top3_codes]
    top3_momentum = [investable_momentum[c] for c in top3_codes]

    return {
        'date': data.index[-1].strftime('%Y-%m-%d'),
        'signal': top3_codes[0],  # 第一名
        'signal_name': top3_names[0],
        'category': top3_categories[0],
        'top3_codes': top3_codes,
        'top3_names': top3_names,
        'top3_categories': top3_categories,
        'top3_momentum': top3_momentum,
        'momentum': momentum,
        'prices': prices,
        'returns': returns,
        'code_names': code_names,
        'code_category': code_category
    }
        'code_names': code_names,
        'code_category': code_category
    }

def format_markdown_message(result, track, config):
    """格式化Markdown输出"""
    code_names = result['code_names']
    code_category = result['code_category']
    exclude_categories = config['settings'].get('exclude_categories', ['现金'])
    
    # 开始构建消息
    lines = []
    lines.append(f"# 📊 ETF轮动信号（Top3）[{result['date']}]")
    lines.append("")
    lines.append(f"## ✅ 今日Top3推荐")
    lines.append("")
    lines.append(f"| 排名 | ETF名称 | 类型 | 25日涨跌 | 建议仓位 |")
    lines.append("|:---:|---------|:----:|---------:|:--------:|")
    
    for i, (code, name, cat, mom) in enumerate(zip(
        result['top3_codes'], 
        result['top3_names'], 
        result['top3_categories'],
        result['top3_momentum']
    ), 1):
        mom_str = f"+{mom:.1f}%" if mom >= 0 else f"{mom:.1f}%"
        position = "33%" if i <= 3 else "-"
        marker = "🔥" if i == 1 else ""
        lines.append(f"| {i} | {marker}{name} | {cat} | {mom_str} | {position} |")
    
    lines.append("")
    
    # ETF表现表格
    lines.append("## 📈 ETF表现排名")
    lines.append("")
    lines.append("| 排名 | ETF名称 | 类型 | 今日涨跌 | 25日涨跌 | 建议 |")
    lines.append("|:---:|---------|:----:|---------:|---------:|:----:|")
    
    # 按涨跌幅排序
    sorted_etfs = sorted(result['momentum'].items(), key=lambda x: -x[1])
    
    rank = 1
    for code, momentum_val in sorted_etfs:
        name = code_names.get(code, code)
        category = code_category.get(code, '其他')
        ret = result['returns'].get(code, 0)
        
        # 格式化涨跌幅
        ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
        momentum_str = f"+{momentum_val:.1f}%" if momentum_val >= 0 else f"{momentum_val:.1f}%"
        
        # 标记
        if code == result['signal']:
            marker = "🔥**买入**"
        elif category in exclude_categories:
            marker = "💰参考"
        else:
            marker = "-"
        
        lines.append(f"| {rank} | {name} | {category} | {ret_str} | {momentum_str} | {marker} |")
        rank += 1
    
    lines.append("")
    
    # 模拟持仓追踪（Top3等权）
    if track['start_date']:
        lines.append("## 📊 模拟持仓追踪（Top3等权）")
        lines.append("")
        lines.append(f"| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| 起始日期 | {track['start_date']} |")
        holding_names = ", ".join(track.get('current_holdings', [track.get('current_holding', 'N/A')]))
        lines.append(f"| 当前持仓 | {holding_names} |")
        nav_return = (track['simulated_nav'] - 1) * 100
        nav_str = f"+{nav_return:.2f}%" if nav_return >= 0 else f"{nav_return:.2f}%"
        lines.append(f"| 累计收益 | **{nav_str}** |")
        lines.append("")
        
        # 近期调仓
        if len(track['signals']) >= 2:
            lines.append("**近期调仓记录：**")
            lines.append("")
            recent = track['signals'][-5:]
            for s in recent:
                if isinstance(s.get('code'), list):
                    # Top3格式
                    names = ", ".join(s.get('names', s.get('code', [])))
                    lines.append(f"- {s['date']} → {names}")
                else:
                    lines.append(f"- {s['date']} → {s['name']}")
            lines.append("")
    
    # 策略说明
    lines.append("## 💡 策略逻辑")
    lines.append("")
    lines.append("- **核心思路**：持有近25日涨幅最高的Top3 ETF")
    lines.append("- **仓位分配**：每只33.3%，等权配置")
    lines.append("- **调仓频率**：每日收盘后计算，次日开盘调仓")
    lines.append("- **现金管理**：现金类仅供参考，不参与轮动")
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
        track = load_track(config)
        today = result['date']

        if track['start_date'] is None:
            track['start_date'] = today
            track['current_holding'] = result['top3_codes']
            track['signals'].append({
                'date': today,
                'codes': result['top3_codes'],
                'names': result['top3_names']
            })
        else:
            # 计算今日收益（Top3等权平均）
            if track['current_holding']:
                today_return = 0
                count = 0
                for code in track['current_holding']:
                    if code in result['returns']:
                        today_return += result['returns'][code] / 100
                        count += 1
                if count > 0:
                    today_return = today_return / count  # 等权平均
                    track['simulated_nav'] *= (1 + today_return)
                    track['daily_returns'].append({
                        'date': today,
                        'return': today_return
                    })

            # 检查是否需要调仓
            if result['top3_codes'] != track['current_holding']:
                track['current_holding'] = result['top3_codes']
                track['signals'].append({
                    'date': today,
                    'codes': result['top3_codes'],
                    'names': result['top3_names']
                })

        save_track(track, config)
        print(format_markdown_message(result, track, config))
    else:
        print("❌ 获取数据失败")

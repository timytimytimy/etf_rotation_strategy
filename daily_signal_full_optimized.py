import akshare as ak
import pandas as pd
import json
import time
import random
from datetime import datetime, timedelta

class ETFRotationPro:
    def __init__(self, config_path="etf_config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

    def get_data(self, symbol, days=250):
        """获取ETF数据，带重试机制"""
        for _ in range(3):
            try:
                # 随机睡眠防止API封禁
                time.sleep(random.uniform(0.5, 1.2))
                df = ak.fund_etf_hist_em(
                    symbol=symbol, period="daily",
                    start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq"
                )
                df['日期'] = pd.to_datetime(df['日期'])
                return df.set_index('日期')['收盘']
            except Exception as e:
                print(f"获取 {symbol} 失败，重试中... Error: {e}")
        return None

    def run(self):
        print(f"🚀 策略启动 | 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        results = []
        p = self.config['params']

        # 1. 扫描所有资产
        for asset in self.config['asset_pool']:
            prices = self.get_data(asset['code'])
            if prices is None or len(prices) < p['trend_window']:
                continue

            # 相对动量 (近1个月收益率)
            ret = (prices.iloc[-1] / prices.iloc[-p['momentum_window']] - 1)
            # 绝对动量 (价格是否在半年线以上)
            ma120 = prices.rolling(window=p['trend_window']).mean().iloc[-1]
            is_above_trend = prices.iloc[-1] > ma120

            results.append({
                "代码": asset['code'],
                "名称": asset['name'],
                "类型": asset['type'],
                "收益率%": round(ret * 100, 2),
                "趋势看多": is_above_trend
            })

        # 2. 排序并应用多样化过滤
        df = pd.DataFrame(results).sort_values(by="收益率%", ascending=False)

        final_positions = []
        category_tracker = {}

        for _, row in df.iterrows():
            if len(final_positions) >= p['top_n']:
                break

            # 风险控制：同类资产不得超过 max_per_category
            curr_cat = row['类型']
            cat_count = category_tracker.get(curr_cat, 0)

            if cat_count < p['max_per_category']:
                # 双动量逻辑：收益率最高 且 价格在均线上；否则买入国债
                target_name = f"{row['名称']}({row['代码']})" if row['趋势看多'] else f"避险资产({self.config['defense_asset']['name']})"
                final_positions.append({
                    "仓位": f"仓位 {len(final_positions)+1}",
                    "目标资产": target_name,
                    "原驱动因子": f"{row['名称']} (收益率 {row['收益率%']}%)"
                })
                category_tracker[curr_cat] = cat_count + 1

        # 3. 输出结果
        print("\n[📊 市场多维扫描数据]")
        print(df.to_markdown(index=False))

        print("\n[🎯 最终调仓决策 (等权重 33.3%)]")
        decision_df = pd.DataFrame(final_positions)
        print(decision_df.to_markdown(index=False))
        print("\n注：若目标资产显示为'避险资产'，说明该强势品种处于下跌通道，已触发防御机制。")

if __name__ == "__main__":
    ETFRotationPro().run()

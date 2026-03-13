import akshare as ak
import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 绘图环境配置
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class AggressiveBacktester:
    def __init__(self, config_path="etf_config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.assets = self.config['asset_pool']
        self.defense = self.config['defense_asset']
        self.params = self.config['params']
        self.data = {}
        self.benchmark_code = "510300" # 以沪深300作为对比基准

    def fetch_all_data(self, start_date="20160101"):
        """获取所有资产的历史数据"""
        print(f"📥 正在获取历史数据 (回测起点: {start_date})...")
        all_codes = [a['code'] for a in self.assets] + [self.defense['code'], self.benchmark_code]
        # 去重
        all_codes = list(set(all_codes))
        
        for code in all_codes:
            try:
                df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, adjust="qfq")
                df['日期'] = pd.to_datetime(df['日期'])
                df.set_index('日期', inplace=True)
                self.data[code] = df['收盘']
                print(f"✅ 加载成功: {code}")
            except:
                print(f"❌ 加载失败: {code}")

    def run_backtest(self):
        """运行全自动调仓模拟"""
        # 以基准代码的时间轴为准
        timeline = self.data[self.benchmark_code].index
        monthly_dates = self.data[self.benchmark_code].resample('ME').last().index
        
        portfolio_val = 1.0
        benchmark_val = 1.0
        equity_curve = []
        
        print(f"\n🚀 激进模式回测启动 | 窗口: {self.params['trend_window']}日 | 选股: Top {self.params['top_n']}")

        for i in range(len(monthly_dates)-1):
            curr_date = monthly_dates[i]
            next_date = monthly_dates[i+1]
            
            # --- 核心选股逻辑 ---
            snapshot = []
            for asset in self.assets:
                code = asset['code']
                if code not in self.data or curr_date not in self.data[code].index:
                    continue
                
                prices = self.data[code].loc[:curr_date]
                if len(prices) < self.params['trend_window']: continue
                
                # 计算相对动量 (20日) 和 绝对动量 (60日均线)
                ret = (prices.iloc[-1] / prices.iloc[-self.params['momentum_window']] - 1)
                ma_trend = prices.rolling(window=self.params['trend_window']).mean().iloc[-1]
                is_alive = prices.iloc[-1] > ma_trend
                
                snapshot.append({'code': code, 'type': asset['type'], 'ret': ret, 'alive': is_alive})
            
            # 排序：收益率最高者优先
            df_snap = pd.DataFrame(snapshot).sort_values(by='ret', ascending=False)
            
            # 多样化过滤 (max_per_category)
            selected = []
            cat_count = {}
            for _, row in df_snap.iterrows():
                if len(selected) >= self.params['top_n']: break
                c_type = row['type']
                if cat_count.get(c_type, 0) < self.params.get('max_per_category', 1):
                    # 如果破位，则该席位换成国债
                    final_code = row['code'] if row['alive'] else self.defense['code']
                    selected.append(final_code)
                    cat_count[c_type] = cat_count.get(c_type, 0) + 1
            
            # --- 计算盈亏 ---
            period_range = self.data[self.benchmark_code].loc[curr_date:next_date].index[1:]
            for d in period_range:
                # 策略收益
                day_rets = []
                for code in selected:
                    day_ret = self.data[code].loc[:d].pct_change().iloc[-1]
                    day_rets.append(day_ret)
                
                portfolio_val *= (1 + np.mean(day_rets))
                # 基准收益
                bench_day_ret = self.data[self.benchmark_code].loc[:d].pct_change().iloc[-1]
                benchmark_val *= (1 + bench_day_ret)
                
                equity_curve.append({
                    'date': d, 
                    'strategy': portfolio_val, 
                    'benchmark': benchmark_val
                })

        # 结果分析
        res_df = pd.DataFrame(equity_curve).set_index('date')
        self.report(res_df)

    def report(self, df):
        # 计算指标
        total_ret = (df['strategy'].iloc[-1] - 1) * 100
        bench_ret = (df['benchmark'].iloc[-1] - 1) * 100
        
        days = (df.index[-1] - df.index[0]).days
        cagr = ((df['strategy'].iloc[-1] ** (365/days)) - 1) * 100
        
        df['max_val'] = df['strategy'].cummax()
        df['drawdown'] = (df['strategy'] / df['max_val'] - 1)
        mdd = df['drawdown'].min() * 100
        
        print("\n" + "="*40)
        print(f"📊 激进版策略回测报告")
        print(f"策略累计收益: {total_ret:.2f}%")
        print(f"基准(沪深300): {bench_ret:.2f}%")
        print(f"年化收益率: {cagr:.2f}%")
        print(f"最大回撤: {mdd:.2f}%")
        print("="*40)

        # 绘图
        plt.figure(figsize=(12, 6))
        plt.plot(df['strategy'], label='激进双动量策略', color='red', linewidth=1.5)
        plt.plot(df['benchmark'], label='沪深300基准', color='gray', linestyle='--', alpha=0.7)
        plt.title('策略净值曲线 vs 基准 (全攻全守版)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig('aggressive_backtest.png')
        print(f"\n📈 曲线图已更新: aggressive_backtest.png")
        plt.show()

if __name__ == "__main__":
    bt = AggressiveBacktester()
    bt.fetch_all_data()
    bt.run_backtest()

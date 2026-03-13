import akshare as ak
import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 设置绘图支持中文
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class SimpleBacktester:
    def __init__(self, config_path="etf_config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.assets = self.config['asset_pool']
        self.defense = self.config['defense_asset']
        self.params = self.config['params']
        self.data = {}

    def fetch_all_data(self, start_date="20180101"):
        """获取所有资产的历史数据"""
        print(f"📥 正在获取历史行情数据 (起点: {start_date})...")
        all_codes = [a['code'] for a in self.assets] + [self.defense['code']]
        
        for code in all_codes:
            try:
                df = ak.fund_etf_hist_em(symbol=code, period="daily", 
                                         start_date=start_date, adjust="qfq")
                df['日期'] = pd.to_datetime(df['日期'])
                df.set_index('日期', inplace=True)
                self.data[code] = df['收盘']
                print(f"✅ 已加载: {code}")
            except Exception as e:
                print(f"❌ 加载失败 {code}: {e}")

    def run_backtest(self):
        """运行回测逻辑"""
        # 1. 准备对齐的时间轴（取沪深300的时间轴作为基准）
        benchmark_code = "510300"
        timeline = self.data[benchmark_code].index
        
        # 2. 初始化净值和持仓
        portfolio_value = 1.0
        equity_curve = []
        current_holdings = []
        
        # 3. 按月频模拟调仓 (每个月的最后一个交易日)
        monthly_dates = self.data[benchmark_code].resample('ME').last().index
        
        print(f"\n🚀 回测开始，共 {len(monthly_dates)} 个调仓周期...")
        
        for i in range(len(monthly_dates)-1):
            current_date = monthly_dates[i]
            next_date = monthly_dates[i+1]
            
            # --- 选股逻辑开始 ---
            snapshot = []
            for asset in self.assets:
                code = asset['code']
                if code not in self.data or current_date not in self.data[code].index:
                    continue
                
                # 获取当前和20日前的价格
                prices = self.data[code].loc[:current_date]
                if len(prices) < self.params['trend_window']: continue
                
                ret = (prices.iloc[-1] / prices.iloc[-self.params['momentum_window']] - 1)
                ma120 = prices.rolling(window=self.params['trend_window']).mean().iloc[-1]
                is_above_ma = prices.iloc[-1] > ma120
                
                snapshot.append({
                    'code': code, 'type': asset['type'], 'ret': ret, 'alive': is_above_ma
                })
            
            # 应用排序和类别限制
            if not snapshot:
                continue
            
            df_snap = pd.DataFrame(snapshot).sort_values(by='ret', ascending=False)
            selected = []
            cat_count = {}
            
            for _, row in df_snap.iterrows():
                if len(selected) >= self.params['top_n']: break
                c_type = row['type']
                if cat_count.get(c_type, 0) < self.params['max_per_category']:
                    # 绝对动量：跌破均线则持有防御资产
                    final_code = row['code'] if row['alive'] else self.defense['code']
                    selected.append(final_code)
                    cat_count[c_type] = cat_count.get(c_type, 0) + 1
            
            # --- 计算本月收益 ---
            month_returns = []
            for code in selected:
                # 获取该资产在下一个月内的日收益
                period_price = self.data[code].loc[current_date:next_date]
                if len(period_price) > 1:
                    r = period_price.pct_change().dropna()
                    month_returns.append(r)
            
            if month_returns:
                # 等权重组合日收益
                combined_daily_ret = pd.concat(month_returns, axis=1).mean(axis=1)
                for r in combined_daily_ret:
                    portfolio_value *= (1 + r)
                    equity_curve.append({'date': combined_daily_ret.index[0], 'value': portfolio_value})

        # 4. 统计结果
        result_df = pd.DataFrame(equity_curve).set_index('date')
        self.calculate_metrics(result_df)
        self.plot_res(result_df)

    def calculate_metrics(self, df):
        """计算量化指标"""
        total_ret = (df['value'].iloc[-1] - 1) * 100
        # 计算年化收益 (简单计算)
        days = (df.index[-1] - df.index[0]).days
        cagr = ((df['value'].iloc[-1] ** (365/days)) - 1) * 100
        # 计算最大回撤
        df['cummax'] = df['value'].cummax()
        df['dd'] = (df['value'] / df['cummax'] - 1)
        mdd = df['dd'].min() * 100
        # 计算夏普比率 (假设无风险收益3%)
        daily_ret = df['value'].pct_change().dropna()
        sharpe = (daily_ret.mean() * 252 - 0.03) / (daily_ret.std() * np.sqrt(252))

        print("\n" + "="*30)
        print(f"📊 回测统计结果")
        print(f"累计收益: {total_ret:.2f}%")
        print(f"年化收益: {cagr:.2f}%")
        print(f"最大回撤: {mdd:.2f}%")
        print(f"夏普比率: {sharpe:.2f}")
        print("="*30)

    def plot_res(self, df):
        """绘制净值曲线"""
        plt.figure(figsize=(12, 6))
        plt.plot(df['value'], label='策略净值')
        plt.title('全球大类资产双动量轮动策略 - 历史回测')
        plt.xlabel('日期')
        plt.ylabel('净值')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig('backtest_result.png')
        print("\n📈 净值曲线已保存至: backtest_result.png")
        plt.show()

if __name__ == "__main__":
    bt = SimpleBacktester()
    bt.fetch_all_data(start_date="20180101")
    bt.run_backtest()

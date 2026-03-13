# ETF轮动策略

一个基于动量的ETF轮动量化策略，通过持有近期表现最佳的ETF来实现超额收益。

## 策略概述

- **核心思路**：持有近25日涨幅最高的Top3 ETF
- **仓位分配**：每只33.3%，等权配置
- **调仓频率**：每周一调仓
- **优化特性**：凯利仓位 + ATR止损 + 多因子排序 + 相关性过滤

## 回测表现

### 全面优化版（2021-2026，5年）

| 指标 | 数值 |
|------|------|
| 累计收益率 | +215.0% |
| 年化收益率 | 25.3% |
| 夏普比率 | 2.09 |
| 最大回撤 | -7.8% |

### 10年回测（2016-2026）

| 指标 | 数值 |
|------|------|
| 累计收益率 | +777.8% |
| 年化收益率 | 24.0% |
| 夏普比率 | 1.82 |
| 最大回撤 | -17.8% |

## 主要文件

- `daily_signal_full_optimized.py` - 全面优化版每日信号脚本（推荐使用）
- `etf_config.json` - ETF候选池配置
- `backtest_full_optimized.py` - 全面优化版回测脚本

## ETF候选池

当前包含17只ETF：

- **宽基**：沪深300ETF、中证500ETF
- **红利**：上证红利ETF、中证红利ETF
- **稳健**：5只自由现金流ETF
- **成长**：创业板ETF、科创50ETF
- **行业**：人工智能ETF、半导体ETF、医药ETF
- **海外**：纳指ETF、恒生科技ETF
- **商品**：黄金ETF

## 使用方法

```bash
# 获取今日信号
python daily_signal_full_optimized.py

# 运行回测
python backtest_full_optimized.py
```

## 依赖

- Python 3.8+
- akshare
- pandas
- numpy

```bash
pip install akshare pandas numpy
```

## 风险提示

⚠️ 历史表现不代表未来收益，投资有风险，入市需谨慎。

## License

MIT

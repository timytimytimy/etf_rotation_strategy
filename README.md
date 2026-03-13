# ETF Global Rotation Strategy Pro 🌏📈

基于 **双动量 (Dual Momentum)** 逻辑的全球大类资产轮动方案。

## 策略亮点
- **全球视野**：资产池涵盖 A股宽基、美股、日经、黄金及周期品。
- **生存法则**：结合绝对动量过滤（半年线），在熊市自动切换至国债。
- **风险对冲**：同类别资产持仓上限限制，防止单一阵地溃败。
- **简单高效**：代码高度模块化，每月仅需运行一次。

## 快速开始
```bash
pip install akshare pandas tabulate
python daily_signal_full_optimized.py
```

## 回测表现

### 10年回测（2016-2026）

| 指标 | 数值 |
|------|------|
| 累计收益率 | +777.8% |
| 年化收益率 | 24.0% |
| 夏普比率 | 1.82 |
| 最大回撤 | -17.8% |

### 5年回测（2021-2026）

| 指标 | 数值 |
|------|------|
| 累计收益率 | +215.0% |
| 年化收益率 | 25.3% |
| 夏普比率 | 2.09 |
| 最大回撤 | -7.8% |

## 策略说明

详细的策略说明请查看：[策略说明.md](./策略说明.md)

## 主要文件

- `daily_signal_full_optimized.py` - 全面优化版每日信号脚本
- `backtest_full_optimized.py` - 全面优化版回测脚本
- `etf_config.json` - ETF候选池配置

## 依赖

```bash
pip install akshare pandas numpy matplotlib
```

## 风险提示

⚠️ 历史表现不代表未来收益，投资有风险，入市需谨慎。

## License

MIT
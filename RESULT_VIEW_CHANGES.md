# 结果查看TAB页改动总结

## 完成的改动

### 1. **removed "交易信号" 页面** ✓
   - 从 `BacktestChartWidget` 中移除了 `PriceSignalWidget` 页面
   - 调整标签页从4个改为3个

### 2. **将"收益分布"页改为"交易详情"** ✓
   - 创建新的 `TradeDetailWidget` 组件
   - 替代了原来的 `TradeDistributionWidget`（直方图）
   - 显示交易表格，包含列：交易日期、买卖方向、数量、价格

### 3. **K线图改进** ✓
   - K线图保留在第一个标签页
   - 交易信号（B/S）正确显示在K线图上（不在单独的页面）
   - 支持从数据库加载OHLC数据

### 4. **从数据库获取OHLC数据** ✓
   - 修改 `result_panel.py` 的 `_ChartDialog` 类
   - 在显示图表前从数据库查询OHLC数据
   - 通过 `DataQuery` 获取指定日期范围内的股票数据

## 修改的文件

### src/gui/chart_widget.py
- 导入修改：添加了 `QTableWidget`, `QTableWidgetItem`, `QHeaderView` 等表格相关类
- 创建新类 `TradeDetailWidget`：显示交易历史表格
- 修改 `BacktestChartWidget`：
  - 移除 `signal_widget` 和 `dist_widget` 引用
  - 添加 `trade_detail_widget`
  - 调整标签页数量和显示顺序
- 优化 `_export_charts` 方法：支持按当前标签页导出

### src/gui/result_panel.py
- 添加导入：`DataQuery`, `Config`, `Path`
- 修改 `_ChartDialog` 类：
  - 新增 `_load_price_data` 方法从数据库获取OHLC数据
  - 在创建图表前调用此方法获取价格数据
  - 将价格数据传递给 `BacktestChartWidget`

## 新的标签页结构

| 位置 | 标签名 | 内容 |
|------|--------|------|
| 第1页 | K线图 | 蜡烛图 + 成交量 + 交易信号（B/S标记） |
| 第2页 | 权益曲线 | 权益曲线 + 回撤曲线 |
| 第3页 | 交易详情 | 表格显示所有交易：日期、方向、数量、成交价 |

## 交易表格功能

- **列**：交易日期、买卖方向（B/S）、数量、价格
- **排序**：按交易日期从早到晚升序排列
- **样式**：
  - 买入信号（B）显示为绿色
  - 卖出信号（S）显示为红色
  - 中心对齐

## K线图信号显示

- **买入信号**：绿色上三角形（△）
- **卖出信号**：红色下三角形（▽）
- 信号标记直接显示在K线图上，无需切换到其他页面

## 数据来源

- **OHLC数据**：从 `data/stock_data.db` 数据库获取
- **配置读取**：从 `config/config.yaml` 读取数据库路径
- **日期范围**：根据回测的 `start_date` 和 `end_date` 查询

## 测试结果

✓ 模块导入成功
✓ TradeDetailWidget 表格渲染正确
✓ BacktestChartWidget 三个标签页正确初始化
✓ GUI 应用成功启动

## 用户体验改进

1. **更清晰的结果展示**：去掉冗余的信号页面，信号直接显示在K线图上
2. **交易详情一目了然**：新的表格显示所有交易信息，易于查看每笔交易的具体数据
3. **数据完整性**：从数据库动态加载OHLC数据，确保K线图数据准确
4. **操作简化**：不需要在多个页面间切换来理解回测结果

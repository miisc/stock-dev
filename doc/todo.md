# 项目开发 TODO 列表

## 股票池三层模型（设计原则）

```
层次1：下载范围（一次性/定期更新）
└── 决定本地数据库里有哪些股票的历史数据
    例：下载"沪深300"，本地就有300只的数据

层次2：回测范围（每次回测时选择）
└── 从本地已有数据中圈定范围
    例：选"上证50"，只对本地已有的这50只跑回测

层次3：个股筛选（可选，进一步缩小）
└── 在层次2基础上手动勾选/排除个别股票
    例：从沪深300中手动勾选金融板块的若干只
```

> **关键原则**：下载与回测解耦。数据下载一次保存本地，之后可反复用不同范围回测，无需重新联网。回测时只能选本地已有数据的股票。

---

> ## 一期目标：MVP Demo
> 一期只实现核心流程的最小可用版本：**下载数据 → 选股票池 → 单策略批量回测 → 汇总结果**。
> **一期必须包含**：前视偏差控制、前复权数据、基础交易成本（否则回测结果不可信）。
> 基准对比、参数优化、组合回测等进阶功能列入二期。

---

## 第一阶段：数据层补全

### 1. 股票池管理器（src/data/universe.py）
- [x] 获取沪深300成分股列表（akshare）
- [x] 获取上证50成分股列表
- [x] 获取创业板50成分股列表
- [x] 获取中证500成分股列表
- [x] 获取全部A股列表
- [x] 本地缓存成分股列表（避免频繁请求）—— `data/universe_cache.json`
- [x] 缓存过期机制（建议每日刷新）—— `_is_cache_stale()` 每日检查

### 2. 批量下载管理器（src/data/batch_downloader.py）
- [x] 接收股票列表，循环调用下载
- [x] 进度回调接口（progress_callback(done, total, ts_code)）
- [x] **并发数已改为 <=3（默认值）；`_rate_limited_sleep()` 确保请求间隔 >= 500ms**
- [x] 失败重试机制（最多3次，retry_delay=1.0s）
- [x] 失败股票列表记录（failures 列表）
- [x] 支持取消操作（`_cancel_event` threading.Event）
- [x] **已重构为 Queue + 单一写入线程（`_writer_worker`），下载线程不直接写 SQLite**

### 3. 增量更新逻辑（src/data/fetcher.py 修改）
- [x] **前复权数据：akshare_source.py 已固定使用 `adjust="qfq"`**
- [x] 检查本地最新日期 —— `_get_meta_last_date()` + `market_meta.json`
- [x] 只下载缺失的日期区间 —— `fetch_incremental()`
- [x] 合并新旧数据写入 storage

### 3b. 数据库索引优化（src/common/database.py）
- [x] **复合索引已建立：`idx_stock_daily_code_date ON stock_daily (ts_code, trade_date)`**
- [x] 回测结果持久化表已建立：`backtest_results`（含策略名/起止日/各项指标/config_json）

---

## 第二阶段：回测层补全

### 4. 回测引擎正确性修复（src/backtesting/backtest_engine.py）

> ✅ 全部修复完成

- [x] **前视偏差控制：信号写入 `pending_orders`，次日开盘价执行（`_collect_signals` + `_execute_pending_orders`）**
- [x] **基础交易成本（CostModel + ExecutionExecutor）**
  - 买入佣金：0.03%（commission_rate=0.0003）✅
  - 卖出佣金：0.03% + 印花税 0.1%（stamp_duty_rate=0.001）✅
  - 滑点：0.1%（slippage_rate=0.001）
- [x] **正确的指标计算（result.py）**
  - 年化收益率：`(1 + total_ret) ** (252 / trading_days) - 1` ✅
  - 最大回撤：从 daily_portfolio total_value 净值曲线计算 ✅
  - 夏普比率：使用无风险利率 2%（risk_free_rate=0.02）✅
- [ ] UI 结果页面注明：「数据基于前复权，含幸存者偏差，仅供参考」（GUI 阶段实现）

### 5. 批量回测调度器（src/backtesting/batch_runner.py）
> ✅ 已完成
- [x] 接收股票列表 + 策略类 + 参数 + 时间范围
- [x] 循环调用 BacktestEngine，每只股票独立回测
- [x] 进度回调接口（on_progress(current, total, ts_code)）
- [x] 单股票失败不中断整体流程，记录失败原因
- [x] 汇总所有股票的 BacktestResult 列表
- [x] 支持取消操作（`_cancel_event`）
- [x] 回测完成后将结果持久化到 backtest_results 表

### 6. 结果聚合（src/analysis/aggregator.py）
> ✅ 已完成
- [x] 汇总多股票回测结果为 DataFrame（ResultAggregator.build_summary()）
- [x] 计算整体胜率（overall_win_rate()）
- [x] Top N / Bottom N 排名（按夏普/收益率等任意列）
- [x] 导出汇总结果到 CSV（to_csv()）
- [x] 统计描述（describe()）

---

## 第三阶段：GUI 层重构

> ✅ 全部完成

> **线程模型**：`Worker(QThread)` 通过 `Signal` 发送进度和结果，主线程只负责更新 UI。

### 7. 数据管理面板 — 层次1：下载范围（src/gui/universe_panel.py）

- [x] 预置股票池选择（沪深300/上证50/创业板50/中证500/全部A股）
- [x] 显示所选池的股票数量预估
- [x] 显示本地已有数据的股票数量及最新日期（`_refresh_local_stats()`）
- [x] 调用 universe.py 获取成分股列表
- [x] 调用 batch_downloader.py 执行批量下载（`DownloadWorker(QThread)`）
- [x] 下载进度条（已下载 x/总数，当前股票名称）
- [x] 失败列表展示，支持单独重试（`_retry_failed()`）
- [x] 取消按钮（通过 `DownloadWorker.cancel()` 取消标志位实现）
- [x] `data_updated` 信号：下载成功后通知回测面板刷新股票列表

### 8. 回测配置面板 — 层次2+3：回测范围与个股筛选（src/gui/backtest_panel.py）

- [x] 层次2 — 下拉列表显示本地已有的各股票池，选择后过滤本地已有股票
- [x] 层次3 — 展示所选池的股票列表（QListWidget），支持全选/全不选/逐只勾选
- [x] 层次3 — 支持按代码搜索过滤股票列表
- [x] 最终选中股票数量实时显示
- [x] 策略选择下拉框 + 策略参数配置表单（动态生成，来自 strategy_config_manager）
- [x] 回测时间范围选择
- [x] 交易成本参数配置（佣金/滑点，显示默认值，允许修改；印花税固定0.1%注明）
- [x] 批量回测进度条（`BatchBacktestWorker(QThread)`）
- [x] 取消按钮（JobWorker `cancel()` 方法）
- [x] `backtest_finished` 信号：回测完成后广播 `List[BacktestResult]`

### 9. 批量结果汇总视图（src/gui/result_panel.py）

- [x] 汇总表格（代码/策略/收益率/年化/夏普/最大回撤/波动率/交易次数/胜率/盈亏比），支持列排序
- [x] **结果页脚注明：「基于前复权数据，含幸存者偏差，交易成本按实际配置计算」**
- [x] 整体胜率统计、平均夏普、平均年化（摘要行）
- [x] 双击/点击「查看图表」按钮展示该股票详细图表弹窗（`_ChartDialog`）
- [x] 导出 CSV 按钮（`ResultAggregator.to_csv()`）

### 10. 主窗口标签页整合（src/gui/main_window.py）

- [x] Tab1：数据管理（UniversePanel）
- [x] Tab2：策略回测（BacktestPanel）
- [x] Tab3：结果查看（ResultPanel）
- [x] 标签页间数据传递：`data_updated` → `refresh_from_db()`；`backtest_finished` → `set_results()` + 自动切换 Tab3
- [x] 状态栏：免责提示「基于前复权数据 | 含幸存者偏差 | 结果仅供参考」

---

## 第四阶段：测试补全

### 11. 单元测试
- [ ] tests/test_universe.py - 股票池获取与缓存
- [ ] tests/test_batch_downloader.py - 批量下载、进度、重试
- [ ] tests/test_batch_runner.py - 批量回测调度
- [ ] tests/test_aggregator.py - 结果聚合与导出
- [ ] **tests/test_lookahead_bias.py - 验证回测无前视偏差（信号日 vs 成交日）**
- [ ] **tests/test_cost_model.py - 验证手续费/印花税/滑点计算正确**
- [ ] **tests/test_metrics.py - 验证年化收益/最大回撤/夏普比率计算正确**

---

## 优先级顺序（一期 MVP）

1. fetcher.py（前复权 + 增量更新）
2. database.py（复合索引 + backtest_results 表）
3. universe.py（股票池管理）
4. batch_downloader.py（Queue写入 + 限速）
5. backtest_engine.py（前视偏差修复 + 交易成本 + 指标修正）
6. batch_runner.py（批量调度 + 持久化）
7. aggregator.py（结果聚合）
8. universe_panel.py（GUI + QThread）
9. backtest_panel.py（GUI + QThread）
10. result_panel.py（汇总视图 + 免责提示）
11. main_window.py（标签页整合）
12. 补全测试（含偏差/成本/指标专项测试）

---

## 二期扩展（暂不实现）

### A. 回测可信度

#### A1. 基准对比（Benchmark）
- [ ] 下载基准指数数据（沪深300/上证指数）并存入本地
- [ ] 回测结果同时显示策略收益曲线 vs 基准收益曲线
- [ ] 计算超额收益（Alpha）、相对基准的夏普比率
- [ ] 汇总表格新增「跑赢基准」列

#### A2. 交易成本进阶
> 基础交易成本已列入一期。二期扩展：
- [ ] 结果页「含成本 vs 不含成本」收益对比图
- [ ] 支持自定义各股票/时期的差异化手续费率

### B. 结果分析深度

#### B1. 交易记录明细
- [ ] 每笔交易记录：买入日期/价格/数量 → 卖出日期/价格/数量 → 单笔盈亏/持仓天数
- [ ] 结果面板新增「交易明细」Tab，展示完整交易流水
- [ ] 支持按盈亏排序、筛选

#### B2. 收益时间分布
- [ ] 按年收益率统计（2020: +25%, 2021: -8%, ...）
- [ ] 按月收益率热力图
- [ ] 最大连续亏损笔数统计
- [ ] 盈亏分布直方图

### C. 资金管理

#### C1. 仓位控制
- [ ] 回测参数新增仓位模式：固定金额 / 固定比例 / 全仓
- [ ] 支持设置最大持仓比例上限

#### C2. 多股票同时持仓（组合回测）
- [ ] 同时持有多只股票时的资金分配逻辑
- [ ] 组合整体收益曲线（非单股票独立）
- [ ] 组合回撤与相关性分析

### D. 防止过拟合

#### D1. 参数敏感性测试
- [ ] 对策略参数进行网格搜索（如短周期3-10，长周期15-30）
- [ ] 热力图展示不同参数组合的收益率分布
- [ ] 识别参数稳健区间 vs 碰巧好的参数

#### D2. 滚动回测 / 时间分段验证
- [ ] 训练集（如2015-2020）找最优参数
- [ ] 测试集（如2020-2024）验证参数是否仍然有效
- [ ] 避免策略过拟合历史数据

### F. 架构与数据质量

#### F1. 幸存者偏差修复
- [ ] 下载历史指数成分股变动记录（需找历史成分股数据源）
- [ ] 回测时按当时的成分股列表构建股票池，而非当前列表

#### F2. 高级并发模型
- [ ] 多线程下载 + Queue 写入升级为 asyncio 异步模型
- [ ] 支持断点续传（程序中断后继续未完成的下载任务）
- [ ] 下载任务持久化队列（重启后可恢复）

### E. 用户体验

#### E1. 回测配置保存与复现
- [ ] 保存当前回测配置（策略+参数+股票池+时间范围）为命名配置
- [ ] 配置列表页，支持一键加载历史配置重新回测

#### E2. 回测历史记录
- [ ] 每次回测自动保存结果到本地数据库
- [ ] 历史回测列表，支持查看和对比不同次回测结果
- [ ] 支持删除历史记录
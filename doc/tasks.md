# 股票回测系统任务拆解（执行版）

## 1. 使用说明

本文件用于单人开发 + Agent 协作执行，目标是每个任务都能直接开工、直接验收。

任务字段固定为 5 项：
1. 目标
2. 前置依赖
3. 完成标准
4. 验证方式
5. 状态（todo/doing/blocked/partial/done）

## 2. 本轮重规划原则

1. 不改 [doc/spec.md](doc/spec.md) 正文，仅输出问题映射并在任务中消化。
2. 保留 M1-M4 与 T1-T12 主编号，不新增 T0 阶段。
3. 高风险阻塞项优先：T3、T6、T10、T11、T12。
4. 每个里程碑必须定义最小验收产物。

## 3. Spec 问题映射（执行输入）

1. P-S1 可复现阈值未细化 -> T12（定义偏差计算与阈值）。
2. P-S2 质量三态与放行边界不清 -> T3（落地三态规则与放行开关）。
3. P-S3 续跑边界不清 -> T6（定义续跑起点、范围、失败重试策略）。
4. P-S4 性能验收口径不够细 -> T12（补充验收基线和证据模板）。
5. P-S5 对比规则不完整 -> T11（明确双实验对比维度和差异说明格式）。

## 4. 总体节奏

1. 总任务数：12
2. 里程碑：4 个（每个 3 任务）
3. 建议顺序：M1 -> M2 -> M3 -> M4
4. 执行规则：同一时刻仅 1 个 doing 任务；每完成 1 个任务即补验证结论

## 5. 最小验收记录模板

每个任务完成后，复制以下模板填写并附在对应任务下方或里程碑验收记录中。

```text
[验收记录]
任务ID：T?
验收日期：YYYY-MM-DD
执行人：
输入：
步骤：
结果：通过/不通过
证据：日志路径/截图路径/报告路径/测试用例
备注：
```

## 6. 任务清单

### M1 数据管理（FR-1/FR-2/FR-3）

#### T1 股票池与输入规则
- 状态：done。
- 最小验收记录样例：任务ID=T1；输入=5组代码样例；结果=5组均可判定；证据=规则文档+样例判定表。

[验收记录]
任务ID：T1
验收日期：2026-04-21
执行人：Agent
输入：5 组代码样例（全合法/全非法/混合/全重复/大组混合）
步骤：`StockPoolManager.validate_codes()` + `build_custom_pool()` 新增输入规则；运行 `pytest tests/test_stock_pool_rules.py -q`
结果：通过
证据：`tests/test_stock_pool_rules.py`（27 passed）；`src/data/stock_pool.py` 新增 `is_valid_code()` / `validate_codes()` / 重写 `build_custom_pool()`
备注：合法格式为 6 位数字，可选带 .SH/.SZ/.BJ 后缀或 sh/sz/bj 前缀；重复代码自动去重；非法代码以 WARNING 日志记录并过滤。

#### T2 下载与增量更新规则
- 状态：done。
- 最小验收记录样例：任务ID=T2；输入=同区间重复下载2次；结果=第二次命中增量判定；证据=下载日志+meta对比。

[验收记录]
任务ID：T2
验收日期：2026-04-21
执行人：Agent
输入：4 类规则场景（重复跳过/增量/失败重试/取消后统计）
步骤：运行 `pytest tests/test_download_incremental_rules.py -q`
结果：通过
证据：`tests/test_download_incremental_rules.py`（6 passed）
备注：同区间重复下载 total=0（全部跳过）；部分存在只下载缺失；max_retries 控制重试次数；取消后成功计数可见。

#### T3 数据质量与放行策略
- 目标：落地数据质量三态和回测放行策略。
- 前置依赖：T2。
- 完成标准：
  1. 通过/警告/失败三态规则明确。
  2. 警告是否放行有默认策略和配置开关。
  3. 质量报告采用结构化输出（JSON）。
- 验证方式：针对缺失、重复、乱序、异常值 4 类场景逐条判定并输出报告样例。
- 状态：done。
- 最小验收记录样例：任务ID=T3；输入=4类质量异常样本；结果=三态判定和放行策略符合预期；证据=JSON质量报告+配置截图。

[验收记录]
任务ID：T3
验收日期：2026-04-21
执行人：Agent
输入：固定阈值质量判定、JSON质量报告落盘、回测前质量门禁拦截场景
步骤：运行 `pytest tests/test_data_quality_gate.py -q`，随后运行 `pytest tests/test_backtest_engine.py tests/test_data_processor.py -q` 回归
结果：通过
证据：`tests/test_data_quality_gate.py`（3 passed）；`tests/test_backtest_engine.py` + `tests/test_data_processor.py`（3 passed）
备注：修复阈值比较口径为“>阈值才触发告警/失败”，避免阈值为0时误报 warning。

M1 并行建议：T1 与 T2 可局部并行调研；T3 必须在 T2 规则稳定后执行。
M1 验收产物：数据任务演示、质量报告样例、失败重试记录。

### M2 回测执行（FR-4/FR-5）

#### T4 策略参数字典与校验
- 状态：done。
- 最小验收记录样例：任务ID=T4；输入=10组参数；结果=合法通过、非法拦截并提示；证据=参数校验记录表。

[验收记录]
任务ID：T4
验收日期：2026-04-21
执行人：Agent
输入：10 组合法/非法参数（Case01-Case10）
步骤：运行 `pytest tests/test_strategy_param_validation.py -q`
结果：通过
证据：`tests/test_strategy_param_validation.py`（15 passed）；合法 5 组通过，非法 5 组被拦截并输出 loguru ERROR
备注：校验含类型强制转换、范围检查（min/max）、choices 枚举、必填项缺失 4 类；默认值通过自身校验规则。

#### T5 批量回测任务状态机
- 状态：done。
- 最小验收记录样例：任务ID=T5；输入=3类任务场景；结果=状态迁移与计数一致；证据=状态流转日志。

[验收记录]
任务ID：T5
验收日期：2026-04-21
执行人：Agent
输入：3 类场景（正常完成 / 部分失败 / 手动取消）
步骤：运行 `pytest tests/test_batch_state_machine.py -q`
结果：通过
证据：`tests/test_batch_state_machine.py`（11 passed）；`get_last_run_status()` 返回 success/failed/cancelled/pending 四态统计
备注：取消后 pending→cancelled；已成功保持 success；失败有错误信息记录；进度回调最终值 current==total。

#### T6 取消与续跑规则
- 目标：明确取消后可见性与续跑边界。
- 前置依赖：T5。
- 完成标准：
  1. 取消后已完成结果保留。
  2. 未完成与失败对象可识别。
  3. 续跑范围规则明确（未完成/失败/全量重跑）。
- 验证方式：构造一次中断任务，输出续跑起点、续跑范围与最终结果对账。
- 状态：done。
- 最小验收记录样例：任务ID=T6；输入=中断后续跑1次；结果=已完成保留、未完成续跑成功；证据=中断前后结果对账单。

[验收记录]
任务ID：T6
验收日期：2026-04-21
执行人：Agent
输入：取消中断场景 + 续跑范围（incomplete/failed）
步骤：运行 `pytest tests/test_batch_runner.py -q`，验证取消后状态可见与续跑范围行为；随后运行 `pytest tests/test_backtest_engine.py -q` 做邻近回归
结果：通过
证据：`tests/test_batch_runner.py`（10 passed）；`tests/test_backtest_engine.py`（1 passed）
备注：新增 `BatchRunner.get_last_run_status()` 与 `BatchRunner.resume(scope=...)`，支持 incomplete/failed/all。

M2 并行建议：T5 与 T6 可分“状态定义”和“续跑策略演练”并行准备。
M2 验收产物：批量回测演示、取消与续跑演示、参数校验清单。

### M3 结果分析（FR-6/FR-7）

#### T7 指标字段标准化
- 状态：done。
- 最小验收记录样例：任务ID=T7；输入=同一标的两种视图指标；结果=定义和数值口径一致；证据=指标对照表。

[验收记录]
任务ID：T7
验收日期：2026-04-21
执行人：Agent
输入：同一 BacktestResult 在 PerformanceMetrics 与 ResultAggregator 两视图对比
步骤：运行 `pytest tests/test_metrics_standardization.py -q`
结果：通过
证据：`tests/test_metrics_standardization.py`（13 passed）；字段名对齐、数值口径误差 < 0.01、单位均为百分比
备注：total_return / annual_return / max_drawdown / sharpe_ratio 四指标数值对照通过；win_rate 范围 [0,100]。

#### T8 筛选展示规则
- 状态：done。
- 最小验收记录样例：任务ID=T8；输入=固定样例集；结果=排序筛选与Top N结果稳定；证据=筛选步骤记录+结果截图。

[验收记录]
任务ID：T8
验收日期：2026-04-21
执行人：Agent
输入：固定样例集（含并列、空列表、n>行数、无效列名、多条件复合筛选）
步骤：运行 `pytest tests/test_filter_rules.py -q`；同时修复 `describe()` 空数据边界行为
结果：通过
证据：`tests/test_filter_rules.py`（19 passed）；top_n/bottom_n/describe/复合筛选全覆盖
备注：describe() 在空 DataFrame 时返回空索引 DataFrame 不崩溃；并列时 top_n 返回行数准确。

#### T9 CSV 导出规范
- 状态：done。
- 最小验收记录样例：任务ID=T9；输入=汇总CSV+交易记录CSV；结果=主流表格工具可正确解析；证据=导出样例文件+打开截图。

[验收记录]
任务ID：T9
验收日期：2026-04-21
执行人：Agent
输入：汇总 CSV（to_csv）+ 交易记录 CSV（trades_to_csv）
步骤：`ResultAggregator.trades_to_csv()` 新增实现；运行 `pytest tests/test_csv_export.py -q`
结果：通过
证据：`tests/test_csv_export.py`（13 passed）；UTF-8 BOM 正确、列顺序固定、日期格式 YYYY-MM-DD、数值精度 ≤4 位
备注：汇总 CSV 精度 2 位、交易记录 CSV 精度 4 位；ts_code 过滤功能已验证；父目录自动创建。

M3 并行建议：T8 与 T9 可在字段字典确定后并行推进。
M3 验收产物：汇总看板演示、Top N 与分布视图、CSV 样例。

### M4 实验管理与复现（FR-8/NFR-4）

#### T10 实验快照最小字段
- 目标：定义并落地可复现实验最小字段集合。
- 前置依赖：T9。
- 完成标准：股票池快照、时间范围、策略参数、成本口径、数据口径、运行信息均可追溯。
- 验证方式：任意结果可回查到完整快照字段。
- 状态：done。
- 最小验收记录样例：任务ID=T10；输入=任意历史实验1条；结果=快照字段完整可回查；证据=实验快照JSON样例。

[验收记录]
任务ID：T10
验收日期：2026-04-21
执行人：Agent
输入：单标的批量回测持久化（包含策略参数）
步骤：运行 `pytest tests/test_batch_runner.py -q`，校验 `backtest_results.config_json` 中 `experiment_snapshot` 字段；随后运行 `pytest tests/test_data_quality_gate.py tests/test_backtest_engine.py -q` 回归
结果：通过
证据：`tests/test_batch_runner.py`（11 passed）；`tests/test_data_quality_gate.py` + `tests/test_backtest_engine.py`（4 passed）
备注：已落盘字段包括 ts_codes_snapshot、start/end、initial_cash、cost_params、data_scope、strategy_snapshot、run_started_at/run_ended_at。

#### T11 历史检索与双实验对比
- 目标：定义实验检索与双实验对比规则。
- 前置依赖：T10。
- 完成标准：支持按名称/时间检索，并输出两次实验关键指标差异与来源说明。
- 验证方式：选取两次实验输出标准化对比报告。
- 状态：done。
- 最小验收记录样例：任务ID=T11；输入=两次实验记录；结果=生成差异与来源说明；证据=对比报告。

[验收记录]
任务ID：T11
验收日期：2026-04-21
执行人：Agent
输入：两次 DualMA 实验（策略参数不同）
步骤：运行 `pytest tests/test_experiment_compare.py -q`，验证历史检索（名称/时间）与双实验对比输出；随后运行 `pytest tests/test_batch_runner.py tests/test_data_query_comprehensive.py -q` 回归
结果：通过
证据：`tests/test_experiment_compare.py`（2 passed）；`tests/test_batch_runner.py` + `tests/test_data_query_comprehensive.py`（14 passed）
备注：新增 `DatabaseManager.search_backtest_results()` 与 `DatabaseManager.compare_backtest_results()`。

#### T12 一致性阈值与最终验收
- 目标：定义重复运行一致性阈值并完成总体验收。
- 前置依赖：T11。
- 完成标准：
  1. 同快照重复执行偏差可判定通过/警告/失败。
  2. 性能与一致性验收证据模板固定。
- 验证方式：至少 2 次重复实验并输出最终验收结论。
- 状态：done。
- 最小验收记录样例：任务ID=T12；输入=同快照重复运行2次；结果=偏差判定与最终结论明确；证据=一致性验收报告。

[验收记录]
任务ID：T12
验收日期：2026-04-21
执行人：Agent
输入：双实验指标差异（pass/warning/failed 场景）+ 验收证据模板生成
步骤：运行 `pytest tests/test_repeatability_checker.py -q` 验证阈值判定与模板结构；随后运行 `pytest tests/test_experiment_compare.py tests/test_metrics.py -q` 做邻近回归
结果：通过
证据：`tests/test_repeatability_checker.py`（2 passed）；`tests/test_experiment_compare.py` + `tests/test_metrics.py`（16 passed）
备注：新增 `RepeatabilityChecker`，输出一致性状态与固定性能证据模板。

M4 并行建议：T10 完成前不建议并行 T11/T12。
M4 验收产物：实验快照样例、历史检索演示、双实验对比报告、最终验收结论。

## 7. 关键路径与阻塞

1. 关键路径：T3 -> T6 -> T10 -> T11 -> T12。
2. 阻塞处理：若关键路径任务 blocked，优先解除阻塞，不切换到低优先级优化项。
3. 切换条件：仅在 blocked 原因和解除条件写清后允许临时切换。

## 8. 快速验收清单

1. M1：数据范围明确、增量规则明确、质量放行明确。
2. M2：参数可校验、任务可取消、中断可续跑。
3. M3：指标一致、筛选可解释、导出可用。
4. M4：结果可追溯、实验可对比、复现可判定。

---

最后更新：2026-04-21
版本：v3.0（执行版）

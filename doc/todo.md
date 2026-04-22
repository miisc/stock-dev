# TODO（基于代码审计）

更新时间：2026-04-21
基准文档：[doc/tasks.md](doc/tasks.md)

## 状态与优先级口径

1. 状态：todo / doing / blocked / partial / done。
2. 优先级：P0（主链阻塞）/ P1（里程碑关键）/ P2（优化项）。
3. 本清单按代码与测试现状评估，不按历史勾选继承。

## 总览

1. 总任务：12
2. 已完成：8（T2, T3, T4, T6, T7, T10, T11, T12）
3. 部分完成：4（T1, T5, T8, T9）
4. 未完成：0
5. P0待完成：0

## 任务清单（按里程碑）

### M1 数据管理

#### T1 股票池与输入规则
- 状态：partial
- 优先级：P1
- 代码证据：
  - 预置池与缓存能力：[src/data/universe.py](src/data/universe.py#L28)
  - 自定义池构建能力：[src/data/stock_pool.py](src/data/stock_pool.py#L110)
- 缺口：非法代码处理与输入规范尚未统一。
- 下一步：补统一输入校验规则、异常分级与样例判定表。

#### T2 下载与增量更新规则
- 状态：done
- 优先级：P1
- 代码证据：
  - 下载进度/失败重试/取消：[src/data/batch_downloader.py](src/data/batch_downloader.py#L120)
  - 增量更新逻辑：[src/data/data_fetcher.py](src/data/data_fetcher.py#L149)
- 验证结论：重复区间可通过已有数据与 meta 判定避免重复下载。

#### T3 数据质量与放行策略
- 状态：done
- 优先级：P0
- 代码证据：
  - 数据清洗与告警基础：[src/data/data_processor.py](src/data/data_processor.py#L127)
  - 质量报告落盘与阈值加载：[src/data/data_fetcher.py](src/data/data_fetcher.py#L41)
  - 回测前质量门禁与warning放行开关：[src/backtesting/backtest_engine.py](src/backtesting/backtest_engine.py#L264)
- 缺口：
  - 已关闭。
- 验证结论：
  - `pytest tests/test_data_quality_gate.py -q` -> 3 passed
  - `pytest tests/test_backtest_engine.py tests/test_data_processor.py -q` -> 3 passed
- 下一步：保持回归即可；P0 主链转入 T10。

### M2 回测执行

#### T4 策略参数字典与校验
- 状态：done
- 优先级：P1
- 代码证据：
  - 参数定义与校验：[src/trading/strategy_config.py](src/trading/strategy_config.py#L24)
  - GUI 参数校验反馈：[src/gui/strategy_panel.py](src/gui/strategy_panel.py#L252)
- 验证结论：参数类型、范围、必填规则已可执行。

#### T5 批量回测任务状态机
- 状态：partial
- 优先级：P1
- 代码证据：
  - 批量回测进度与失败不中断：[src/backtesting/batch_runner.py](src/backtesting/batch_runner.py#L47)
- 缺口：缺少统一状态机定义与结构化落库字段。
- 下一步：补状态模型（排队/运行/部分成功/取消/完成）并统一对外口径。

#### T6 取消与续跑规则
- 状态：done
- 优先级：P0
- 代码证据：
  - 取消能力与状态可见性：[src/backtesting/batch_runner.py](src/backtesting/batch_runner.py)
  - 续跑范围（incomplete/failed/all）：[src/backtesting/batch_runner.py](src/backtesting/batch_runner.py)
  - GUI 取消入口：[src/gui/backtest_panel.py](src/gui/backtest_panel.py#L528)
- 缺口：
  - 已关闭。
- 验证结论：
  - `pytest tests/test_batch_runner.py -q` -> 10 passed
  - `pytest tests/test_backtest_engine.py -q` -> 1 passed
- 下一步：进入 T10（实验快照最小字段），推进 P0 主链。

### M3 结果分析

#### T7 指标字段标准化
- 状态：done
- 优先级：P1
- 代码证据：
  - 聚合字段清单：[src/analysis/aggregator.py](src/analysis/aggregator.py#L20)
  - 面板列映射：[src/gui/result_panel.py](src/gui/result_panel.py#L28)
- 验证结论：汇总字段与展示字段已基本一致。

#### T8 筛选展示规则
- 状态：partial
- 优先级：P1
- 代码证据：
  - 排序能力：[src/gui/result_panel.py](src/gui/result_panel.py#L133)
  - Top/Bottom 能力：[src/analysis/aggregator.py](src/analysis/aggregator.py#L90)
- 缺口：多条件筛选行为与分布视图入口未固化。
- 下一步：补筛选规则文档与最小分布视图闭环。

#### T9 CSV 导出规范
- 状态：partial
- 优先级：P1
- 代码证据：
  - 汇总 CSV 导出：[src/analysis/aggregator.py](src/analysis/aggregator.py#L127)
  - GUI 导出入口：[src/gui/result_panel.py](src/gui/result_panel.py#L231)
- 缺口：单标的交易记录导出路径、字段字典与精度规范未完整。
- 下一步：补齐交易记录 CSV 导出与字段规范说明。

### M4 实验管理与复现

#### T10 实验快照最小字段
- 状态：done
- 优先级：P0
- 代码证据：
  - 回测结果表与配置字段：[src/common/database.py](src/common/database.py#L112)
  - 批量回测写入 experiment_snapshot：[src/backtesting/batch_runner.py](src/backtesting/batch_runner.py)
  - 快照持久化测试：[tests/test_batch_runner.py](tests/test_batch_runner.py)
- 缺口：
  - 已关闭。
- 验证结论：
  - `pytest tests/test_batch_runner.py -q` -> 11 passed
  - `pytest tests/test_data_quality_gate.py tests/test_backtest_engine.py -q` -> 4 passed
- 下一步：进入 T11（历史检索与双实验对比）。

#### T11 历史检索与双实验对比
- 状态：done
- 优先级：P0
- 代码证据：
  - 历史检索接口：[src/common/database.py](src/common/database.py)
  - 双实验对比接口：[src/common/database.py](src/common/database.py)
  - 对比测试用例：[tests/test_experiment_compare.py](tests/test_experiment_compare.py)
- 缺口：
  - 已关闭。
- 验证结论：
  - `pytest tests/test_experiment_compare.py -q` -> 2 passed
  - `pytest tests/test_batch_runner.py tests/test_data_query_comprehensive.py -q` -> 14 passed
- 下一步：进入 T12（一致性阈值与最终验收）。

#### T12 一致性阈值与最终验收
- 状态：done
- 优先级：P0
- 代码证据：
  - 一致性判定模块：[src/analysis/repeatability.py](src/analysis/repeatability.py)
  - analysis 对外导出：[src/analysis/__init__.py](src/analysis/__init__.py)
  - 阈值与性能目标配置：[config/config.yaml](config/config.yaml)
  - 测试覆盖：[tests/test_repeatability_checker.py](tests/test_repeatability_checker.py)
- 缺口：
  - 已关闭。
- 验证结论：
  - `pytest tests/test_repeatability_checker.py -q` -> 2 passed
  - `pytest tests/test_experiment_compare.py tests/test_metrics.py -q` -> 16 passed
- 下一步：P0 主链已完成，转入 P1（T1/T5/T8/T9）补齐。

## 推荐执行顺序（单人串行）

1. P0 主链：已完成。
2. P1 补齐：T1 -> T5 -> T8 -> T9。
3. done 任务仅做回归，不重复返工：T2、T3、T4、T6、T7、T10、T11、T12。

## 测试侧证据（用于 T12）

1. 前视偏差测试：[tests/test_lookahead_bias.py](tests/test_lookahead_bias.py)
2. 成本模型测试：[tests/test_cost_model.py](tests/test_cost_model.py)
3. 指标计算测试：[tests/test_metrics.py](tests/test_metrics.py)

## 本次变更摘要

1. 新增优先级字段（P0/P1/P2）。
2. 统一状态词典为 todo/doing/blocked/partial/done。
3. 将 spec 关键风险映射到 P0 主链任务，明确执行顺序。

# Copilot Instructions — Stock Trading & Backtesting System

## Project Overview

A Python-based A-share stock trading and backtesting system. It supports data acquisition via **akshare** (primary), sina, eastmoney, and tushare, strategy backtesting, and simulated trading with a **PyQt5** GUI.

## Tech Stack

- **Language**: Python 3.10+
- **Data source**: akshare (primary), sina, eastmoney, tushare
- **Storage**: SQLite via `src/common/database.py`
- **Config**: YAML files in `config/` loaded via `src/common/config.py`
- **GUI**: PyQt5 — panels in `src/gui/`
- **Logging**: loguru
- **Testing**: pytest, test files in `tests/`
- **Virtual env**: `.venv/` (activate with `.venv\Scripts\Activate.ps1`)

## Project Structure

```
src/
  common/       # Config, database, logger utilities
  data/         # Data fetching, processing, storage, universe management      backtesting/  # Backtest engine, executor, position manager, cost model, result
  analysis/     # Result aggregation and metrics
  gui/          # PyQt5 panels and main window
config/         # config.yaml, strategies.yaml
tests/          # pytest test files, named test_*.py
```

## Coding Conventions

### Strategies
- All strategies **must inherit** from `src.trading.strategy.Strategy` (abstract base class).
- Strategy constructor signature: `__init__(self, strategy_id: str, name: str, params: Optional[Dict[str, Any]] = None)`.
- Implement abstract methods: `on_init(self) -> None` and `on_bar(self, bar: BarData) -> None`.
- Strategy parameters are managed via `src.trading.strategy_config.StrategyConfig`.
- Place new strategy files in `src/trading/strategies/` and register them in `src/trading/strategies/__init__.py`.

### Backtesting
- Use `BacktestConfig` dataclass to configure a run (start/end date, initial_cash, commission_rate, slippage_rate).
- Entry point is `BacktestEngine` in `src/backtesting/backtest_engine.py`.
- Batch runs use `src/backtesting/batch_runner.py`.

### Data
- Fetch data through `src/data/data_fetcher.py` or `src/data/data_query.py`.
- Stock universe is managed via `src/data/universe.py` and cached in `data/universe_cache.json`.
- All raw data goes through `src/data/data_processor.py` before storage.

### Configuration
- Default trading params: `commission_rate=0.0003`, `slippage_rate=0.001`, `initial_capital=100000`.
- Risk limits: `max_drawdown=0.15`, `position_limit=0.8`, `max_position_ratio=0.2`.
- Do **not** hardcode these values; read from `config/config.yaml` via `src/common/config.py`.

### Logging
- Use `loguru` logger imported from `src/common/logger.py`, not the stdlib `logging`.
- Log file: `logs/stock_system.log`.

### Testing
- Write tests in `tests/`, named `test_<module>.py`.
- Use `pytest`. Run with: `pytest tests/` from the project root with the virtual env activated.
- Avoid real network calls in unit tests; mock akshare responses where needed.

## Key Entry Points

| Task | Command |
|------|---------|
| Run GUI | `python main.py` |
| CLI backtest | `python cli.py` |
| Run tests | `pytest tests/` |
| Activate env (Windows) | `.\.venv\Scripts\Activate.ps1` |

## Do Not

- Do not commit API tokens or secrets; they belong in environment variables or a local `.env` file (not tracked).
- Do not add new dependencies without updating `requirements.txt` (or `.venv`).
- Do not bypass the `Strategy` base class when implementing new strategies.

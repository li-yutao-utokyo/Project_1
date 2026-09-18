# 開発ログ (Work Log)

> このファイルには毎回の作業内容を追記していく。新しいエントリは末尾に追加すること。

---

## 2026-09-18: Phase 0 — プロジェクトスキャフォールド

**やったこと:**
- ローカル git リポジトリを初期化(`git init -b main`)
- README 第6節のディレクトリ構成に沿って `src/`(ingestion / processing / storage /
  analysis / orchestration/dags / dashboard)、`tests/`、`data/{raw,processed}`、`docs/`
  を作成し、各 Python パッケージに `__init__.py` を配置
- `pyproject.toml` を作成:プロジェクトメタ情報、依存関係(httpx, pandas, sqlalchemy,
  psycopg, python-dotenv, apscheduler, streamlit, alembic)、dev 依存(pytest,
  pytest-mock, ruff)、ruff/pytest 設定
- `docker-compose.yml`:PostgreSQL 15 サービス定義(healthcheck 付き、named volume で永続化)
- `.env.example`:DB接続情報 + Open-Meteo API ベースURL + Airflow UID
- `.gitignore`:`.venv`, `__pycache__`, `.env`, `data/raw`, `data/processed` の実データなど
- `data/raw/.gitkeep`, `data/processed/.gitkeep` でディレクトリ構造のみ git 管理
- `tests/test_placeholder.py`:pytest が確実に1件収集・成功するプレースホルダーテスト
  (README の受け入れ基準「pytest が(用例が無くても)通ること」を満たすため)
- `.github/workflows/ci.yml`:push/PR (main) で ruff lint → pytest を実行する CI
- `docs/architecture.md`:ADR形式の決定記録を開始(uv/poetry未導入のためpip運用である旨を記録)

**確認事項 / 未確認:**
- ローカル環境に `uv` / `poetry` が未インストール。当面 `pip install -e ".[dev]"` で運用。
- `.venv` を作成し `pip install -e ".[dev]"` → `ruff check .` / `pytest -q` を実行し、
  どちらも成功することを確認済み(ruff: All checks passed / pytest: 1 passed)。
- `docker-compose up -d` を実行したが、Docker Desktop のデーモンが起動しておらず
  (`/Users/peach/.docker/run/docker.sock` に接続できない)失敗。Docker Desktop アプリを
  起動してから再実行して DB 起動を確認する必要あり(次回セッションでの確認事項)。
- CI (GitHub Actions) はリモートリポジトリに push されるまで実行結果を確認できない
  (現時点でこのリポジトリに GitHub remote は未設定)。

**次にやること(Phase 1 着手時):**
- `src/ingestion/openmeteo_client.py`:Open-Meteo API から都市/日付範囲で過去データ取得
- `src/storage/models.py` に `raw_observations` テーブル定義(README 第9節参照)
- `python -m src.ingestion.run --city tokyo --start ... --end ...` の手動実行スクリプト
- API レスポンスパース処理の単体テスト(実ネットワークに依存しない mock ベース)

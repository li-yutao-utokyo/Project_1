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

---

## 2026-09-18 (続き): Phase 0 検証完了 + Phase 1 — MVP バッチ取り込みパイプライン

**やったこと:**
- Docker Desktop 起動後に `docker-compose up -d` を再実行し、`urban-climate-postgres`
  コンテナが `healthy` になり `pg_isready` が accepting connections を返すことを確認
  (Phase 0 の受け入れ基準を完全にクリア)
- `src/storage/models.py`:SQLAlchemy 2.x (`DeclarativeBase`/`Mapped`) で
  `RawObservation` モデル(`raw_observations` テーブル、README §9 のスキーマ通り)を定義
- `src/storage/db.py`:`.env` から `DATABASE_URL` を読み込むエンジン管理と、
  テストで engine を差し替え可能な `get_session()` コンテキストマネージャ
- `src/storage/init_db.py`:`Base.metadata.create_all()` でテーブル作成
  (`python -m src.storage.init_db` で実行可能。README §10 の手順と一致)
- `src/ingestion/openmeteo_client.py`:Open-Meteo Historical Weather API クライアント
  - `CITY_COORDINATES` に tokyo/osaka/nagoya の代表都市を登録(全観測点網羅はしない、非目標§2.2)
  - `fetch_historical_weather()`:httpx でAPI呼び出し(`client` 引数でテスト時に注入可能)
  - `parse_openmeteo_response()`:hourly JSON配列を `raw_observations` 行のlistに変換
- `src/ingestion/run.py`:`python -m src.ingestion.run --city --start --end` CLI。
  fetch → parse → `RawObservation` として DB へ commit
- `tests/test_ingestion.py`:6ケース、全て実ネットワーク非依存
  - レスポンスパース(正常系・空レスポンス)
  - 未知都市で `UnknownCityError`
  - `httpx.MockTransport` でリクエストパラメータ検証(実HTTP不使用)
  - `run()` の end-to-end 検証(SQLite in-memory engine 注入 + `fetch_historical_weather` を
    monkeypatch)
- ruff / pytest ともに全通過(6 passed)
- 実環境での動作確認:`python -m src.storage.init_db` でテーブル作成 →
  `python -m src.ingestion.run --city tokyo --start 2024-06-01 --end 2024-06-02` を実際に
  Open-Meteo API + ローカル Postgres に対して実行し、48件のレコードが正しく
  `raw_observations` に入ったことを `psql` で確認済み

**決定事項:**
- Alembic はまだ導入していない(現時点では `create_all()` で十分、最初のスキーマ変更が
  発生したタイミングで導入する)。README §11「最小可動版から始める」方針に沿った判断。
  `pyproject.toml` の依存には alembic を残しているので、導入時の追加作業は設定ファイルの
  用意のみ。

**確認事項 / 未確認:**
- ローカル Postgres には検証用に投入した48件のテストデータ(tokyo, 2024-06-01~02)が
  残っている。Phase 2 のクリーニング処理の入力として使うか、破棄するかは未定。

**次にやること(Phase 2 着手時):**
- raw → processed の清掃・変換ロジック(重複排除、欠損値処理、異常値フィルタ、
  風速のm/s統一、`wind_direction_octant` 8方位分類)
- `processed_observations` テーブル定義
- 汚いデータを含むサンプルでのクリーニングロジックのテスト

---

## 2026-09-18 (続き2): Phase 2 — データ処理(raw → processed)

**やったこと:**
- `src/storage/models.py`:`ProcessedObservation` モデルを追加
  (`processed_observations` テーブル、`wind_direction_octant` 列を含む README §9 準拠のスキーマ)
- `src/processing/clean.py`:
  - `drop_duplicates()`:`(city, timestamp, source)` で重複排除(最新行を優先)
  - `drop_missing_required()`:`wind_speed` / `temperature` が欠損した行を除去
  - `filter_outliers()`:風速の負値・気温の非現実的な値・風向の範囲外値を除去
- `src/processing/transform.py`:
  - `ensure_utc_timestamp()`:タイムゾーンをUTCに統一
  - `standardize_wind_speed()`:ソース別の換算係数(現状 open-meteo は 1.0)でm/sに統一
  - `classify_wind_direction_octant()`:風向を8方位(N/NE/E/SE/S/SW/W/NW)に分類
- `src/processing/run.py`:`python -m src.processing.run --city --start --end` CLI。
  raw_observations を読み込み→clean→transform→該当期間の processed_observations を
  削除してから再書き込み(同じ範囲を再実行しても冪等)
- `tests/test_processing.py`:18ケース(既存6件+新規12件)。汚いデータサンプル
  (重複行、負の風速、欠損気温、範囲外風向)でのクリーニング検証、8方位分類の境界値テスト、
  SQLite in-memory での `run()` end-to-end テスト。ruff / pytest 全通過
- テスト設計時の失敗と修正:最初のテストで複数行に同一 `timestamp` を使い回していたため、
  意図しない重複排除で行が丸ごと1件に潰れてしまい3件失敗。各行に別々の時刻を持たせて修正
  (`_at(hour, **overrides)` ヘルパーを追加)。8方位境界値のテストケースも一部誤り
  (44度は NE であり N ではない)があったため修正
- 実環境での動作確認:`python -m src.processing.run --city tokyo --start 2024-06-01
  --end 2024-06-02` を実行し、Phase 1 で投入済みの48件の raw データから48件の
  processed_observations が生成されたことを `psql` で確認(このサンプルには外れ値・
  重複がなかったため件数は変わらず)

**確認事項 / 未確認:**
- ローカル Postgres の `raw_observations` / `processed_observations` には検証用データ
  (tokyo, 2024-06-01~02)が残ったまま。実データでの本格運用時は整理が必要。

**次にやること(Phase 3 着手時):**
- 風向分類(8方位、`wind_direction_octant` は既に用意済み)と気温の相関統計
- 歩行者高度風速換算(`pedestrian_wind_speed = R * observed_wind_speed`)
- 非適風日数判定ロジック(強風/弱風閾値は可変)
- `optimize_r.py`:Rのグリッドサーチで非適風日数合計が最小になるRを探索
- 既知の入力での換算・判定ロジックのテスト

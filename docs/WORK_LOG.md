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

---

## 2026-09-18 (続き3): Phase 3 — 核心分析機能(風向-気温相関 + R値最適化)

**やったこと:**
- `src/storage/queries.py` を新設し、Phase 2 の `processing/run.py` にあった
  「city/期間で観測データをDataFrameとして読み込む」ロジックを `load_observations()` として
  共通化(2箇所目の利用が出たタイミングでの抽出、`processing/run.py` 側もこれを使うよう修正)
- `src/storage/models.py` に `RWindOptimizationResult`(`analysis_r_optimization` テーブル、
  README §9 のスキーマ + `city` 列を追加。複数都市の結果が衝突しないようにするため)
- `src/analysis/wind_comfort.py`:
  - `pedestrian_wind_speed()`:`R × observed wind_speed`
  - `daily_max_pedestrian_wind_speed()`:日別の代表値として日最大値を採用
    (Lawson基準のような厳密な超過確率評価ではなく簡略化した日次判定。README §8の
    「精度の完全再現は求めない」方針に沿った判断)
  - `classify_uncomfortable_days()`:日最大の歩行者高度風速が強風閾値(既定5.0 m/s)を
    超えたら強風不適日、弱風閾値(既定1.0 m/s)を下回ったら弱風不適日
  - `wind_direction_temperature_stats()`:風向8方位ごとの気温 mean/std/count
- `src/analysis/optimize_r.py`:
  - `optimize_r()`:R を `r_min`〜`r_max`(既定0.3〜1.0、既定step 0.01)でグリッドサーチし、
    各Rでの強風/弱風/合計不適日数を `DataFrame(columns=[r, strong_wind_days,
    weak_wind_days, total_days])` として返す
  - `find_optimal_r()`:合計不適日数が最小の行を返す(同点の場合は最小のRを採用)
- `src/analysis/run.py`:`python -m src.analysis.run --city --start --end [--r-min --r-max
  --r-step --strong-threshold --weak-threshold --plot PATH]` CLI。
  processed_observations を読み込み→風向-気温統計を表示→Rグリッドサーチ実行→
  結果を `analysis_r_optimization` に削除後再書き込み(期間指定で冪等)→最適Rを表示→
  `--plot` 指定時は matplotlib(Aggバックエンド)で「不適日数 vs R」のPNGを保存
- 依存関係に `numpy`, `matplotlib` を追加
- `tests/test_analysis.py`:14ケース追加。境界値の浮動小数点誤差を避けるため、
  「全域で快適(total_days=0固定)」「全域で不快適(total_days=2固定)」「両端が
  不快適で中央に最小値0が来るU字型」という3パターンを意図的に作って検証
  (単一の厳密な閾値ちょうどの点をピンポイントで assert するのは避けた)。
  `run()` の再実行が重複せず置き換わることも確認。ruff / pytest 全通過(28 passed)
- 実環境での動作確認:`python -m src.analysis.run --city tokyo --start 2024-06-01
  --end 2024-06-02 --plot <path>` を実行。風向別気温統計表とPNGプロットが正しく出力され、
  `analysis_r_optimization` に71件(R=0.30〜1.00, step0.01)が書き込まれたことを
  `psql` で確認。ただしこの2日分のサンプルは風が全体的に穏やかだったため、
  どのRでも不適日数が0で最適Rの一意な決定打にはならなかった(R=0.30が採用された)。
  U字カーブそのものを実データで見るには、より長い期間・強風日を含むデータで
  再実行する必要がある(Phase 5のDashboardや長期データ取得時に確認)

**決定事項:**
- `analysis_r_optimization` テーブルに README §9 未記載の `city` 列を追加(複数都市対応のため)

**確認事項 / 未確認:**
- ローカル Postgres に検証用データ(tokyo, 2024-06-01~02の raw/processed/analysis結果)が
  残ったまま
- R値カーブのU字形状は今回の短期間・穏やかな気象データでは確認できていない
  (ロジック自体は `tests/test_analysis.py` の人工データで検証済み)

**次にやること(Phase 4 着手時):**
- APScheduler(またはcron)で「毎日自動的に前日分を取得」するMVP簡易版の編成
- 進阶:Airflow移行、`daily_pipeline.py` DAG で ingestion→processing→analysis を連結
- Airflowはdocker-composeでローカル起動(webserver + scheduler + postgres metadata db)

---

## 2026-09-18 (続き4): Phase 4 — 編成自動化(APScheduler MVP + Airflow DAGコード)

**やったこと:**
- `src/orchestration/pipeline.py`:`run_daily_pipeline(city, target_date=None,
  analysis_window_days=30)` を新設。ingestion→processing→analysis(直近30日の
  ローリングウィンドウでR最適化を再計算)を1回の呼び出しでチェーンする共通ロジック。
  APScheduler と Airflow DAG の両方から同じ関数を呼ぶことで、二重実装を避けた
- `src/orchestration/scheduler.py`:APScheduler(`BlockingScheduler`)によるMVP簡易版。
  `python -m src.orchestration.scheduler --once` で即時1回実行、`--hour` オプションで
  毎日実行時刻(UTC)を指定可能。対象都市は環境変数 `PIPELINE_CITIES`(カンマ区切り、
  既定 "tokyo")で設定。1都市の失敗が他都市の実行を止めないよう例外を個別にキャッチ
- `src/orchestration/dags/daily_pipeline.py`:Airflow DAG(進阶版)。
  ingestion/processing/analysis を3つの独立した `PythonOperator` タスクとして
  `ingest >> process >> analyze` でチェーン(1関数にまとめず、Airflow UI 上で
  各ステップの成功/失敗・ログが個別に見えるようにするため)。毎日 01:00 UTC 実行、
  `catchup=False`
- `tests/test_orchestration.py`:10ケース追加(33 passed)。`run_daily_pipeline` が
  正しい日付(既定=前日UTC、30日ウィンドウ)で各ステップを呼び出すことを monkeypatch で検証、
  `PIPELINE_CITIES` のパース、1都市が例外を投げても他都市の処理が継続することを確認
- ruff は Airflow 未インストールでも構文チェックのみで通過することを確認済み
  (DAGファイルは実際には Airflow コンテナ内でのみ import・実行される想定)
- 実環境での動作確認:
  - `run_daily_pipeline('tokyo', date(2024,6,1), analysis_window_days=2)` を直接呼び出し、
    ingestion 24件・processing 24件・analysis 71件(R=0.3〜1.0)が実行されたことを確認
  - `python -m src.orchestration.scheduler --once` を実行し、実際に「昨日(2026-09-17)」の
    データを Open-Meteo から取得→処理→直近30日分析まで一気通貫で成功することを確認
    (Open-Meteo archive API は前日分もすでに提供していることが分かった)

**未完了 / 次回の論点:**
- README Phase 4 の受け入れ基準(「DAGがAirflow UIで手動トリガーでき、全工程が成功し
  ログが見られること」)はまだ満たしていない。`daily_pipeline.py` のコードは書いたが、
  Airflowをdocker-composeで実際に起動して動作確認するステップが残っている
- Airflow は apache/airflow イメージが大きく(数GB規模)、webserver+scheduler+
  メタデータDBなど複数コンテナが必要になるため、ローカル環境のリソース・実行時間への
  影響を作者に確認してから着手する方針とした(README §11「大きな判断は事前確認」に沿う)

**次にやること(Phase 4 継続 / Phase 5 着手時):**
- (要確認)Airflow用の docker-compose 追加(webserver + scheduler + metadata db)、
  プロジェクト依存をインストールしたカスタムイメージ、`.env` 経由でアプリ用DBに接続
- DAGをAirflow UIで手動トリガーし、3タスクが成功してログが見えることを確認
- Streamlit Dashboard(風配図、気温-風速散布図、R値最適化曲線)

---

## 2026-09-18 (続き5): Phase 4 完了 — Airflow を実際にDocker Composeで起動・検証

作者確認の結果、「今すぐ構築・検証する」を選択。以下を実施:

**やったこと:**
- 現行の Airflow 最新安定版を調査(WebFetch でDocker Hub/公式ドキュメントを確認)した結果、
  3.3.2 であり、公式クイックスタートの docker-compose.yaml は CeleryExecutor 前提
  (redis, worker, triggerer, dag-processor, api-server, flower 等7サービス以上、
  RAM 4〜8GB推奨)に変わっていることが判明。README想定の軽量構成(3サービス)とズレるため、
  `docs/architecture.md` に決定事項として記録した上で、Airflow 3.x の `airflow standalone`
  コマンド(webserver/api-server・scheduler・dag-processor・triggerer を1プロセスに
  まとめる、公式ドキュメントが最初のローカル検証に推奨する方式)+ `LocalExecutor` を採用
- `docker/airflow/Dockerfile`:`apache/airflow:3.3.2-python3.11` をベースに、Airflowの
  constraints ファイルを使って `httpx`/`pandas`/`numpy`/`matplotlib`/`psycopg[binary]`/
  `python-dotenv` を追加インストール(SQLAlchemy等Airflow自身の依存とのバージョン衝突を
  回避するため、requirements には含めずAirflow側の既存バージョンに委ねた)
- `docker-compose.yml` に `airflow-postgres`(メタデータDB専用、アプリ用DBとは分離)と
  `airflow`(standalone、`LocalExecutor`、`DATABASE_URL`でアプリ用Postgresに接続、
  ポート8080でUI公開)を追加
- `docker-compose build airflow` → `docker-compose up -d airflow-postgres airflow` で
  起動。ビルドはAirflowベースイメージに既にpandas/httpx/numpy/psycopg/python-dotenvが
  含まれており、matplotlib関連のみ新規インストールで完了(依存衝突なし)
- `airflow dags list` でDAGがインポートエラーなく認識されることを確認 → `unpause` →
  `airflow dags trigger --logical-date 2024-06-01T00:00:00+00:00` で手動トリガー
- **バグ発見と修正**:最初のトリガーで `daily_pipeline.py` の `_target_date()` が
  `context["data_interval_start"]` を参照していたため、手動トリガー時は
  `--logical-date` を指定しても実際の対象日が「今日」になってしまう不具合を発見
  (Airflow 3.xでは手動トリガーのdata_intervalは既定でトリガー時刻になるため)。
  `logical_date` を参照するよう修正し(スケジュール実行では両者は一致するため実害なし)、
  再トリガーで `2024-06-05` として正しく処理されることを確認
- `airflow tasks states-for-dag-run` で3タスク(ingest_tokyo → process_tokyo →
  analyze_tokyo)すべて `success` であることを確認。タスクログ(JSON構造化ログ、
  `/opt/airflow/logs/dag_id=.../task_id=.../attempt=1.log`)で
  「ingested 24 raw rows」「processed 24 rows」「optimal R=0.30」を確認
  (Airflow 3.xでは `airflow tasks logs` CLIサブコマンドが廃止されており、ログファイルを
  直接catする必要があった)
- Airflow経由で書き込まれたデータが、アプリ用の共有Postgres(`raw_observations`)に
  実際に反映されていることを `psql` で確認 → DB接続設定(`DATABASE_URL`経由で
  `postgres` サービスに到達)が正しいことを実証
- `docker-compose up -d`(サービス指定なし)で `postgres` コンテナが再作成された際も
  named volume のおかげでデータが保持されることを確認
- 管理者UI初回パスワードの取得方法を確認:
  `docker exec urban-climate-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated`
  (Airflow 3.x standalone は `_AIRFLOW_WWW_USER_*` 環境変数ではなく、このファイルに
  自動生成パスワードを書き出す方式に変わっている)
- README §10 に Airflow起動の手順(オプション)を追記、§7 Phase 4 の3項目すべてに
  チェックを入れた。ruff / pytest は変更なし(33 passed)

**確認事項 / 未確認:**
- ローカル環境で `docker-compose up -d` のたびに Airflow standalone のパスワードが
  再生成される可能性がある(コンテナ再作成時は要再確認)
- Airflow UI (http://localhost:8080) 自体をブラウザで目視確認したのは作者側の想定
  (このセッションにはブラウザ操作手段がないため、CLI経由でのDAGトリガー・状態確認・
  ログ確認で代替した)

**次にやること(Phase 5 着手時):**
- Streamlit Dashboard(風配図、気温-風速散布図、R値最適化曲線)
- 実装量に応じて、クラウド(AWS/GCP)へのデプロイ(Phase 5後半、オプション)

---

## 2026-09-18 (続き6): Phase 5 前半 — Streamlit Dashboard

**やったこと:**
- デモ用データを充実化:東京の2024年1〜3月(冬季、季節風で風向・強風日にメリハリが出る
  期間)を ingestion → processing → analysis まで実行(2184時間分)。この期間だと
  Optimal R = 0.30(strong=3, weak=1, total=4)と、Phase 3検証時の穏やかな2日間データ
  (常に total=0)とは違う、意味のある結果が得られることを確認
- `src/dashboard/app.py`:Streamlit アプリ本体
  - サイドバー:都市選択、日付範囲、R探索範囲/step、強風/弱風閾値をすべてUIから調整可能
  - 風配図(matplotlib polar bar chart、8方位)、気温-風速散布図、風向別気温統計表、
    「不適日数 vs R」曲線 + 最適R値メトリクスを表示
  - 新規依存追加なし(matplotlib は Phase 3 で追加済み)。データ読み込み・R探索・
    風向統計はすべて Phase 2/3 で作った関数をそのまま再利用(ダッシュボード側での
    ロジック重複なし)
  - データが無い期間を選んだ場合は警告メッセージを表示(空実装ではなくフォールバック)
- `tests/test_dashboard.py`:4ケース追加(37 passed)。matplotlib描画を伴う関数は
  「例外を投げずFigureを返すこと」をスモークテストし、`wind_direction_counts()`の
  データ整形ロジック(固定順序へのreindex、0件方位の扱い)は個別に検証
- **UIなのでブラウザで実際に確認**(指示に従い、テストスイートだけでなく実機能を確認):
  - `run` スキルの手順に従い、まずプロジェクト固有の起動スキルの有無を確認(無し)→
    "browser-driven" パターンを採用
  - `chromium-cli` は未導入だったため、`npx playwright` でChromiumを一時取得し、
    スクリプトでヘッドレスブラウザ操作(スクリーンショット + コンソールエラー確認)
  - `streamlit run` でアプリ起動 → 初回スクリーンショットで**バグを発見**:
    都市セレクタの既定値が `sorted(CITY_COORDINATES)` の並び順で "nagoya"(アルファベット順
    先頭)になっており、かつ日付範囲の既定値(直近90日)には実データが無かったため、
    空データの警告メッセージが表示された(ロジック自体は正しく動作)
  - 都市="tokyo"・期間=2024-01-01〜2024-03-31 をUI操作(セレクトボックス入力、日付
    フィールドのreact-aria入力)で設定し直したところ、風配図(北/北西寄りの卓越風向が
    明確に可視化)・散布図・統計表・R曲線すべて正常描画、コンソールエラー0件、
    Streamlit例外ボックス0件を確認
  - 発見したバグ(既定都市がアルファベット順で決まってしまう)を修正:`tokyo` を
    デフォルト選択するよう `st.selectbox(..., index=...)` を指定。再起動して
    既定値が "tokyo" になったことを確認
  - 検証に使ったスクリーンショットを `docs/screenshots/dashboard_tokyo_2024q1.png` として
    リポジトリに保存(招聘資料転用時の参考用)
  - 検証用に一時取得した Playwright/Chromium はプロジェクトの依存には追加していない
    (スクラッチパッドで完結、`package.json` 等はリポジトリ外)
- README §7 Phase 5 の1項目目にチェック、Dashboard起動コマンドとスクリーンショットへの
  参照を追記。ruff / pytest 全通過(37 passed)

**確認事項 / 未確認:**
- Dashboard の既定の日付範囲(直近90日)は、実運用でスケジューラが毎日データを
  投入し続けている前提の設計。ローカル検証時のように過去の任意期間を見たい場合は
  日付を手動で変更する必要がある(仕様として妥当と判断、UIで明示的に警告も出る)
- Phase 5 の残り2項目(クラウドデプロイ、招聘向けREADME整備)は未着手。クラウドデプロイは
  実際の費用・認証情報が絡むため、着手前に作者確認が必要

**次にやること(Phase 5 後半、要確認):**
- クラウド(AWS or GCP)デプロイ:DBをRDS/Cloud SQL等マネージドサービスに、パイプラインを
  ECS/Cloud Runで実行 — 実費用・認証情報が発生するため着手前に方針確認
- README冒頭を日本語/英語の招聘向け展示版に書き換え、現在の開発仕様書部分は
  `docs/DEVELOPMENT.md` に退避(README冒頭のnoteに記載済みの計画)

**2026-09-18 作者確認結果:** クラウドデプロイは当面スキップ(費用・認証情報が絡むため)。
招聘向けREADME整備は今回は着手リクエストなし。Phase 0〜4 は完全達成、Phase 5 は
Dashboard(1/3項目)のみ完了した状態でいったん区切り。両タスクとも再開時はこのログの
「次にやること」を参照

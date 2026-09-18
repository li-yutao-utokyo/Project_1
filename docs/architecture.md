# アーキテクチャ設計決定記録 (Architecture Decision Records)

技術選定を変更する場合(例:Airflow をやめて別の軽量ツールに変更する等)は、
コードを変更する前にここへ決定理由を記録する。

## 決定ログ

### 2026-09-18: プロジェクト初期化
- README.md の仕様に沿って Phase 0(プロジェクトスキャフォールド)を実施
- パッケージ管理は `pyproject.toml`(PEP 621)+ `pip`。ローカルに `uv`/`poetry` が
  未導入のため、当面は `pip install -e ".[dev]"` を利用する。導入可能になり次第 `uv` に切替可
- DB は PostgreSQL 15 を Docker Compose で起動
- Lint は ruff、テストは pytest、CI は GitHub Actions

### 2026-09-18: Airflow 3.x を採用、CeleryExecutor ではなく standalone/LocalExecutor 構成に
- README §4 の想定は「webserver + scheduler + postgres metadata db」という軽量構成だったが、
  現行の Airflow 最新安定版は 3.3.2 であり、公式の docker-compose クイックスタートは
  CeleryExecutor 前提(redis, worker, triggerer, dag-processor, api-server, flower等
  7サービス以上、RAM 4〜8GB推奨)に変わっていた
- ポートフォリオ用途のローカル環境としては明らかにオーバースペックなため、代わりに
  Airflow 3.x の `airflow standalone` コマンド(webserver/api-server・scheduler・
  dag-processor・triggerer を1プロセスにまとめて起動する、公式ドキュメントが
  「最初のローカル動作確認に最適」と案内している方式)を採用
- メタデータDBは README の想定通り独立した PostgreSQL コンテナ(`airflow-postgres`)を使用。
  Executor は `LocalExecutor`(Celery/Redis 不要)
- DAG から自作モジュール(`src.ingestion.run` 等)をインポートできるよう、Airflow用に
  カスタムDockerイメージ(`docker/airflow/Dockerfile`)をビルドし、Airflowの
  constraints ファイルを使って依存関係の競合(特に SQLAlchemy)を回避
- 結果としてサービス数は当初想定(3つ)に近い、`postgres`(アプリ用)+ `airflow-postgres`
  (メタデータ用)+ `airflow`(standalone、1コンテナ)の3コンテナ構成に収まった

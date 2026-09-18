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

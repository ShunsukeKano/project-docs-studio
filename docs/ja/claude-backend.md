# backend

FastAPI（src レイアウト: `src/app/`）、SQLAlchemy 2.0（async）、Alembic、PostgreSQL。パッケージ管理は uv。
共通のルール（Spec Kit の進め方、`docs/`、言語の方針）は、ルートの `../CLAUDE.md` に従う。

> これは、`backend/CLAUDE.md`（英語）の日本語版。英語版を変更したら、同じ変更でこのファイルも更新する。

- レイヤー: router（HTTP のみ）→ service（業務ルール、状態遷移、トランザクション。コミットするのはこの層だけ）→ repository（薄く。SQL のみ）。service で `HTTPException` を投げない。
- 入出力スキーマは Create、Update、Read で分け、すべてのレスポンスは `response_model` を通す。すべてのルートに `operation_id` を明示し、`specs/001-docs-studio/contracts/openapi.yaml` の camelCase にする。
- エラーは1つの形にそろえる: `{"error": {"code", "message", "details"}}`。
- DB は PostgreSQL: 本番は Cloud SQL、ローカルは Docker Compose で起動する PostgreSQL 17（ルートの `compose.yaml` の `db`、`db-test`）。接続先は環境変数 `DATABASE_URL` で選ぶので、Auth Proxy 経由の Cloud SQL も使える。
- テストは `tests/`（`src` の外）に置く。**テストは、名前が `_test` で終わる専用の DB だけを使い**、`TEST_DATABASE_URL` から読み、それ以外の DB に対しては実行を拒否する。ホストはローカル（`localhost` または `127.0.0.1`）でなければならない。唯一の例外は `TEST_DATABASE_EXTRA_HOSTS` で明示したホストで、Compose の `test` コンテナが `db-test` に使う。名前のルールは決して緩めない。
- 書き手のルートは Basic 認証が要る。明示的な設定 `BASIC_AUTH_ENABLED` で切り替え、本番では必須（なければアプリは起動しない）、ローカルの実行では既定でオフ（起動時に警告を出す）。`BASIC_AUTH_USER` と `BASIC_AUTH_PASSWORD` は環境変数から読み、コードには書かず、`secrets.compare_digest` で比べる。公開 API（`/api/v1/public/*`）には要らない。
- DDL は `db-automation-apply/` に、番号つきの SQL ファイル（`001_schema.sql`）として保存する。その SQL が正で、`docs/nextjs-fastapi-architecture.html` の 7 節はそれに従う。適用済みのファイルは編集せず、変更は新しい番号のファイルで行う。
- マイグレーション: `uv run alembic upgrade head`。
- `Dockerfile` と `cloudbuild.yaml` はこのフォルダにある。ローカルの実行では Docker Compose が `Dockerfile` をビルドし（リポジトリのルートで `docker compose up --build`）、Cloud Run 用には Cloud Build がビルドする（優先度は低い）。

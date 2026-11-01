# backend

FastAPI（src レイアウト: `src/app/`）、SQLAlchemy 2.0（async）、Alembic、PostgreSQL。パッケージ管理は uv。
共通のルール（Spec Kit の進め方、`docs/`、言語の方針）は、ルートの `../CLAUDE.md` に従う。

> これは、`backend/CLAUDE.md`（英語）の日本語版。英語版を変更したら、同じ変更でこのファイルも更新する。

- レイヤー: router（HTTP のみ）→ service（業務ルール、状態遷移、トランザクション。コミットするのはこの層だけ）→ repository（薄く。SQL のみ）。service で `HTTPException` を投げない。
- 入出力スキーマは Create、Update、Read で分け、すべてのレスポンスは `response_model` を通す。すべてのルートに `operation_id` を明示し、`specs/001-docs-studio/contracts/openapi.yaml` の camelCase にする。
- エラーは1つの形にそろえる: `{"error": {"code", "message", "details"}}`。
- DB は PostgreSQL: 本番は Cloud SQL、ローカルは Docker Compose で起動する PostgreSQL 17（ルートの `compose.yaml` の `db`、`db-test`）。接続先は環境変数 `DATABASE_URL` で選ぶので、Auth Proxy 経由の Cloud SQL も使える。
- テストは `tests/`（`src` の外）に置く。**テストは、名前が `_test` で終わる専用の DB だけを使い**、`TEST_DATABASE_URL` から読み、それ以外の DB に対しては実行を拒否する。ホストはローカル（`localhost` または `127.0.0.1`）でなければならない。唯一の例外は `TEST_DATABASE_EXTRA_HOSTS` で明示したホストで、Compose の `test` コンテナが `db-test` に使う。名前のルールは決して緩めない。
- 書き手のルートは Basic 認証が要る。明示的な設定 `BASIC_AUTH_ENABLED` で切り替え、本番では必須（なければアプリは起動しない）、ローカルの実行では既定でオフ（起動時に警告を出す）。`BASIC_AUTH_USER` と `BASIC_AUTH_PASSWORD` は環境変数から読み、コードには書かず、`secrets.compare_digest` で比べる。公開 API（`/api/v1/public/*`）には要らない。設定は、ログイン情報の前後の空白を取り除く（コンソールで保存したシークレットは、末尾に改行が付くことがある）。
- 任意の AI の追加機能（`src/app/domains/ai/`。ルートは `GET /api/v1/ai/status` と `POST /api/v1/ai/draft`）: `AI_ENABLED` が true でない限りオフで、キーなしでオンにすると、サービスは起動を拒否する。記事の本文を server-sent events として順に返し（`delta`、そのあと `done` か `error`。最初の断片より前の失敗は、通常の 502 `ai_unavailable`）、返すのは提案だけで（DB には触れない）、制限がある（入力の長さ、出力のトークン上限、1インスタンスあたり1分に5回（429））。モデルは `ANTHROPIC_MODEL`（既定は `claude-sonnet-4-6`）で、prefill もサンプリングのパラメータも送らない。キーは環境変数（Google Cloud では Secret Manager）から渡し、ログには出さない。**テストは API を呼ばない**（偽のジェネレーターを `app.state` に差し込む）。`tests/conftest.py` が AI の設定を強制的にオフにするので、開発者の `.env` がテストで AI をオンにすることはない。
- `app.openapi` は `main.py` の `_tidy_openapi` で包んでいる: 検証エラーは本物のエラーエンベロープで説明し、書き手の操作に Basic のスキームを宣言する。ルートを変えたら、`backend/openapi.json` を再生成する（`make check-api`）。
- DDL は `db-automation-apply/` に、番号つきの SQL ファイル（`001_schema.sql`）として保存する。その SQL が正で、`docs/nextjs-fastapi-architecture.html` の 7 節はそれに従う。適用済みのファイルは編集せず、変更は新しい番号のファイルで行う。
- マイグレーション: `uv run alembic upgrade head`。Google Cloud では、手動のビルド（`cloudbuild.yaml`）が Cloud Run Job で実行する。GitHub からの自動デプロイは実行しないので、スキーマを変えたあとは、Job を手動で実行する（`gcloud run jobs execute docs-studio-api-migrate --region asia-northeast1`）。
- `Dockerfile` と `cloudbuild.yaml` はこのフォルダにある。ローカルの実行では Docker Compose が `Dockerfile` をビルドし（リポジトリのルートで `docker compose up --build`）、Cloud Run 用には Cloud Build がビルドする（優先度は低い）。

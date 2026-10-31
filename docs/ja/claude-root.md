# Northbeam Docs Studio

社内ライター向けの記事管理（API + 最小UI）と、公開済み記事だけを見られる公開ドキュメントサイト。すべてを1つのリポジトリで管理する。

> これは、ルートの `CLAUDE.md`（英語）の日本語版。英語版を変更したら、同じ変更でこのファイルも更新する。

| フォルダ | 内容 |
|---|---|
| `backend/` | FastAPI（src レイアウト）と PostgreSQL。詳細は `backend/CLAUDE.md` |
| `frontend/` | Next.js 16（App Router）。詳細は `frontend/CLAUDE.md` |
| `docs/` | 要件と設計資料（フロントとバックで共通）。Canadian English。日本語版は `docs/ja/` |
| `specs/` | Spec Kit の成果物。`specs/001-docs-studio/` に `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`、`tasks.md` がある |
| `README.md` | 評価者向け: デプロイ先のアドレス、実行方法、データモデルとその理由、トレードオフ、機能の状況の表 |

このプロジェクトのルールは `.specify/memory/constitution.md` にある。最初に読む。

## 言語の方針
- **`docs/ja/` の外は、すべて Canadian English で書く**（例: behaviour、colour、grey、defence、organize、analyze）。対象は、`docs/` の文書、specs、README、コード、コードと設定ファイルのコメント、`CLAUDE.md` のファイル。
- **日本語は `docs/ja/` にだけ置く。** `docs/` のすべての文書には、同じファイル名の日本語版が `docs/ja/` にある。英語版を変更したら、同じ変更で日本語版も更新する（片方だけ変えない）。
- `CLAUDE.md` の日本語版は、`docs/ja/claude-root.md`、`docs/ja/claude-backend.md`、`docs/ja/claude-frontend.md`。
- 確認: `ls docs docs/ja`（同じファイル名がそろっている）と、`grep -rlP "[\x{3040}-\x{30ff}\x{4e00}-\x{9fff}]" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=ja .`（何も出力されない）。
- 固有名詞（Northbeam Docs Studio など）は文中に残してよいが、フォルダ名・ファイル名には使わない。

## 参照ドキュメント（`docs/`）
作業の前に、関係するものを読む。`docs/` と `specs/` が食い違ったら、確定仕様である `specs/` に従い、`docs/` を直す。

| ファイル | 内容 | いつ読むか |
|---|---|---|
| `docs/requirements.md`（日本語版: `docs/ja/requirements.md`） | 課題から抽出した要件: 機能要件 FR、不変条件 INV、制約、提出物、すべての判断（13 節） | `/speckit-specify` の入力として。ルールやテストの根拠を確認するとき |
| `docs/nextjs-fastapi-architecture.html`（日本語版: `docs/ja/`） | 構成、レイヤー、DB（DDL と ER 図）、状態遷移、API の案、Cloud Run の構成、テスト計画の図 | `/speckit-plan`、実装、DB の作業のとき |

## 進め方: Spec Kit（仕様が先）
新機能や大きな変更は、この順で進め、各段階の成果物を次に進む前にコミットする。履歴で、仕様が実装より先だと分かるようにするため。
1. `/speckit-constitution`: プロジェクトの原則（最初の1回）
2. `/speckit-specify`: `spec.md`（要件、不変条件、エッジケース）
3. `/speckit-clarify`（任意）: 曖昧な点の洗い出し
4. `/speckit-plan`: `plan.md` と設計の成果物（データモデル、API の形、楽観的排他制御の方式などの判断）
5. `/speckit-tasks`: `tasks.md`（ビルド順のタスク）
6. `/speckit-analyze`（任意）: 3つの成果物の整合チェック
7. `/speckit-implement`: `tasks.md` に沿って実装

- **最初のコミットの順序**: (1) ツール類（`.specify/`、`.claude/`、`CLAUDE.md`、`.gitignore`）、`docs/`、`README.md`、`specs/001-docs-studio/` をまとめて、(2) それ以外（`backend/` と `frontend/` の下の DDL、Dockerfile、YAML、コード）。`spec.md` より前に、`backend/` と `frontend/` の下のもの（各 `CLAUDE.md` を除く）をコミットしない。`scripts/check-spec-first.sh`（タスク T002）で確認する。
- 実装中に仕様を変える必要が出たら、コードより先に spec、plan、tasks を更新する。
- 履歴の書き換えはしない（squash、rebase、force push をしない）。
- API を変更したら、`backend/openapi.json` を更新し、`frontend` の型を再生成する。
- 小さな修正やバグ修正に、spec は要らない。

## ローカルでの実行（Docker Compose）
新規チェックアウトから、`cp .env.example .env` と `docker compose up --build` で、システム全体（PostgreSQL、スキーマ、API、Web アプリ）が起動する。必要なのは Docker だけ。`make setup`、`make dev`、`make test` は、アプリをコンテナなしで、Compose の DB か、`DATABASE_URL` で指定した任意の PostgreSQL に対して動かす。`make test-docker` は、Docker だけでバックエンドのテストをコンテナの中で実行する。書き手のログインは、ローカルの実行では既定でオフ（`BASIC_AUTH_ENABLED`。本番では常にオン）。ルートの `compose.yaml` は、短いセットアップコマンドの一部なので、優先度は低くない。

## デプロイ（GCP Cloud Run）
優先度は低く、ビルドして実行するまでは検証済みではない。各サービスは、自分のフォルダ（`Dockerfile` と `cloudbuild.yaml` がある）からビルドする。

```bash
gcloud builds submit backend --config backend/cloudbuild.yaml
gcloud builds submit frontend --config frontend/cloudbuild.yaml
```

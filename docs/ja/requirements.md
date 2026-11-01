# Northbeam Docs Studio 要件

## 1. 目的

- 社内ライター向けの記事管理サービス（API + 最小限UI）と、公開済み記事だけを見られる公開サイトを作る。
- 評価の中心は**データの整合性とライフサイクルの正しさ**。
- コア機能を正しく完成させる。未実装分は README に「何が未実装か」「どう実装する予定だったか」を書く。

## 2. 前提・用語

| 用語 | 意味 |
|---|---|
| 下書き（Draft） | `articles` 行の `draft_*` 列に持つ編集中の内容。公開側からは見えない |
| スナップショット / バージョン | 公開時に作る不変の記録（`article_versions`） |
| 公開中バージョン | `current_published_version_id` が指すバージョン |
| 状態（status） | `draft`（**未公開**: 一度も公開していない）/ `published` / `unpublished`（公開停止） |
| 保護されたバージョン | `current_published_version_id` が指すバージョン。記事の状態にかかわらず（公開停止後も）削除できない |

- 書き手は単一のユーザー（Basic 認証で保護する）。公開側は未認証の一般ユーザー。

## 3. 機能要件

### 3.1 ライター側

| ID | 要件 |
|---|---|
| FR-1 | 記事を作成できる。入力は title、slug、本文（Markdown）、tags。slug が使われていれば、末尾に番号を付け、実際に保存した slug を返す（13 節 U15） |
| FR-2 | 既存記事の下書きを編集できる |
| FR-3 | **Publish**: 現在の下書きを公開できる（詳細は 3.3） |
| FR-4 | **Unpublish**: 記事の公開を停止できる（詳細は 3.4） |
| FR-5 | バージョン履歴を新しい順に一覧できる |
| FR-6 | 特定バージョンの内容を表示できる |
| FR-7 | **Restore**: 過去バージョンの内容を下書きに復元できる（詳細は 3.5） |
| FR-8 | 保護されていないバージョンを削除できる。保護されたバージョンの削除は API が拒否する（詳細は 3.6） |
| FR-9 | 下書きの同時編集で、古いデータによる上書きを検知する（詳細は 4 の INV-5） |
| FR-13 | 書き手側（`/studio` の画面と書き手の API）は、有効にしたとき **Basic 認証**で保護する。制御するのは、明示的な1つの設定 `BASIC_AUTH_ENABLED` で、**本番では必ずオン**にし、オフにしてよいのはローカルでの実行だけ。認証情報は環境変数（`BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD`）で渡し、コードには書かない。有効なときは、GET を含むすべての書き手のルートで、検索や入力検証より**前**に認証を確認し、`WWW-Authenticate: Basic` と標準のエラー形式（コード `unauthorized`）で 401 を返す。認証が有効で、どちらかの認証情報が空なら、サービスは起動しない。本番では、認証が有効でなければ起動しない。オフのときは、起動時に警告をはっきりログに出す。公開サイト、公開用 API（`/api/v1/public/*`）、`GET /healthz` は認証なし。書き手のレスポンスには `Cache-Control: no-store` を付ける。本番では `/docs` と `/openapi.json` を無効にする。課題文にない追加（13 節 R1、R17） |
| FR-14 | 書き手は、すべての記事（どの状態でも）を一覧できる。表示は下書きの title、slug、status、`draft_version`、`updated_at`。`updated_at` の新しい順（同じなら `id` の降順）、最大 100 件、任意の `status` フィルタ付き（未知の値は 422） |
| FR-15 | 編集フォームに、公開サイトと同じレンダラーとサニタイズのルール（U7）を使った、Markdown のプレビューを表示する |
| FR-16 | `version_conflict` を受け取ったとき、編集フォームは未送信の入力を保持し、サーバー側が変わったことを示して、最新を読み込み直すか、新しい `draft_version` で入力を再送するかを選ばせる |
| FR-17 | **（任意の追加機能。課題の評価範囲の外。コアの作業が済んだあとに実装した。13 節 R15。仕様書では User Story 9 と FR-042）** 書き手は、すでに入力したタイトル、タグ、メモから、ボタン1つ（「Generate with AI」）で、Claude に記事の本文を書かせられる。文章は、書かれるのに合わせて本文欄に**少しずつ**表示され（Stop ボタンで、そこまでの分を残して止められる）、**提案としてのみ**扱う。通常の下書き保存（`expected_draft_version` つき）で保存するまで何も保存されず、書き手が Publish するまで何も公開されない。ボタンは常に表示し、機能がオフのときは、案内つきで無効にする。`AI_ENABLED` を設定しない限り、この機能は無効（デプロイ先では有効にしてある）で、前払いした Claude API のクレジットが残っている間だけ動く |

### 3.2 公開側（未認証）

| ID | 要件 |
|---|---|
| FR-10 | 公開済み記事の一覧を見られる（公開済みのものだけ。一度も公開されていない記事と、公開停止中の記事は、一覧に含めない）。表示項目は title、tags、公開日（初回公開日 `published_at`）。再公開されている記事（公開中スナップショットの `version_number` が 2 以上）は、更新日（公開中スナップショットの作成日時）も併記する。並び順は `published_at` の降順、同じなら `id` の降順。最大 100 件（`limit` / `offset`） |
| FR-11 | 公開済み記事の詳細を見られる。**内容は必ず現在の公開中スナップショットから取得**し、下書きは使わない（title と tags もスナップショットから取る。公開後に下書きを編集しても、見える内容は最後に公開したもの）。公開側のレスポンスは専用のスキーマ（許可リスト）にする: slug、title、tags、body（詳細のみ）、`published_at`、公開中スナップショットの作成日時。`draft_*`、`draft_version`、`articles.updated_at`、`status`、内部 ID は含めない |
| FR-12 | 一度も公開されていない記事、公開停止中の記事、存在しない slug（形式が不正なものを含む）へのアクセスは、いずれも同じ **HTTP 404**（同じ本文）。エラー内容や下書きの中身を出さない |

### 3.3 Publish の動作

以下は**1つのトランザクション**で、この順に行う。

1. 記事の行をロックする（`SELECT … FOR UPDATE`）。記事がなければ 404。
2. リクエストの `expected_draft_version`（**必須**: 書き手が見ていた版）と `draft_version` を比べる。違えば 409 `version_conflict` で拒否し、何も変えない（見ていない下書きを公開しない）。
3. 下書きの title と body が空でないことを確認する。空なら 422 `empty_content`。
4. **冪等チェック（U8）**: 公開中スナップショットがあり、下書きの title、body、tags がそれと同じなら、スナップショットを作らず、`published_at`、参照、`draft_version` も変えない。状態が `unpublished` なら `published` に戻す。公開中の版を 200 で返す。
5. そうでなければ、下書きから**不変の新しいスナップショット**を作る。番号は記事ごとのカウンタ（`last_version_number + 1`。13 節 R12）で付ける。status を `published` にし、`current_published_version_id` を新しいスナップショットに更新し、`published_at` は**まだ空のときだけ**（初回公開）設定し、`draft_version` を 1 増やす。新しい版を 201 で返す。

`published_at` の設定も含めて 1 つのトランザクションなので、公開済みで `published_at` が空という状態は作らない（INV-2）。時刻はトランザクション開始時ではなく、各文の実行時刻（`clock_timestamp()`）を使う。ロック待ちをしたリクエストが、前の版より早い時刻にならないようにするため。

すべての書き手のリクエストでの確認の順序: 認証（401）→ 記事の存在（404）→ 入力の形とフィールドの検証（422）→ `expected_draft_version`（409）→ 業務ルール（`empty_content` の 422、`not_published` の 409 など）。

`draft_version` が増えるのは、編集、Restore、スナップショットを作る Publish。Unpublish、版の削除、冪等な Publish では変わらない。`expected_draft_version` が必須なのは、編集、Restore、Publish だけ。Unpublish と版の削除では不要。

### 3.4 Unpublish の動作

- 公開側から見えなくする（status を `unpublished` にする）。
- 最後に公開したスナップショットを**削除しない**。`published_at` と参照も**保持する**。
- ステータス変更のみで、コンテンツと `draft_version` は変更しない。
- 記事が `published` でなければ 409 `not_published`。
- 記事の行ロックを取るので、同時の Publish と Unpublish は直列化され、どちらの順になっても正しい結果とする。

### 3.5 Restore の動作

- 選んだ過去スナップショットの title、body、tags を、**1つの文で現在の下書きにコピーするだけ**。slug には触れない。
- Restore は、記事がどの状態（未公開、公開中、公開停止）でも、`status`、`current_published_version_id`、`published_at` を**一切変えない**。公開もしない。
- リクエストには `expected_draft_version` を**必須**で含める。不一致なら 409。成功したら `draft_version` を増やす。
- 記事にない版の番号は 404 で、何も変えない。
- 新しいスナップショットは作らない。既存スナップショットは変更・削除しない。

### 3.6 版の削除の動作

- **保護されたバージョン**は、`current_published_version_id` が指す版。記事がどの状態でも、公開停止後も同じ。それ以外の版は削除できる。
- 保護された版の削除は 409 `version_is_live`。記事にない版の番号は 404。削除に成功したら 204。
- 削除は、Publish、Unpublish、Restore と同じ記事の行ロックを取る。そのため、Publish と競合した削除で、参照が宙に浮いたり 500 になったりしない。複合外部キーは最後の砦で、それでも発動したとき（SQLSTATE 23503）は同じ 409 に変換する。
- 公開中の版は常に最大番号で、削除できないので、一度公開した記事の履歴が空になることはない。
- `expected_draft_version` は不要。

## 4. 不変条件（最重要）

| ID | 不変条件 | テストで確認すること |
|---|---|---|
| INV-1 | 公開済みスナップショットは、公開後に変更されない。編集は必ず下書き経由 | 公開後に下書きを編集しても、スナップショットと公開側の表示が変わらない。スナップショットを更新する API が存在せず、**さらに DB のトリガーが `article_versions` への UPDATE をすべて拒否する**（生の UPDATE を試して失敗することをテストする） |
| INV-2 | **Publish は原子的**。次の不整合が起きない: 公開済みなのに参照先がない / 公開済みなのに古い参照 / 未公開なのに新しい公開バージョンだけ設定されている。クラッシュや同時リクエストでも維持する | Publish の各手順で失敗を注入（パラメータ化）すると、全体がロールバックされる: 新しい版の行はなく、`status`、`current_published_version_id`、`published_at`、`draft_version`、`last_version_number` も変わらない。同じ `expected_draft_version` での同時 Publish 2 件（別々の接続）: ちょうど 1 件が 201、もう 1 件が 409 で、5xx は出ない。version_number は連続し、参照は最新の版を指す。`status='published'` で参照または `published_at` が NULL になる手書きの UPDATE を、DB の CHECK が拒否する |
| INV-3 | 保護されたバージョン（参照が指す版。公開停止中も同じ）は削除できない（UIで隠すだけでは不可。**API で拒否**） | v1 を Publish → Unpublish → v1 を削除すると 409 `version_is_live` で、行は残る。v2 を Publish したあとで v1 を削除すると 204。Publish と競合した削除で、5xx が出ず、参照が宙に浮かない |
| INV-4 | Restore は履歴を壊さない。スナップショットの変更・新規作成・削除をしない | Restore の前後で、その記事の `article_versions` の**全行・全列**が同一で、`status`、`current_published_version_id`、`published_at` も変わらない。変わるのは下書きの列と `draft_version` だけ。存在しない版番号の Restore は 404 で、何も変わらない |
| INV-5 | **楽観的排他制御**。古いデータに基づく更新は明確なエラーで拒否し、新しい編集を黙って上書きしない | 古い `draft_version` での更新は 409 で、何も変わらない。`draft_version` は、成功した編集、Restore、スナップショットを作る Publish のたびに増える。同じ `expected_draft_version` での編集と Restore: ちょうど 1 件が成功する。コミット済みの編集より古い `expected_draft_version` での Publish は 409 で、スナップショットを作らない |
| INV-6 | Unpublish 後も公開履歴を保持する。スナップショットと `published_at` は消えない | Unpublish 後もバージョン一覧・内容・`published_at` が残る。再公開しても `published_at` は初回のまま |

すべての不変条件（INV-1〜INV-6）に、自動テストが少なくとも1つあり、`make test` がすべてを実行する。

## 5. 制約

| 項目 | 内容 |
|---|---|
| 技術 | 言語・フレームワークは自由 |
| 永続化 | 実DB必須（**PostgreSQL を採用**）。インメモリのみは不可。再起動してもデータが残ること。ローカルでは Docker Compose で起動する PostgreSQL を使う。`DATABASE_URL` で、別の DB（例: Auth Proxy 経由の Cloud SQL）にも切り替えられる |
| 実行 | 新規チェックアウトから、**`docker compose up --build` ですべてが起動する**（PostgreSQL、スキーマ、API、Web アプリ）。必要なのは Docker だけ。`make setup`、`make dev`、`make test` は、アプリをコンテナなしで、Compose の DB か、`DATABASE_URL` で指定した任意の PostgreSQL に対して動かす。評価者は、このローカルでの実行か、デプロイ済みの Cloud Run のサイトのどちらを使ってもよい（13 節 U14） |
| データベース | ローカル開発は専用の DB（`<name>_dev` と `<name>_test`）を使い、本番 DB は使わない。テストは `TEST_DATABASE_URL` を読み、最初の文を実行する前に、DB 名が `_test` で終わり、ホストが `localhost` か `127.0.0.1`（`/cloudsql` のソケットは不可）でなければ中止する。この防御には単体テストを付ける。テストは、テストごとに、`SET LOCAL docs.allow_reset = 'on'` を実行したトランザクションの中で `TRUNCATE` してデータを戻し（スナップショットの表の `TRUNCATE` を止める守りが許すのは、このときだけ）、同時実行のテストは本物の別接続（プールは 2 以上）。`compose.yaml` が、開発用の `db` とテスト用の `db-test` の両方を提供するを使う |
| テスト | 自動テストは**必須**で、任意ではない。単一コマンド（`make test`。Docker だけのマシンでは `make test-docker`、つまり `docker compose --profile test run --rm test`）で実行できること。バックエンドのテスト、OpenAPI の差分チェック、フロントの型チェック・lint・Markdown サニタイズのテストを実行する。INV-1〜INV-6 の各不変条件に、自動テストが少なくとも1つ必要（4 節）。テストのない不変条件は欠陥とみなす |
| テスト対象 | Publish / Unpublish / Restore / Delete / Concurrency のライフサイクル不変条件。**UIテストより優先** |

## 6. 対象外（実装しない）

認証・ロール・マルチテナント（※書き手側の Basic 認証だけは追加で入れる。13 節 R1）/ リッチMarkdown拡張・WYSIWYG（通常の入力欄とプレビューで可）/ ファイル・メディアのアップロード / 検索 / 大規模ページネーション / キャッシュ層 / 本番デプロイ / CI/CD / IaC。

> 記事そのものの削除も実装しない（13 節 U9）。

> 本番デプロイ・CI/CD・IaC は課題上の対象外だが、実行基盤は GCP Cloud Run と決めたため、必要な設定ファイルは用意する（12 節）。優先度はコア機能の完成より低く、未完成でも課題の評価には影響しない。例外は、ローカル用の `compose.yaml` で、短いセットアップコマンドの一部なので、README より前に仕上げる。

## 7. 最小UI

記事編集フォーム、記事一覧、バージョン履歴パネル。それに公開側の一覧と詳細。

インターフェースは、**Tailwind CSS で作る、ミニマルでスタイリッシュな見た目**にする: 落ち着いた色の配色に、アクセントの色は1色、システムフォント、ゆったりした余白、共通の小さな部品（ボタン、入力欄、タグ、状態バッジ、空の状態）、見えるキーボードフォーカス、スマートフォンからデスクトップの幅まで崩れないレイアウト。見た目の仕上げは、機能とそのテストが**済んだあとに**、決めた時間の枠の中で行い、コア機能を遅らせない（見た目は評価されない）。

## 8. 提出物

1. **Git リポジトリ**: 動くコードに加え、**仕様が実装より先（または並行）に作られたと分かるコミット履歴**。最初のコミットには、ツール類（`.specify/`、`.claude/`、`CLAUDE.md`）、`docs/`、`specs/001-docs-studio/`（`spec.md`、`plan.md`、`tasks.md`）だけを入れる。`spec.md` をコミットするまで、`backend/` と `frontend/` の下のもの（コード、`db-automation-apply/` の DDL、Dockerfile、YAML）は一切コミットしない。例外は各 `CLAUDE.md` だけ。履歴の書き換え（squash・rebase など）はしない。
   - **検証方法:** `git log --reverse --diff-filter=A --name-only --format='commit %h' -- specs/001-docs-studio/spec.md backend frontend ':(exclude)backend/CLAUDE.md' ':(exclude)frontend/CLAUDE.md'` が、ファイルが最初に追加された順に並べる。`specs/001-docs-studio/spec.md` が、`backend/` と `frontend/` の下のどのファイルよりも先に現れなければならない。スクリプト `scripts/check-spec-first.sh`（tasks で作る）が、この確認を行い、順序が違えば失敗する。
2. **SDD 成果物**: Spec Kit の規約どおり `specs/001-docs-studio/` に `spec.md`、`plan.md`、`tasks.md`。
   - spec: 要件と不変条件を自分の言葉で整理。エッジケースとして Publish の原子性、公開中バージョンの削除防止、非破壊の復元、同時編集を必ず含める。
   - plan: データモデル、API 設計、楽観的排他制御などの設計判断。
   - tasks: 実装順のタスク分解。
3. **README.md**: 最初に評価者向けの手順（デプロイ済みの Cloud Run の URL。Basic 認証の認証情報はリポジトリの外で共有する）を書き、続けて、ローカルでの実行方法 / データモデルの説明 / そのモデルを選んだ理由 / 時間制約での設計上のトレードオフ（1段落以上）/ 時間があれば行う改善 / 機能ごとの状況（完了・一部・未実装）の表と、未実装のものをどう作る予定だったか。Cloud Run 用のファイルは任意で、評価対象の範囲では検証していないことも書く。
4. **自動テスト**: 単一コマンドで実行できるもの。

## 9. 推奨データモデル（必須ではない）

`articles`: id、slug（一意）、status（draft/published/unpublished）、draft_title、draft_body、draft_tags、draft_version（楽観的排他制御用）、current_published_version_id（NULL可）、published_at（NULL可）、created_at、updated_at

`article_versions`: id、article_id（外部キー）、version_number（記事ごとに一意）、title、body、tags、created_at

> 下書きと公開内容を**同じ行に混ぜない**のが要点。

## 10. 任意の追加機能（最大1〜2個）

採用するのは **3. Slug 重複処理**（13 節 U15）と **4. Idempotent Publish**（13 節 U8）の2つ。Save as Version と Diff View は採用しない。

1. Save as Version: 公開せずに下書きをバージョンとして保存する
2. Diff View: 下書きと過去版、または2つの版を比較する
3. Slug 重複処理: 重複時に末尾へ番号を付けて一意にする
4. Idempotent Publish: 下書きが変わっていない状態の再 Publish で、同一内容の重複スナップショットを作らない

## 11. 仕様化の前に決める点（課題文に明記なし）

> 以下の「仮の方針」のうち、13 節（U1〜U15）で決めたものは 13 節の決定が優先する。

| 論点 | 課題文の状況 | 仮の方針（spec/plan で確定する） |
|---|---|---|
| 古い更新のエラーコード | 「明確なエラー」としか書かれていない | 409 Conflict + 現在の `draft_version` を返す |
| Unpublish → 再 Publish | 明記なし | 可能。status を `published` に戻し、`published_at` は維持 |
| 公開中でない版の削除後の version_number | 明記なし | **再利用しない**。記事ごとのカウンタ列（`last_version_number`）を、行ロックの下で増やすため、どの版が存在するかに依存しない（13 節 R12） |
| Unpublish 中に、元公開中だった版を削除できるか | 「公開中の記事が参照する版」は削除不可。公開停止後の参照は未規定 | 参照は保持される（INV-6 の「最後に公開した内容を確認できる」を守るため）ので、**削除不可**とする |
| 一度も公開していない記事（status=draft）の Publish | 可能 | 可能（これが初回公開） |
| slug の変更可否 | 明記なし | **作成後は変更不可**（U3）。PATCH は slug を受け付けない。未知のフィールドは 422 |
| 他の記事の slug と重複 | 一意制約。重複時の挙動は任意機能 | 採用（U15）: 末尾に番号を付け、保存した slug を返す。やり直しをすべて競合で失うときだけ 409 `slug_conflict` |

### 判断済みの事項

| 論点 | 判断 |
|---|---|
| Publish・Restore の `draft_version` | **必須**。不一致は 409 |
| 公開側の日付 | 原則は初回公開日（`published_at`）。再公開済みの記事は更新日も併記。更新日は**公開中スナップショットの作成日時**を使う（`articles.updated_at` は下書き編集でも変わるため使わない） |
| 認証 | 書き手側だけに **Basic 認証**を掛ける（課題文では認証は Out of Scope だが、デプロイ先で誰でも編集・公開・削除できてしまうのを避けるための追加）。`BASIC_AUTH_ENABLED` で制御し、**本番では必須**、**ローカルでの実行では既定でオフ**（13 節 R17）。公開サイトと公開用 API は認証なし |
| API の公開範囲 | 公開用 API（`/api/v1/public/*`）は**無認証**で公開。書き手の API は **Basic 認証必須**。ID トークンなどの処理は実装しない |

## 12. 実行・デプロイ環境（採用方針）

課題文は技術選定を自由としているため、次を採用する。

| 項目 | 採用 |
|---|---|
| DB | **PostgreSQL**: ローカルは Docker Compose の PostgreSQL 17（開発用の `db`、テスト用の `db-test`）、本番は **Cloud SQL for PostgreSQL**。接続先は環境変数 `DATABASE_URL` で切り替える |
| ローカルでの動かし方 | `docker compose up --build`（すべてをコンテナで）、または、Compose の DB に対して `make setup` と `make dev` でコンテナなしで動かす。代わりに Cloud SQL を使うときは、Cloud SQL Auth Proxy（`cloud-sql-proxy`、`gcloud auth application-default login`）で `localhost` に中継し、`DATABASE_URL` を設定する。`plan.md` で確定する |
| 実行基盤 | **GCP Cloud Run**（フロント `docs-studio-web` と API `docs-studio-api` を別サービスとしてデプロイ） |
| デプロイ（実施内容） | 2026-11-01 に、2つの `cloudbuild.yaml` で、手動で一度デプロイした（プロジェクト `develop-513313`、リージョン `asia-northeast1`、Cloud SQL インスタンス `docs-studio-db` とデータベース `docs_prod`、実行用サービスアカウント `api-sa` と `web-sa`）。その後は自動: Cloud Run のコンソールで、リポジトリ `ShunsukeKano/project-docs-studio` に対して作った Cloud Build トリガー2つが、`main` への push のたびに `backend/Dockerfile` と `frontend/Dockerfile` をビルドし、2つのサービスを更新する（設定、シークレット、サービスアカウントは保持される）。デプロイ先が動くことは、所有者がブラウザで確認した。クイックスタートのシナリオは、ローカルの Docker で実行した。CI/CD は評価範囲の外 |
| マイグレーション | Alembic。手動ビルド（`backend/cloudbuild.yaml`）では、Cloud Run Job で `alembic upgrade head` を実行する。GitHub からの自動デプロイは、イメージを差し替えるだけで、Job は**実行しない**。スキーマを変えたときは、手動で実行する（`gcloud run jobs execute docs-studio-api-migrate --region asia-northeast1`） |
| DDL | DDL は `backend/db-automation-apply/` に、番号つきの SQL ファイル（`001_schema.sql`）として保存する。Alembic でどう適用するかは `plan.md` で決める |
| 公開範囲 | フロント（公開サイトと書き手の画面）と API を Cloud Run で公開する（`ENV=prod`、`BASIC_AUTH_ENABLED=true`）。書き手側だけ Basic 認証。公開サイトは認証なし |
| 秘密情報 | Secret Manager（`database-url`、`basic-auth-user`、`basic-auth-password`） |
| キャッシュ | なし。公開ページは毎回動的に描画する（`force-dynamic`）ので、公開停止が即座に反映される。キャッシュ層は対象外（13 節 R11） |
| データベース | 本番、開発、テストの DB は別にする（5 節、13 節 R14） |
| 上限 | 両方のサービスに `--max-instances` を設定する。API の接続プールは、Cloud SQL の `max_connections` に合わせて決める（例: インスタンス 3 つなら `pool_size=3`、`max_overflow=2`）。マイグレーション Job は `--max-retries=0` |
| AI による本文生成（任意の追加機能。実装済み。デプロイ先では有効） | API が、Anthropic の SDK を通じて **Claude API**（既定のモデルは `claude-sonnet-4-6`。`ANTHROPIC_MODEL` で変更）を呼び、本文を server-sent events として順に返す（`POST /api/v1/ai/draft`。`GET /api/v1/ai/status` は、画面に有効かどうかを伝える）。キーは Secret Manager（`anthropic-api-key`）に置き、サービスに `ANTHROPIC_API_KEY` として渡す（コード、イメージ、ログには出さない）。費用は**前払いのクレジット**で上限が決まる。Anthropic コンソールで、自動チャージをオフにし、ワークスペースの支出上限を設定する。設定: `AI_ENABLED`（既定はオフ。キーなしでオンにすると、起動を拒否する）と `ANTHROPIC_MODEL`。歯止め: タイトル200文字まで、タグ10個まで、メモ5,000文字まで、指示1,000文字まで。出力のトークン上限（既定3,000）。1インスタンスあたり1分に5回（429）。内部の詳細を出さない一般的な失敗（502）。インスタンス数の上限。テストは Claude API を呼ばず、ローカルの `.env` の AI の設定も無視する |

### 必要な YAML ファイル

| ファイル | 場所 | 状態 | 役割 |
|---|---|---|---|
| `compose.yaml` | リポジトリのルート | 作成済み | ローカル実行: 開発用（`db`）とテスト用（`db-test`）の PostgreSQL 17、Dockerfile からビルドする `migrate`、`backend`、`frontend`、`test`。`docker compose up --build` で全体が動き、`docker compose --profile test run --rm test` でバックエンドのテストが動く。短いセットアップコマンドの一部なので、優先度は低くない |
| `cloudbuild.yaml` | backend | 作成済み。手動で一度実行 | ビルド（`run` ステージのみ）→ Artifact Registry → マイグレーション Job → Cloud Run（api）。任意の AI 用シークレットは、`_AI_ENABLED=true` でビルドしたときだけ割り当てる。GitHub からの自動デプロイは、このファイルを使わない |
| `cloudbuild.yaml` | frontend | 作成済み。手動で一度実行 | ビルド → Artifact Registry → Cloud Run（web）。GitHub からの自動デプロイは、このファイルを使わない |

### Dockerfile

| ファイル | 場所 | 状態 | 内容 |
|---|---|---|---|
| `Dockerfile` / `.dockerignore` | backend | 作成済み（未ビルド） | python:3.12-slim + uv。依存層を先に作り、src・alembic を同梱。非 root、ポート 8000 |
| `Dockerfile` / `.dockerignore` | frontend | 作成済み（未ビルド） | node:22-slim の3段ビルド（standalone 出力）。非 root、ポート 3000 |

- Docker は、ローカルでの実行に使う: Docker Compose が同じ Dockerfile をビルドする。本番用のイメージは、Cloud Build が GCP 上でビルドする。
- Dockerfile は `pyproject.toml` / `uv.lock`（backend）、`package.json` / `pnpm-lock.yaml` と `next.config.ts` の `output: "standalone"`（frontend）を前提にする。これらを作ったあとでビルドを確認する（tasks に入れる）。
- `cloudbuild.yaml` の `_SQL_INSTANCE`、`_RUNTIME_SA`、`_API_URL` は空欄。環境ごとに指定する。
- Cloud SQL、Artifact Registry、Secret Manager、サービスアカウントの作成は手動（IaC は対象外）。
- API は無認証のため、ID トークンの処理は不要。外から直接大量に呼ばれる場合に備え、Cloud Run の最大インスタンス数で上限を付ける。
- 書き手側の Basic 認証は、課題文にない追加（13 節 R1）。実装の優先度はコア機能より低いが、デプロイ先を公開する前には必ず入れる。
- Cloud Build の実行主体には、`roles/run.admin`、実行用サービスアカウントへの `roles/iam.serviceAccountUser`、`roles/artifactregistry.writer`、`roles/logging.logWriter` が要る。`run`、`sqladmin`、`secretmanager`、`artifactregistry`、`cloudbuild` の API を有効にする。組織ポリシーが `allUsers` を禁止していると、`--allow-unauthenticated` は失敗する（デプロイ時に確認する）。
- 評価の間、Cloud Run のサイトと Cloud SQL は動かしておく。Basic 認証の認証情報は、リポジトリの外で評価者に渡す。
- Dockerfile と YAML は、まだビルドも実行もしていない。実行するまでは、検証済みとは書かない（Compose での実行が Dockerfile を検証し、Cloud Run は最後に検証する）。

## 13. 要件の再考（課題と解決方法）

課題文をそのまま実装するだけでは問題になる点や、課題文に明記がなかった点を洗い出し、背景とともに判断を記録する。課題文にない追加・変更は、すべてここに根拠を残す。`spec.md` と `plan.md` はこの決定に従う。

- **R1〜R17**: 課題文の要件を見直して変えた点（課題と解決方法）
- **U1〜U15**: 課題文に明記がなく、決めた点（論点と決定）
- 表の読み方: 「背景」の列に **AS-IS**（課題文の想定と、そこで生じた経緯）、「解決方法・決定」の列に **TO-BE**（決定後の状態）を書く。

| # | 背景 | 課題・論点 | 解決方法・決定 | 理由・反映先 |
|---|---|---|---|---|
| R1 | **AS-IS:** 課題文は認証を Out of Scope とし、書き手は信頼された単一のユーザーを想定している。一方、私たちは Cloud Run で公開するため、その前提が成り立たない。 | 課題文では認証は Out of Scope で、評価もされない。だが、デプロイ先をそのまま公開すると、誰でも記事を編集・公開・削除できてしまう。API は Cloud Run で公開されるため、画面にだけ認証を掛けても、API を直接呼ばれると防げない | **TO-BE:** **書き手側にだけ Basic 認証を入れる**（課題文にない追加）。`BASIC_AUTH_ENABLED` で切り替え、本番では必須、ローカルでの実行では既定でオフ（R17）。FastAPI の書き手のルートで検証し（検証の正）、Next.js は `Authorization` ヘッダーをそのまま転送して、401 を受けたら `WWW-Authenticate` を付けて返す（ブラウザが入力画面を出す）。ID とパスワードは環境変数 `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` で渡し、コードには書かない（本番は Secret Manager、ローカル用の値は `.env.example`）。公開サイトと公開用 API は認証なしのまま。比較は定数時間（`secrets.compare_digest`）で行う。時間が足りなければ、実装は後回しにしてよいが、書き手側を認証なしで公開デプロイしてはならない | 反映先: FR-13、12 節  |
| R2 | **AS-IS:** 実行基盤を Cloud Run に決め、フロントと API を別サービスにした。API を非公開（IAM 認証）にする案を検討した。 | 非公開 API（IAM 認証）にすると、フロントのサーバーが ID トークンを付ける処理が必要になる。認証が対象外の課題には過剰で、ローカルと本番で挙動も変わる | **TO-BE:** API は IAM 認証を使わず、**インターネットに公開**する（公開用 API は認証なし、書き手の API は Basic 認証）。ID トークンの処理は実装せず、ローカルと本番で同じコードを動かす。外から直接大量に呼ばれる場合に備え、Cloud Run の最大インスタンス数で上限を付ける | 反映先: 12 節、`backend/cloudbuild.yaml`  |
| R3 | **AS-IS:** 要件を整理する中で、Publish のトランザクション範囲（手順1〜4）に、`published_at` の設定が入っていないことに気づいた。 | Publish のトランザクション範囲が「手順1〜4」で、`published_at` の設定（手順5）が含まれていなかった。別トランザクションになると「公開済みなのに `published_at` が空」という不整合が生まれ、INV-2 に反する | **TO-BE:** トランザクションを**手順1〜5**とし、`published_at` も同じトランザクションで設定する。DB の CHECK 制約でも、公開済みなら参照と `published_at` が必須であることを強制する | 反映先: 3.3、アーキテクチャ資料の DB 構造  |
| R4 | **AS-IS:** 下書きの同時編集の検知だけが求められているが、Publish や Restore も、古い画面から実行できてしまう。 | 課題文では、Publish や Restore が「画面で見ていた下書き」を前提にしているか不明。古い画面から Publish すると、他の人が直した下書きを知らずに公開したり、Restore で上書きしたりしうる | **TO-BE:** Publish と Restore に `expected_draft_version` を**必須**にする。DB の値と一致しなければ 409 で拒否し、何も作らない。成功したら `draft_version` を増やす | 反映先: 3.3、3.5  |
| R5 | **AS-IS:** 課題文は一覧に「公開日」を表示するとしか書いていない。再公開しても `published_at` は初回を維持する要件があり、更新があったことを見せたい要望とずれる。 | 「公開日」が初回公開日か最新の公開日か不明。再公開しても `published_at` を変えない要件と、「更新があったことを見せたい」要望が両立しない | **TO-BE:** 公開日は**初回公開日（`published_at`）**を表示し、再公開済みの記事には**更新日**も併記する。更新日は**公開中スナップショットの作成日時**を使う。`articles.updated_at` は下書きを編集するたびに変わり、公開側に下書きの動きが漏れるため使わない | 反映先: FR-10  |
| R6 | **AS-IS:** 課題文は本番デプロイ・CI/CD・IaC を対象外としているが、実行基盤を Cloud Run と決めたため、設定ファイルが必要になった。 | 課題文は本番デプロイ・CI/CD・IaC を対象外としているが、実行基盤を Cloud Run と決めたため設定ファイルが必要になる | **TO-BE:** `cloudbuild.yaml` と `Dockerfile` は用意するが、**優先度はコア機能の完成より低い**。未完成でも課題の評価には影響しない。Cloud SQL などの作成は手動（IaC は対象外） | 反映先: 6 節、12 節  |
| R7 | **AS-IS:** ローカル開発を、Docker なしで Cloud SQL に直接つなぎたかった。一方、課題文は、新規チェックアウトから短いセットアップコマンドで実行できることを求めている。 | Docker がないと、評価者は、何かが動く前に PostgreSQL を自分で入れて設定する必要があり、課題文より弱い。また、共有の DB に触れるテストは、開発中のデータを壊しうる | **TO-BE:** ルートに **`compose.yaml`**（開発用とテスト用の PostgreSQL 17、マイグレーション、API、Web アプリ）を用意し、Docker だけが入った新規チェックアウトから、`docker compose up --build` ですべてが動くようにする。テストは専用の DB（名前が `_test` で終わるもの）だけを使い、それ以外には実行を拒否する。DB は引き続き `DATABASE_URL` と `TEST_DATABASE_URL` で選ぶので、Auth Proxy 経由の Cloud SQL も使える。Cloud Run も、同じく有効な評価の場として残す（U14 を参照） | 反映先: 5 節、12 節 |
| R8 | **AS-IS:** 課題文は挙動を細かく定めておらず、実装者によってぶれる点がある。 | 課題文にない挙動（Unpublish 中の版の削除、再 Publish、欠番など）が、実装者によってぶれる | **TO-BE:** 仮の方針を決めて、11 節に記録した（Unpublish 中も参照は保持して**削除不可**、version_number は**再利用しない**、古い更新は 409 など） | 反映先: 11 節  |
| R9 | **AS-IS:** 課題文は、公開中の版は削除できず、Unpublish は最後のスナップショットを残すとしている。両方を合わせると、公開停止中の記事が指す版も保護され、削除は Publish と競合しうる。 | 公開停止後は「公開中の版」が曖昧になり、Publish と競合した削除が、参照を宙に浮かせたり 500 を出したりしうる | **TO-BE:** **保護されたバージョン**を、状態にかかわらず参照が指す版と定義する。削除は Publish と同じ記事の行ロックを取り、保護された版には 409 `version_is_live` を返し、外部キー違反も同じ 409 に変換する | 反映先: 3.6、INV-3 |
| R10 | **AS-IS:** 最初の設計は「フロントが Authorization ヘッダーを転送する」としていた。Server Action は自分では Authorization ヘッダーを持たず、`WWW-Authenticate` も返せない。 | 最初の説明どおりでは、Server Action 経由の Basic 認証は動かない | **TO-BE:** Server Action は、受け取ったヘッダーを `headers()` で読み、API を呼ぶたびに渡す。API が 401 を返したら、action はそれを呼び出し元に伝え、route handler（action ではない）が `WWW-Authenticate: Basic` つきの `401` を返して、ブラウザに再入力させる。Basic 認証にはログアウトがないが、許容する。検証するのは FastAPI だけ | 反映先: FR-13、アーキテクチャ資料 5 節 |
| R11 | **AS-IS:** 課題文はキャッシュ層を対象外とし、公開停止した記事は一般ユーザーに 404 を返すことを求めている。 | ページやデータのキャッシュがあると、公開停止した記事を出し続けうる | **TO-BE:** キャッシュしない。公開ページは毎回動的に描画し、公開用 API も長いキャッシュ用ヘッダーを付けない | 反映先: 12 節、アーキテクチャ資料 5 節 |
| R12 | **AS-IS:** 最初の設計は、次の版番号を `MAX(version_number) + 1` で求めていた。「番号を再利用しない」を満たすのは、たまたま最大の版が削除できないからにすぎない。 | 公開中でない版が最大になりうる場合（Save as Version を入れたときなど）、番号が再利用されうる | **TO-BE:** 記事ごとのカウンタ列 `last_version_number` を、行ロックの下で増やす | 反映先: アーキテクチャ資料 7、9 節 |
| R13 | **AS-IS:** 最初の CHECK 制約は、参照と `published_at` を 1 回の UPDATE で消せば、`published` の行を `draft` に戻すことを許してしまい、履歴を壊す（INV-6）。 | INV-6 を DB が守っておらず、原子性を保証するのは制約ではなくトランザクションだった | **TO-BE:** `articles` の BEFORE UPDATE トリガーで、参照や `published_at` を消すこと、参照を後ろに戻すこと、`draft` に戻ることを禁止する。制約とトリガーが、それぞれ何を保証するかを、アーキテクチャ資料に正しく書く | 反映先: アーキテクチャ資料 7 節 |
| R14 | **AS-IS:** ローカル開発も本番も Cloud SQL を使うが、両者が別であることが書かれていなかった。 | 本番 DB に対して `make setup` やテストを実行すると、本番のサイトを壊す | **TO-BE:** 本番、開発、テストの DB を分ける。テストは `TEST_DATABASE_URL` を読み、名前が `_test` で終わりホストがローカルでなければ実行を拒否する。この防御にも専用のテストを付ける | 反映先: 5 節、12 節 |
| R15 | **AS-IS:** 課題文に AI 機能はない。AI で記事を自動生成したい。Cloud Run から Vertex AI を呼ぶ案を検討したが、無制限に呼ばれうるサービスでは、費用が青天井になりうる。 | AI 生成を追加するか。費用を青天井にせず、コアのライフサイクル、テスト、時間の枠を危うくせずに追加するにはどうするか | **TO-BE:** 計画では**最初は除外し、あとから実装した**。コア機能、不変条件のテスト、README、採用済みの任意機能がすべて済んだあとに、評価範囲の外の追加機能として作った（FR-17。仕様書: User Story 9、FR-042、A-7、A-9）。Vertex AI ではなく、**前払いのクレジットを入れた Claude API** を使い、合計の支出が、入れた金額を超えないようにする。実装した設計: (1) `POST /api/v1/ai/draft` は書き手のルート（Basic 認証）で、タイトル、タグ、任意のメモ、任意の指示を受け取り、**本文を文字列として順に返す**（server-sent events）。**何も書き込まない**。書き手が確認し、通常の編集で `expected_draft_version` つきで保存するので、INV-1〜INV-6 には触れず、自動では何も公開されない。(2) 書き手のタイトルとタグは、決して変えない。(3) Claude のクライアントは小さなインターフェースの裏に置き、テストは偽物を使って API を呼ばないので、`make test` にキーは要らず、費用もかからない。(4) 既定はオフ（`AI_ENABLED`）。キーは環境変数（Google Cloud では Secret Manager）から渡し、ログには出さない。入力の長さ、出力トークン、インスタンスごとのレート制限がある。オフのときは `503 ai_disabled`、回数超過は `429 rate_limited`、モデルの失敗は `502 ai_unavailable`（ストリームが始まったあとなら `error` イベント）。(5) 画面は、結果を「公開前に確認する提案」と明示し、ボタンは常に表示する（機能がオフのときは、案内つきで無効にする）。(6) README に、課題の項目の外の追加機能であることを書く | 前払いの残高は、従量課金のクラウドサービスにはない、確実な支出の上限になる。便利ではあるが、評価範囲の外で、「最大1〜2個」の任意機能の枠も超えるので、最後に作り、コアに影響しないようにした | 反映先: FR-17、12 節、アーキテクチャの 10・11 節 |
| R16 | **AS-IS:** 課題文は、最小限のインターフェースだけを求め、見た目は同点のときの判断材料にすぎないとしている。それでも、すっきりした見た目にしたい。 | コアに必要な時間を使わずに、インターフェースをどこまで、何で仕上げるか | **TO-BE:** **Tailwind CSS** で、**ミニマルでスタイリッシュ**に仕上げる: 落ち着いた配色にアクセントの色は1色、システムフォント、ゆったりした余白、共通の小さな部品、見えるキーボードフォーカス、スマートフォンからデスクトップの幅まで崩れないレイアウト。コンポーネントライブラリは使わない。見た目の仕上げは、**機能とそのテストが済んだあとの、時間を区切った作業**で、コア機能を遅らせない | Tailwind は、少ないコードで統一した見た目になり、別のデザインシステムが要らない。時間の枠が、評価される作業を守る | 反映先: 7 節、spec の FR-038、plan、research の R-19 |
| R17 | **AS-IS:** 課題文は、書き手側に認証は不要（「信頼された単一のユーザー」）としている。私たちは、インターネットに公開するデプロイ先を守るため、Basic 認証を追加した。 | 常にオンだと、認証情報なしで書き手の API を呼ぶ評価者（たとえば、認証が要らないと書いてある課題文に従ったスクリプト）が 401 を受け取り、壊れていると思うおそれがある | **TO-BE:** 明示的な1つの設定 `BASIC_AUTH_ENABLED`。本番では**必ずオン**にする（そうでなければ起動せず、どちらかの認証情報が空でも起動しない）。ローカルでの実行（`ENV` が `prod` でない）では、**オフにしてよく、環境変数のサンプルファイルはオフにしてある**ので、`docker compose up --build` はサインインが要らず、課題文の「認証なし」のとおりに動く。オフのときは、起動時に警告をはっきりログに出す。暗黙のフォールバックではなく、必ず明示的な設定にする（スイッチがオンで認証情報が未設定なら、エラー）。ルート走査のテストは、認証を有効にして実行する | デプロイ先は保護されたまま、新規のローカル実行は、課題文の記述どおりに動く | 反映先: FR-13、憲章の原則 IV、spec の FR-028〜FR-031 |
| U1 | **AS-IS:** 課題文は、古い更新に「明確なエラー」を返すとしか書いていない。 | 古い更新のエラー形式 | **TO-BE:** **409 Conflict**。エラーコードは `version_conflict`。`details` に現在の `draft_version` を入れる。送るのはリクエスト本文の `expected_draft_version`（`If-Match` は使わない） | 画面が「再読み込みして統合する」案内を出せる。ヘッダーより本文のほうが実装・テストが簡単  |
| U2 | **AS-IS:** 課題文は Unpublish の動作を書いているが、公開中でない記事に実行したときは書いていない。 | 公開中でない記事に Unpublish したとき | **TO-BE:** **409**（コード `not_published`）で拒否する | 冪等にすると「効いたのか効いていないのか」が分からなくなる。状態遷移を厳密に保つ  |
| U3 | **AS-IS:** slug は「一意の URL 識別子」とされているだけで、文字種、長さ、変更の可否が不明。 | slug の規則と変更 | **TO-BE:** 小文字英数とハイフンのみ（`^[a-z0-9]+(-[a-z0-9]+)*$`）、1〜100 文字、一意。**作成後は変更不可** | 公開 URL が変わらない。履歴や外部リンクが壊れない  |
| U4 | **AS-IS:** tags は入力項目としてあるだけで、規則がない。 | tags の規則 | **TO-BE:** 最大 10 個、1 個あたり 1〜30 文字。前後の空白を除き**小文字に正規化**し、重複は除く（順序は保持） | 一覧の表示とデータの揺れを防ぐ  |
| U5 | **AS-IS:** title と body の長さ、空の扱いが不明。 | title / body の長さと空の扱い | **TO-BE:** title は 1〜200 文字（空白のみは不可）。body は最大 100,000 文字。**下書きは body が空でもよい**が、**Publish 時は title・body とも空不可**（422、コード `empty_content`） | 書きかけの保存を許しつつ、空の記事を公開させない  |
| U6 | **AS-IS:** 公開一覧の並び順が書かれていない。 | 公開一覧の並び順 | **TO-BE:** **初回公開日（`published_at`）の新しい順**。同じ値なら `id` の降順 | 並びが毎回同じになる  |
| U7 | **AS-IS:** 本文は Markdown で、公開サイトで HTML として表示する。入力をそのまま描画すると、XSS になりうる。 | Markdown を HTML にするときの XSS 対策 | **TO-BE:** **生の HTML は描画しない**（サニタイズ）。リンクは `http`、`https`、`mailto` のみ許可 | 本文は書き手が入力するが、公開サイトで読む人を守る  |
| U8 | **AS-IS:** 課題文は、任意機能を4つから最大2つ選ぶとしている。 | 採用する任意機能（最大2）と、採用するものの細かい規則 | **TO-BE:** **Idempotent Publish** を採用。下書きの title、body、tags（tags は順序つきの配列）を、**公開中スナップショットだけ**と比べる。古い版と同じ内容でも、新しい版を作る。同じなら、スナップショットを作らず、`published_at`、参照、`draft_version` も変えない。状態が `unpublished` なら `published` に戻す。応答は 200（新しいスナップショットは 201）。確認の順序は、`expected_draft_version`（409）、`empty_content`（422）、冪等チェック。残りの3つのうち、Slug の重複処理は U15 で採用する。Save as Version と Diff View は採用しない | 整合性の要件と直接つながり、テストしやすい。Save as Version は「公開中でない版」の意味が変わり、複雑になる |
| U9 | **AS-IS:** 課題文に、記事そのものの削除が書かれていない。 | 記事そのものの削除 | **TO-BE:** **対象外**。実装しない | 課題文にない。履歴の保持という方針とも合う  |
| U10 | **AS-IS:** 推奨データモデルは `id` と `slug` の両方を持つが、API がどちらで引くかは書かれていない。 | ID と引き方 | **TO-BE:** ID は `bigint`（自動採番）。書き手の API は `id` で、公開側の API は `slug` で引く | 書き手側は slug を後から変えない前提でも、`id` が最も確実。公開側は URL に slug が必要  |
| U11 | **AS-IS:** Restore はスナップショットを下書きに戻すが、推奨データモデルのスナップショットには slug がない。 | Restore で slug をコピーするか | **TO-BE:** **コピーしない**。title、body、tags だけを下書きに戻す | スナップショットに slug を持たせない設計のため  |
| U12 | **AS-IS:** 課題文は「短いセットアップコマンド」と「単一コマンドのテスト」を求めるが、具体的なコマンドや、同時 Publish・クラッシュの再現方法は書かれていない。 | セットアップとテストの方法 | **TO-BE:** セットアップは `make setup`（依存のインストールとマイグレーション）、起動は `make dev`、テストは `make test`。テストは専用 DB のみ使う。**同時 Publish** は `asyncio.gather` で同時に 2 リクエストを送って確認する。**クラッシュ時の原子性**は、service 内の 2 つ目の SQL の後で例外を注入し、全体がロールバックされることを確認する | 課題の「単一コマンドでテスト」と、INV-2 の検証を両立する  |
| U13 | **AS-IS:** 「下書き」が、`draft_*` 列と `status=draft` の2つの意味で使われている。 | 用語「下書き」の二義 | **TO-BE:** 「下書き」は `articles` の `draft_*` 列の内容だけを指す。`status=draft` の記事は「**未公開**」と呼ぶ | 2 つの意味が混ざらないようにする（2 節の用語表に反映済み）  |
| U14 | **AS-IS:** 評価者は私たちの Cloud SQL に接続できず、課題文は、新規チェックアウトからプロジェクトが動くことを期待している。 | 評価者がどう確認するか | **TO-BE:** **`compose.yaml` を用意する。** README に両方の方法を書く: 自分のマシンで `docker compose up --build`（必要なのは Docker だけ）、または、デプロイ済みの Cloud Run のサイト（URL と Basic 認証の認証情報はリポジトリの外で共有し、評価の間、サイトと Cloud SQL は動かしておく）。どちらも、有効な評価の方法とする | Docker Compose が「新規チェックアウトから短いセットアップコマンドで」を満たす。デプロイ済みのサイトは、何もインストールしなくてよい |
| U15 | **AS-IS:** 課題文は Slug の重複処理を任意機能の1つとしている（最大2つまで採用できる）。採用しなければ、使われている slug はただのエラーになる。 | 新しい記事の slug が既に使われているときの扱い | **TO-BE:** Slug の重複処理を、2つ目の任意機能として**採用**する。作成時に slug が使われていれば、`-2`、`-3`、…（空いている最小の番号）を付け、実際に保存した slug を返す。結果が 100 文字に収まるよう、必要なら元の部分を短くする。同じ slug を取り合う同時の作成は、一意制約違反で採番をやり直す（最大 5 回）ので、それぞれ別の slug になり、500 にならない。すべての試行を失ったときだけ、API は 409 `slug_conflict` を返す。slug は作成後に変更できないまま（U3） | 一意性を弱めずに、記事を作りやすくする。保証するのは一意制約のまま |

## 14. 評価項目の対応表（評価される点が、どこで定義され、どう検証されるか）

| 評価される点（課題文より） | 定義している場所 | 検証の方法 |
|---|---|---|
| spec が機能要件と不変条件を整理している | 3 節、4 節 | `specs/001-docs-studio/spec.md`（Spec Kit） |
| エッジケース: Publish の原子性 | 3.3、INV-2、R3、R12、R13、アーキテクチャ資料 7 節・9 節 | 各手順での失敗の注入、同時 Publish、CHECK とトリガーのテスト（アーキテクチャ資料 12.1） |
| エッジケース: 公開中の版は削除不可 | 3.6、INV-3、R9 | 公開停止後、Publish と競合した場合を含む削除のテスト |
| エッジケース: 履歴を壊さない Restore | 3.5、INV-4 | `article_versions` の全行を、前後で比較 |
| エッジケース: 同時編集 | 3.3、INV-5、R4、U1 | 古い編集、古い Publish、編集と Restore の競合 |
| plan: データモデル | 9 節、アーキテクチャ資料 7 節、`backend/db-automation-apply/001_schema.sql` | 制約とトリガーのテスト |
| plan: API 設計 | アーキテクチャ資料 10 節 | API テスト |
| plan: 楽観的排他制御などの重要な設計判断 | 13 節、アーキテクチャ資料 8 節・9 節 | `plan.md` が各判断を記録する |
| tasks: 順序立てた作業の分解 | アーキテクチャ資料 12.2 | `tasks.md` |
| Git 履歴で、spec が先であることが分かる | 8 節の 1 | `scripts/check-spec-first.sh` |
| Publish、Unpublish、Restore、Delete、Concurrency の自動テスト | 4 節、5 節、アーキテクチャ資料 12.1 | `make test` |
| 短いコマンドでローカル実行できる | 5 節（実行、データベース）、U12、U14 | `docker compose up --build`（または `make setup` と `make dev`）。またはデプロイ済みのサイト |
| README の内容と、未実装機能の書き方 | 1 節、8 節の 3 | README のレビュー |
| 任意機能（最大2つ） | 10 節、U8、U15 | Idempotent Publish と slug 重複処理のテスト |

この文書の詳しさは、評価が重視する点に最も多く割いています。ライフサイクルの操作（3）、不変条件（4）、テスト（5）、判断（13）です。デプロイ（12）は意図的に短く、優先度を低くしてあり、AI 機能（FR-17）は計画から除外しています。

# frontend

Next.js 16（App Router）、TypeScript の strict モード、pnpm。
共通のルール（Spec Kit の進め方、`docs/`、言語の方針）は、ルートの `../CLAUDE.md` に従う。

> これは、`frontend/CLAUDE.md`（英語）の日本語版。英語版を変更したら、同じ変更でこのファイルも更新する。

- 型は `../backend/openapi.json` から生成する（`src/lib/api/generated/` は手で編集しない。型を手書きしない）。
- 読み取りは Server Components、書き込みは Server Actions。API の URL と認証情報は、ブラウザに渡さない。
- 書き手の画面（`/studio`）は、`BASIC_AUTH_ENABLED` が true のとき Basic 認証（本番では常に。ローカルの実行では既定でオフ）。確認するのは FastAPI で、Next.js は `Authorization` ヘッダーを転送する。`src/proxy.ts` は、ヘッダーがないとき、リクエストされたアドレスそのものに `401` と `WWW-Authenticate` を返す（リダイレクトするとループする）。API が認証情報を拒否したときは、ページは `/auth/challenge` に移る。これは route handler で、**認証情報を API で確認し**、API が受け付けたときだけ `/studio` に戻し、そうでなければ `401` を返して、ブラウザにもう一度尋ねさせる（この確認なしにリダイレクトしてはいけない。誤ったパスワードで、永久にループして画面が空白のままになる）。公開サイトに認証は要らない。
- 新しい記事は、エディタで直接書く（`/studio/new`、`new-article-form.tsx`）。最初の保存まで何も作られず、スラッグは、編集するまでタイトルに追従する（スラッグ欄にはスラッグだけを入れる）。「Save & publish」は、下書きを保存してから、保存した版を公開する。公開だけが失敗したときは、下書きは保存したと画面に表示する。
- 任意の AI の追加機能: 「Generate with AI」ボタン（`ai-generate-bar.tsx`）は常に表示し、サーバーでこの機能がオフのときは、案内つきで無効にする。server-sent のストリームは、route handler `src/app/(studio)/studio/ai-draft/route.ts` を通して読む（ブラウザの `Authorization` ヘッダーとストリームを、そのまま中継するので、API のアドレスとキーはブラウザに渡らない）。書き換えるのは本文欄だけで、保存はせず、タイトルとタグは変えない。
- 画像は `public/images/` のファイルで、アプリ自身が配信する（`next/image` の `unoptimized`）。どのページも、画像、フォント、スクリプトをほかのサイトから読み込まない。ソースに画像ホストの名前があると `tests/no-external-assets.test.ts` が失敗し、コンテンツセキュリティポリシーも、アプリ自身の画像だけを許す。
- すべてのページが、同じコンテンツ幅（2つのレイアウトの `max-w-4xl`）を使う。
- 公開ページは、リクエストのたびに動的に描画し（`force-dynamic`）、何もキャッシュしない。
- スタイルは Tailwind CSS だけを使う（コンポーネントライブラリは使わない）: ミニマルでスタイリッシュにし、落ち着いた配色、アクセントの色は1色、システムフォント、ゆったりした余白、見えるキーボードフォーカス、レスポンシブなレイアウトにする。機能とそのテストが済んだあとの、時間を区切った仕上げで、見た目は評価されない。
- Markdown は、共通の1つのレンダラーとサニタイザー（`src/lib/markdown.ts`）で描画し、公開ページと書き手のプレビューの両方で使う。
- `Dockerfile` には、`next.config.ts` の `output: "standalone"` が要る。
- 実ブラウザのテストは `e2e/`（Playwright、`playwright.config.ts`）にある。リポジトリのルートから `make e2e` で実行し、使い捨てのシステムを起動して、終わると削除する（Docker と Chrome が要る）。`pnpm test`（Vitest は `tests/` だけを実行する）や `make test` には含まれない。各テストは、一意のスラッグで、API 経由で自分のデータを作り、「Generate with AI」は押さない（そのシステムでは AI の機能はオフ）。
- `Dockerfile` と `cloudbuild.yaml` はこのフォルダにある。Google Cloud では、`main` への push で、この `Dockerfile` が自動でビルドされる（Cloud Run のコンソールで作った Cloud Build トリガー）。

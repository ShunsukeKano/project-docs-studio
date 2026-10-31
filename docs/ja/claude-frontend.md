# frontend

Next.js 16（App Router）、TypeScript の strict モード、pnpm。
共通のルール（Spec Kit の進め方、`docs/`、言語の方針）は、ルートの `../CLAUDE.md` に従う。

> これは、`frontend/CLAUDE.md`（英語）の日本語版。英語版を変更したら、同じ変更でこのファイルも更新する。

- 型は `../backend/openapi.json` から生成する（`src/lib/api/generated/` は手で編集しない。型を手書きしない）。
- 読み取りは Server Components、書き込みは Server Actions。API の URL と認証情報は、ブラウザに渡さない。
- 書き手の画面（`/studio`）は、`BASIC_AUTH_ENABLED` が true のとき Basic 認証（本番では常に。ローカルの実行では既定でオフ）。確認するのは FastAPI で、Next.js は `Authorization` ヘッダーを転送し、401 のときは route handler から `WWW-Authenticate` を返す。公開サイトに認証は要らない。
- 公開ページは、リクエストのたびに動的に描画し（`force-dynamic`）、何もキャッシュしない。
- スタイルは Tailwind CSS だけを使う（コンポーネントライブラリは使わない）: ミニマルでスタイリッシュにし、落ち着いた配色、アクセントの色は1色、システムフォント、ゆったりした余白、見えるキーボードフォーカス、レスポンシブなレイアウトにする。機能とそのテストが済んだあとの、時間を区切った仕上げで、見た目は評価されない。
- Markdown は、共通の1つのレンダラーとサニタイザー（`src/lib/markdown.ts`）で描画し、公開ページと書き手のプレビューの両方で使う。
- `Dockerfile` には、`next.config.ts` の `output: "standalone"` が要る。
- `Dockerfile` と `cloudbuild.yaml` はこのフォルダにある。

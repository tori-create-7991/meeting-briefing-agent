# Meeting Briefing Agent — Milestone 2 設計: Cloud Run MCP 入口 + Agent Runtime

- 承認: 2026-10-28（auto あり）
- 個人のメールアドレス・組織 ID・プロジェクト ID・請求先は公開リポジトリに載せない。実値は git 管理外の `terraform.tfvars` に置く

## 目的

| 項目 | 内容 |
|---|---|
| Outcome | Claude Code から MCP ツール `get_briefing` を呼ぶと、Agent Runtime 上のエージェントが Calendar / Docs を読み、日本語のブリーフィングを返す |
| User | 本人（自分の Google Workspace アカウント）。会議の準備に使う |
| Why now | M1 でローカル動作を確認済み。Gemini Enterprise Agent Platform の作法（Agent Runtime・Agent Identity・トレース・評価）を身につけ、発信の題材にする |
| Success | `uv run pytest -q` が 0 で終わる / 2 つの Terraform 構成で `terraform validate` が通る / デプロイ後に Claude Code から `get_briefing(date=予定のある日)` を呼ぶと日本語のブリーフィングが返る / Cloud Trace に実行の記録が残る |
| Constraints | us-central1。Terraform で管理。保存する秘密はゼロ（鍵なしのドメイン全体の委任）。自分の Workspace 組織の下の専用プロジェクト |
| Out of scope | 下の「やらないこと」 |

## 決定表

| # | 論点 | 決定 | 理由 | 却下した案 |
|---|---|---|---|---|
| D1 | 範囲 | 呼び出したときだけ動く。定期実行は M3 | 結果の届け先が未定。範囲が倍になる | 定期実行まで含める |
| D2 | M1 との関係 | 最初に PR #1 をレビューし、問題がなければマージ。M2 は main から切る | M1 の修正を取り込み直す手間を避ける | M1 ブランチの上に積む |
| D3 | 構成 | Cloud Run に薄い MCP 入口、エージェント本体は Agent Runtime | Agent Platform の機能を最も多く使える。Agent Runtime に MCP を直接置く方法は公式に無い | 全部 Cloud Run / Agent Runtime に自前コンテナで MCP |
| D4 | ツールの形 | `get_briefing(date: str \| None = None, max_events: int = 5) -> str` | `date` 省略で今から先、指定でその日（JST）。準備に一番使うのは日付指定 | 件数のみ / 予定1件単位の2ツール |
| D5 | エージェントの形 | `SequentialAgent[ContextFetcher(BaseAgent), BriefingWriter(LlmAgent)]`。全予定を 1 回の LLM 呼び出しで書く | 取得は決まった手順のまま（M1 の方針）。Agent Runtime の 1 回の問い合わせで完結する | LLM にツールとして取得させる / 予定ごとに別セッション |
| D6 | 言語 | 指示文は英語のまま、`BRIEFING_LANGUAGE`（既定 `ja`）で出力言語を指定 | OSS として英語の指示文を保ちつつ、本人は日本語で読む | 英語のまま / 日本語固定 |
| D7 | リージョン | us-central1（Cloud Run・Agent Runtime） | 新機能が先に来る。Cloud Run の無料枠の対象リージョン | asia-northeast1 |
| D8 | モデル | Vertex AI 経由、`BRIEFING_MODEL`（既定 `gemini-3.5-flash`） | Agent Platform 寄せ。正確な ID は実装時に確認 | AI Studio の API キー / 2.5 Flash / Pro |
| D9 | IaC | Terraform を 2 段に分ける。`infra/bootstrap`（プロジェクトと状態用バケット、状態は手元）、`infra/main`（残り全部、状態は GCS） | プロジェクトが無いうちはその中にバケットを作れない | スクリプト / 状態を手元だけに置く |
| D10 | GCP プロジェクト | 組織の下に専用プロジェクトを新しく作る（ID は `terraform.tfvars` で指定）。請求先は、組織のアカウントから紐付けられる既存の請求先アカウント | 他の用途と権限が混ざらない。作り直しや片付けが簡単。無料枠は請求先アカウント単位 | 既存プロジェクトに同居 |
| D11 | 読むアカウント | 本人の Workspace アカウント（`workspace_subject`） | 委任は Workspace のユーザーにしか使えない | 個人の Gmail |
| D12 | Workspace の認証 | 鍵なしのドメイン全体の委任。委任用 SA `workspace-reader` が IAM の signBlob で署名し、`subject` を本人に固定。スコープは `calendar.readonly` と `documents.readonly` のみ | 保存する秘密がゼロ、更新作業も無い。同意画面を Terraform で作れない問題も消える | refresh token を Secret Manager に置く |
| D13 | ローカル開発 | M1 のブラウザ同意（`credentials.json` / `token.json`）を `WORKSPACE_AUTH=local_oauth` として残す | 手元で手軽に動かせる | 委任のみ |
| D14 | Drive スコープ | 外す | 呼んでいない。最も厳しく扱われる区分のスコープ。添付の fileId はそのまま Docs の ID として使える | 残す |
| D15 | 実行の ID | Agent Identity。足す権限は `workspace-reader` に対する `iam.serviceAccounts.signBlob` だけ（その SA の上でだけ付ける）。Gemini は既定の権限で呼ぶ | エージェント専用の ID で、共有も成り代わりも鍵も無い。Google は project 全体の権限を付けないよう案内している | 専用 SA（予備として変数 `runtime_identity` で切り替え可能にする） |
| D16 | MCP 入口の認証 | Cloud Run の IAM（`run.invoker` は本人だけ）。Claude Code は user スコープの `headersHelper`（`scripts/mcp_headers.sh --account`）で本人の ID トークンを付ける。期限切れは 401/403 で Claude Code が helper を再実行して取り直す | 公開範囲がゼロのまま。アプリ側に認証コードが要らない | アプリ側 OAuth / IAP |
| D17 | MCP 入口の実装 | Python の FastMCP。状態を持たない Streamable HTTP（`/mcp`）。実行 ID は `mcp-front` SA で、Agent Runtime を呼ぶ権限だけ | エージェント本体と同じ言語。Cloud Run の公式手順に沿う | TypeScript |
| D18 | 観測・評価 | 環境変数 `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` で Cloud Trace（本文は載せない。下の「実装で変えた点」）。評価は 3 ケースのテスト集を `adk eval` で手動実行 | 目的が習得と発信。LLM を呼ぶ評価は結果がぶれるので CI には入れない | 評価なし / CI で評価 |

## 構成

```
Claude Code ──(ID トークン / headersHelper)──▶ Cloud Run: mcp-front（get_briefing）
                                                    │ 実行 ID: mcp-front SA（Agent Runtime の get / query だけ）
                                                    ▼
                                    Agent Runtime: meeting-briefing-agent
                                      SequentialAgent
                                        ├ ContextFetcher（LLM なし）
                                        │    credentials.py → 鍵なしの委任（IAM signBlob）
                                        │    pipeline → Calendar API / Docs API
                                        └ BriefingWriter（LlmAgent, Vertex AI Gemini）
                                      実行 ID: Agent Identity
                                                    │ signBlob（workspace-reader の上でだけ）
                                                    ▼
                                    workspace-reader SA（GCP の権限ゼロ）
                                                    │ Workspace 管理コンソールで 2 スコープのみ許可
                                                    ▼
                                    workspace_subject の Calendar / Docs（読み取り）
```

## データの流れ

1. Claude Code が `get_briefing(date="2026-10-29", max_events=5)` を呼ぶ。
2. `mcp-front` が Agent Runtime に `{"date": "2026-10-29", "max_events": 5}` を JSON の文字列で送る（`user_id` は呼び出し元のメールアドレス。セッションはメモリ上にしか作らないので残らない）。
3. `ContextFetcher` が JSON を読み、`date` から JST のその日 0:00〜24:00 を作り、予定を取得し、資料を探して本文を読む。結果を `state["briefing_contexts"]` に入れる。
4. `BriefingWriter` が `{briefing_contexts}` と出力言語を受け取り、予定ごとの見出し付きでブリーフィングを書く。予定が無ければ LLM を呼ばずに「予定なし」の文を返す（`before_agent_callback`）。
5. `mcp-front` が返ってきたテキストをつないでツールの結果として返す。

## エラー処理

| 失敗 | 動き |
|---|---|
| 委任の署名が拒否される（signBlob の権限なし） | `ContextFetcher` が「workspace-reader に対する signBlob 権限がない」と分かるメッセージで失敗し、MCP のエラーとして返る |
| Workspace で委任が許可されていない（`unauthorized_client`） | 「管理コンソールで client ID <id> に 2 スコープを許可する」と案内するメッセージ |
| ドキュメントの取得に失敗 | 警告を出し、その資料を `{"id", "error": "fetch_failed"}` として続行。執筆役は「取得できなかった」と書き、中身を推測しない |
| `date` の形式が不正 | MCP 入口で検証し、`YYYY-MM-DD` を求めるエラーを返す（Agent Runtime を呼ばない） |
| Agent Runtime の呼び出し失敗 | `mcp-front` がエラー内容を付けて MCP のエラーとして返す |
| Agent Runtime が 240 秒以内に答えない | `mcp-front` が待つのをやめ、時間切れと分かるエラーを返す（Cloud Run の 300 秒より前） |

## テスト

- 単体テスト（`uv run pytest -q`、外部 API は呼ばない）
  - `calendar_client`: `time_max` を渡すこと
  - `pipeline`: `date` から JST の範囲を作ること
  - `credentials`: 委任モードで `iam.Signer` と `subject` を正しく組むこと（モック）
  - `fetcher`: リクエスト JSON を読み、state に結果を入れる Event を出すこと（取得処理は差し替え）
  - `agent`: `SequentialAgent` の並びと、指示文に言語が入ること
  - MCP 入口: `date` の検証、Agent Runtime クライアント（差し替え）から返るテキストをつなぐこと
- Terraform: `init -backend=false` と `validate`（両構成）
- 評価: `tests/eval/briefing.evalset.json`（3 ケース）を `adk eval` で手動実行
- 動作確認（手作業）: デプロイ後に Claude Code から呼ぶ。Cloud Trace を確認

## 最初に検証する前提（デプロイ時）

| 前提 | 確かめ方 | だめだった場合 |
|---|---|---|
| Agent Identity から `workspace-reader` で署名し、Calendar を読める | デプロイ後に `get_briefing` を呼ぶ | 変数 `runtime_identity = "service_account"` に切り替え、専用 SA（`briefing-runtime`）を実行 ID にする |
| `gemini-3.5-flash` の ID が us-central1 の Vertex AI で使える | Model Garden / 呼び出しで確認 | `BRIEFING_MODEL` を使える ID に変える（結果: us-central1 には無く、`global` で使う。「実装で変えた点」） |
| ソースを変えたとき Agent Runtime が上書き更新か作り直しか | 2 回目の `terraform plan` | 作り直しでも IAM は Terraform が付け直すので構成は変えない。記録だけ残す（結果: 上書き更新。2026-10-29 と 2026-11-04 に確認） |
| `mcp-front` に必要な権限名（`aiplatform.reasoningEngines.get` / `.query`） | 呼び出しで確認 | 足りない権限をカスタムロールに足す |

## やらないこと

- 定期実行（Cloud Scheduler）と結果の届け先 — M3
- Memory Bank — 範囲を絞るため M3 以降
- Gemini Enterprise への登録 — Standard 以上の契約が要る
- claude.ai・モバイル向けの OAuth 入口 — Claude Code だけで足りる
- Agent Gateway — Cloud Run 向けの入口がまだ coming soon
- Gmail ユーザー向けの refresh token 方式 — OSS で必要になったら追加
- 費用アラート（予算）の自動設定 — 請求先アカウントの権限が絡む。`docs/deploy.md` で手作業として案内する
- ドキュメント内の表の読み取り — M1 からの既知の制限

## 実装で変えた点

実装中に分かった事実に合わせて、次の点を設計から変えた。

| 点 | 設計時 | 実装 | 理由 |
|---|---|---|---|
| 署名 API への接続 | 普通の HTTPS | `AuthorizedSession.configure_mtls_channel()` を通した mTLS 接続で signBlob を呼ぶ（証明書が無い手元では何もしない） | Agent Runtime の Agent Identity のトークンはエージェントの証明書に紐付いていて、mTLS でないと IAM API が 401 を返す（2026-10-29 に確認）。紐付けを切る環境変数もあるが、Google が非推奨としているので使わない |
| 委任の署名に使う権限 | `iam.serviceAccounts.signJwt` | `iam.serviceAccounts.signBlob`（`workspace-reader` の上でだけ付与） | `google.auth.iam.Signer` は IAM Credentials の signBlob API を呼ぶ |
| Agent Runtime の `class_methods` | 指定なし | `scripts/gen_class_methods.py` で AdkApp から生成し、Terraform に渡す | ソースから載せるときは必須（SDK も自動生成して送っている） |
| MCP の実装 | `FastMCP` | `mcp` 2.x の `MCPServer`。入力エラーと Agent Runtime の失敗は `ToolError` で返す | 2.x で改名。普通の例外は「Error executing tool」だけに丸められ、原因が呼び出し側に届かない |
| MCP の Host 検査 | — | `host="0.0.0.0"` でアプリを作る | localhost 向けの自動 Host 検査が Cloud Run のホスト名を弾くため。認証は Cloud Run の IAM が担う |
| 呼び出し元の `user_id` | 呼び出し元のメールアドレス | Cloud Run が検証済みの ID トークンから email を取り出す。取れなければ `anonymous` | セッションのラベルにしか使わず、認可には使わない |
| 執筆担当の指示文 | `{briefing_contexts}` の差し込み | InstructionProvider で組み立て、データは `<briefing_contexts>` タグで囲む | ADK の `{...}` 差し込みが予定本文の波括弧を誤解しないようにする |
| Dockerfile | `Dockerfile.mcp` | `Dockerfile` と `.gcloudignore` | `gcloud builds submit --tag` は `./Dockerfile` しか使えない |
| Agent Runtime の台数 | 指定なし | `agent_min_instances = 0`、`agent_max_instances = 2` | 呼び出し時だけ動かすので待機中の課金を避ける。0 が拒否されたら 1 にする |
| Agent Runtime の 1 台の大きさ | 指定なし（既定は 4 vCPU / 4Gi） | `agent_cpu = "1"`、`agent_memory = "2Gi"` | 処理の大半は Calendar・Docs・Gemini の応答待ち。無料枠（請求先アカウントごとに月 50 vCPU 時間・100 GiB 時間）が約 4 倍長くもち、最小台数 0 が通らず常時 1 台になったときの費用も約 1/4 になる |
| Artifact Registry の古いイメージ | 指定なし | 7 日より古い版を消す。ただし新しい 3 版は残す | 無料枠 0.5 GB を古いビルドで埋めない。Cloud Run が使う版と、戻し先は残る |
| Cloud Build の実行 ID | 既定（Compute Engine の既定 SA） | 専用 SA `mcp-builder` と専用バケット `<project>-build`（7 日で削除）。権限はそのバケットの読み書き、イメージ置き場への push、ログ書き込みだけ | 新しいプロジェクトでは既定 SA に権限が付かず、アップロードしたソースを読めずに失敗した（2026-10-29 に確認） |
| プロジェクト ID | 既定値あり | 既定値なし（`terraform.tfvars` で必須） | 公開リポジトリに組織固有の値を置かない |
| headersHelper | `gcloud auth print-identity-token` を呼ぶだけ | gcloud と Python 3.10+ を自分で探す。`--account` で使うアカウントを固定。`--impersonate` でサービスアカウントとして呼ぶ道も用意（audience は Cloud Run の URL）。スクリプトは安定した場所に置き、user スコープで登録する | helper はログインシェルの PATH なしで動き得る（最小の PATH だと gcloud がシステムの Python 3.9 を拾い起動に失敗するのを確認）。gcloud の設定が複数あると、別アカウントのトークンで 403 になる |
| Gemini の呼び出し先 | エージェントと同じ us-central1 | `BRIEFING_MODEL_LOCATION`（Terraform の既定は `global`）。ADK の `Gemini(client_kwargs={"location": ...})` で、Gemini の呼び出しだけを `global` に向ける。評価の判定役も `gemini-3.5-flash` に変更 | Gemini 3 系は `global` でしか提供されず、us-central1 では 404 になる。`gemini-2.5-flash` はこのプロジェクトではどちらでも 404（2026-11-04 に確認）。`GOOGLE_CLOUD_LOCATION` は Agent Runtime が予約していて、セッションにもエージェントのリージョンが要るので変えない |
| トレースに残す内容 | 指定なし（ADK の既定） | `AdkApp(enable_tracing=True)` をやめ、Terraform で `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` を渡す | `enable_tracing=True` だと `AdkApp.set_up()` が `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=true` に上書きし、LLM のリクエストと応答の全文が span に載る。予定と資料の本文が Cloud Trace に 30 日残っていた（2026-11-04 に実物で確認。`agent_app.py` で既定値を false にする最初の修正も、この上書きで効かなかった）。環境変数で有効にすると AdkApp が false にする。所要時間とトークン数は残る |
| セッションの保存先 | Agent Runtime の既定（マネージドのセッション） | `InMemorySessionService`（`session_service_builder`） | 既定では呼び出しごとにセッションが作られ、取得した本文と呼び出し元のメールアドレスが期限なしで残る。1 回きりの呼び出しなので保存しない。Sessions の課金も発生しない |
| 予定が 0 件のとき | 「予定なし」を返して終える（データの流れ 3） | 執筆役の `before_agent_callback` が LLM を呼ばずに定型文を返す | 実装が LLM を呼んでいたのをレビューで指摘された。費用を使わない |
| 指示文に埋め込むデータ | JSON をそのまま | `<` と `>` を `\u003c` / `\u003e` にして埋め込む | 招待の説明文に `</briefing_contexts>` と書けば区切りを閉じて指示を足せた。JSON の文字列の中なので意味は変わらない |
| `mcp-front` の待ち時間 | 指定なし | 240 秒で打ち切る（`asyncio.wait_for`） | Cloud Run の 300 秒で接続ごと切られる前に、理由の分かるエラーを返す。普段は約 10 秒 |

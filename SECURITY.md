# Security Policy

このリポジトリは public として運用します。「秘密情報を入れない」「AI の出力を信頼しない」「fork からの PR を信頼しない」
「ダウンロードするものを信頼しない」を前提に設計しています。

## 脆弱性の報告

1. public な Issue には書かないでください
2. GitHub の **Security Advisories**（Security タブ → Report a vulnerability）から報告してください
3. 内容: 説明、再現手順、影響、あれば修正案

48 時間以内に返信します。

## 脅威モデルと対策

| # | 脅威 | 対策 |
| --- | --- | --- |
| T1 | 秘密情報・個人の絶対パス・社内情報の混入 | PR ごとの secret-scan（gitleaks + TruffleHog + `scripts/ci/hygiene.py`）、日次の全履歴監査、pre-commit の gitleaks |
| T2 | AI の出力（MCP ツールの引数）で任意のパス読み書き・コマンド実行 | `src/rtl_harness/_safety.py`: consumer root 配下に限定、登録テストのみ実行、`shell=False`、timeout、出力上限、stdio のみ |
| T3 | fork からの PR で CI の権限・secrets・GHCR 書込みを悪用 | `permissions: contents: read` 既定、`pull_request_target` 不使用、イメージ build は main のみ、evals は environment で隔離、Actions は SHA 固定 |
| T4 | ダウンロード物（Verible / gitleaks / cocotb sdist / Docker ベース）の改ざん | `rules/common/tool-versions.toml` の sha256 / digest で検証。https のみ |
| T5 | チケットの転記で社内 RTL・環境情報が漏れる | `harness.toml [tickets].redact`、`ticket escalate` は本文表示と明示確認が必須 |

MCP サーバ（`mcp/server.py`）はローカルでツール（Verible / Verilator / cocotb）を実行します。信頼できるリポジトリでだけ起動してください。
`run_sim` はリポジトリ内の Python テストを実行するため、レビュー済みのテストだけを対象にしてください。

## ブランチ保護（public 化時に設定）

```bash
gh api repos/MameMame777/rtl-harness/branches/main/protection --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Secret scan / scan","CI / sanity"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false

gh api repos/MameMame777/rtl-harness --method PATCH \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

リポジトリ設定（Settings → Actions → General）: Workflow permissions を **Read repository contents**、
「Allow GitHub Actions to create and approve pull requests」を **無効**。

## 貢献者向けチェックリスト

自動チェック（CI）
- [ ] secret-scan が通る（gitleaks / TruffleHog）
- [ ] `hygiene.py` が通る（絶対パス、内部 URL、メールアドレス、公開 IP が無い）

手動確認
- [ ] API キー・トークン・パスワードが無い
- [ ] 社内固有の情報（プロジェクト名、ホスト名、ライセンスサーバ）が無い
- [ ] お手本 RTL は自作で、ベンダ IP のコピーではない
- [ ] 例に使う値はプレースホルダ（`<project>`、`$env:VAR`、相対パス）

## パスと認証情報の書き方

```powershell
# BAD - 絶対パスの直書き
$root = "E:\Users\John\Projects\MyProject"

# GOOD - 環境変数か探索で解決する
$root = $env:MSYS2_ROOT
```

```powershell
# BAD - 認証情報の埋め込み
$apiKey = "sk-abc123xyz456"

# GOOD - 環境変数 / GitHub secrets
$apiKey = $env:API_KEY
```

意図的に絶対パスの例を書く行には `hygiene-ok` を含むコメントを付けてください（例: `# hygiene-ok: well-known install roots`）。

## 事故が起きたとき

1. 露出した認証情報を即座に無効化・再発行する
2. 影響を受ける関係者に連絡する
3. `git filter-repo --path <file> --invert-paths` で履歴から除去し、force push する（管理者）
4. 検出の仕組み（`.gitleaks.toml`、`hygiene.py`）を見直す

---

Last updated: 2026-09-24

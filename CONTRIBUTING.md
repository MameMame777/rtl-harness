# Contributing

## 流れ

1. **Issue を立てる**: テンプレート（AI の失敗・逸脱 / ルール提案 / ツール不具合）から選ぶ。領域ラベルで担当オーナーに届く
2. **PR を出す**: PR テンプレートのセキュリティ自己確認と変更種別のチェックを埋める
3. **CI が通る**: `CI`（lint / sim / lint-off 検出 / doctor）と `Secret scan`
4. **オーナーが承認する**: CODEOWNERS の担当が 1 人以上。共通部（`AGENTS.md`、`rules/common`）はリリース担当も承認

## 変更の種類と判定基準

| 変更の種類 | 触る場所 | 判定基準 |
| --- | --- | --- |
| 強制ルールの追加 | `rules/` + `AGENTS.md` か `docs/` の 1 行 | 既存 `examples/` が通ること。既存プロジェクトでの違反件数を PR に書く |
| 設計スタイルの修正 | `examples/` + `docs/` | お手本自体がフォーマッタ・lint・シミュを通ること |
| ツールの改修 | `src/rtl_harness/`、`mcp/`、`tb/` | `tests/` が通り、evals のモデル別正答率が下がらないこと |
| モデルの追加 | `scripts/sync/templates/`、`evals/runner/config.toml` | そのモデルの初回正答率を基準値として記録すること |
| 課題の追加 | `evals/<領域>/` | 課題の正解 RTL がシミュを通ること |

`lint_off` / `verilog_lint: waive` を追加する PR は CI が検出し、ラベル `lint-off-approved` を担当オーナーが付けるまでマージできません。

## 開発環境

```powershell
.\scripts\setup_toolchain.ps1              # MSYS2 ucrt64 + 2 つの venv + Verible + VPI ライブラリ
uv run --project . pytest tests            # ユニットテスト
uv run --project . rtl-harness lint examples/**/*.sv
uv run --project . rtl-harness sim --all
uv run --project . pre-commit install      # コミット前に lint と gitleaks を走らせる
```

## 書き方の約束

- AI に読ませるファイル（`AGENTS.md`、`docs/` の規則、お手本のコメント）は英語 ASCII。人向けの文書は日本語
- 絶対パス・認証情報・社内固有の情報を書かない（`SECURITY.md`）
- Python は `ruff` の設定に従う（`uv run --project . ruff check .`）
- RTL は `rules/common` の規約に従う。お手本は 150 行以内

## 秘密情報を見つけたら

`SECURITY.md` の「事故が起きたとき」に従ってください。public な Issue には書かないでください。

## セキュリティ自己確認（必須）

この PR に次のものが **含まれていない** ことを確認しました:
- [ ] API キー・トークン・パスワード・認証情報
- [ ] 絶対パスの直書き（例 `C:\Users\...`、`E:\...`、`/home/...`）
- [ ] 内部 URL・IP アドレス・ホスト名
- [ ] メールアドレス（GitHub noreply を除く）
- [ ] 社内固有・機密の情報、ベンダ IP のコピー

## 変更の種類

- [ ] 強制ルールの追加（`rules/` + `AGENTS.md` / `docs/` の 1 行）
- [ ] 設計スタイルの修正（`examples/` + `docs/`）
- [ ] ツールの改修（`src/rtl_harness/`、`mcp/`、`tb/`）
- [ ] モデルの追加（`scripts/sync/templates/`、`evals/runner/config.toml`）
- [ ] 課題の追加（`evals/<領域>/`）
- [ ] その他

## 内容

何を、なぜ変えたか。

## ハーネス固有の確認

- [ ] `lint_off` / `verilog_lint: waive` / waiver ファイルの追加は **無い**（有る場合は理由を書き、オーナーが `lint-off-approved` を付ける）
- [ ] 強制ルール追加の場合: 既存プロジェクトでの違反件数 = ___ 件（`rtl-harness lint --json` の counts）
- [ ] ツール改修の場合: `tests/` が通り、evals の正答率が前回から下がらない
- [ ] `examples/` が全チェックを通る（`rtl-harness lint examples/**/*.sv` / `rtl-harness sim --all`）

## 関連 Issue

Fixes #

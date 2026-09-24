# Changelog

セマンティックバージョニング。強制ルールは「警告（マイナー版）→ エラー（メジャー版）」の 2 段階で入れる。

## v0.1.0 (2026-09-24)

初回リリース。P0〜P2 が動く状態、P3〜P6 は骨格。

### 動く

- `rtl-harness lint`: Verible（format + lint）、Verilator `--lint-only`、独自チェック（timescale / reset-style /
  module-name-style / no-todo、BUS: valid-depends-on-ready / combinational-ready-path、CPU: unique-case）、
  severity マップ、lint 抑止コメントの検出
- `rtl-harness sim`: cocotb 2.0.1 + Verilator 5.048（Windows ネイティブ MSYS2 ucrt64 / Linux コンテナ）、要約 JSON
- MCP サーバ（4 ツール、stdio）。CLI と同じ JSON を返すことをテストで保証
- `rtl-harness provision` / `ticket`: チケット機能の add-if-missing 導入、ローカル `tickets/` と GitHub Issue の二層
- お手本: `examples/bus/{skid_buffer, axi4lite_regs}`、`examples/cpu/{pipelined_alu, hazard_unit}`、`examples/verif/*`
- `AGENTS.md`（63 行）、`docs/{bus,cpu,verification,tool-schema,governance,consumer-setup}.md`
- CI: sanity / harness（lint + sim + doctor をコンテナで）/ lint-off、secret-scan、日次監査、CodeQL、Dependabot
- セキュリティ: 入力検証（`_safety.py`）、sha256 固定のダウンロード、Actions の SHA 固定、read-only token

### 骨格のみ

- `rtl-harness sync`（P3）: テンプレートと I/F のみ
- `get_waveform` / `list_design`（P5）: 契約と stub
- evals（P4）: 課題一覧と dry-run runner

### 強制ルール（error）

timescale、module-filename、always-comb / always-ff-non-blocking、case-missing-default、no-tabs、
no-trailing-spaces、posix-eof、forbid-defparam、line-length 100、parameter-name-style（ALL_CAPS）、
enum-name-style、one-module-per-file、Verilator WIDTH* / LATCH / CASEINCOMPLETE / UNOPTFLAT / BLKSEQ /
COMBDLY / MULTIDRIVEN / IMPLICIT、reset-style（同期 active-low `rst_n`）、no-todo、valid-depends-on-ready

### 警告（次のメジャー版で error 候補）

explicit-begin、signal-name-style、explicit-parameter-storage-type、Verilator UNUSED* / UNDRIVEN、
module-name-style、combinational-ready-path、unique-case

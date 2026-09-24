# rtl-harness

AI エージェント（Claude Code / GitHub Copilot）が書く RTL を、**同じ規約・同じ道具・同じ検証**で
揃えるための共有ハーネスです。「中身は 1 つ、ツールごとの違いは入口だけ」を原則に、
各 FPGA プロジェクトが git submodule として取り込んで使います。

- 読ませるルールは `AGENTS.md`（目次）と `docs/`、強制するルールは `rules/`（Verible + Verilator + 独自チェック）
- 検証は cocotb 2.0.1 + Verilator 5.048（Windows ネイティブ MSYS2 ucrt64 / Linux コンテナ）
- AI から見える道具は MCP サーバ 1 つ・4 ツール（`run_lint` / `run_sim` / `get_waveform` / `list_design`）
- 同じ Python 関数を CLI・pre-commit・CI からも呼ぶので、3 つの入口で結果が一致する

> 状態: v0.1.0 開発中（P0〜P2 を実装中）。設計の経緯は `docs/plan/` を参照。

## クイックスタート（ハーネス自身の開発）

```powershell
# 前提: MSYS2 (ucrt64) と uv, git, gh
.\scripts\setup_toolchain.ps1        # 2 つの venv (.venv / .venv-sim), Verible, VPI ライブラリ
uv run --project . rtl-harness lint tb/smoke/smoke_counter.sv --json
uv run --project . rtl-harness sim smoke_counter
```

各設計プロジェクトへの導入は `docs/consumer-setup.md` を参照してください。

## リポジトリの中身

| パス | 役割 |
| --- | --- |
| `AGENTS.md` | AI に読ませるルールの目次（100 行以内） |
| `docs/` | 領域ごとのルール、ツールの JSON 契約、運用 |
| `examples/` | お手本 RTL とテスト（bus / cpu / verif） |
| `rules/` | Verible・Verilator の設定、severity、独自チェック |
| `src/rtl_harness/` | lint / sim / ticket / provision / sync の実体（標準ライブラリのみ） |
| `mcp/server.py` | MCP サーバ（4 ツール） |
| `tb/` | cocotb + Verilator の共通部品と Windows ワークアラウンド |
| `evals/` | モデル別の正答率を測る課題と runner |
| `scripts/` | セットアップ、入口ファイル生成、チケットのテンプレート |
| `.github/` | CI、秘密情報スキャン、Issue / PR テンプレート |

## セキュリティ

public リポジトリとして運用します。秘密情報・絶対パス・社内固有情報を含めないでください。
詳細は `SECURITY.md` と `CONTRIBUTING.md` を参照してください。

## ライセンス

MIT。流用元は `THIRD-PARTY-NOTICES.md` に記載しています。

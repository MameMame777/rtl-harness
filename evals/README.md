# evals（P4、骨格）

モデル別の正答率・スタイル違反率を測る課題と runner です。この版では課題の題名と入出力の約束だけを置き、
runner は `--dry-run` のみ動きます。

## 課題（領域ごとに 3 題、計 9 題）

| 領域 | 課題 | 期待する書き方 |
| --- | --- | --- |
| bus | `sync_fifo`: 同期 FIFO（valid/ready 両側、パラメータ深さ） | registered ready、`$clog2` 幅、`'0` リセット |
| bus | `rr_arbiter2`: valid/ready 2 入力ラウンドロビンアービタ | valid が ready に依存しない、3 プロセス FSM |
| bus | `axi4lite_irq`: AXI4-Lite 割込みレジスタ（status / mask / pending） | `wstrb`、SLVERR、typed enum |
| cpu | `regfile_fwd`: フォワーディング付きレジスタファイル | ステージ接頭辞、x0 の扱い |
| cpu | `branch_flush`: 分岐判定とフラッシュ | valid 伝播、`unique case` |
| cpu | `mul_stall`: ストール付き乗算器 | valid/ready でのストール、`$clog2` |
| verif | `add_test`: 既存 RTL へのテスト追加 | `build_and_test`、Scoreboard、timeout |
| verif | `find_bug`: バグ入り RTL の原因特定 | `run_sim` → `get_waveform` の流れ |
| verif | `add_assert`: アサーション追加 | 別モジュールに `bind` |

## 課題ディレクトリの約束

```text
evals/<domain>/<nnn>-<slug>/
├─ task.md            仕様（AI に渡す指示。英語）
├─ ports.sv           ポート定義（空のモジュール）
├─ test_<slug>.py     採点用 cocotb テスト（正解 RTL で PASS すること）
└─ reference.sv       正解 RTL（採点には使わない。CI が sim で検証）
```

## runner

```powershell
uv run --project . python evals/runner/run.py --dry-run           # 課題一覧と設定の確認
uv run --project . python evals/runner/run.py --model claude --task bus/001-sync_fifo   # P4
```

採点: `run_lint` の error 0 かつ `run_sim` PASS で正答。試行は複数回（`config.toml`）、スタイル違反率は
warning 件数 / ファイル数。結果は `evals/results/<date>-<model>.json`（gitignore）。

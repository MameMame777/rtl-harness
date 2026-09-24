# tickets/

このプロジェクトで見つかった問題の記録です。rtl-harness の `ticket` コマンドで作ります。

```powershell
uv run --project harness rtl-harness ticket new --kind bug|deviation|rule|tool --domain bus|cpu|verif --title "..." [--model claude] [--attach-last] [--files rtl/x.sv]
uv run --project harness rtl-harness ticket list [--all]
uv run --project harness rtl-harness ticket close <id>
uv run --project harness rtl-harness ticket escalate <id> [--yes]   # deviation / rule / tool を harness へ転記
```

- 1 チケット = 1 ファイル（`<yyyymmdd>-<nnn>-<slug>.md`）。先頭の frontmatter が状態です
- GitHub リモートがあるプロジェクトでは、`ticket new` が同時に Issue を立て、`issue:` に URL が入ります
- リモートが無いプロジェクトでは `status:` をこのファイルで管理します（`ticket close`）
- `--attach-last` は直近の `run_lint` / `run_sim` の要約（`.harness/last/`）を貼り込みます
- ハーネス側の問題（AI の逸脱・規則・ツール）は `ticket escalate` で `MameMame777/rtl-harness` に転記します。
  転記前に絶対パスやメールアドレスなどは自動でマスクされ、本文を確認してから `--yes` で送ります

## kind の使い分け

| kind | 内容 | 行き先 |
| --- | --- | --- |
| bug | このプロジェクトの RTL / テストのバグ | このプロジェクト |
| deviation | AI が規約・お手本から外れた | harness（escalate） |
| rule | 規則の提案・変更 | harness（escalate） |
| tool | run_lint / run_sim などの不具合 | harness（escalate） |

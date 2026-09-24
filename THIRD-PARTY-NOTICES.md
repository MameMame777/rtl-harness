# Third-party notices

## このリポジトリに取り込んだコード（vendoring）

| 場所 | 出自 | ライセンス | 備考 |
| --- | --- | --- | --- |
| `tb/harness_tb/{site,runner_support,bootstrap_vpi}.py`, `tb/sitecustomize.py`, `tb/conftest.py`, `tb/toolchain/verilator.cmd` | 同一作者の MIPI2HDMI プロジェクト `verification/cocotb/`（cocotb + Verilator を Windows ネイティブで動かす 8 つのワークアラウンド） | MIT（同一作者） | 消費側プロジェクトの root 解決と Linux での no-op を追加 |
| `tb/harness_tb/lib/{clkreset,scoreboard,axis}.py` | 同上 `verification/cocotb/lib/` | MIT（同一作者） | `gap` 依存を整数列に置換 |
| `.github/workflows/{secret-scan,security-audit}.yml`, `.gitleaks.toml`, `SECURITY.md` の骨子 | 同一作者の knowledge-share リポジトリ | MIT（同一作者） | gitleaks をピン留めバイナリに変更、hygiene チェックを Python 化 |
| `docs/tool-schema.md` の `list_design` の JSON 形 | 同一作者の RTLScope（`dump-ports` の出力形） | MIT / Apache-2.0（同一作者） | 将来 `rtlscope` に差し替えるための契約 |

Windows ネイティブ cocotb + Verilator の手順は作者自身の Qiita 記事（VerilatorPlusCoCotb）に基づく。

## ダウンロードして使うツール（取り込んではいない）

| ツール | ライセンス | 固定方法 |
| --- | --- | --- |
| Verilator | LGPL-3.0 / Artistic-2.0 | MSYS2 パッケージ / Docker イメージの digest（`rules/common/tool-versions.toml`） |
| Verible | Apache-2.0 | release 資産の sha256 |
| cocotb | BSD-3-Clause | PyPI の版と sdist の sha256 |
| gitleaks | MIT | release 資産の sha256 |
| MCP Python SDK (`mcp`) | MIT | `pyproject.toml` の版範囲と `uv.lock` |
| uv | MIT / Apache-2.0 | Docker イメージの digest |

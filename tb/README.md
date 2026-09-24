# tb/ -- cocotb + Verilator test harness

`harness_tb` は、各プロジェクトの `test_<block>.py` が呼ぶ共通部品です。

```text
tb/
├─ harness_tb/
│   ├─ site.py             ツールチェーンとパスの解決（MSYS2 root、consumer root、build root）
│   ├─ runner_support.py   build_and_test(): ビルド → sim 実行 → マーカー出力
│   ├─ bootstrap_vpi.py    Windows 用の静的 VPI ライブラリを自前ビルド
│   └─ lib/                clkreset / scoreboard / valid_ready / axis / gap
├─ sitecustomize.py        sim プロセス側の DLL ディレクトリ登録（Windows）
├─ toolchain/verilator.cmd perl ラッパ（cocotb が verilator.bat を拾わないように）
├─ smoke/                  ハーネス自身の疎通テスト
└─ manifest.toml           任意のブロック登録（suites / engine）
```

## テストの書き方

```python
from pathlib import Path
import cocotb
from harness_tb.lib.clkreset import bringup
from harness_tb.lib.scoreboard import check_eq


@cocotb.test()
async def counts(dut):  # sim プロセス側。名前は test_ で始めない
    clk, _ = await bringup(dut)  # rst_n を同期解除
    ...


def test_my_block():  # pytest ホスト側。build_and_test を呼ぶだけ
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="my_block",
        sources=["rtl/my_block.sv"],
        toplevel="my_block",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": 8},
    )
```

`sources` は consumer プロジェクト root からの相対パス。ブロック名はファイル名 `test_<block>.py` から決まります。
実行は `rtl-harness sim <block>`（`.venv-sim` の python で pytest を起動）です。

## Windows ワークアラウンド（ucrt64）

| # | 問題 | 対策 | 場所 |
| --- | --- | --- | --- |
| 1 | ツールが PATH に無い | `ucrt64/bin` と `usr/bin`（perl）を前置 | `site.prepend_path` |
| 2 | `shutil.which("verilator")` が perl で実行できない `.bat` を拾う | perl ラッパ `verilator.cmd` を PATH 先頭に | `toolchain/verilator.cmd` |
| 3 | `make` が無い（`mingw32-make.exe`） | `make.exe` shim を初回コピー（gitignore） | `runner_support._ensure_make_shim` |
| 4 | `VERILATOR_ROOT` のバックスラッシュが Makefile を壊す | forward slash | `site.verilator_root` |
| 5 | cocotb が Windows 用 `libcocotbvpi_verilator` を同梱しない | 静的 `.a` を自前ビルド | `bootstrap_vpi.ensure` |
| 6 | `-Os` で `std::string` の move ctor が未定義 | `-O2` を強制 | `site.common_build_args` |
| 7 | 波形 | `waves=True` → `dump.vcd` を build dir に移動 | `runner_support.build_and_test` |
| 8 | sim の埋め込み Python が stdlib `.pyd` を読めない | `os.add_dll_directory` | `sitecustomize.py` |

Linux（CI コンテナ）ではこれらは全て no-op です。

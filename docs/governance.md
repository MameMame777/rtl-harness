# 運用（governance）

## 役割と承認

| 役割 | いま | Organization 移行後 | 担当範囲 |
| --- | --- | --- | --- |
| リリース担当 | @MameMame777 | `@org/harness-release` | `AGENTS.md` 共通部、`rules/common`、`scripts/sync`、リリース、2 段階導入、月次棚卸しの進行 |
| BUS 領域オーナー | @MameMame777 | `@org/owners-bus` | `examples/bus`、`rules/bus`、`docs/bus.md`、`evals/bus` |
| プロセッサ領域オーナー | @MameMame777 | `@org/owners-cpu` | `examples/cpu`、`rules/cpu`、`docs/cpu.md`、`evals/cpu` |
| 検証領域オーナー | @MameMame777 | `@org/owners-verif` | `tb/`、`mcp/`、`src/rtl_harness/`、`evals/runner`、`docs/verification.md`、CI |

承認ルール（`CODEOWNERS` で機械化）
- 領域内の変更は、その領域のオーナー 1 人以上が承認する
- 共通部（`AGENTS.md`、`rules/common`）はリリース担当と、影響を受ける領域のオーナー 1 人が承認する
- `lint_off` / waiver を追加する PR は、担当オーナーがラベル `lint-off-approved` を付けるまでマージできない

## ブランチ保護と GitHub 設定

2026-09-25 に public 化し、次を有効にした（`SECURITY.md` の `gh api` コマンド）。

- required status checks（strict）: `sanity`、`harness (lint, sim, doctor)`、`scan`
- required reviews: 1 人、code owner review 必須、stale review の破棄、会話の解決必須
- force push と削除の禁止
- **管理者のバイパスは当面許可**（`enforce_admins=false`）: メンテナが 1 人の間は、自分の PR を承認できる人がいないため。領域オーナーが 2 人以上になったら `enforce_admins=true` に切り替える
- secret scanning + push protection、Dependabot alerts / security updates、CodeQL（Python、`codeql.yml`）
- Settings → Actions: Workflow permissions は Read repository contents、Actions による PR 作成・承認は無効

GHCR のイメージ `rtl-harness-ci` の可視性は REST では変えられないので、Package settings（Danger Zone → Change visibility）で
public にする。private のままでも CI はイメージをその場でビルドして動く（遅くなるだけ）。

## バージョンと 2 段階導入

- セマンティックバージョニング。各プロジェクトは submodule のタグで固定する
- 強制ルールは **警告として導入（マイナー版）→ エラーへ格上げ（次のメジャー版）**
- 実体は `rules/common/rules.toml` の `[severity.*]`。マイナー版では `warning` を追加し、メジャー版で `error` に書き換える
- 消費側は `harness.toml [lint].severity_overrides` で **格上げだけ** できる（格下げはできない）

## 月次の棚卸し

リリース担当が進行し、領域オーナーが出席する。議題は 4 つに固定する。

1. `stage:triage` の「AI の失敗・逸脱」のうち、`rules/` へ昇格できるものの選定（→ `stage:promote-rules` / `stage:promote-examples`）
2. ルール提案の採否
3. evals のモデル別正答率・スタイル違反率の推移
4. 警告段階のルールを次のメジャー版でエラーにするかの判断

## 問題の流れ

```text
現場（consumer project）
  rtl-harness ticket new      → tickets/ に記録、GitHub リモートがあれば Issue
  rtl-harness ticket escalate → harness リポジトリの Issue（kind:deviation / rule / tool）
harness リポジトリ
  issue-router.yml            → domain:* から担当オーナーを assign、stage:triage
  月次棚卸し                  → rules/ or examples/ へ昇格、evals 課題化
  リリース                    → Dependabot / Renovate の submodule 更新 PR で各プロジェクトへ
```

## リリース手順

1. `CHANGELOG.md` に変更を書く（強制ルールの追加は「警告」「エラー」を明記）
2. `pyproject.toml` の version を上げ、`git tag vX.Y.Z`
3. `image.yml` が CI イメージを更新するのを確認し、`ci.yml` のイメージタグを合わせる
4. 消費側プロジェクトには submodule 更新 PR を出す（自動化は P6 で検討）

## セキュリティ自己確認（必須）

この PR に次のものが **含まれていない** ことを確認しました:
- [ ] API キー・トークン・パスワード・認証情報
- [ ] 絶対パスの直書き、内部 URL、IP アドレス、メールアドレス
- [ ] 社内固有・機密の情報

## 内容

何を、なぜ変えたか。

## ハーネスの確認

- [ ] `rtl-harness lint` が error 0（`lint_off` / waiver の追加が無い。有る場合は理由を書き、オーナーが `lint-off-approved` を付ける）
- [ ] 変更したブロックの `rtl-harness sim <block>` が PASS
- [ ] 見つけたが直していない問題は `rtl-harness ticket new` で記録した（#）

## 関連 Issue / チケット

Fixes #

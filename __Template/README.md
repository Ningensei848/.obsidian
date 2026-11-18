---
tags:
  - readme
title: 共通ノートテンプレート
---

# 共通ノートテンプレート

[Knewrova の __Template](https://github.com/Ningensei848/Knewrova/tree/main/__Template) を基にした共通テンプレート。
このディレクトリが配布元で、`scripts/setup.py` がVault直下の `__Template` に配置する。

- [[Daily]]: 日付・目標・メモ・振り返り・前回の Next Action。
- [[Misc]]: 通常のメモ。無題ノートだけを時刻とユーザー名でリネームする。
- `config.js`: Daily notes の設定を取得する。
- `daily.js`: 対象ノートの日付を解析し、180日前までの前回ノートを探す。
- `util.js`: Linux / Windows 共通のユーザー名取得と通常ノートの処理。

デイリーの初期保存先は `MyWork/Daily/YYYY/MM/YYYYMMDD.md`。Daily notes の日時書式で保存先を決めるため、テンプレートからの移動・削除は行わない。
名前付きの通常ノートはその名前を保ち、無題ノートは `YYYYMMDD_HHmmss_ユーザー名.md` になる。同名があれば連番を付ける。

配布設定を変える場合は `.obsidian` 側の `*.default.json` を編集して再配置する。Vault側だけでテンプレートを編集した場合、再配置時には内容の違いが検出される。

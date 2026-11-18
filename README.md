---
tags:
  - readme
title: .obsidian/README.md
---

# Obsidian の設定ファイルをまとめて管理する

このリポジトリでは、`.obsidian` に含まれる設定ファイルを管理する

## 導入

Python 3.10 以上を使う。外部のPythonパッケージは不要。
このリポジトリをVault直下の `.obsidian` として配置し、対象Vaultを閉じてから実行する。
`.obsidian` がすでにある場合は、その内容を確認してから配置する。

Linux / Ubuntu（Vault直下で実行）:

```sh
python3 .obsidian/scripts/setup.py --dry-run
python3 .obsidian/scripts/setup.py --overwrite
```

Windows / PowerShell（Vault直下で実行）:

```powershell
py -3 .obsidian/scripts/setup.py --dry-run
py -3 .obsidian/scripts/setup.py --overwrite
```

別の場所に置いたこのリポジトリから、配置先のVaultを指定することもできる。
この場合、管理対象の設定と同梱済みプラグインの配布ファイルも `<Vault>/.obsidian` へコピーする。

```sh
python3 scripts/setup.py --vault "/path/to/My Vault" --dry-run
python3 scripts/setup.py --vault "/path/to/My Vault"
```

```powershell
py -3 scripts/setup.py --vault "C:\Users\your-name\Documents\My Vault"
```

スクリプトは次の処理を行う。

1. `__Template` 内のテンプレートとユーザースクリプトをVault直下へ配置する。
2. ルートとプラグイン内の `*.default.json` から、`.default` を取り除いた名前の設定JSONを生成する（例: `daily-notes.json`、`plugins/templater-obsidian/data.json`）。再利用する原本は残す。
3. 設定で参照するノート・デイリー・添付ファイルの保存フォルダを作成する。

同じ内容のファイルは変更しない。JSONは改行コード・末尾空白だけの違いでも既存ファイルを維持する。
内容が異なるファイルがあれば、書き込み前に停止する。
`--overwrite` 指定時は、異なる既存ファイルをOSの一時領域の `dot-obsidian-backup-*` へ退避してから置き換える。
退避先は実行結果に表示される。Vault内に `docs/`、`tmp/`、作業記録は作成しない。
途中で失敗した場合は原因コード・対象・処理段階・書き込み済み件数を標準エラーへ出力し、終了コード1で停止する。
バックアップからの復元は、退避先にあるファイルを同じ相対パスへ戻す。

コミュニティプラグインの利用を許可したうえで、Vaultを開き直す。
プラグインは同梱済みの配布ファイルを使い、スクリプトからのダウンロードは行わない。
配置前にフォルダ名とmanifestのIDの一致、本体 `main.js` の存在、有効化一覧にあるプラグインの同梱を確認する。

## Templater の自動実行

[Templater 2.27.0 の新規ファイル作成時の自動実行設定](https://github.com/SilentVoid13/Templater/blob/2.27.0/src/settings/LocalSettings.ts)は、設定JSONではなく端末・Vaultごとのローカルストレージに保存される。
ObsidianでTemplaterが有効になっており、[Obsidian CLI](https://help.obsidian.md/cli) が利用可能なら、次のコマンドで有効にできる。

```sh
python3 .obsidian/scripts/setup.py --activate
```

```powershell
py -3 .obsidian/scripts/setup.py --activate
```

CLIがPATHにない場合は `--obsidian-cli "実行ファイルのパス"` を指定する。
Windowsでは必要に応じて `Obsidian.com` を指定する。同名のVaultが複数ある場合は `--obsidian-vault "Vault ID"` で選ぶ。
スクリプトはObsidianが開いているVaultの実際のパスを照合し、一致した場合だけ自動実行を有効にする。システムコマンドと起動時テンプレートの有効・無効は維持する。
CLIの実行環境とObsidianは同じOSを使う（Windows版Obsidianに対してはWindows側のPythonから実行する）。

CLIを使わない場合は、Templaterの **Trigger Templater on new file creation** をこの端末・Vaultで一度有効にする。
JSONの生成が成功しても、この設定が無効ならテンプレート内のTemplater構文は展開されない。

## デイリーノートとフォルダ別テンプレート

Daily notes の「今日のデイリーノートを開く」で作成する。
日時書式 `YYYY/MM/YYYYMMDD` により、例えば `MyWork/Daily/2026/11/20261118.md` に保存される。
同じ日のノートは既存ファイルが開かれ、テンプレートによる移動・削除は行わない。
本文の日時と前回ノートの探索は対象ファイルの日付を基準とし、過去日・未来日にも対応する。

| 作成場所 | 適用テンプレート |
| --- | --- |
| `MyWork/Daily` とその子フォルダ | `__Template/Daily.md` |
| `MyWork/Misc` とその子フォルダ | `__Template/Misc.md` |
| 専用ルールのないフォルダ | `__Template/Misc.md`（ルート `/` のルールを継承） |
| `__Template` / `__Attachment` | 自動適用の対象外 |

フォルダ別ルールは `plugins/templater-obsidian/data.default.json` の `folder_templates` を編集する。
例えば `Projects` 向けのテンプレートを追加する場合は、`__Template/Project.md` を用意して次のルールを追加し、セットアップを再実行する。
Templaterは作成場所から親フォルダへたどり、最も近いフォルダのルールを使う。

```json
{
  "folder": "Projects",
  "template": "__Template/Project.md"
}
```

保存先は `daily-notes.default.json` の `folder` / `format` と、Templaterのフォルダ別ルールを合わせて変更する。
従来の `YYYYMMDD_ユーザー名.md` を続ける場合は、例えば日時書式を `YYYY/MM/YYYYMMDD[_your-name]` にする。既存ノートの移動や改名は行わない。
通常ノートの無題時リネームに使うユーザー名は、Windowsの `USERNAME`、Linuxの `USER` / `LOGNAME`、ホームフォルダ名の順で取得し、未取得時は `user` にする。

## 検証

```sh
python3 -B -m unittest discover -s tests
```

```powershell
py -3 -B -m unittest discover -s tests
```

## サードパーティプラグイン

全件を利用する場合の最低 Obsidian バージョンは **1.13.3**。

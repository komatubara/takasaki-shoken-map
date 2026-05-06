# 手動補正ガイド

ジオコーディングで取得できなかった店舗（精度=town・none）に、手動で正確な座標を与えるための手順書。

---

## 目次
1. [概要](#概要)
2. [対象ファイル](#対象ファイル)
3. [作業手順](#作業手順)
4. [Googleマップで座標を取得する方法](#googleマップで座標を取得する方法)
5. [反映と公開](#反映と公開)
6. [優先順位とフォールバック](#優先順位とフォールバック)
7. [よくある質問](#よくある質問)

---

## 概要

`scripts/geocodingjp_search.py` と `scripts/retry_advanced.py` でも自動取得できなかった店舗（現状約48件）は、**町の中心点**を仮の座標として表示しています。これらの店舗は地図上に表示されますが、ポップアップに「⚠️ 正確な位置情報を取得できませんでした」という警告が出ます。

このガイドの手順で `corrections_template.csv` に正しい座標を書き込めば、警告が消え、実際の店舗位置に正しくピンが立つようになります。

**1件ずつでも、まとめてでもOK**。気になった店舗から順に補正できます。

---

## 対象ファイル

```
C:\Users\komic\Downloads\高崎商品券\corrections_template.csv
```

このファイルを Excel で開いて編集します。**UTF-8 BOM CSV** で保存してください（Excelでは「CSV UTF-8（コンマ区切り）」を選択）。

### 列構成

| 列 | 編集 | 内容 |
|---|------|------|
| 店舗名 | × | 識別キー（変更禁止） |
| 町名 | × | 識別キー（変更禁止） |
| 電話番号 | × | 参考情報 |
| 業種 | × | 参考情報 |
| 失敗理由 | × | なぜ自動取得できなかったか |
| 現在lat | × | 今プロットされている座標（町中心） |
| 現在lng | × | 同上 |
| Googleマップ検索 | × | クリックで店舗をGoogle検索 |
| **補正lat** | **○** | 正しい緯度を書き込む |
| **補正lng** | **○** | 正しい経度を書き込む |
| **メモ** | **○** | 任意の備考（廃業、住所変更など） |

「店舗名」「町名」は内部的な識別キーとして使われます。**絶対に変更しないでください**（変更すると補正が認識されません）。

---

## 作業手順

### ステップ1: ファイルを開く

エクスプローラから `corrections_template.csv` をダブルクリック。Excelが起動します。

### ステップ2: 補正したい店舗を見つける

48件のうち、外出先でよく使いそうな店舗、馴染みのある店舗から優先的に補正していきましょう。

### ステップ3: Googleマップ検索URLをクリック

該当行の「Googleマップ検索」セル（H列）をクリックすると、ブラウザでGoogleマップが開き、店舗名+高崎市+町名で検索された結果が表示されます。

### ステップ4: 座標を取得

[Googleマップでの座標取得方法](#googleマップで座標を取得する方法) を参照。

### ステップ5: 補正座標を書き込む

「補正lat」（I列）に緯度、「補正lng」（J列）に経度を書き込みます。

例:
```
補正lat: 36.32153
補正lng: 139.00872
```

### ステップ6: メモを残す（任意）

「メモ」列に気付きを書き込めます：
```
メモ: 廃業らしい / 住所変更 / オーパ内 / 火・水定休
```

### ステップ7: 保存

Excelで「ファイル > 名前を付けて保存」→ 形式を「**CSV UTF-8（コンマ区切り）(*.csv)**」を選んで上書き保存。

⚠️ 通常の「CSV (コンマ区切り)」を選ぶとShift-JISで保存され、文字化けします。**必ずUTF-8**を選んでください。

---

## Googleマップで座標を取得する方法

### 方法A: 右クリック（PC・推奨）

1. Googleマップで店舗を見つける
2. 店舗の正確な位置（建物の中央など）を**右クリック**
3. メニュー先頭に表示される「**緯度経度の数字**」（例：`36.319473, 139.010803`）をクリック
4. 自動的に座標がクリップボードにコピーされる
5. Excelに貼り付け → 「,」で2セルに分かれない場合は手動で分割

### 方法B: URL から抽出

GoogleマップのURLには座標が含まれます：
```
https://www.google.com/maps/place/.../@36.319473,139.010803,17z/...
                                     ^^^^^^^^^ ^^^^^^^^^^
                                     latitude  longitude
```
`@` の直後の2つの数字をコピーします。

### 方法C: スマホの場合

1. Googleマップアプリで店舗を表示
2. 店舗のピンを**長押し**
3. 画面下部に表示される住所と座標をタップ
4. 座標をメモ → PCに送って入力

### 注意

- **小数点以下6桁**程度で十分です（センチメートル単位の精度）
- 緯度は **約36** （北緯）、経度は **約139**（東経）の範囲にあるはず
- 高崎市内は緯度 36.18〜36.50、経度 138.75〜139.15 の範囲

---

## 反映と公開

補正をいくつか書き込んだら、以下のコマンドを実行します：

```bash
cd "C:\Users\komic\Downloads\高崎商品券"

# ① 補正を取り込んで最終CSV再生成
python scripts/merge_final.py

# ② JSON再生成（Web用）
python scripts/csv_to_json.py
```

`merge_final.py` の出力で「**手動補正: N件**」と表示されれば取り込み成功です。

```
=== 精度内訳 ===
  manual (手動補正):                  3件   ← ここに件数が出る
  exact  (geocoding.jp 高精度):      17件
  ...
```

### Webサイトに反映

```bash
git add corrections_template.csv 高崎市民商品券取扱店一覧_geo_final.csv web/data/stores.json
git commit -m "data: 手動補正◯件追加"
git push
```

push 後、約20〜30秒で https://komatubara.github.io/takasaki-shoken-map/ に反映されます。

### 検証

ブラウザで該当店舗のピンを確認：
- ✅ 警告ボックス（⚠️ メッセージ）が消えている
- ✅ ポップアップに「位置精度: **手動補正**」と表示
- ✅ ピンが補正後の場所にある

---

## 優先順位とフォールバック

`merge_final.py` の座標決定ロジックは以下の優先順位です：

```
① 手動補正 (corrections_template.csv に補正lat/補正lng が両方記入済み)
   → 精度=manual, ソース=corrections
   ↓ ない場合
② geocoding.jp 結果 (高崎市bbox内)
   → 精度=exact (needs_verify=no) または approx (needs_verify=yes)
   → ソース=geocoding.jp
   ↓ ない/bbox外の場合
③ 国土地理院 町代表点
   → 精度=town, ソース=gsi  ← 警告表示の対象
   ↓ 町名すらない場合
④ 座標なし
   → 精度=none  ← 警告表示の対象
```

### 安全機構

- 補正座標が**高崎市bbox外** (138.75〜139.15, 36.18〜36.50) の場合は**自動で無効化**されます
- 誤って他県の座標を入れても警告なくスキップされ、自動取得値が維持されます
- 補正lat または 補正lng のどちらか片方しか埋まっていない行も無効

---

## よくある質問

### Q1. 1件ずつ補正してもいい？
A. はい。何件埋めてもmerge_final.py + csv_to_json.py + git push で都度反映できます。

### Q2. 補正後の店舗を間違えた場合は？
A. corrections_template.csv の補正lat/補正lngを空欄に戻して保存→merge_final.py を実行すれば、自動取得値（または町中心点）に戻ります。

### Q3. corrections_template.csv が消えた場合は？
A. 以下のコマンドで48件の空テンプレートを再生成できます：
```bash
python -c "
import csv, json, urllib.parse, sys
sys.path.insert(0, 'scripts')
from lib.geocoding import in_takasaki_bbox
with open('geocodingjp_progress.json', encoding='utf-8') as f:
    gj = json.load(f)
items = []
with open('高崎市民商品券取扱店一覧_geo_final.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row.get('精度') != 'town':
            continue
        store = (row['店舗名'] or '').strip()
        town = (row['町名'] or '').strip()
        key = f'{store}|{town}'
        gj_result = gj.get(key)
        if not gj_result:
            reason = '未照会'
        elif gj_result.get('status') == 'ok':
            lat, lng = gj_result.get('lat'), gj_result.get('lng')
            reason = f'bbox外({lat:.3f},{lng:.3f})' if not in_takasaki_bbox(lat, lng) else '採用済み'
        else:
            reason = gj_result.get('status', '?')
        gmap = f'https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f\"{store} 高崎市{town}\")}'
        items.append({
            '店舗名': store, '町名': town,
            '電話番号': (row['電話番号'] or '').strip(),
            '業種': (row['取り扱い商品・サービス'] or '').strip(),
            '失敗理由': reason,
            '現在lat': row.get('lat', ''), '現在lng': row.get('lng', ''),
            'Googleマップ検索': gmap,
            '補正lat': '', '補正lng': '', 'メモ': '',
        })
fields = ['店舗名','町名','電話番号','業種','失敗理由','現在lat','現在lng','Googleマップ検索','補正lat','補正lng','メモ']
with open('corrections_template.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(items)
print(f'Re-generated: {len(items)} rows')
"
```

### Q4. 補正したのに反映されない
原因と対処：

| 症状 | 原因 | 対処 |
|------|------|------|
| 「手動補正: 0件」と出る | 補正lat/lngが空欄 | 両方の値が入っているか確認 |
| 「手動補正: 0件」と出る | 数値以外の文字が混入 | 余分なスペースや「N」等を削除 |
| 「手動補正: 0件」と出る | bbox外の座標 | 緯度36.18〜36.50、経度138.75〜139.15内か確認 |
| サイトに反映されない | git push 忘れ | git status で未push確認 |
| デプロイは成功したがピンの場所が変わらない | ブラウザキャッシュ | Ctrl+F5 (強制再読込) または30分待つ |

### Q5. 店舗名や町名を修正したい場合は？
A. corrections_template.csv ではなく、マスター CSV (`高崎市民商品券取扱店一覧.csv`) を直接編集してください（手順は別途）。

### Q6. 全部補正しないとダメ？
A. いいえ。**1件も補正しなくても問題なく動作**します。補正していない店舗は町中心点に黄色の警告付きで表示され、ユーザーは「Googleマップで見る」ボタンから実位置を確認できます。

---

## 参考：48件の内訳（2026-05-06時点）

| 失敗理由 | 件数 | 主な業種 | 補正の難易度 |
|---------|------|---------|-----------|
| exception | 33 | 飲食店・理美容（英語混じりの店名） | 中（Google検索で見つかる店多い） |
| bbox外 | 13 | 倉渕町川浦の山間部、他県の同名店 | 中〜難（山間部は要確認） |
| error | 2 | API側エラー | 低（普通に検索可能） |

優先補正候補：
- **大型チェーン**（コンビニ・ドラッグストア） → 検索しやすい
- **駅前の飲食店** → ユーザーが利用する確率高い
- **イオンモール内/オーパ内テナント** → モールの座標で代用可能

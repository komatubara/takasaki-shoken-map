# 高崎商品券マップ

高崎市民商品券の取扱店をブラウザの地図上で探せるWebアプリ。

🌐 **公開URL**: https://komatubara.github.io/takasaki-shoken-map/

## 概要

高崎市が公式PDFで配布している取扱店一覧（57ページ・3,138店舗）を、外出先のスマホで「近くのお店」を視覚的に探せるよう、地図上に展開したものです。

- 国土地理院タイル + Leaflet による地図表示
- 業種フィルタ・店舗名検索・現在位置取得
- マーカークラスタリングで3,000件規模を快適表示

## データパイプライン

```
40177.pdf  (高崎市公式PDF)
    │
    ├─ pdfplumber でテーブル抽出
    ▼
高崎市民商品券取扱店一覧.csv   ← マスターデータ
    │
    ├─ scripts/geocodingjp_search.py  (店舗名 + 町名 を geocoding.jp に問合せ)
    │   → geocodingjp_progress.json  (キャッシュ)
    │
    ├─ scripts/retry_exceptions.py    (XML パース失敗ぶんを再試行)
    │
    ├─ scripts/merge_final.py         (geocoding.jp + GSI町中心 + bboxバリデーション)
    │   → 高崎市民商品券取扱店一覧_geo_final.csv
    │
    └─ scripts/csv_to_json.py         (Web用JSON生成・ジッター付加)
        → web/data/stores.json        ← フロントエンドが読込
```

## セットアップ

### 必要環境
- Python 3.10+
- ブラウザ（Chrome / Edge / Safari / Firefox）

### Python依存
```bash
pip install pdfplumber pymupdf
```
（geocoding.jp 問合せは標準ライブラリのみ）

## 主要スクリプト

| スクリプト | 役割 |
|----------|------|
| `scripts/geocodingjp_search.py` | geocoding.jp で全店舗を一括ジオコード（中断/再開対応） |
| `scripts/retry_exceptions.py` | API失敗・XMLパース失敗ぶんを特殊文字除去でリトライ |
| `scripts/merge_final.py` | geocoding.jp結果＋GSI町中心点をマージ・bboxで外れ値除外 |
| `scripts/csv_to_json.py` | 最終CSV → Web用JSON変換 |

## ローカルでの動作確認

```bash
# Webサーバ起動（任意のポートでOK）
cd web
python -m http.server 8765

# ブラウザで http://localhost:8765/ を開く
```

## デプロイ

`main` ブランチへのpushで自動的にGitHub Pagesにデプロイされます（`.github/workflows/deploy-pages.yml`）。

`web/` 配下またはワークフロー自体に変更があった場合のみデプロイが走ります。

## データ更新の手順

元PDFが更新された場合：

```bash
# 1. PDF差し替え後、CSV再抽出は手動（pdfplumberの抽出スクリプトはアドホックに作成）

# 2. ジオコーディング（時間がかかる: 約9時間）
python scripts/geocodingjp_search.py

# 3. 失敗分のリトライ（約12分）
python scripts/retry_exceptions.py

# 4. 最終マージ
python scripts/merge_final.py

# 5. JSON生成
python scripts/csv_to_json.py

# 6. コミット・プッシュ
git add 高崎市民商品券取扱店一覧_geo_final.csv web/data/stores.json
git commit -m "data: PDF更新を反映"
git push
```

CSV内の店舗名を手動修正した場合は、ステップ3〜6だけでOK。

## 技術スタック

| 層 | 採用技術 |
|---|--------|
| 地図ライブラリ | Leaflet 1.9.4 |
| マーカークラスタ | Leaflet.markercluster 1.5.3 |
| 地図タイル | 国土地理院 標準地図 |
| ジオコーディング | geocoding.jp（無料、店舗名対応）+ 国土地理院（町中心点） |
| フロントエンド | バニラJS（ES Modules）+ CSS |
| データ形式 | UTF-8 BOM CSV → JSON |
| ホスティング | GitHub Pages（GitHub Actions経由） |

## ドキュメント

- [DEVLOG.md](./DEVLOG.md) - 開発経緯・技術判断の時系列記録
- [CORRECTIONS.md](./CORRECTIONS.md) - 自動取得できなかった店舗の手動補正手順

## ライセンス・出典

- 取扱店データ: 高崎市公開資料 (`40177.pdf`) より抽出
- 地図タイル: 国土地理院（出典記載が必須）
- 本リポジトリのコード: 個人利用・非商用利用前提
- geocoding.jp は商用利用禁止のため、本データの商用転用も不可

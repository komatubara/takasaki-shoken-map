# 高崎市民商品券マップ - 開発記録

外出先で「近くの取扱店」を視覚的に探せるWebアプリを作る。

## ゴール

- スマホブラウザで動作するPWA
- 地図上に取扱店を表示、現在位置から近い順に検索
- 業種フィルタ、店舗詳細ポップアップ
- 費用ゼロで運用可能（OSS + 無料API中心）

## 技術スタック

| 層 | 採用 | 理由 |
|----|------|------|
| 地図ライブラリ | Leaflet.js | 軽量(15KB)・OSS・APIキー不要 |
| 地図タイル | OpenStreetMap / 国土地理院 | 無料・日本国内に強い（GSI） |
| 大量マーカー | Leaflet.markercluster | 3,000件規模に必須 |
| ジオコーディング | 国土地理院API → Google Places(将来) | 段階的フォールバック |
| データ形式 | CSV → JSON | 静的ホスティング可能 |

---

## タイムライン

### 2026-05-04: ソースPDF入手・CSV化
- 高崎市公式PDF `40177.pdf`（57ページ）を入手
- pdfplumber でテーブル抽出 → `高崎市民商品券取扱店一覧.csv`
- 5列構成：店舗名 / 町名 / 電話番号 / 取り扱い商品・サービス / 大型店
- 抽出結果：**3,161店舗**（ヘッダー1行＋データ）
- 文字コード：UTF-8 with BOM（Excel互換）

### 2026-05-05: 可視化方針決定
- 箇条書きCSVは外出先で使いにくい → 地図化が必要
- 検討した3案：
  - 案A：Googleマイマップ（手軽・カスタム性低）
  - 案B：Leaflet + OSM 自作Web/PWA ← **採用**
  - 案C：CSV+Googleマップ検索URL（妥協案）
- 決定：B案（業種フィルタ・現在地検索などUI自由度が必要）

### 2026-05-05: ジオコーディング戦略策定
- 課題：CSVは「町名」までで番地なし
- 戦略：
  1. **フェーズ1**: 国土地理院APIで町代表点を全町取得（全店共通基盤）
  2. **フェーズ2**: Nominatimで店舗名POI検索 → ヒットしたら座標上書き
  3. **フェーズ3**: 残りはGoogle Places API（少額課金前提・将来）

### 2026-05-05: フェーズ1 完了
- 対象：208ユニーク町名
- 結果：**208/208 成功**（失敗ゼロ）
- 出力：`town_coords.json`、`高崎市民商品券取扱店一覧_geo_phase1.csv`
- 統計：3,138店舗にtown精度座標付与、23店舗は町名なしで未付与
- 所要時間：約1分（GSI APIは高速）

### 2026-05-05: フェーズ2 中止判断
- Nominatimでサンプル16店舗をテスト → **高崎市内ヒット率 0%**
- 原因：日本国内の個人商店レベルはOSMにほぼ未登録
- 例：「あーく」検索 → 埼玉県戸田市のアパートがヒット
- 例：「earth music&ecology natural store」→ 0 hit
- 例：「コナカ 高崎中央店」→ 0 hit
- ブランドのみクエリ（`セブン-イレブン 高崎駅`）は機能するが、CSVの店舗名形式（`AOKI 高崎棟高店`等の店舗詳細名）では検索不能
- 判断：**Nominatimをスキップ**、町代表点ベースで進む
- 全店舗53分かけて成果ゼロは不合理

### 2026-05-05: geocoding.jp を代替候補として調査
- ユーザー提案で https://www.geocoding.jp/ を検証
- 9店舗サンプルテスト → **実質100%が座標を返す**（Nominatim 0%から大幅改善）
- 内部はGoogle/Yahoo APIのラッパー、無料、商用利用禁止（個人利用OK）
- レート制限：**1リクエスト/10秒**（厳守要請）
- 全件処理時間：3,161件 × 10.5秒 = **約9.2時間**
- レスポンスXMLに `<needs_to_verify>` フィールドあり（精度ヒント）

### 2026-05-05: geocoding.jp 採用 + 中断/再開対応スクリプト作成
- `geocodingjp_search.py` を作成
- 設計:
  - 進捗JSONに5件ごと/60秒ごと自動保存
  - SIGINT（Ctrl+C）で安全停止 → 再起動で続き
  - レート制限sleepも細切れにして停止応答性を確保
  - 統計（OK_no/OK_yes/NG）と残り時間ETAを表示
- 5件テスト走行で動作確認
- **観測**: needs_verify=yes でも座標が高崎市外に飛ぶケースあり（例：セブン-イレブン高崎倉賀野店 → 138.79は安中市側）
- → 最終マージ時に高崎市バウンディングボックスでバリデーションする方針

### 2026-05-05〜06: geocoding.jp 全件実行 + cp932クラッシュ復旧
- 初回実行で282/3161件処理時にUnicodeEncodeErrorで停止
  - 原因：店舗名の `é` 文字をWindowsコンソールが扱えない
  - 修正：`sys.stdout.reconfigure(encoding='utf-8')` を script 冒頭に追加
- 再起動して継続、PCスリープを跨いで完走
- 結果（ユニーク3,154件）：
  - ok: 3,039件（needs_verify=no:18 / yes:3,021）
  - exception: 71件 / zero_coord: 40件 / error: 4件

### 2026-05-05: フロントエンド初期実装
- `web/index.html` `web/style.css` `web/app.js` でシンプル一画面構成
- Leaflet 1.9.4 + markercluster + 国土地理院タイル
- 業種フィルタ・テキスト検索・現在位置取得（FAB）
- ヘッドレスEdgeでスクショ撮影による視覚確認

### 2026-05-05: GitHub Pages デプロイ
- `gh repo create komatubara/takasaki-shoken-map --public`
- `.github/workflows/deploy-pages.yml` で web/ をアーティファクトとしてアップロード
- gh API で `build_type=workflow` 設定
- 公開URL: https://komatubara.github.io/takasaki-shoken-map/
- main push で自動再デプロイ

### 2026-05-06: 最終マージ・bboxバリデーション・本番反映
- bbox判定の初期設定 (138.85, 36.18, 139.10, 36.50) は **狭すぎ**
  - 倉渕町・新町・榛名山町（2006年合併編入地域）が除外されてしまう
  - GSI町代表点の実範囲を確認し (138.75, 36.18, 139.15, 36.50) に拡大
- `scripts/merge_final.py` で結果統合
  - geocoding.jp座標がbbox内 → 採用 (needs_verify=no→exact、yes→approx)
  - bbox外 or 失敗 → GSI町代表点にフォールバック (town)
- 最終内訳：
  - exact: 17件 / approx: 3,009件 / town: 133件 / none: 2件
  - **95.7%が店舗名検索による実位置レベルに精度向上**
- 例: 「ジョイフーズ高崎西店」が町中心点から約220m西の実店舗位置に補正
- 例: 上佐野町の13店舗が同一点重複から個別座標に分散

### 次のステップ
- 実機での動作確認（ユーザー帰宅後）
- 64カテゴリの整理（多すぎる場合のグルーピング）
- PWA対応（manifest.json + service-worker.js）
- 失敗115件のうち復旧可能な店舗の手動修正検討

---

## 技術メモ

### 国土地理院ジオコーディングAPI
- URL: `https://msearch.gsi.go.jp/address-search/AddressSearch?q={住所}`
- レスポンス: GeoJSON Feature の配列
- 座標: `[lng, lat]` の順（GeoJSON標準）
- レート制限: 公式記述なし、礼儀として0.2秒間隔で運用
- 認証不要・無料・日本住所に強い

### Nominatim API
- URL: `https://nominatim.openstreetmap.org/search?q={query}&format=json&countrycodes=jp&limit=1`
- レート制限: **1リクエスト/秒**（厳守）
- User-Agent ヘッダー必須（連絡先含めるのが望ましい）
- 日本のPOIカバレッジは限定的、ブランド系は中、個人商店は弱

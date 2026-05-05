"""
Nominatim API で店舗POI検索を実行（フェーズ2）
- レート制限: 1リクエスト/秒（公式ガイドライン）
- 失敗・成功問わず、進捗を nominatim_progress.json に逐次保存
- 中断後に再開可能
"""
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

INPUT_CSV = '高崎市民商品券取扱店一覧_geo_phase1.csv'
PROGRESS_JSON = 'nominatim_progress.json'
USER_AGENT = 'TakasakiVoucherMap/1.0 (komainu022.ryou@gmail.com)'

# 進捗読み込み（再開用）
if os.path.exists(PROGRESS_JSON):
    with open(PROGRESS_JSON, 'r', encoding='utf-8') as f:
        progress = json.load(f)
else:
    progress = {}

# 元データ読み込み
rows = []
with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"対象: {len(rows)}件 / 既存進捗: {len(progress)}件", flush=True)

def clean_store_name(name):
    """店舗名のクレンジング: 全角スペース・括弧内などを整理"""
    name = name.strip()
    # 半角スペース置換
    name = name.replace('　', ' ')
    # 括弧内除去（補足が混乱要因になることが多い）
    name = re.sub(r'[\(（].*?[\)）]', '', name)
    return name.strip()

def query_nominatim(store, town):
    """Nominatim検索: 店舗名 + 高崎市 + 町名"""
    cleaned = clean_store_name(store)
    query = f"{cleaned} 群馬県高崎市{town}"
    url = (
        f"https://nominatim.openstreetmap.org/search?"
        f"q={urllib.parse.quote(query)}"
        f"&format=json&countrycodes=jp&limit=1"
    )
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode('utf-8'))
        if data:
            return {
                'lat': float(data[0]['lat']),
                'lng': float(data[0]['lon']),
                'display_name': data[0].get('display_name', ''),
            }
    except Exception as e:
        print(f"  ERROR {store}: {e}", file=sys.stderr, flush=True)
    return None

# メインループ
hits = sum(1 for v in progress.values() if v is not None)
miss = sum(1 for v in progress.values() if v is None)
last_save = time.time()

for i, row in enumerate(rows, 1):
    store = row['店舗名'].strip() if row['店舗名'] else ''
    town = row['町名'].strip() if row['町名'] else ''
    if not store:
        continue

    key = f"{store}|{town}"
    if key in progress:
        continue

    result = query_nominatim(store, town)
    progress[key] = result
    if result:
        hits += 1
    else:
        miss += 1

    # 30件ごと、または60秒ごとに進捗保存
    if i % 30 == 0 or (time.time() - last_save) > 60:
        with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=1)
        last_save = time.time()
        print(f"  進捗 {i}/{len(rows)} hit:{hits} miss:{miss}", flush=True)

    # Nominatim利用規約: 1秒以上の間隔
    time.sleep(1.05)

# 最終保存
with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
    json.dump(progress, f, ensure_ascii=False, indent=1)

print(f"\n=== Nominatim検索完了 ===", flush=True)
print(f"処理済: {len(progress)}件", flush=True)
print(f"hit: {hits} / miss: {miss}", flush=True)
print(f"ヒット率: {hits/len(progress)*100:.1f}%", flush=True)

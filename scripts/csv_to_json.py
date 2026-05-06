"""CSV → web/data/stores.json 変換

入力: 高崎市民商品券取扱店一覧_geo_final.csv
出力: web/data/stores.json

機能:
- 同一町に重なる店舗にハッシュベースのジッター付加（最大±50m程度）
- 店舗IDの自動採番
- カテゴリ一覧の抽出
- メタ情報（生成日時・件数・精度内訳）を埋め込み
"""
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config
from lib.progress import setup_utf8_stdout


def jitter(seed_str, scale_lat=0.00025, scale_lng=0.0003):
    """店舗名+町名から決定的に座標オフセットを生成（同じ入力→同じオフセット）"""
    h = hashlib.md5(seed_str.encode('utf-8')).digest()
    fx = (int.from_bytes(h[0:4], 'big') / 0xFFFFFFFF) * 2 - 1
    fy = (int.from_bytes(h[4:8], 'big') / 0xFFFFFFFF) * 2 - 1
    return fx * scale_lat, fy * scale_lng


def main():
    setup_utf8_stdout()
    stores = []
    categories = set()
    precision_counts = {'town': 0, 'none': 0, 'exact': 0, 'approx': 0}

    with open(config.FINAL_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            name = (row.get('店舗名') or '').strip()
            if not name:
                continue

            town = (row.get('町名') or '').strip()
            phone = (row.get('電話番号') or '').strip()
            category = (row.get('取り扱い商品・サービス') or '').strip()
            mall = (row.get('大型店') or '').strip()
            precision = (row.get('精度') or 'none').strip()
            source = (row.get('ソース') or '').strip()

            try:
                lat = float(row.get('lat') or 0)
                lng = float(row.get('lng') or 0)
            except ValueError:
                lat = lng = 0

            if category:
                categories.add(category)

            # 座標があり町精度の場合はジッター付加（重なり回避）
            if lat and lng and precision == 'town':
                dlat, dlng = jitter(f"{name}|{town}")
                lat += dlat
                lng += dlng

            precision_counts[precision] = precision_counts.get(precision, 0) + 1

            stores.append({
                'id': i,
                'name': name,
                'town': town,
                'phone': phone,
                'category': category,
                'mall': mall,
                'lat': round(lat, 6) if lat else None,
                'lng': round(lng, 6) if lng else None,
                'precision': precision,
                'source': source,
            })

    output = {
        'meta': {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'source': config.FINAL_CSV.name,
            'count': len(stores),
            'precision_counts': precision_counts,
        },
        'categories': sorted(categories),
        'stores': stores,
    }

    config.WEB_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(config.WEB_DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = config.WEB_DATA_JSON.stat().st_size / 1024
    print(f"✓ 出力: {config.WEB_DATA_JSON.relative_to(config.ROOT)}")
    print(f"  店舗数: {len(stores)}件")
    print(f"  カテゴリ数: {len(categories)}件")
    print(f"  精度内訳: {precision_counts}")
    print(f"  ファイルサイズ: {size_kb:.1f} KB")


if __name__ == '__main__':
    main()

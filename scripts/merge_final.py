"""最終マージスクリプト

geocoding.jp 結果 + GSI町代表点 + 手動補正(任意) を統合し、
bboxバリデーション込みで最終CSV (高崎市民商品券取扱店一覧_geo_final.csv) を生成する。

採用ロジック（優先順位）:
  1. corrections_template.csv の「補正lat/補正lng」が両方埋まっていれば最優先
     → 精度 manual / ソース corrections
  2. geocoding.jp の座標が高崎市bbox内
     → needs_verify=no  → 精度 exact
     → needs_verify=yes → 精度 approx
     → ソース geocoding.jp
  3. それ以外（API失敗 or bbox外）かつ町名が辞書にあれば
     → GSI町代表点 / 精度 town / ソース gsi
  4. それ以外
     → 座標なし / 精度 none
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config
from lib.geocoding import in_takasaki_bbox
from lib.progress import setup_utf8_stdout


def load_corrections():
    """corrections_template.csv を読み、有効な補正のみ {key: (lat, lng, memo)} で返す

    補正lat/補正lng が両方とも数値として解釈できる行のみを採用。
    """
    corrections = {}
    if not config.CORRECTIONS_CSV.exists():
        return corrections

    with open(config.CORRECTIONS_CSV, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            store = (row.get('店舗名') or '').strip()
            town = (row.get('町名') or '').strip()
            try:
                lat = float((row.get('補正lat') or '').strip())
                lng = float((row.get('補正lng') or '').strip())
            except ValueError:
                continue
            # 高崎市bbox内チェック（外なら無効）
            if not in_takasaki_bbox(lat, lng):
                continue
            key = f"{store}|{town}"
            corrections[key] = (lat, lng, (row.get('メモ') or '').strip())
    return corrections


def main():
    setup_utf8_stdout()

    with open(config.GEOCODING_PROGRESS, encoding='utf-8') as f:
        gj_results = json.load(f)
    with open(config.TOWN_COORDS, encoding='utf-8') as f:
        town_coords = json.load(f)
    corrections = load_corrections()

    stats = {'manual': 0, 'exact': 0, 'approx': 0, 'town': 0, 'none': 0,
             'gj_used': 0, 'gj_outlier': 0, 'gj_failed': 0}

    rows_out = []
    with open(config.INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            store = (row.get('店舗名') or '').strip()
            town = (row.get('町名') or '').strip()

            lat = lng = None
            precision = 'none'
            source = ''

            if store:
                key = f"{store}|{town}"

                # ① 手動補正があれば最優先
                if key in corrections:
                    lat, lng, _memo = corrections[key]
                    precision = 'manual'
                    source = 'corrections'
                else:
                    # ② geocoding.jp の結果（bbox内のみ）
                    gj = gj_results.get(key)
                    if gj and gj.get('status') == 'ok':
                        g_lat, g_lng = gj.get('lat'), gj.get('lng')
                        if g_lat and g_lng and in_takasaki_bbox(g_lat, g_lng):
                            lat, lng = g_lat, g_lng
                            precision = 'exact' if gj.get('needs_verify') == 'no' else 'approx'
                            source = 'geocoding.jp'
                            stats['gj_used'] += 1
                        else:
                            stats['gj_outlier'] += 1
                    else:
                        stats['gj_failed'] += 1

                    # ③ フォールバック: GSI町代表点
                    if lat is None and town and town in town_coords:
                        tc = town_coords[town]
                        lat, lng = tc['lat'], tc['lng']
                        precision = 'town'
                        source = 'gsi'

            stats[precision] = stats.get(precision, 0) + 1

            row['lat'] = round(lat, 6) if lat else ''
            row['lng'] = round(lng, 6) if lng else ''
            row['精度'] = precision
            row['ソース'] = source
            rows_out.append(row)

    fieldnames = ['店舗名', '町名', '電話番号', '取り扱い商品・サービス', '大型店',
                  'lat', 'lng', '精度', 'ソース']
    with open(config.FINAL_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"✓ 出力: {config.FINAL_CSV.name}")
    print(f"  全店舗数: {len(rows_out)}件")
    if corrections:
        print(f"  ※ corrections_template.csv の有効な補正: {len(corrections)}件")
    print()
    print(f"=== 精度内訳 ===")
    print(f"  manual (手動補正):              {stats['manual']:>5}件")
    print(f"  exact  (geocoding.jp 高精度):   {stats['exact']:>5}件")
    print(f"  approx (geocoding.jp 通常):     {stats['approx']:>5}件")
    print(f"  town   (GSI町代表点フォールバック): {stats['town']:>5}件")
    print(f"  none   (位置情報なし):           {stats['none']:>5}件")
    print()
    print(f"=== geocoding.jp 採用判定 ===")
    print(f"  採用 (bbox内):  {stats['gj_used']:>5}件")
    print(f"  除外 (bbox外):  {stats['gj_outlier']:>5}件 → GSI町代表点へフォールバック")
    print(f"  API失敗:        {stats['gj_failed']:>5}件 → GSI町代表点へフォールバック")


if __name__ == '__main__':
    main()

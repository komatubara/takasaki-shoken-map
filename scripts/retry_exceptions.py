"""
geocoding.jp で exception 発生した店舗を、特殊文字除去版でリトライ

対象: geocodingjp_progress.json の status='exception' エントリ
処理: 店舗名から '&' '＆' を空白に置換してリトライ
       その他の例外（通信エラー等）も同様にリトライ
書込: 同じキーで上書き（成功した場合のみ）。失敗した場合は元のexceptionを残す。
"""
import csv
import json
import os
import re
import signal
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROGRESS_JSON = 'geocodingjp_progress.json'
USER_AGENT = 'TakasakiVoucherMap/1.0 (komainu022.ryou@gmail.com; personal-use)'
RATE_LIMIT_SEC = 10.5

_should_exit = False


def handle_sigint(signum, frame):
    global _should_exit
    if _should_exit:
        sys.exit(1)
    _should_exit = True
    print("\n[停止要求] 進捗保存後に終了", flush=True)


def clean_store_name(name):
    """特殊文字を除去・置換した店舗名を返す"""
    s = name.strip().replace('　', ' ')
    s = s.replace('&', ' ').replace('＆', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def query_geocodingjp(query):
    url = f"https://www.geocoding.jp/api/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            xml_text = res.read().decode('utf-8')
        root = ET.fromstring(xml_text)
        err = root.find('error')
        if err is not None:
            return {'status': 'error', 'message': err.text or 'unknown'}
        coord = root.find('coordinate')
        if coord is None:
            return {'status': 'no_coord'}
        lat_el, lng_el = coord.find('lat'), coord.find('lng')
        if lat_el is None or lng_el is None:
            return {'status': 'no_coord'}
        try:
            lat, lng = float(lat_el.text), float(lng_el.text)
        except (ValueError, TypeError):
            return {'status': 'parse_error'}
        if lat == 0.0 and lng == 0.0:
            return {'status': 'zero_coord'}
        verify_el = root.find('needs_to_verify')
        gmap_el = root.find('google_maps')
        addr_el = root.find('address')
        return {
            'status': 'ok',
            'lat': lat, 'lng': lng,
            'needs_verify': verify_el.text if verify_el is not None else None,
            'google_maps': gmap_el.text if gmap_el is not None else None,
            'matched_address': addr_el.text if addr_el is not None else None,
        }
    except Exception as e:
        return {'status': 'exception', 'message': str(e)}


def main():
    signal.signal(signal.SIGINT, handle_sigint)

    with open(PROGRESS_JSON, 'r', encoding='utf-8') as f:
        progress = json.load(f)

    # exception 対象を抽出
    targets = [(k, v) for k, v in progress.items()
               if v and v.get('status') == 'exception']
    print(f"=== リトライ対象: {len(targets)}件 ===")
    print(f"予想所要時間: 約 {len(targets) * RATE_LIMIT_SEC / 60:.1f}分")
    print("-" * 60, flush=True)

    recovered_ok = recovered_other = still_exc = 0
    for i, (key, old) in enumerate(targets, 1):
        if _should_exit:
            break
        store, town = key.split('|', 1)
        cleaned = clean_store_name(store)
        # 元のクエリ
        if cleaned:
            query = f"{cleaned} 高崎市{town}" if town else f"{cleaned} 高崎市"
        else:
            print(f"[SKIP] {i}/{len(targets)} {store} (クレンジング後が空)")
            continue

        result = query_geocodingjp(query)

        if result.get('status') == 'ok':
            progress[key] = result
            recovered_ok += 1
            mark = 'OK'
        elif result.get('status') == 'exception':
            # 失敗が続く場合は元データを残す
            still_exc += 1
            mark = 'EXC'
        else:
            # zero_coord/error/no_coord等：上書きする（少なくとも分類が変わる）
            progress[key] = result
            recovered_other += 1
            mark = result.get('status', '?')[:7]

        print(f"[{mark:<7}] {i}/{len(targets)} {store[:35]:<35} | OK:{recovered_ok} 他:{recovered_other} EXC:{still_exc}", flush=True)

        # 5件ごとに保存
        if i % 5 == 0:
            with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=1)

        # レート制限
        if not _should_exit and i < len(targets):
            t_end = time.time() + RATE_LIMIT_SEC
            while time.time() < t_end:
                if _should_exit:
                    break
                time.sleep(min(0.5, t_end - time.time()))

    # 最終保存
    with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=1)

    print()
    print("=" * 60)
    print(f"OK復旧:       {recovered_ok}件")
    print(f"その他に変化: {recovered_other}件 (zero_coord/no_coord等)")
    print(f"依然exception: {still_exc}件")


if __name__ == '__main__':
    main()

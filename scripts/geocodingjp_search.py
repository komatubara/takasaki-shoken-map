"""
geocoding.jp で店舗ジオコーディング（中断/再開対応）

特徴:
- レート制限: 1req/10.5秒（10秒制約 + 安全マージン）
- 進捗保存: 5件処理ごと、または60秒経過ごと
- Ctrl+C で安全停止 → 進捗保存して終了
- 再起動時は既処理キーをスキップして続行
- needs_to_verify=no/yes で精度を区分

使い方:
    python geocodingjp_search.py
    # 中断: Ctrl+C
    # 再開: もう一度同じコマンド実行
"""
import csv
import json
import os
import signal
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Windows: 標準出力をUTF-8に切替（店舗名にアクセント付き文字が含まれてもクラッシュしない）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

INPUT_CSV = '高崎市民商品券取扱店一覧_geo_phase1.csv'
PROGRESS_JSON = 'geocodingjp_progress.json'
USER_AGENT = 'TakasakiVoucherMap/1.0 (komainu022.ryou@gmail.com; personal-use)'
RATE_LIMIT_SEC = 10.5  # 規約の10秒+0.5秒マージン
SAVE_EVERY_N = 5
SAVE_EVERY_SEC = 60

# グローバル状態（シグナルハンドラから参照）
_progress = {}
_dirty = False  # 未保存の変更がある
_should_exit = False  # Ctrl+C検出フラグ


def save_progress():
    """進捗をJSONに保存"""
    global _dirty
    tmp = PROGRESS_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_progress, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS_JSON)
    _dirty = False


def handle_sigint(signum, frame):
    """Ctrl+C対応: フラグを立てるだけ。実際の終了はメインループで処理"""
    global _should_exit
    if _should_exit:
        # 2回目のCtrl+Cで強制終了
        print("\n[強制終了]", flush=True)
        sys.exit(1)
    _should_exit = True
    print("\n[停止要求受信] 進捗を保存して安全に終了します（もう一度Ctrl+Cで強制終了）", flush=True)


def query_geocodingjp(query):
    """geocoding.jp APIへ問い合わせ。成功時dict、失敗時None"""
    url = f"https://www.geocoding.jp/api/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            xml_text = res.read().decode('utf-8')
        root = ET.fromstring(xml_text)

        # エラー応答チェック
        err = root.find('error')
        if err is not None:
            return {'status': 'error', 'message': err.text or 'unknown'}

        coord = root.find('coordinate')
        if coord is None:
            return {'status': 'no_coord'}

        lat_el = coord.find('lat')
        lng_el = coord.find('lng')
        if lat_el is None or lng_el is None:
            return {'status': 'no_coord'}

        try:
            lat = float(lat_el.text)
            lng = float(lng_el.text)
        except (ValueError, TypeError):
            return {'status': 'parse_error'}

        # 0,0は実質的に無効
        if lat == 0.0 and lng == 0.0:
            return {'status': 'zero_coord'}

        verify_el = root.find('needs_to_verify')
        gmap_el = root.find('google_maps')
        addr_el = root.find('address')

        return {
            'status': 'ok',
            'lat': lat,
            'lng': lng,
            'needs_verify': verify_el.text if verify_el is not None else None,
            'google_maps': gmap_el.text if gmap_el is not None else None,
            'matched_address': addr_el.text if addr_el is not None else None,
        }
    except Exception as e:
        return {'status': 'exception', 'message': str(e)}


def make_query(store, town):
    """店舗+町名のクエリ文字列を組み立て"""
    store = store.strip().replace('　', ' ')
    if town:
        return f"{store} 高崎市{town.strip()}"
    return f"{store} 高崎市"


def make_key(store, town):
    """進捗辞書のキー"""
    return f"{store.strip()}|{(town or '').strip()}"


def format_eta(remaining_count):
    """残り時間を人間可読に"""
    sec = remaining_count * RATE_LIMIT_SEC
    if sec < 60:
        return f"{sec:.0f}秒"
    if sec < 3600:
        return f"{sec/60:.1f}分"
    return f"{sec/3600:.1f}時間"


def main():
    global _progress, _dirty

    signal.signal(signal.SIGINT, handle_sigint)

    # 進捗読込
    if os.path.exists(PROGRESS_JSON):
        with open(PROGRESS_JSON, 'r', encoding='utf-8') as f:
            _progress = json.load(f)
        print(f"[再開] 既存進捗: {len(_progress)}件", flush=True)
    else:
        print("[初回起動]", flush=True)

    # 入力読込
    rows = []
    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            store = (row.get('店舗名') or '').strip()
            if store:  # 店舗名のあるもののみ対象
                rows.append(row)

    total = len(rows)
    pending = [r for r in rows if make_key(r['店舗名'], r['町名']) not in _progress]
    eta = format_eta(len(pending))

    print(f"対象店舗: {total}件 / 未処理: {len(pending)}件", flush=True)
    print(f"予想所要時間: {eta}", flush=True)
    print(f"完了予定: {(datetime.now() + timedelta(seconds=len(pending)*RATE_LIMIT_SEC)).strftime('%Y-%m-%d %H:%M')}", flush=True)
    print("-" * 60, flush=True)

    if not pending:
        print("すべて処理済みです。", flush=True)
        return

    # 統計カウンタ
    stats = {'ok_no': 0, 'ok_yes': 0, 'fail': 0}
    for v in _progress.values():
        if v and v.get('status') == 'ok':
            if v.get('needs_verify') == 'no':
                stats['ok_no'] += 1
            else:
                stats['ok_yes'] += 1
        else:
            stats['fail'] += 1

    last_save = time.time()
    processed_in_run = 0
    start_time = time.time()

    try:
        for idx, row in enumerate(pending, 1):
            if _should_exit:
                break

            store = row['店舗名'].strip()
            town = (row['町名'] or '').strip()
            key = make_key(store, town)

            # 二重チェック（並行実行回避）
            if key in _progress:
                continue

            query = make_query(store, town)
            result = query_geocodingjp(query)
            _progress[key] = result
            _dirty = True
            processed_in_run += 1

            # 統計更新
            if result.get('status') == 'ok':
                if result.get('needs_verify') == 'no':
                    stats['ok_no'] += 1
                    mark = 'OK'
                else:
                    stats['ok_yes'] += 1
                    mark = '~'
            else:
                stats['fail'] += 1
                mark = 'NG'

            # 進捗ログ
            elapsed = time.time() - start_time
            remaining_in_run = len(pending) - idx
            avg_per_item = elapsed / processed_in_run if processed_in_run else RATE_LIMIT_SEC
            eta_sec = remaining_in_run * avg_per_item
            print(
                f"[{mark}] {idx}/{len(pending)} ({(idx/len(pending)*100):.1f}%) "
                f"{store[:25]:<25} | "
                f"OK_no:{stats['ok_no']} OK_yes:{stats['ok_yes']} NG:{stats['fail']} | "
                f"残り {format_eta(remaining_in_run)}",
                flush=True
            )

            # 保存判定
            if (processed_in_run % SAVE_EVERY_N == 0) or (time.time() - last_save > SAVE_EVERY_SEC):
                save_progress()
                last_save = time.time()

            # レート制限
            if not _should_exit and idx < len(pending):
                # 細切れsleepで停止要求への応答性を確保
                t_end = time.time() + RATE_LIMIT_SEC
                while time.time() < t_end:
                    if _should_exit:
                        break
                    time.sleep(min(0.5, t_end - time.time()))

    finally:
        if _dirty:
            save_progress()
            print(f"\n[保存完了] {PROGRESS_JSON}", flush=True)

    # サマリ
    print("\n" + "=" * 60, flush=True)
    print(f"このセッションの処理: {processed_in_run}件", flush=True)
    print(f"累計処理: {len(_progress)}件 / 全{total}件", flush=True)
    print(f"  高精度(OK_no):  {stats['ok_no']}件", flush=True)
    print(f"  低精度(OK_yes): {stats['ok_yes']}件", flush=True)
    print(f"  失敗(NG):       {stats['fail']}件", flush=True)
    remain = total - len(_progress)
    if remain > 0:
        print(f"  未処理:         {remain}件 (再実行で続行)", flush=True)


if __name__ == '__main__':
    main()

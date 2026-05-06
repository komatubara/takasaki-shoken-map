"""geocoding.jp で全店舗ジオコーディング（中断/再開対応）

特徴:
- レート制限: 1req/10.5秒（規約10秒+安全マージン）
- 進捗保存: 5件処理ごと、または60秒経過ごと
- Ctrl+C で安全停止 → 進捗保存して終了
- 再起動時は既処理キーをスキップして続行
- needs_to_verify=no/yes で精度を区分

使い方:
    python scripts/geocodingjp_search.py
    # 中断: Ctrl+C
    # 再開: もう一度同じコマンド実行
"""
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config
from lib.geocoding import build_query, query_geocodingjp
from lib.progress import (load_progress, save_progress, setup_sigint_handler,
                          setup_utf8_stdout, should_exit)


def make_key(store, town):
    """進捗辞書のキー（店舗名|町名）"""
    return f"{store.strip()}|{(town or '').strip()}"


def format_eta(remaining_count):
    """残り時間を人間可読に"""
    sec = remaining_count * config.RATE_LIMIT_SEC
    if sec < 60:
        return f"{sec:.0f}秒"
    if sec < 3600:
        return f"{sec/60:.1f}分"
    return f"{sec/3600:.1f}時間"


def collect_initial_stats(progress):
    """既存進捗から精度統計を集計"""
    stats = {'ok_no': 0, 'ok_yes': 0, 'fail': 0}
    for v in progress.values():
        if v and v.get('status') == 'ok':
            if v.get('needs_verify') == 'no':
                stats['ok_no'] += 1
            else:
                stats['ok_yes'] += 1
        else:
            stats['fail'] += 1
    return stats


def main():
    setup_utf8_stdout()
    setup_sigint_handler()

    progress = load_progress(config.GEOCODING_PROGRESS)
    if progress:
        print(f"[再開] 既存進捗: {len(progress)}件", flush=True)
    else:
        print("[初回起動]", flush=True)

    # 入力CSVから店舗一覧を読込
    rows = []
    with open(config.INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            store = (row.get('店舗名') or '').strip()
            if store:
                rows.append(row)

    total = len(rows)
    pending = [r for r in rows if make_key(r['店舗名'], r['町名']) not in progress]

    print(f"対象店舗: {total}件 / 未処理: {len(pending)}件", flush=True)
    print(f"予想所要時間: {format_eta(len(pending))}", flush=True)
    eta_dt = datetime.now() + timedelta(seconds=len(pending) * config.RATE_LIMIT_SEC)
    print(f"完了予定: {eta_dt.strftime('%Y-%m-%d %H:%M')}", flush=True)
    print("-" * 60, flush=True)

    if not pending:
        print("すべて処理済みです。", flush=True)
        return

    stats = collect_initial_stats(progress)
    last_save = time.time()
    processed_in_run = 0
    start_time = time.time()
    dirty = False

    try:
        for idx, row in enumerate(pending, 1):
            if should_exit():
                break

            store = row['店舗名'].strip()
            town = (row['町名'] or '').strip()
            key = make_key(store, town)

            if key in progress:  # 二重チェック（並行実行回避）
                continue

            query = build_query(store, town)
            result = query_geocodingjp(query)
            progress[key] = result
            dirty = True
            processed_in_run += 1

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

            elapsed = time.time() - start_time
            remaining_in_run = len(pending) - idx
            avg_per_item = elapsed / processed_in_run if processed_in_run else config.RATE_LIMIT_SEC
            print(
                f"[{mark}] {idx}/{len(pending)} ({(idx/len(pending)*100):.1f}%) "
                f"{store[:25]:<25} | "
                f"OK_no:{stats['ok_no']} OK_yes:{stats['ok_yes']} NG:{stats['fail']} | "
                f"残り {format_eta(remaining_in_run)}",
                flush=True
            )

            # 保存判定
            if (processed_in_run % config.SAVE_EVERY_N == 0) or \
               (time.time() - last_save > config.SAVE_EVERY_SEC):
                save_progress(config.GEOCODING_PROGRESS, progress)
                dirty = False
                last_save = time.time()

            # レート制限（細切れsleepで停止応答性を確保）
            if not should_exit() and idx < len(pending):
                t_end = time.time() + config.RATE_LIMIT_SEC
                while time.time() < t_end:
                    if should_exit():
                        break
                    time.sleep(min(0.5, t_end - time.time()))

    finally:
        if dirty:
            save_progress(config.GEOCODING_PROGRESS, progress)
            print(f"\n[保存完了] {config.GEOCODING_PROGRESS.name}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(f"このセッションの処理: {processed_in_run}件", flush=True)
    print(f"累計処理: {len(progress)}件 / 全{total}件", flush=True)
    print(f"  高精度(OK_no):  {stats['ok_no']}件", flush=True)
    print(f"  低精度(OK_yes): {stats['ok_yes']}件", flush=True)
    print(f"  失敗(NG):       {stats['fail']}件", flush=True)
    remain = total - len(progress)
    if remain > 0:
        print(f"  未処理:         {remain}件 (再実行で続行)", flush=True)


if __name__ == '__main__':
    main()

"""geocoding.jp で exception 発生した店舗を、特殊文字除去版でリトライ

対象: geocodingjp_progress.json の status='exception' エントリ
処理: 店舗名から '&' '＆' を空白に置換してリトライ
書込: 同じキーで上書き（成功した場合のみ）。失敗した場合は元のexceptionを残す。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config
from lib.geocoding import build_query, query_geocodingjp
from lib.progress import (load_progress, save_progress, setup_sigint_handler,
                          setup_utf8_stdout, should_exit)


def main():
    setup_utf8_stdout()
    setup_sigint_handler()

    progress = load_progress(config.GEOCODING_PROGRESS)

    # exception 対象を抽出
    targets = [(k, v) for k, v in progress.items()
               if v and v.get('status') == 'exception']
    print(f"=== リトライ対象: {len(targets)}件 ===")
    print(f"予想所要時間: 約 {len(targets) * config.RATE_LIMIT_SEC / 60:.1f}分")
    print("-" * 60, flush=True)

    recovered_ok = recovered_other = still_exc = 0
    for i, (key, _old) in enumerate(targets, 1):
        if should_exit():
            break

        store, town = key.split('|', 1)
        query = build_query(store, town, clean_special=True)
        if not query:
            print(f"[SKIP   ] {i}/{len(targets)} {store} (クレンジング後が空)")
            continue

        result = query_geocodingjp(query)

        if result.get('status') == 'ok':
            progress[key] = result
            recovered_ok += 1
            mark = 'OK'
        elif result.get('status') == 'exception':
            still_exc += 1
            mark = 'EXC'
        else:
            progress[key] = result
            recovered_other += 1
            mark = result.get('status', '?')[:7]

        print(f"[{mark:<7}] {i}/{len(targets)} {store[:35]:<35} | "
              f"OK:{recovered_ok} 他:{recovered_other} EXC:{still_exc}",
              flush=True)

        # 5件ごとに保存
        if i % config.SAVE_EVERY_N == 0:
            save_progress(config.GEOCODING_PROGRESS, progress)

        # レート制限
        if not should_exit() and i < len(targets):
            t_end = time.time() + config.RATE_LIMIT_SEC
            while time.time() < t_end:
                if should_exit():
                    break
                time.sleep(min(0.5, t_end - time.time()))

    save_progress(config.GEOCODING_PROGRESS, progress)

    print()
    print("=" * 60)
    print(f"OK復旧:        {recovered_ok}件")
    print(f"その他に変化:  {recovered_other}件 (zero_coord/no_coord等)")
    print(f"依然exception: {still_exc}件")


if __name__ == '__main__':
    main()

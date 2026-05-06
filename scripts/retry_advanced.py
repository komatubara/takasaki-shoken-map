"""town精度（GSI町中心へフォールバック）の店舗を、複数クエリ戦略でリトライ

失敗タイプ別に1〜3個の戦略を順に試し、最初の「OK応答かつbbox内」で採用。

戦略:
  zero_coord → ①「高崎」除去  ②「◯◯店」除去  ③ 群馬県付加
  exception  → ① 日本語のみ   ② 記号除去      ③ 群馬県付加
  bbox外     → ① 群馬県強調   ② 簡略化+群馬県
  error      → ① 単純再試行
"""
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config
from lib.geocoding import in_takasaki_bbox, query_geocodingjp
from lib.progress import (load_progress, save_progress, setup_sigint_handler,
                          setup_utf8_stdout, should_exit)


# ===== 文字列クレンジング =====

def japanese_only(s):
    """日本語（ひらがな・カタカナ・漢字・長音）以外を除去"""
    return re.sub(r'[^ぁ-ゖァ-ヺ一-鿿ー]', '', s).strip()


def strip_takasaki(s):
    """店舗名から「高崎」を除去"""
    return re.sub(r'高崎', '', s).strip()


def strip_branch_suffix(s):
    """末尾の「◯◯店」を除去（半角/全角スペース区切り）"""
    return re.sub(r'\s+\S+店$', '', s).strip()


def strip_symbols(s):
    """`&` `＆` `.` `'` `'` 等の記号を除去"""
    s = re.sub(r"[&＆.''’\"#$%]", '', s)
    return re.sub(r'\s+', ' ', s).strip()


# ===== 戦略生成 =====

def build_strategies(store, town, failure_type):
    """失敗タイプに応じたリトライ用クエリのリストを返す

    Returns:
        List[(label, query)]
    """
    s = store.strip().replace('　', ' ')
    strategies = []

    if failure_type == 'zero_coord':
        c1 = strip_takasaki(s)
        if c1 and c1 != s:
            strategies.append(('高崎除去', f"{c1} 高崎市{town}"))
        c2 = strip_branch_suffix(s)
        if c2 and c2 != s:
            strategies.append(('支店名除去', f"{c2} 高崎市{town}"))
        strategies.append(('群馬県付加', f"{s} 群馬県高崎市{town}"))

    elif failure_type == 'exception':
        ja = japanese_only(s)
        if ja:
            strategies.append(('日本語のみ', f"{ja} 高崎市{town}"))
        no_sym = strip_symbols(s)
        if no_sym and no_sym != s:
            strategies.append(('記号除去', f"{no_sym} 高崎市{town}"))
        strategies.append(('群馬県付加', f"{s} 群馬県高崎市{town}"))

    elif failure_type == 'bbox_out':
        strategies.append(('群馬県強調', f"群馬県高崎市{town} {s}"))
        c = strip_branch_suffix(strip_takasaki(s))
        if c and c != s:
            strategies.append(('簡略化+群馬県', f"群馬県高崎市{town} {c}"))

    elif failure_type == 'error':
        strategies.append(('再試行', f"{s} 高崎市{town}"))

    return strategies


# ===== レート制限ヘルパー =====

def rate_limit_sleep():
    """RATE_LIMIT_SEC待機。should_exit()が立ったら早期終了。"""
    t_end = time.time() + config.RATE_LIMIT_SEC
    while time.time() < t_end:
        if should_exit():
            break
        time.sleep(min(0.5, t_end - time.time()))


# ===== 対象抽出 =====

def collect_targets(progress):
    """final CSVを読んで town精度の店舗を、失敗タイプ付きで返す"""
    targets = []
    with open(config.FINAL_CSV, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row.get('精度') != 'town':
                continue
            store = (row['店舗名'] or '').strip()
            town = (row['町名'] or '').strip()
            if not store:
                continue
            key = f"{store}|{town}"
            gj = progress.get(key)
            if not gj:
                continue

            status = gj.get('status', '?')
            if status == 'ok':
                lat, lng = gj.get('lat'), gj.get('lng')
                if lat is not None and lng is not None and not in_takasaki_bbox(lat, lng):
                    failure_type = 'bbox_out'
                else:
                    continue  # bbox内ならスキップ（採用済み）
            elif status == 'zero_coord':
                failure_type = 'zero_coord'
            elif status == 'exception':
                failure_type = 'exception'
            elif status == 'error':
                failure_type = 'error'
            else:
                continue  # 不明ステータスは対象外

            targets.append((key, store, town, failure_type))
    return targets


# ===== メイン処理 =====

def main():
    setup_utf8_stdout()
    setup_sigint_handler()

    progress = load_progress(config.GEOCODING_PROGRESS)
    targets = collect_targets(progress)

    if not targets:
        print("リトライ対象なし。すべて採用済みです。", flush=True)
        return

    # 戦略数を概算（最大値）
    max_queries = sum(len(build_strategies(s, t, ft)) for _, s, t, ft in targets)
    print(f"=== 高度リトライ対象: {len(targets)}件 ===")
    print(f"最大クエリ数: {max_queries}件")
    print(f"最大所要時間: {max_queries * config.RATE_LIMIT_SEC / 60:.1f}分")
    print("-" * 60, flush=True)

    recovered = 0
    failed = 0
    queries_made = 0

    for i, (key, store, town, ftype) in enumerate(targets, 1):
        if should_exit():
            break

        strategies = build_strategies(store, town, ftype)
        success = False

        for label, query in strategies:
            if should_exit():
                break

            result = query_geocodingjp(query)
            queries_made += 1

            if result.get('status') == 'ok':
                lat, lng = result.get('lat'), result.get('lng')
                if lat is not None and lng is not None and in_takasaki_bbox(lat, lng):
                    progress[key] = result
                    recovered += 1
                    success = True
                    print(f"[OK ] {i}/{len(targets)} {store[:30]:<30} | "
                          f"{label} → ({lat:.4f},{lng:.4f}) | "
                          f"R:{recovered} F:{failed} Q:{queries_made}",
                          flush=True)
                    rate_limit_sleep()
                    break

            rate_limit_sleep()

        if not success and not should_exit():
            failed += 1
            print(f"[NG ] {i}/{len(targets)} {store[:30]:<30} | "
                  f"({ftype}) 全戦略失敗 | "
                  f"R:{recovered} F:{failed} Q:{queries_made}",
                  flush=True)

        # 5件ごとに保存
        if i % config.SAVE_EVERY_N == 0:
            save_progress(config.GEOCODING_PROGRESS, progress)

    save_progress(config.GEOCODING_PROGRESS, progress)

    print()
    print("=" * 60)
    print(f"リトライ対象: {len(targets)}件")
    print(f"OK復旧:       {recovered}件")
    print(f"失敗:         {failed}件")
    print(f"発行クエリ数: {queries_made}件 ({queries_made * config.RATE_LIMIT_SEC / 60:.1f}分使用)")


if __name__ == '__main__':
    main()

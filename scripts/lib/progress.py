"""進捗JSON保存・SIGINTハンドラ・Windows UTF-8出力"""
import json
import os
import signal
import sys

# モジュールレベルフラグ（SIGINT検知用）
_should_exit = False


def setup_utf8_stdout():
    """Windows: 標準出力をUTF-8に切替

    cp932のデフォルトでは店舗名の 'é' などでクラッシュするため必須。
    """
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def setup_sigint_handler():
    """Ctrl+C で安全停止できるようハンドラ登録

    1回目: フラグだけ立てる（メインループが次イテレーションで判定）
    2回目: 即時強制終了
    """
    def handler(signum, frame):
        global _should_exit
        if _should_exit:
            print("\n[強制終了]", flush=True)
            sys.exit(1)
        _should_exit = True
        print("\n[停止要求受信] 進捗を保存して安全に終了します（もう一度Ctrl+Cで強制終了）",
              flush=True)

    signal.signal(signal.SIGINT, handler)


def should_exit():
    """SIGINT を受信したか確認"""
    return _should_exit


def load_progress(path):
    """進捗JSONを読み込み（ファイルがなければ空dict）"""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_progress(path, data):
    """進捗JSONをアトミック保存（一時ファイル経由）

    保存中の異常終了で破損するのを防ぐ。
    """
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)

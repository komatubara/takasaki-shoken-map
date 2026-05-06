"""共通設定定数"""
from pathlib import Path

# プロジェクトルート（scripts/lib/config.py から見て2階層上）
ROOT = Path(__file__).resolve().parent.parent.parent

# ===== データファイルパス =====
INPUT_CSV = ROOT / '高崎市民商品券取扱店一覧.csv'
PHASE1_CSV = ROOT / '高崎市民商品券取扱店一覧_geo_phase1.csv'
FINAL_CSV = ROOT / '高崎市民商品券取扱店一覧_geo_final.csv'
GEOCODING_PROGRESS = ROOT / 'geocodingjp_progress.json'
TOWN_COORDS = ROOT / 'town_coords.json'
WEB_DATA_JSON = ROOT / 'web' / 'data' / 'stores.json'

# ===== geocoding.jp API 設定 =====
USER_AGENT = 'TakasakiVoucherMap/1.0 (komainu022.ryou@gmail.com; personal-use)'
RATE_LIMIT_SEC = 10.5  # 規約「10秒に1回」+ 0.5秒マージン
REQUEST_TIMEOUT = 20

# ===== 高崎市の境界 =====
# 2006年合併で編入された倉渕町・新町・榛名山町等を含む実範囲
# (west, south, east, north)
TAKASAKI_BBOX = (138.75, 36.18, 139.15, 36.50)

# ===== 進捗保存設定 =====
SAVE_EVERY_N = 5
SAVE_EVERY_SEC = 60

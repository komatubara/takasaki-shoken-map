"""geocoding.jp API クライアントとbbox判定"""
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from . import config


def build_query(store, town, clean_special=False):
    """店舗名+町名から geocoding.jp 用クエリ文字列を組み立て

    Args:
        store: 店舗名
        town: 町名（空可）
        clean_special: True なら '&' '＆' を空白に置換（XMLパース失敗対策）

    Returns:
        str: クエリ文字列。store が空ならNone
    """
    s = (store or '').strip().replace('　', ' ')
    if clean_special:
        s = s.replace('&', ' ').replace('＆', ' ')
        s = re.sub(r'\s+', ' ', s).strip()
    if not s:
        return None
    if town:
        return f"{s} 高崎市{town.strip()}"
    return f"{s} 高崎市"


def query_geocodingjp(query):
    """geocoding.jp API へ問合せ

    Returns:
        dict: status='ok' なら lat, lng, needs_verify, google_maps,
              matched_address を含む。失敗時は status と message。
    """
    url = f"https://www.geocoding.jp/api/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={'User-Agent': config.USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as res:
            xml_text = res.read().decode('utf-8')
        root = ET.fromstring(xml_text)
    except Exception as e:
        return {'status': 'exception', 'message': str(e)}

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


def in_takasaki_bbox(lat, lng):
    """座標が高崎市内（合併編入地域含む）か判定"""
    bbox = config.TAKASAKI_BBOX
    return bbox[1] <= lat <= bbox[3] and bbox[0] <= lng <= bbox[2]

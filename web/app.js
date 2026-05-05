/**
 * 高崎商品券マップ - クライアントサイドロジック
 *
 * 構成:
 * - state: アプリ状態（全店舗・選択カテゴリ・現在地）
 * - map:   Leafletマップとマーカークラスタ
 * - ui:    ヘッダー・フィルタパネル・ステータスバー
 * - data:  JSON読み込み・絞り込みロジック
 */

const TAKASAKI_CENTER = [36.322, 139.013];  // 高崎駅周辺
const INITIAL_ZOOM = 13;

// ===== 状態 =====
const state = {
    allStores: [],
    categories: [],
    selectedCategories: new Set(),  // 空 = すべて表示
    searchQuery: '',
    currentLocation: null,
};

// ===== マップ初期化 =====
const map = L.map('map', {
    zoomControl: true,
    preferCanvas: true,
}).setView(TAKASAKI_CENTER, INITIAL_ZOOM);

// 国土地理院 標準地図
L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>',
    maxZoom: 18,
    minZoom: 10,
}).addTo(map);

// マーカークラスタ
const cluster = L.markerClusterGroup({
    chunkedLoading: true,
    chunkInterval: 100,
    maxClusterRadius: 50,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true,
});
map.addLayer(cluster);

// 現在位置マーカー（後で更新）
let locationMarker = null;
let locationCircle = null;

// ===== ステータス表示 =====
const statusBar = document.getElementById('status-bar');
const statusText = document.getElementById('status-text');

function setStatus(text, autoHide = false) {
    statusText.textContent = text;
    statusBar.classList.remove('hidden');
    if (autoHide) {
        clearTimeout(setStatus._t);
        setStatus._t = setTimeout(() => statusBar.classList.add('hidden'), 2500);
    }
}

// ===== ポップアップHTML =====
function popupHtml(s) {
    const phoneLink = s.phone
        ? `<a href="tel:${s.phone.replace(/-/g, '')}">${escapeHtml(s.phone)}</a>`
        : '<span>—</span>';
    const mall = s.mall ? `<div class="popup-row"><span class="label">大型店</span><span class="value">${escapeHtml(s.mall)}</span></div>` : '';
    const gmapsQuery = encodeURIComponent(`${s.name} 高崎市${s.town || ''}`);
    const precisionLabel = {
        'exact': '番地レベル',
        'approx': '町・周辺',
        'town': '町中心',
        'none': '位置情報なし',
    }[s.precision] || s.precision;

    return `
        <div class="popup-name">${escapeHtml(s.name)}</div>
        <div class="popup-row"><span class="label">業種</span><span class="value">${escapeHtml(s.category || '—')}</span></div>
        <div class="popup-row"><span class="label">町名</span><span class="value">${escapeHtml(s.town || '—')}</span></div>
        <div class="popup-row"><span class="label">電話</span><span class="value">${phoneLink}</span></div>
        ${mall}
        <div class="popup-row precision">位置精度: ${precisionLabel}</div>
        <div class="popup-actions">
            <a href="https://www.google.com/maps/search/?api=1&query=${gmapsQuery}" target="_blank" rel="noopener">Googleマップで見る</a>
        </div>
    `;
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, m =>
        ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[m]));
}

// ===== マーカー描画 =====
function renderMarkers() {
    cluster.clearLayers();
    const visible = filteredStores();
    const markers = [];

    for (const s of visible) {
        if (s.lat == null || s.lng == null) continue;
        const m = L.marker([s.lat, s.lng]);
        m.bindPopup(() => popupHtml(s), { maxWidth: 280 });
        markers.push(m);
    }

    cluster.addLayers(markers);
    setStatus(`${visible.length}件表示中`, true);
}

function filteredStores() {
    const cats = state.selectedCategories;
    const q = state.searchQuery.toLowerCase().trim();

    return state.allStores.filter(s => {
        if (cats.size > 0 && !cats.has(s.category)) return false;
        if (q) {
            const hay = (s.name + ' ' + (s.town || '')).toLowerCase();
            if (!hay.includes(q)) return false;
        }
        return true;
    });
}

// ===== フィルタパネル =====
const filterPanel = document.getElementById('filter-panel');
const filterOptions = document.getElementById('filter-options');
const filterLabel = document.getElementById('filter-label');
const searchInput = document.getElementById('store-search');

function buildCategoryOptions() {
    // カテゴリごとの店舗数を集計
    const counts = {};
    for (const s of state.allStores) {
        if (s.category) counts[s.category] = (counts[s.category] || 0) + 1;
    }

    const html = state.categories.map(cat => `
        <label>
            <input type="checkbox" value="${escapeHtml(cat)}"
                ${state.selectedCategories.has(cat) ? 'checked' : ''}>
            <span>${escapeHtml(cat)}</span>
            <span class="count">${counts[cat] || 0}</span>
        </label>
    `).join('');

    filterOptions.innerHTML = html;
}

function openFilterPanel() {
    buildCategoryOptions();
    filterPanel.hidden = false;
}

function closeFilterPanel() {
    filterPanel.hidden = true;
}

function applyFilter() {
    // チェックボックスから選択カテゴリを集計
    const checks = filterOptions.querySelectorAll('input[type="checkbox"]:checked');
    state.selectedCategories = new Set([...checks].map(c => c.value));
    state.searchQuery = searchInput.value;

    // ヘッダーラベル更新
    if (state.selectedCategories.size === 0) {
        filterLabel.textContent = 'すべての業種';
    } else if (state.selectedCategories.size === 1) {
        filterLabel.textContent = [...state.selectedCategories][0];
    } else {
        filterLabel.textContent = `${state.selectedCategories.size}業種選択中`;
    }

    renderMarkers();
    closeFilterPanel();
}

document.getElementById('filter-btn').addEventListener('click', openFilterPanel);
document.getElementById('filter-close').addEventListener('click', closeFilterPanel);
document.getElementById('filter-apply').addEventListener('click', applyFilter);
document.getElementById('filter-clear').addEventListener('click', () => {
    filterOptions.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false);
    searchInput.value = '';
});
filterPanel.addEventListener('click', e => {
    if (e.target === filterPanel) closeFilterPanel();
});

// 検索入力もEnterで適用
searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') applyFilter();
});

// ===== 現在位置 =====
const locateBtn = document.getElementById('locate-btn');
locateBtn.addEventListener('click', () => {
    if (!navigator.geolocation) {
        setStatus('現在位置取得は非対応の端末です', true);
        return;
    }
    setStatus('現在位置取得中…');
    navigator.geolocation.getCurrentPosition(
        pos => {
            const { latitude, longitude, accuracy } = pos.coords;
            state.currentLocation = [latitude, longitude];

            if (locationMarker) map.removeLayer(locationMarker);
            if (locationCircle) map.removeLayer(locationCircle);

            const icon = L.divIcon({
                className: '',
                html: '<div class="current-location-marker"></div>',
                iconSize: [18, 18],
                iconAnchor: [9, 9],
            });
            locationMarker = L.marker([latitude, longitude], { icon, interactive: false }).addTo(map);
            locationCircle = L.circle([latitude, longitude], {
                radius: accuracy,
                color: '#4285f4',
                fillColor: '#4285f4',
                fillOpacity: 0.1,
                weight: 1,
                interactive: false,
            }).addTo(map);

            map.setView([latitude, longitude], 16);
            setStatus(`現在位置 (誤差±${Math.round(accuracy)}m)`, true);
        },
        err => {
            const msg = {
                1: '位置情報の使用が許可されていません',
                2: '現在位置を取得できませんでした',
                3: '位置情報取得がタイムアウトしました',
            }[err.code] || '位置情報取得に失敗しました';
            setStatus(msg, true);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
});

// ===== データ読込 =====
async function loadData() {
    setStatus('データ読み込み中…');
    try {
        const res = await fetch('./data/stores.json');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        state.allStores = json.stores;
        state.categories = json.categories;

        buildCategoryOptions();  // フィルタパネル展開前にカテゴリリスト事前構築
        renderMarkers();
        setStatus(`${json.stores.length}件読込完了`, true);
    } catch (e) {
        console.error(e);
        setStatus('データ読み込みに失敗しました', true);
    }
}

// ===== 起動 =====
loadData();

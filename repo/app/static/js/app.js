// Service Worker registration — served from /sw.js with scope '/' so the
// worker can intercept requests for all app routes, not just /static/.
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(() => console.log('SW registered'))
        .catch(err => console.error('SW failed', err));
}

// On logout the server sends HX-Trigger: clearSwCache.
// Wipe all SW caches AND the IndexedDB write queue so no authenticated data
// remains for the next user, then navigate to the login page.
document.body.addEventListener('clearSwCache', function() {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_ALL' });
    }
    window.location.href = '/auth/login';
});

// When the login page loads, proactively clear any stale caches/queues left
// from a previous session (covers session-expiry without explicit logout).
if (window.location.pathname === '/auth/login') {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_ALL' });
    }
}

// Offline detection
const offlineBanner = document.getElementById('offline-indicator');
function updateOnlineStatus() {
    if (offlineBanner) {
        offlineBanner.style.display = navigator.onLine ? 'none' : 'block';
    }
}
window.addEventListener('online', () => {
    updateOnlineStatus();
    showToast('Back online', 'success');
    // Trigger queue replay as a fallback for browsers without Background Sync.
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'REPLAY_QUEUE' });
    }
});
window.addEventListener('offline', () => { updateOnlineStatus(); showToast('You are offline', 'warning'); });
updateOnlineStatus();

// Toast notifications
function showToast(message, type = 'info', duration = 5000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => { toast.classList.add('toast-fade'); setTimeout(() => toast.remove(), 300); }, duration);
}
window.showToast = showToast;

// HMAC headers for HTMX requests to /api/*
function toUtf8Bytes(str) {
    return new TextEncoder().encode(str);
}

function bytesToHex(bytes) {
    let out = '';
    for (let i = 0; i < bytes.length; i++) {
        out += bytes[i].toString(16).padStart(2, '0');
    }
    return out;
}

function sha256Bytes(inputBytes) {
    const K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];
    const H = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    const bytes = Array.from(inputBytes);
    const bitLen = bytes.length * 8;
    bytes.push(0x80);
    while ((bytes.length % 64) !== 56) bytes.push(0);
    const high = Math.floor(bitLen / 0x100000000);
    const low = bitLen >>> 0;
    bytes.push((high >>> 24) & 0xff, (high >>> 16) & 0xff, (high >>> 8) & 0xff, high & 0xff);
    bytes.push((low >>> 24) & 0xff, (low >>> 16) & 0xff, (low >>> 8) & 0xff, low & 0xff);

    const w = new Array(64);
    const rotr = (x, n) => (x >>> n) | (x << (32 - n));

    for (let i = 0; i < bytes.length; i += 64) {
        for (let t = 0; t < 16; t++) {
            const j = i + t * 4;
            w[t] = ((bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3]) >>> 0;
        }
        for (let t = 16; t < 64; t++) {
            const s0 = (rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3)) >>> 0;
            const s1 = (rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10)) >>> 0;
            w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
        }

        let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];

        for (let t = 0; t < 64; t++) {
            const S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
            const ch = ((e & f) ^ (~e & g)) >>> 0;
            const temp1 = (h + S1 + ch + K[t] + w[t]) >>> 0;
            const S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
            const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
            const temp2 = (S0 + maj) >>> 0;

            h = g;
            g = f;
            f = e;
            e = (d + temp1) >>> 0;
            d = c;
            c = b;
            b = a;
            a = (temp1 + temp2) >>> 0;
        }

        H[0] = (H[0] + a) >>> 0;
        H[1] = (H[1] + b) >>> 0;
        H[2] = (H[2] + c) >>> 0;
        H[3] = (H[3] + d) >>> 0;
        H[4] = (H[4] + e) >>> 0;
        H[5] = (H[5] + f) >>> 0;
        H[6] = (H[6] + g) >>> 0;
        H[7] = (H[7] + h) >>> 0;
    }

    const out = [];
    for (let i = 0; i < H.length; i++) {
        out.push((H[i] >>> 24) & 0xff, (H[i] >>> 16) & 0xff, (H[i] >>> 8) & 0xff, H[i] & 0xff);
    }
    return out;
}

function sha256Hex(str) {
    return bytesToHex(sha256Bytes(toUtf8Bytes(str)));
}

function hmacSha256Hex(key, msg) {
    let keyBytes = Array.from(toUtf8Bytes(key));
    if (keyBytes.length > 64) keyBytes = sha256Bytes(keyBytes);
    while (keyBytes.length < 64) keyBytes.push(0);

    const oKeyPad = keyBytes.map(b => b ^ 0x5c);
    const iKeyPad = keyBytes.map(b => b ^ 0x36);
    const msgBytes = Array.from(toUtf8Bytes(msg));
    const inner = sha256Bytes([...iKeyPad, ...msgBytes]);
    const outer = sha256Bytes([...oKeyPad, ...inner]);
    return bytesToHex(outer);
}

function serializeParams(params) {
    const usp = new URLSearchParams();
    Object.keys(params || {}).forEach(key => {
        const value = params[key];
        if (Array.isArray(value)) {
            value.forEach(v => usp.append(key, String(v)));
        } else if (value !== undefined && value !== null) {
            usp.append(key, String(value));
        }
    });
    return usp.toString();
}

function makeNonce() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
    }
    const arr = new Uint8Array(16);
    window.crypto.getRandomValues(arr);
    return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

const hmacMeta = document.querySelector('meta[name="hmac-client-secret"]');
const hmacClientSecret = hmacMeta ? hmacMeta.getAttribute('content') : '';

document.body.addEventListener('htmx:configRequest', function(evt) {
    if (!hmacClientSecret) return;
    const rawPath = evt.detail.path || (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) || '';
    if (!rawPath) return;
    const url = new URL(rawPath, window.location.origin);
    if (!url.pathname.startsWith('/api/')) return;

    const method = (evt.detail.verb || 'GET').toUpperCase();
    const body = (method === 'GET' || method === 'HEAD') ? '' : serializeParams(evt.detail.parameters || {});
    const timestamp = String(Math.floor(Date.now() / 1000));
    const nonce = makeNonce();
    const bodyHash = sha256Hex(body);
    const signingString = `${method}\n${url.pathname}\n${timestamp}\n${nonce}\n${bodyHash}`;
    const signature = hmacSha256Hex(hmacClientSecret, signingString);

    evt.detail.headers['X-Timestamp'] = timestamp;
    evt.detail.headers['X-Nonce'] = nonce;
    evt.detail.headers['X-Signature'] = signature;
});

// HTMX error handling
document.body.addEventListener('htmx:responseError', function() {
    showToast('Request failed. Please try again.', 'error');
});
document.body.addEventListener('htmx:sendError', function() {
    showToast('Connection failed. You may be offline.', 'warning');
});

// Character counter for textareas with maxlength
document.querySelectorAll('textarea[maxlength]').forEach(ta => {
    const max = parseInt(ta.getAttribute('maxlength'));
    const counter = document.createElement('small');
    counter.className = 'char-counter';
    counter.textContent = '0 / ' + max;
    ta.parentNode.insertBefore(counter, ta.nextSibling);
    ta.addEventListener('input', () => {
        counter.textContent = ta.value.length + ' / ' + max;
        counter.style.color = ta.value.length > max ? 'var(--danger)' : '';
    });
});

// ── Offline write-queue UI ───────────────────────────────────────────────────
// The SW notifies the page whenever the queue changes via QUEUE_UPDATE messages.
// We update a sticky banner and (on failure) a persistent toast.

function updateQueueIndicator(pending, failed) {
    const el = document.getElementById('queue-indicator');
    if (!el) return;

    if (pending === 0 && failed === 0) {
        el.style.display = 'none';
        el.className = 'queue-banner';
        el.textContent = '';
        return;
    }

    el.style.display = 'block';
    if (failed > 0) {
        el.className = 'queue-banner queue-banner-failed';
        el.textContent =
            `${failed} offline change${failed !== 1 ? 's' : ''} could not sync — ` +
            'please redo them manually.';
    } else {
        el.className = 'queue-banner queue-banner-pending';
        el.textContent =
            `${pending} change${pending !== 1 ? 's' : ''} queued offline, ` +
            'will sync automatically when online.';
    }
}

if ('serviceWorker' in navigator) {
    // Listen for queue-state messages from the SW.
    navigator.serviceWorker.addEventListener('message', function(evt) {
        if (!evt.data || evt.data.type !== 'QUEUE_UPDATE') return;
        const pending = evt.data.pending || 0;
        const failed  = evt.data.failed  || 0;
        updateQueueIndicator(pending, failed);
        if (failed > 0) {
            showToast(
                `${failed} queued write${failed !== 1 ? 's' : ''} failed to sync. Please retry manually.`,
                'error',
                8000
            );
        } else if (pending === 0) {
            // Queue just drained — let the user know if they had items waiting.
            const el = document.getElementById('queue-indicator');
            if (el && el.style.display !== 'none') {
                showToast('All queued changes synced successfully.', 'success');
            }
        }
    });

    // On page load, ask the SW for the current queue state so the indicator
    // reflects any items that were queued before this page load.
    navigator.serviceWorker.ready.then(() => {
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({ type: 'GET_QUEUE_STATUS' });
        }
    });
}

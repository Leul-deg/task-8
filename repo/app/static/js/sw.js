const STATIC_CACHE_NAME = 'clinical-ops-static-v1';
const PAGE_CACHE_NAME = 'clinical-ops-pages-v1';
const STATIC_ASSETS = [
    '/static/css/main.css',
    '/static/js/app.js',
];
const QUEUE_DB_NAME = 'clinical-ops-queue';
const QUEUE_STORE   = 'write_queue';

// Only cache requests whose path is in the explicit static allowlist or
// starts with /static/.  Authenticated pages and API responses are never
// stored so they cannot leak to a subsequent user.
function isStaticAsset(url) {
    const pathname = new URL(url).pathname;
    return STATIC_ASSETS.includes(pathname) || pathname.startsWith('/static/');
}

// ── IndexedDB helpers ────────────────────────────────────────────────────────

function openQueueDb() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(QUEUE_DB_NAME, 1);
        req.onupgradeneeded = e => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(QUEUE_STORE)) {
                const store = db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
                store.createIndex('status', 'status', { unique: false });
            }
        };
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function idbGetAll(store) {
    return new Promise((resolve, reject) => {
        const req = store.getAll();
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function idbPut(store, record) {
    return new Promise((resolve, reject) => {
        const req = store.put(record);
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function idbDelete(store, id) {
    return new Promise((resolve, reject) => {
        const req = store.delete(id);
        req.onsuccess = () => resolve();
        req.onerror   = e => reject(e.target.error);
    });
}

// Serialize a Request into a plain object that can be stored in IndexedDB.
// Body is read as text (covers JSON and URL-encoded form payloads).
async function serializeRequest(request) {
    const headers = {};
    request.headers.forEach((value, key) => { headers[key] = value; });
    let body = '';
    try { body = await request.clone().text(); } catch (_) {}
    return {
        url:       request.url,
        method:    request.method,
        headers,
        body,
        timestamp: Date.now(),
        status:    'pending',
        failReason: null,
    };
}

async function enqueueRequest(request) {
    const record = await serializeRequest(request);
    const db = await openQueueDb();
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    const id = await idbPut(tx.objectStore(QUEUE_STORE), record);
    db.close();
    return id;
}

async function getQueueCounts() {
    const db  = await openQueueDb();
    const tx  = db.transaction(QUEUE_STORE, 'readonly');
    const all = await idbGetAll(tx.objectStore(QUEUE_STORE));
    db.close();
    return {
        pending: all.filter(r => r.status === 'pending').length,
        failed:  all.filter(r => r.status === 'failed').length,
    };
}

async function broadcastQueueUpdate() {
    const counts  = await getQueueCounts();
    const clients = await self.clients.matchAll({ includeUncontrolled: true });
    clients.forEach(c => c.postMessage({ type: 'QUEUE_UPDATE', ...counts }));
}

// Attempt to replay every pending queued request in insertion order.
// Success (2xx) → delete.
// Client error (4xx, e.g. expired CSRF / permission denied) → mark failed.
// Network error or 5xx → leave pending and abort loop (still offline / server down).
async function replayQueue() {
    const db      = await openQueueDb();
    const tx      = db.transaction(QUEUE_STORE, 'readwrite');
    const store   = tx.objectStore(QUEUE_STORE);
    const records = await idbGetAll(store);
    const pending = records.filter(r => r.status === 'pending')
                           .sort((a, b) => a.timestamp - b.timestamp);

    for (const record of pending) {
        try {
            const resp = await fetch(record.url, {
                method:  record.method,
                headers: record.headers,
                body:    record.body || undefined,
            });

            if (resp.ok) {
                // Accepted by server — remove from queue
                await idbDelete(store, record.id);
            } else if (resp.status >= 400 && resp.status < 500) {
                // Client error (CSRF expired, validation failure, auth issue) —
                // this will not succeed on retry; mark failed so the user is notified
                record.status    = 'failed';
                record.failReason = `HTTP ${resp.status}`;
                await idbPut(store, record);
            }
            // 5xx / unexpected: leave pending for next sync attempt
        } catch (_) {
            // Network error — still offline; stop replaying
            break;
        }
    }

    db.close();
    await broadcastQueueUpdate();
}

// ── SW lifecycle ─────────────────────────────────────────────────────────────

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => ![STATIC_CACHE_NAME, PAGE_CACHE_NAME].includes(k)).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// ── Fetch handler ─────────────────────────────────────────────────────────────

self.addEventListener('fetch', event => {
    const { method, url } = event.request;

    if (method !== 'GET') {
        event.respondWith(
            fetch(event.request.clone()).catch(async () => {
                const id = await enqueueRequest(event.request);
                await broadcastQueueUpdate();
                // Register a Background Sync tag so the browser replays when
                // connectivity returns even if the page is closed.
                if (self.registration.sync) {
                    await self.registration.sync.register('write-queue').catch(() => {});
                }
                return new Response(
                    JSON.stringify({
                        queued: true,
                        id,
                        message: 'Your change has been queued and will sync when online.',
                    }),
                    { status: 202, headers: { 'Content-Type': 'application/json' } }
                );
            })
        );
        return;
    }

    // Authenticated pages and API endpoints are network-first. Only responses
    // explicitly marked safe via X-Offline-Cacheable are stored for offline
    // fallback. This avoids caching sensitive authenticated HTML by default.
    if (!isStaticAsset(url)) {
        event.respondWith(
            fetch(event.request).then(async response => {
                if (response.ok && response.headers.get('X-Offline-Cacheable') === '1') {
                    try {
                        const headers = new Headers(event.request.headers);
                        headers.set('X-Offline-Cache-Variant', '1');
                        const cacheRequest = new Request(event.request.url, {
                            method: event.request.method,
                            headers,
                            credentials: 'same-origin',
                        });
                        const cacheResponse = await fetch(cacheRequest);
                        if (cacheResponse.ok) {
                            caches.open(PAGE_CACHE_NAME).then(cache => cache.put(event.request, cacheResponse.clone()));
                        }
                    } catch (_) {}
                }
                return response;
            }).catch(async () => {
                const cached = await caches.open(PAGE_CACHE_NAME).then(cache => cache.match(event.request));
                if (cached) return cached;
                throw new Error('Offline and no cache entry available');
            })
        );
        return;
    }

    // Static assets: stale-while-revalidate
    event.respondWith(
        caches.match(event.request).then(cached => {
            const fetchPromise = fetch(event.request).then(response => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(STATIC_CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => cached);
            return cached || fetchPromise;
        })
    );
});

// ── Background Sync ───────────────────────────────────────────────────────────

self.addEventListener('sync', event => {
    if (event.tag === 'write-queue') {
        event.waitUntil(replayQueue());
    }
});

// ── Message handler ───────────────────────────────────────────────────────────

async function clearWriteQueue() {
    try {
        const db = await openQueueDb();
        const tx = db.transaction(QUEUE_STORE, 'readwrite');
        tx.objectStore(QUEUE_STORE).clear();
        db.close();
    } catch (_) {}
}

async function clearAll() {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
    await clearWriteQueue();
}

self.addEventListener('message', event => {
    if (!event.data) return;
    switch (event.data.type) {
        case 'CLEAR_CACHE':
            event.waitUntil(
                caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))
            );
            break;
        case 'CLEAR_ALL':
            event.waitUntil(clearAll());
            break;
        case 'REPLAY_QUEUE':
            event.waitUntil(replayQueue());
            break;
        case 'GET_QUEUE_STATUS':
            event.waitUntil(broadcastQueueUpdate());
            break;
    }
});

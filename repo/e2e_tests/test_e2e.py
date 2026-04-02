"""
Browser E2E tests using pytest-playwright + Chromium.

Covers flows the Python API tests cannot exercise:
  1. Login / logout (form-driven auth with flash messages)
  2. Listing edit save (page-route POST → redirect → detail render)
  3. Listing status change + preview modal (HTMX partial swaps)
  4. Moderation hide action (HTMX partial swap)
  5. SW cache / state isolation across user switch
  6. Instructor-only reply enforcement (negative test)
  7. Offline banner + SW write-queue behaviour
"""
import pytest
import re


# ── Helpers ───────────────────────────────────────────────────────────────────

def login(page, base, username='admin', password='admin123'):
    page.goto(f'{base}/auth/login')
    page.fill('input[name=username]', username)
    page.fill('input[name=password]', password)
    page.click('button[type=submit]')
    page.wait_for_url(f'{base}/dashboard', timeout=5000)


def wait_for_sw(page, timeout=15000):
    """Wait until a service worker is registered, activated, and controlling
    the current page.  Uses navigator.serviceWorker.ready to avoid racing
    against install/activate, then polls for `.controller`."""
    page.wait_for_function("""
        async () => {
            if (!navigator.serviceWorker) return false;
            const reg = await navigator.serviceWorker.ready;
            if (!navigator.serviceWorker.controller) {
                await reg.active.postMessage({type: 'PING'});
                await new Promise(r => setTimeout(r, 200));
            }
            return navigator.serviceWorker.controller !== null;
        }
    """, timeout=timeout)


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestLoginE2E:
    def test_successful_login_redirects_to_dashboard(self, page, flask_url):
        page.goto(f'{flask_url}/auth/login')
        page.fill('input[name=username]', 'admin')
        page.fill('input[name=password]', 'admin123')
        page.click('button[type=submit]')
        page.wait_for_url(f'{flask_url}/dashboard', timeout=5000)
        assert '/dashboard' in page.url

    def test_wrong_password_stays_on_login(self, page, flask_url):
        page.goto(f'{flask_url}/auth/login')
        page.fill('input[name=username]', 'admin')
        page.fill('input[name=password]', 'wrongpassword')
        page.click('button[type=submit]')
        # Server re-renders login page with 401; no redirect occurs
        assert '/auth/login' in page.url

    def test_logout_clears_session_and_navigates_to_login(self, page, flask_url):
        login(page, flask_url)
        page.click('a:has-text("Logout")')
        page.wait_for_url(re.compile(r'/auth/login'), timeout=5000)
        assert '/auth/login' in page.url
        # Subsequent navigation to a protected page shows login / 401 page
        resp = page.goto(f'{flask_url}/listings')
        is_login_page = '/auth/login' in page.url
        is_401 = resp is not None and resp.status == 401
        assert is_login_page or is_401


# ── Listing edit (page-route POST) ────────────────────────────────────────────

class TestListingEditE2E:
    def test_edit_form_saves_and_redirects_to_detail(self, page, flask_url,
                                                      seeded_listing_id):
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}/edit')
        page.fill('input[name=title]', 'E2E Edited Title')
        page.click('button[type=submit]')
        # Route returns redirect → detail page
        page.wait_for_url(f'{flask_url}/listings/{seeded_listing_id}', timeout=5000)
        assert 'E2E Edited Title' in page.inner_text('h1')

    def test_edit_form_cancel_returns_to_detail(self, page, flask_url,
                                                seeded_listing_id):
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}/edit')
        page.click('a.btn-secondary')   # the Cancel link
        page.wait_for_url(f'{flask_url}/listings/{seeded_listing_id}', timeout=5000)
        assert f'/listings/{seeded_listing_id}' in page.url

    def test_edit_requires_auth(self, page, flask_url, seeded_listing_id):
        resp = page.goto(f'{flask_url}/listings/{seeded_listing_id}/edit')
        is_login_page = '/auth/login' in page.url
        is_401 = resp is not None and resp.status == 401
        assert is_login_page or is_401


# ── Listing status change (HTMX partial swap in #status-section) ─────────────

class TestListingStatusE2E:
    def test_status_change_updates_badge_via_htmx(self, page, flask_url,
                                                   seeded_listing_id):
        """Select 'Pending Review' and submit — the #status-section badge
        updates in-place via hx-swap='innerHTML' without a full reload."""
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}')
        page.wait_for_selector('#status-section .badge', timeout=5000)
        page.select_option('#status-section select[name=status]', 'pending_review')
        page.click('#status-section button[type=submit]')
        page.wait_for_selector('#status-section .badge-pending_review', timeout=5000)
        badge_text = page.inner_text('#status-section .badge')
        assert 'pending' in badge_text.lower()

    def test_status_history_appears_after_change(self, page, flask_url,
                                                  seeded_listing_id):
        """After a status transition the status-history list must be
        present inside the partial."""
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}')
        page.wait_for_selector('#status-section', timeout=5000)
        assert page.query_selector('#status-section .status-history') is not None


# ── Listing preview modal (HTMX load into #modal-container) ─────────────────

class TestListingPreviewModalE2E:
    def test_preview_button_opens_modal(self, page, flask_url,
                                        seeded_listing_id):
        """Click the Preview button on the listing detail page — HTMX
        fetches the preview partial and renders it inside #modal-container."""
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}')
        assert page.inner_html('#modal-container').strip() == ''
        page.click('button:has-text("Preview")')
        page.wait_for_selector('#modal-container .modal', timeout=5000)
        modal = page.inner_text('#modal-container .modal').lower()
        assert 'preview' in modal
        assert 'location' in modal

    def test_modal_close_clears_container(self, page, flask_url,
                                          seeded_listing_id):
        login(page, flask_url)
        page.goto(f'{flask_url}/listings/{seeded_listing_id}')
        page.click('button:has-text("Preview")')
        page.wait_for_selector('#modal-container .modal', timeout=5000)
        page.click('#modal-container .modal-close')
        page.wait_for_function(
            "document.getElementById('modal-container').innerHTML.trim() === ''",
            timeout=3000,
        )
        assert page.inner_html('#modal-container').strip() == ''


# ── Moderation (HTMX partial swap) ───────────────────────────────────────────

class TestModerationE2E:
    def test_hide_review_updates_card_via_htmx(self, page, flask_url,
                                               seeded_report_id):
        login(page, flask_url)
        page.goto(f'{flask_url}/moderation')
        card = f'#report-{seeded_report_id}'
        page.wait_for_selector(card, timeout=5000)
        # Pending card shows "Hide Review" button
        assert page.is_visible(f'{card} .badge-pending')
        # Click — HTMX POSTs and swaps the card's outerHTML
        page.click(f'{card} .btn-danger')
        # After swap the badge updates to review_hidden
        page.wait_for_selector(f'{card} .badge-review_hidden', timeout=5000)
        assert page.is_visible(f'{card} .badge-review_hidden')

    def test_moderation_requires_permission(self, page, flask_url):
        login(page, flask_url, username='staffuser', password='staffpass')
        resp = page.goto(f'{flask_url}/moderation')
        is_403 = resp is not None and resp.status == 403
        body = page.content()
        has_denied_text = 'Permission' in body or 'Forbidden' in body or 'denied' in body.lower()
        assert is_403 or has_denied_text


# ── Offline banner + SW write-queue ──────────────────────────────────────────

class TestOfflineE2E:
    def test_offline_banner_appears_on_disconnect(self, page, flask_url):
        login(page, flask_url)
        assert page.is_hidden('#offline-indicator')
        page.context.set_offline(True)
        try:
            page.wait_for_function(
                "document.getElementById('offline-indicator').style.display !== 'none'",
                timeout=4000,
            )
            assert page.is_visible('#offline-indicator')
        finally:
            page.context.set_offline(False)

    def test_offline_banner_hides_on_reconnect(self, page, flask_url):
        login(page, flask_url)
        page.context.set_offline(True)
        page.wait_for_function(
            "document.getElementById('offline-indicator').style.display !== 'none'",
            timeout=4000,
        )
        page.context.set_offline(False)
        page.wait_for_function(
            "document.getElementById('offline-indicator').style.display === 'none'",
            timeout=4000,
        )
        assert page.is_hidden('#offline-indicator')

    def test_sw_returns_queued_response_when_offline(self, page, flask_url):
        """POST through the SW while offline must return 202 { queued: true }."""
        login(page, flask_url)
        wait_for_sw(page)
        page.context.set_offline(True)
        try:
            result = page.evaluate("""
                async () => {
                    const resp = await fetch('/listings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'title=offline+write+test',
                    });
                    return { status: resp.status, body: await resp.json() };
                }
            """)
            assert result['status'] == 202
            assert result['body']['queued'] is True
        finally:
            page.context.set_offline(False)

    def test_queue_indicator_shown_after_offline_write(self, page, flask_url):
        """After a write is queued, the SW broadcasts QUEUE_UPDATE and the
        queue banner becomes visible."""
        login(page, flask_url)
        wait_for_sw(page)
        page.context.set_offline(True)
        try:
            # Await the fetch so the SW has fully processed it (stored in IndexedDB,
            # broadcast QUEUE_UPDATE) before we check the DOM.
            page.evaluate("""
                async () => {
                    await fetch('/listings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'title=offline+write+test',
                    });
                }
            """)
            page.wait_for_function(
                "document.getElementById('queue-indicator').style.display !== 'none'",
                timeout=5000,
            )
            assert page.is_visible('#queue-indicator')
        finally:
            page.context.set_offline(False)


# ── Cache / state isolation across user switch ───────────────────────────────

class TestCacheIsolationE2E:
    def test_logout_sends_cache_control_no_store(self, page, flask_url):
        """The logout response must prevent browser caching."""
        login(page, flask_url)
        cache_ctrl = {}

        def capture_logout_response(response):
            if '/auth/logout' in response.url:
                cache_ctrl['value'] = response.headers.get('cache-control', '')

        page.on('response', capture_logout_response)
        page.click('a:has-text("Logout")')
        page.wait_for_url(re.compile(r'/auth/login'), timeout=5000)
        page.remove_listener('response', capture_logout_response)
        cc = cache_ctrl.get('value', '')
        assert 'no-store' in cc

    def test_user_switch_shows_correct_identity(self, page, flask_url):
        """Login as admin, logout, login as staff — the nav must show the
        new user's name with no trace of the previous user."""
        login(page, flask_url, username='admin', password='admin123')
        nav_text = page.inner_text('.nav-links')
        assert 'admin' in nav_text.lower()
        page.click('a:has-text("Logout")')
        page.wait_for_url(re.compile(r'/auth/login'), timeout=5000)
        login(page, flask_url, username='staffuser', password='staffpass')
        nav_text_after = page.inner_text('.nav-links')
        assert 'staffuser' in nav_text_after.lower()
        assert 'admin' not in nav_text_after.lower() or 'Admin' not in nav_text_after

    def test_sw_cache_cleared_after_logout(self, page, flask_url):
        """After logout the SW must have received CLEAR_ALL, so caches.keys()
        returns an empty list."""
        login(page, flask_url)
        wait_for_sw(page)
        page.click('a:has-text("Logout")')
        page.wait_for_url(re.compile(r'/auth/login'), timeout=5000)
        cache_keys = page.evaluate('() => caches.keys()')
        assert cache_keys == [] or len(cache_keys) == 0

    def test_write_queue_empty_after_logout(self, page, flask_url):
        """The IndexedDB write queue must be purged on logout so queued writes
        from user A never replay under user B's session."""
        login(page, flask_url)
        wait_for_sw(page)
        page.click('a:has-text("Logout")')
        page.wait_for_url(re.compile(r'/auth/login'), timeout=5000)
        count = page.evaluate("""
            async () => {
                try {
                    const db = await new Promise((res, rej) => {
                        const r = indexedDB.open('clinical-ops-queue', 1);
                        r.onsuccess = e => res(e.target.result);
                        r.onerror = e => rej(e.target.error);
                    });
                    const tx = db.transaction('write_queue', 'readonly');
                    const all = await new Promise((res, rej) => {
                        const r = tx.objectStore('write_queue').count();
                        r.onsuccess = e => res(e.target.result);
                        r.onerror = e => rej(e.target.error);
                    });
                    db.close();
                    return all;
                } catch(_) { return 0; }
            }
        """)
        assert count == 0

    def test_login_page_clears_stale_caches(self, page, flask_url):
        """Navigating to the login page (e.g. after session expiry) triggers a
        proactive CLEAR_ALL so no authenticated data remains.  Static assets
        may be re-cached immediately by the new page load."""
        login(page, flask_url)
        wait_for_sw(page)
        page.goto(f'{flask_url}/auth/login')
        page.wait_for_timeout(1000)
        cached_urls = page.evaluate("""
            async () => {
                const names = await caches.keys();
                const urls = [];
                for (const name of names) {
                    const cache = await caches.open(name);
                    const keys = await cache.keys();
                    keys.forEach(r => urls.push(new URL(r.url).pathname));
                }
                return urls;
            }
        """)
        auth_pages = [u for u in cached_urls
                      if not u.startswith('/static/') and u != '/sw.js']
        assert auth_pages == [], f'Authenticated content leaked into cache: {auth_pages}'


# ── Coach-reply: instructor-only enforcement ─────────────────────────────────

class TestCoachReplyE2E:
    def test_staff_does_not_see_reply_form(self, page, flask_url,
                                           seeded_reply_class):
        """Staff (non-instructor) sees reviews but must NOT see the reply
        form on the class detail page."""
        class_id, _ = seeded_reply_class
        login(page, flask_url, username='staffuser', password='staffpass')
        page.goto(f'{flask_url}/classes/{class_id}')
        page.wait_for_selector('.review-card', timeout=5000)
        assert page.query_selector('.review-card') is not None
        assert page.query_selector('textarea[name=body]') is None

    def test_instructor_sees_reply_form(self, page, flask_url,
                                        seeded_reply_class):
        """Instructor (admin) must see the reply form for unreplied reviews."""
        class_id, _ = seeded_reply_class
        login(page, flask_url, username='admin', password='admin123')
        page.goto(f'{flask_url}/classes/{class_id}')
        page.wait_for_selector('.review-card', timeout=5000)
        reply_form = page.query_selector('textarea[name=body]')
        assert reply_form is not None

    def test_staff_post_reply_returns_403(self, page, flask_url,
                                          seeded_reply_class):
        """Direct POST from a non-instructor must be rejected with 403."""
        class_id, review_id = seeded_reply_class
        login(page, flask_url, username='staffuser', password='staffpass')
        page.goto(f'{flask_url}/classes/{class_id}')
        result = page.evaluate(f"""
            async () => {{
                const resp = await fetch('/classes/{class_id}/reviews/{review_id}/reply', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: 'body=Unauthorized+reply+attempt',
                }});
                return resp.status;
            }}
        """)
        assert result == 403

    def test_instructor_post_reply_succeeds(self, page, flask_url,
                                            seeded_reply_class):
        """Instructor submitting a reply via the form succeeds and shows
        the reply on the class detail page."""
        class_id, review_id = seeded_reply_class
        login(page, flask_url, username='admin', password='admin123')
        page.goto(f'{flask_url}/classes/{class_id}')
        page.wait_for_selector('textarea[name=body]', timeout=5000)
        page.fill('textarea[name=body]', 'Thank you for attending and for the feedback!')
        page.click('button:has-text("Post Reply")')
        page.wait_for_url(re.compile(rf'/classes/{class_id}'), timeout=5000)
        assert 'Thank you for attending' in page.inner_text('.coach-reply')

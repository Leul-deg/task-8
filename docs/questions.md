# Business Logic Questions Log

This document records prompt ambiguities and the implementation choices made in `repo/`.
It is intended to satisfy the requirement that important assumptions be written down rather than hidden in code.

1. Which requests should use HMAC signing?
Question: The prompt requires HMAC signing for API requests, but the app is also server-rendered and uses HTMX for browser interactions.
My Understanding: If browser HTMX requests are forced through `/api/*`, the browser either needs a client-signing mechanism or those flows break outside test mode.
Solution: 
- `/api/*` is the signed surface and requires:
  - logged-in session
  - `X-Signature`
  - `X-Timestamp`
  - `X-Nonce`
- Browser HTMX interactions use page routes instead of `/api/*`.
- Page routes rely on session auth plus CSRF.
This preserves the prompt’s signed API requirement without breaking normal browser behavior.

2. Who may create training classes?
Question: The prompt says instructors run classes, but did not explicitly define the permission codename or whether any authenticated user could create them.
My Understanding: Class creation should be a permissioned action, not merely a logged-in action.
Solution: 
- A dedicated `class.create` permission is required for both:
  - `GET /classes/new`
  - `POST /classes`
- The submitted `org_unit_id` must also be inside the current user’s accessible org scope.
This matches the instructor/admin intent while remaining consistent with the app’s RBAC model.

3. Which org units can a user read or act inside?
Question: The prompt references hierarchical organization scope, but does not spell out whether parent-unit access should include descendant units.
My Understanding: A user assigned to a higher-level org unit should inherit read access to descendant units.
Solution: 
- `user_accessible_org_ids()` includes:
  - direct org memberships
  - all descendant org units
- Permission checks with an `org_unit_id` also accept ancestor-based access.
This makes campus-level or department-level roles practical without copying memberships to every child node.

4. Who is allowed to leave a class review?
Question: The prompt says reviews come from “verified attendees,” but does not define how verification is represented in the database.
My Understanding: A review should require an attendance record that explicitly marks the user as having attended.
Solution: 
- Only users with `ClassAttendee(attended=True)` for the class may review it.
- Duplicate reviews by the same user for the same class are rejected.
Registration alone is not a reliable proxy for attendance.

5. Who may reply to a review?
Question: The prompt says coaches can post one threaded reply, but does not define whether that is role-based, ownership-based, or both.
My Understanding: Replies should require both feature permission and object ownership.
Solution: 
- Page and API reply flows require `review.reply`.
- The current user must also be the instructor for the associated class.
- Only one reply is allowed per review.
This prevents other instructors or staff from replying on someone else’s behalf.

6. How should reviewer identity display be governed?
Question: The prompt requires full name / initials / anonymous display, but does not state where the setting lives.
My Understanding: Identity display should be controlled at the organization level because classes belong to org units.
Solution: 
- `OrgUnit.reviewer_display_mode` stores the active mode.
- Org admins can manage it through:
  - page flow: `/admin/org-settings`
  - API flow: `/api/admin/org-units/<org_id>/settings`
- Review rendering reads the class org unit’s mode and falls back to config only when needed.
This makes display policy part of org governance, not only deployment config.

7. What drug content is visible before approval?
Question: The prompt states only approved content becomes visible, but does not define whether privileged editors may still see drafts and pending items.
My Understanding: Ordinary users should see only approved drugs; editors/approvers may see non-approved content.
Solution: 
- Non-privileged users see approved drugs only.
- Unapproved drug detail or non-approved status filtering is restricted to users with `drug.edit` or `drug.approve`.
This preserves editorial workflow without exposing draft clinical content broadly.

8. How should moderation auto-flagging work offline/basic-rule style?
Question: The prompt requires simple keyword rules plus manual moderation, but does not define the initial keyword set or how auto-flagging changes review visibility.
My Understanding: A conservative keyword list should immediately hide flagged reviews and create a pending moderation report.
Solution: 
- A fixed keyword blocklist is scanned with word-boundary matching.
- If matched:
  - the review is hidden
  - a `ModerationReport` is created
  - matched keywords are stored on the report
This creates an auditable moderation entry rather than silently hiding content.

9. When can an appeal be filed, and by whom?
Question: The prompt says appeals must be filed within 14 calendar days and resolved within 5 business days, but does not define the start point or authorized actor.
My Understanding: The appeal window should begin when the moderation action is resolved and only the original review author should be allowed to appeal.
Solution: 
- Appeals may only be filed for reports in `review_hidden`.
- Only the original review author may file.
- Appeal text must be 20 to 2000 characters.
- The filing deadline is `resolved_at + 14 calendar days`.
- The resolution deadline is computed as `filed_at + 5 business days`.
This aligns with the wording of the prompt while grounding the timing in a stored moderation event.

10. What should happen when an appeal is overturned?
Question: The prompt says the UI should show when a review is restored or finalized, but does not define whether an overturned appeal should automatically restore the review.
My Understanding: An overturned appeal should restore the review as part of the same action.
Solution: 
- Resolving an appeal with decision `overturned` calls `restore_review(...)`.
- Upholding the appeal leaves the hidden state in place.
This avoids requiring moderators to perform a second manual action after an overturn.

11. How should temporary permissions expire?
Question: The prompt requires auto-expiring temp grants, but does not define whether expiry is handled lazily or by a separate scheduler.
My Understanding: Expiry should be enforced both opportunistically and via queue jobs.
Solution: 
- Expired grants are deactivated in a `before_request` hook.
- A queue handler for `expire_grants` is also registered so background processing can enforce the same rule.
This keeps behavior correct even in low-traffic and request-driven environments.

12. What should the offline queue store and replay?
Question: The prompt requires queued write intents, but does not define persistence model or retry semantics.
My Understanding: The queue should persist failed non-GET browser requests in IndexedDB and retry them in order.
Solution: 
- Service Worker stores failed non-GET requests in IndexedDB.
- Queue replay order is oldest-first.
- Success (`2xx`) deletes the queued item.
- Client errors (`4xx`) mark the item failed and surface manual-retry messaging.
- Network errors and `5xx` leave the item pending for later replay.
This gives deterministic behavior and avoids endlessly retrying requests that are invalid rather than temporarily unreachable.

13. What data may be cached on shared workstations?
Question: The prompt wants offline capability, but also requires safe behavior on shared clinic devices.
My Understanding: Only static assets should be cached; authenticated pages and API responses should stay network-only.
Solution: 
- Service Worker caches only static assets.
- Authenticated pages and API responses are never stored in the SW cache.
- Logout and login-page entry both trigger `CLEAR_ALL` to purge cache and queued writes.
This balances offline support with cross-user isolation.

14. How should backups and restores be handled?
Question: The prompt requires encrypted nightly backups, retention, and admin-console restore verification.
My Understanding: Backup files should be encrypted with the same environment-specific AES-GCM key used for sensitive data, and restore should support a dry-run validation mode.
Solution: 
- Backups are SQLite copies encrypted with AES-GCM.
- Plaintext temporary backup files are deleted immediately after encryption.
- Old backups are pruned by retention window.
- Restore supports:
  - filename validation
  - decryption
  - SQLite integrity check
  - optional `dry_run`
The dry-run path makes “testable restore” practical without forcing a destructive restore every time.

15. Which fields are masked for non-privileged users?
Question: The prompt says sensitive UI fields should be masked for non-privileged roles, but does not fully define role-by-field policy.
My Understanding: Admins and property managers need full operational visibility; ordinary staff should see partially masked PII.
Solution: 
- `org_admin` and `property_manager` receive unmasked values.
- For less privileged roles:
  - names are reduced to initials
  - emails are partially masked
  - address lines are partially masked
This preserves operational usability while reducing exposure for general staff.

16. Requested examples that do not apply to this app
Question: The original company-guideline examples mention concepts like credit score thresholds, 12-hour cancellation breaches, waitlist auto-promotion, content version triggers, dwell-time heartbeat analytics, canary feature-flag rollout. However, it wasn't specified if these should be handled.
My Understanding: Those are not part of the implemented Clinical Ops Portal domain in `repo/`, so no app-specific resolution was needed for them. This document focuses on the ambiguities that actually appear in the implemented system.
Solution: Focus the document only on ambiguities that actually appear in the implemented system, and do not include app-specific resolutions for unrelated examples.

# Setting up reviewer accounts

Owners and service keys keep working as before. This guide adds team members who sign in to review escalations.

## 1. Run the migration

Supabase, **SQL Editor**, **New query**. Paste all of `PHASE8_MIGRATION.sql`, click **Run**. Safe to run twice.

## 2. Give the backend your publishable key

1. Supabase, **Project Settings**, then **API** (or **API Keys**).
2. Copy the **anon** or **publishable** key. It's public by design.
3. Render, **guardloop-api**, **Environment**, add `SUPABASE_PUBLISHABLE_KEY` with that value, then **Save Changes**.
4. Locally, add the same line to `E:\guardloop\backend\.env`.

The frontend already uses this key as `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

## 3. Create your own account, and make yourself the owner

1. Supabase, **Authentication**, then **Users**, then **Add user**, then **Create new user**.
2. Enter your email and a password. Tick **Auto Confirm User**. Click **Create user**.
3. Open `https://guardloop-api.onrender.com/docs`, click **Authorize**, and paste your organization API key.
4. Run `POST /members` with:
   ```json
   {"email": "you@example.com", "role": "owner", "display_name": "Your Name"}
   ```
   The email must match the Supabase user exactly (case doesn't matter).

## 4. Invite a reviewer

1. Create their user the same way as step 3 (Supabase, Authentication, Users, Add user).
2. In Swagger, run `POST /members` with `{"email": "their@example.com", "role": "reviewer", "display_name": "Their Name"}`.

Roles:
- **owner**: everything, including members and the audit log.
- **reviewer**: resolve and assign reviews.
- **viewer**: read the dashboard and queue only.

## 5. Sign in

Open `https://guardloop-iota.vercel.app/reviewer-login`, enter the email and password, and you land on the review queue.

Sessions last about an hour. After that, sign in again.

## 6. Add links to the dashboard header

In `frontend\app\dashboard\page.tsx`, find the `<Link` that points to `/dashboard/settings`. Directly above it, add:

```tsx
<Link href="/review" className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5">
  Review queue
</Link>
<Link href="/audit" className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5">
  Audit log
</Link>
```

## What to check

- Sign in as a reviewer, open the queue, assign a review to another member, approve one. The Audit log (as owner) should show `escalation.resolved` with the reviewer's name, not `demo@guardloop.ai`.
- As a reviewer, try opening `/audit`. It should say only owners can view it.
- Export decisions from the Audit page. Open the CSV in Excel: nothing should run as a formula.
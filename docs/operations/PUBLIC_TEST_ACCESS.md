# Public Test Access (ngrok)

Lets testers use the app from anywhere while it runs on this machine: the CRM,
the API and the Telegram bot are served at one public HTTPS address,
`https://<NGROK_DOMAIN>`. Access ends as soon as the stack (or the machine)
stops.

```
tester's browser ──https──► ngrok ──► edge (nginx) ──► /api/, /uploads/profile/ ──► api
                                                   └─► everything else         ──► crm
Telegram ◄──long polling── bot   (its buttons and links point to https://<NGROK_DOMAIN>)
```

Files involved:

| File | Purpose |
| --- | --- |
| `docker-compose.public.yml` | Override on top of `docker-compose.yml`: adds `crm`, `edge` and `ngrok`, and points every backend service's `FRONTEND_BASE_URL` / `GOOGLE_REDIRECT_URI` at the public URL. |
| `deploy/nginx-public/default.conf` | Edge routing, one origin for API and CRM (no CORS needed). |
| `scripts/public.ps1` | `up` / `down` / `status` / `logs` helper. |

## One-time setup

1. Create a free account at <https://dashboard.ngrok.com>.
2. Copy **Your Authtoken** and your **dev domain** (Domains page, e.g.
   `something.ngrok-free.app`). The free plan has exactly one domain, and it
   stays the same across restarts, so the public URL never changes.
3. Add both to the root `.env` (gitignored, see `.env.example`):

   ```env
   NGROK_AUTHTOKEN=<your authtoken>
   NGROK_DOMAIN=something.ngrok-free.app
   ```

   `NGROK_DOMAIN` is the bare host: no `https://`, no trailing slash.

4. Optional, Google sign-in: put the CRM's client id in the root `.env` as
   `VITE_GOOGLE_CLIENT_ID=...`, and in the Google Cloud Console add
   `https://<NGROK_DOMAIN>` to *Authorized JavaScript origins* and
   `https://<NGROK_DOMAIN>/oauth/callback` to *Authorized redirect URIs*.
   Without the client id the public CRM simply hides the Google button.

The Telegram bot needs nothing extra: it long-polls Telegram, so it works
without an inbound route. It must already be configured in `backend/.env`
(`TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`).

## Start and stop

```powershell
.\scripts\public.ps1 up        # build + start, prints the public URL
.\scripts\public.ps1 status    # containers and the live ngrok URL
.\scripts\public.ps1 logs      # follow ngrok and edge logs
.\scripts\public.ps1 down      # back to local-only
```

Add `-NoBot` to `up` to start without the Telegram bot.

Without the script:

```bash
docker compose -f docker-compose.yml -f docker-compose.public.yml --profile telegram up -d --build
docker compose --profile telegram up -d --remove-orphans   # back to local-only
```

Local addresses while public access is on:

- `http://localhost:8090`: the same routing as the public URL, without ngrok.
- `http://localhost:4040`: ngrok traffic inspector (every request testers make).

## Good to know

- **Frontend changes need a rebuild.** The public CRM is a production build
  (not the Vite dev server). Run `.\scripts\public.ps1 up` again to publish
  new frontend or backend code.
- **Links follow the mode.** While public, emails and bot buttons link to
  `https://<NGROK_DOMAIN>`. `down` recreates the backend with the local
  `FRONTEND_BASE_URL` from `backend/.env`.
- **ngrok warning page.** On the free plan, a browser's first visit shows an
  ngrok notice; testers click *Visit Site* once. API calls and Telegram are not
  affected.
- **Only the CRM is public.** The free plan has one domain, and the landing site
  and the CRM both need `/`, so the landing site stays local
  (`npm run dev` in `landing/`).
- **Not exposed:** Postgres, Redis, Flower, the API's `/docs`, and the ngrok
  inspector (bound to `127.0.0.1`).
- **One agent per account.** The free plan allows one running ngrok agent. Stop
  any other `ngrok` process first, or `up` fails with `ERR_NGROK_108`.

## Security

Anyone with the URL reaches the app. Use test data and test accounts, use strong
passwords for admin users, and run `down` when testing is over.

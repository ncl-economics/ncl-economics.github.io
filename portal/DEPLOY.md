# Running the portal for real

Pick one of the three setups below. All of them build the same Docker image
(`portal/Dockerfile`), keep the database and PDFs on a persistent disk, and
serve the portal over HTTPS. Budget: about £6-7 a month for a hosted option,
nothing extra for a university VM.

Before any of them, collect these values:

| Value | Where it comes from |
|---|---|
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate. Resource owner: **ncl-economics**. Repository access: only **ncl-economics.github.io**. Permissions: **Contents: Read and write**. Expiry: one year, then renew. |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | A mailbox allowed to send. For Microsoft 365: host `smtp.office365.com`, port 587, the mailbox address as user, and its password, provided IT has enabled "Authenticated SMTP" for that mailbox (ask for it on a shared mailbox such as econ.media@newcastle.ac.uk). Otherwise a transactional service (Postmark, Resend, Brevo) gives SMTP credentials in minutes. |
| `ADMIN_EMAIL` | You: the review links are sent here. |
| `MARKETING_EMAILS` | The Marketing & Communication contact(s), comma-separated. |
| `SECRET_KEY`, `ADMIN_PASSWORD` | Random strings. `python3 -m app.cli secrets` prints fresh ones (Render generates them for you). |
| `SUBMIT_CODE` | Optional: a word colleagues must type on the form. Leave empty to disable. |

The files `render.yaml` and `fly.toml` are read from the repository's
**default branch**, so merge the `portal` branch into `main` first.

---

## Option A: Render (recommended, no server to manage)

1. Sign in at https://render.com with your GitHub account and grant it access
   to the `ncl-economics` organisation when asked.
2. Open **https://render.com/deploy?repo=https://github.com/ncl-economics/ncl-economics.github.io**.
   Render reads `render.yaml`, shows the service "ncl-wp-portal" and asks for
   the values marked `sync: false` (token, e-mail settings). Fill them in and
   click **Apply**.
3. Wait for the first build (5-10 minutes: the image includes Chromium for
   the cover page). The service page shows the address, something like
   `https://ncl-wp-portal.onrender.com`. That is the link for colleagues.
4. Open `https://<address>/admin`. The password is in the service's
   **Environment** tab under `ADMIN_PASSWORD`.

Updates: every push to `main` redeploys automatically. Data lives on the
1 GB disk attached to the service; Render takes daily snapshots.

## Option B: Fly.io (cheapest, command line)

```bash
curl -L https://fly.io/install.sh | sh        # install flyctl
fly auth signup                               # or: fly auth login
git clone https://github.com/ncl-economics/ncl-economics.github.io && cd ncl-economics.github.io
fly launch --copy-config --no-deploy          # accept the app name from fly.toml
fly volumes create portal_data --size 1 --region lhr
fly secrets set \
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  ADMIN_PASSWORD="choose-one" \
  GITHUB_TOKEN="github_pat_..." \
  SMTP_HOST="smtp.office365.com" SMTP_USER="econ.media@newcastle.ac.uk" SMTP_PASSWORD="..." \
  MAIL_FROM="Newcastle Economics Discussion Papers <econ.media@newcastle.ac.uk>" \
  ADMIN_EMAIL="francesco.fusari@newcastle.ac.uk" \
  MARKETING_EMAILS="someone@newcastle.ac.uk"
fly deploy
```

The portal is then at `https://ncl-wp-portal.fly.dev`. Re-run `fly deploy`
after pulling changes. The machine stops when idle and starts on the first
request, which takes a few seconds.

## Option C: a university VM with Docker (keeps everything on campus)

Needs: a Linux VM with Docker installed, a DNS name (for example
`wp-portal.ncl.ac.uk`) pointing at it, and ports 80 and 443 open.

```bash
git clone https://github.com/ncl-economics/ncl-economics.github.io && cd ncl-economics.github.io
cp portal/.env.example portal/.env && nano portal/.env     # fill in the values above
echo "PORTAL_DOMAIN=wp-portal.ncl.ac.uk" > portal/deploy/.env
docker compose -f portal/deploy/docker-compose.yml up -d --build
```

Caddy obtains the HTTPS certificate automatically. The portal is at
`https://wp-portal.ncl.ac.uk`. To update: `git pull` and run the same
`docker compose ... up -d --build`. Back up the `portal-data` Docker volume.

---

## First run checklist

1. Open the portal address: the form appears.
2. Open `/admin` with user `admin` and the password you set.
3. Submit a test paper yourself with a small PDF. You receive the
   "New submission" e-mail; the submitter address receives a confirmation.
4. Follow the review link, check the template, click **Approve & publish**.
   The archive repository gets a commit with the template, the PDF (cover
   added) and the updated index; Marketing & Communication get their
   e-mail with the PDF attached.
5. If the test should not stay in the archive, revert that commit on GitHub
   (the commit page has a **Revert** button) before RePEc's next mirroring run.
   The portal will not reuse the number, so set the next real paper's number
   by hand on its review page if you want to recover it.
6. Share the portal address (and `SUBMIT_CODE`, if set) with colleagues.

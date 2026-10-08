# Setting up the FlickOS count server on Cloudflare

> `FLICKOS` is your clone of FlickOS (default `~/Documents/Projects/FlickOS`).
> The scripts here read it from `FLICKOS`.

`flickos-countme` is ready on every installed FlickOS, but it sends nothing
yet, because `URL` in `packages/flickos-countme/usr/bin/flickos-countme` is
empty. This guide takes you from no Cloudflare account to a running server
with its address in the package:

1. try the whole thing on your own computer, without an account;
2. create the Cloudflare account and log in from the terminal;
3. create the database, deploy the Worker and check it from outside;
4. put its address into flickos-countme, test that on your own FlickOS, and
   publish it.

**What was run while writing this guide.** Everything in steps 1–3 (Node,
wrangler 4.144.0, the local database, the local Worker, `check-server.sh`,
the real client) ran on FlickOS 2.1, and the outputs shown are the real ones.
Steps 4 onwards need **your** Cloudflare account, so they weren't run. Where
this guide shows what Cloudflare prints or asks, that is what to expect, not
a recording. Cloudflare changes its website often: if a button has moved,
look for the same words nearby.

- **Time:** about an hour, half of it in step 1.
- **Cost:** nothing. Everything fits in Cloudflare's free plan (step 12).
- **What it touches:** steps 1–3 change nothing outside a temporary folder.
  From step 4 on you create things in your Cloudflare account, and from step
  13 on every FlickOS computer that updates will send its weekly count.

## What's in this folder

| File | What it is |
|---|---|
| `README.md` | This guide |
| `local-test.sh` | The whole count path on your computer: local database, local Worker, `check-server.sh`, the real client. No account needed |
| `check-server.sh` | Checks a count server from the outside. Use it on the local one (`--local`) and on the deployed one. It sends one test count with the made-up version `0.0` and deletes it again afterwards |
| `client-run.py` | Runs FlickOS's real `flickos-countme` program with its files moved into a folder of your choice, so it can talk to a test server without `sudo` |

## Contents

0. [The picture](#0-the-picture)
1. [The words](#1-the-words)
2. [The tools: Node.js, npx, wrangler](#2-the-tools-nodejs-npx-wrangler)
3. [Try it all locally first](#3-try-it-all-locally-first)
4. [Decide the address before you deploy](#4-decide-the-address-before-you-deploy)
5. [Create the Cloudflare account](#5-create-the-cloudflare-account)
6. [Log in from the terminal](#6-log-in-from-the-terminal)
7. [Create the database](#7-create-the-database)
8. [Create the table](#8-create-the-table)
9. [Deploy the Worker](#9-deploy-the-worker)
10. [Check it from outside](#10-check-it-from-outside)
11. [Check that nothing is logged](#11-check-that-nothing-is-logged)
12. [What the free plan allows](#12-what-the-free-plan-allows)
13. [Put the address into flickos-countme](#13-put-the-address-into-flickos-countme)
14. [Test it on your own FlickOS](#14-test-it-on-your-own-flickos)
15. [Commit and publish](#15-commit-and-publish)
16. [Reading the numbers](#16-reading-the-numbers)
17. [Optional: your own domain](#17-optional-your-own-domain)
18. [When something goes wrong](#18-when-something-goes-wrong)
19. [Fill-in sheet](#19-fill-in-sheet)

---

## 0. The picture

```
 an installed FlickOS                          Cloudflare
 ┌──────────────────────────────┐              ┌──────────────────────────────┐
 │ flickos-countme.timer (daily)│              │ Worker "flickos-countme"     │
 │   └ flickos-countme run      │  once a week │   worker.js                  │
 │       GET URL?version=2.1    │ ───────────▶ │   checks version and age     │
 │               &age=2         │              │   adds 1 to one row  ──┐     │
 │                              │ ◀─────────── │                        ▼     │
 │   writes state/last-week     │  "counted"   │ D1 database "flickos-countme"│
 └──────────────────────────────┘              │   table counts:              │
                                               │   week | version | age | n   │
 you, any browser or curl                      │   2026-W40 | 2.1 | 2 | 57    │
   GET /v1/stats  ───────────────────────────▶ │                              │
                                               └──────────────────────────────┘
```

The repo already has both halves:

| Half | Where | What it is |
|---|---|---|
| Client | `packages/flickos-countme/` | Python program, systemd timer and service, installer page, *Settings → Privacy* |
| Server | `server/countme/` | `worker.js` (the program), `schema.sql` (the table), `wrangler.toml` (the settings that tell Cloudflare what to create) |

The server isn't a `.deb` and runs on no FlickOS computer. You upload it to
Cloudflare once, and again whenever `worker.js` changes.

## 1. The words

- **Cloudflare**: a company that runs servers in hundreds of cities. Many
  websites go through it. We use two of its products.
- **Worker**: a small JavaScript program that Cloudflare runs whenever a
  request comes to its address. There's no server for you to maintain,
  update or reboot. You upload `worker.js` and it runs. Ours is 65 lines.
- **D1**: Cloudflare's database. It is SQLite (the same as the `sqlite3`
  command) kept on Cloudflare's side. The Worker reaches it through a
  **binding**: `wrangler.toml` says `binding = "DB"`, so in `worker.js`
  the database is `env.DB`.
- **workers.dev**: a free address Cloudflare gives every Worker, e.g.
  `https://flickos-countme.yourname.workers.dev`. `yourname` is your
  account's **workers.dev subdomain**. You pick it once, for the whole
  account.
- **wrangler**: Cloudflare's command-line tool. It creates the database,
  uploads the Worker, runs SQL and runs the Worker on your own computer for
  testing. It is written in JavaScript, so it needs Node.js.
- **ISO week**: weeks numbered Monday to Sunday, written `2026-W40`. The
  client counts once per ISO week and the server stores per ISO week, both
  in UTC.
- **age**: how long ago the computer was installed. 1 = its first count
  ever (so a new install is counted exactly once), 2 = first month,
  3 = first half year, 4 = older.

## 2. The tools: Node.js, npx, wrangler

You already have Node.js through **nvm** (Node Version Manager, which
installs Node in your home folder, not system-wide):

```sh
node --version          # v24.21.0
npx --version
```

- **npm** installs JavaScript packages. **npx** runs a package's command
  without installing it permanently: `npx wrangler …` downloads wrangler
  into a cache (`~/.npm/_npx/`) the first time, then reuses it. Nothing
  goes into the FlickOS repo, and no `node_modules/` folder appears there.
- The first `npx wrangler` asks `Need to install the following packages:
  wrangler … Ok to proceed? (y)`. Answer `y`.

```sh
npx wrangler --version  # 4.144.0 when this was written
```

**wrangler's usage statistics.** wrangler can send Cloudflare anonymous
usage data about its own commands. The scripts here turn that off with
`WRANGLER_SEND_METRICS=false`. For your own terminal, either put
`export WRANGLER_SEND_METRICS=false` in `~/.bashrc`, or run
`npx wrangler telemetry disable` once.

**Where it runs.** Every `npx wrangler` command below runs **in
`$FLICKOS/server/countme`**, because wrangler reads `wrangler.toml` from
the current folder:

```sh
cd "$FLICKOS/server/countme"
```

wrangler keeps a work folder `.wrangler/` there (local database, build
output). The repo ignores it (`.gitignore`), so it never gets committed.

## 3. Try it all locally first

This needs no account. It shows the whole path working before you create
anything real.

```sh
cd ~/Documents/flickos-countme-server
./local-test.sh
```

What it does, step by step (read the script, it's commented):

1. copies `server/countme` into a temporary folder, so your repo gets no
   test data;
2. `npx wrangler d1 execute flickos-countme --local --file schema.sql`:
   runs the SQL file against a **local** D1, an SQLite file under
   `.wrangler/state/`. `--local` is the default, and `--remote` means the
   real one at Cloudflare. Keep that difference in mind for later;
3. `npx wrangler dev --ip 127.0.0.1 --port 8787`: runs `worker.js` on your
   computer in `workerd`, the same runtime Cloudflare uses, with the local
   database as `env.DB`. It is started with `setsid`, in its own process
   group, so the script can stop it and all of its children with one
   `kill`;
4. runs `check-server.sh` against it (below);
5. runs the **real** `flickos-countme` client (`client-run.py`) with
   `Url=http://127.0.0.1:8787/v1/countme`. The client isn't changed; only its
   file paths are moved into the temporary folder;
6. prints what the database holds and the Worker's own log.

Real output (a few blank lines removed):

```
== 4. check-server.sh
== Requests that must be refused (nothing is stored)
ok    GET / -> 404
ok    POST /v1/countme -> 405
ok    GET /v1/countme?version=2.0&age=9 -> 400
ok    GET /v1/countme?version=2.0&age=1&id=abc -> 400
ok    GET /v1/countme?version=latest&age=1 -> 400
== One test count (version 0.0)
ok    GET /v1/countme?version=0.0&age=1 -> 200
ok    /v1/stats shows it
== Deleting the test count (--local)
ok    gone again
All checks passed.
== 5. The real client
$ flickos-countme show
Once a week: GET http://127.0.0.1:8787/v1/countme?version=2.1&age=1
User-Agent: flickos-countme/1
Nothing else is sent: no machine id, no user or computer name, no hardware, no list of programs.
The server keeps only the number of requests per week, version and age.
$ flickos-countme run --dry-run
Would send: GET http://127.0.0.1:8787/v1/countme?version=2.1&age=1
$ flickos-countme run
Counted in 2026-W40.
$ flickos-countme run
Already counted in 2026-W40.
== 6. What the server keeps
[{"week":"2026-W40","version":"2.1","age":1,"n":1}]
```

Things to notice:

- `age=9` and the extra `id=abc` are **refused**. The Worker takes exactly
  two parameters with allowed values, so even a changed client can't make
  it store more.
- The second `run` sends nothing: `state/last-week` already says `2026-W40`.
- The database row has no address, no time and no user agent. There is no
  column where they could go.

**Poking at it by hand.** To try your own requests, run the Worker yourself
in a scratch copy (not in the repo):

```sh
cp -a "$FLICKOS/server/countme" /tmp/countme && cd /tmp/countme
npx wrangler d1 execute flickos-countme --local --file schema.sql
npx wrangler dev                    # leave it running; Ctrl+C stops it
# in a second terminal:
curl "http://127.0.0.1:8787/v1/countme?version=2.1&age=3"
curl http://127.0.0.1:8787/v1/stats
```

## 4. Decide the address before you deploy

The address you put into `URL` goes into every FlickOS package and ISO. You
**can** change it later, because installed systems get the new
flickos-countme through their updates. But a computer that doesn't update
keeps sending to the old address, so choose one you'll keep.

| Option | Address | Needs | Recommendation |
|---|---|---|---|
| **workers.dev** | `https://flickos-countme.SUBDOMAIN.workers.dev/v1/countme` | nothing | Fine to start with. Pick `SUBDOMAIN` carefully (e.g. `flickos`), because it is in the address for good |
| **Your own domain** | e.g. `https://count.flickos.net/v1/countme` | a domain whose DNS is on Cloudflare | Best if you own a domain: you can later move the server anywhere without changing FlickOS |

You can start with workers.dev and add a domain later (step 17). If you do,
switching `URL` is a normal package update.

**Also decided already (by the design, `PRIVACY.md`):**

- `/v1/stats` is **public**: anyone can read the totals. PRIVACY.md
  promises this, so don't lock it.
- **Anyone can send fake counts.** There is no id to check, which is the
  point, so someone could inflate a number. The Worker limits the damage:
  only allowed values are stored, and an obviously silly week stands out.
  Rate limiting is possible later (step 18) but isn't needed to start.

## 5. Create the Cloudflare account

1. Open <https://dash.cloudflare.com/sign-up> in a browser.
2. Sign up with an email you'll keep. If the project ever has more people,
   an address like `flickos@…` is easier to hand over than your personal
   one. Use a strong password from a password manager.
3. Confirm the email Cloudflare sends.
4. If the dashboard asks what you want to do (add a website, etc.), you can
   skip it. You don't need a website for a Worker.
5. **Turn on two-factor authentication** (profile icon → *My Profile* →
   *Authentication*). This account controls an address that every FlickOS
   computer contacts, so it's worth protecting.

No payment details are needed for the free plan.

## 6. Log in from the terminal

```sh
cd "$FLICKOS/server/countme"
npx wrangler login
```

- wrangler opens your browser on a Cloudflare page listing what it asks
  permission for (Workers, D1 and others). Click **Allow**.
- The browser shows that you may close the window, and the terminal says
  `Successfully logged in.`
- How it works: wrangler briefly listened on `localhost:8976` for the
  browser to hand back a **token**, and saved it in your home folder. From
  now on wrangler acts as you. `npx wrangler logout` deletes the token.
- If no browser opens, wrangler prints a long URL: open it by hand, on the
  same computer (the answer goes back to `localhost`).

Check it:

```sh
npx wrangler whoami
```

It prints your email and a table with your **account name** and **account
ID**. Before logging in, it said `You are not authenticated. Please run
wrangler login.` Copy the account ID into the sheet (step 19).

## 7. Create the database

```sh
npx wrangler d1 create flickos-countme
```

- `d1 create` creates an empty D1 database named `flickos-countme` in your
  account (this is `--remote`: there is no local version of `create`).
- It prints a block like this:

  ```toml
  [[d1_databases]]
  binding = "DB"
  database_name = "flickos-countme"
  database_id = "0123abcd-…"
  ```

- If it asks **whether to add it to your config for you, answer No.**
  `wrangler.toml` already has exactly that block, with a placeholder id, and
  letting wrangler add another would give two `DB` bindings.
- Copy the `database_id` and put it into `wrangler.toml` in place of
  `REPLACE-WITH-DATABASE-ID`:

  ```toml
  database_id = "0123abcd-…"     # yours
  ```

- The id is **not a secret**. It only works with your logged-in account, so
  it's fine (and needed) to commit it (step 15).

Optional: `--location apac` (or `weur`, `enam`, …) hints where the database
lives. Counts come from everywhere and speed doesn't matter here, so
leaving it out is fine.

## 8. Create the table

```sh
npx wrangler d1 execute flickos-countme --remote --file schema.sql
```

- The same command as in step 3, but **`--remote`**: the SQL runs on the
  real database at Cloudflare. wrangler may ask you to confirm, because it
  can't be undone. Answer yes.
- `schema.sql` uses `CREATE TABLE IF NOT EXISTS`, so running it twice does
  no harm.

Check that the table is there:

```sh
npx wrangler d1 execute flickos-countme --remote --command "SELECT name FROM sqlite_master WHERE type='table'"
```

The results include `counts`.

## 9. Deploy the Worker

```sh
npx wrangler deploy
```

What happens:

- wrangler bundles `worker.js` (the `main =` in `wrangler.toml`), uploads it
  as a Worker named `flickos-countme` (`name =`), connects `env.DB` to the
  database (the `[[d1_databases]]` block) and applies `[observability]
  enabled = false` (no request logs).
- **The first time only**, if your account has no workers.dev subdomain
  yet, wrangler asks you to register one. This is the `SUBDOMAIN` from step
  4. Choose it carefully: it's part of the address.
- It ends by printing the address, e.g.

  ```
  Deployed flickos-countme triggers
    https://flickos-countme.SUBDOMAIN.workers.dev
  ```

  Copy it into the sheet.

A brand-new workers.dev subdomain can take a few minutes before it answers.
If the next step gets connection errors, wait a little and try again.

**Updating later.** After any change to `worker.js`, run `npx wrangler
deploy` again. It replaces the Worker within seconds, and the data in D1 is
kept.

## 10. Check it from outside

```sh
cd ~/Documents/flickos-countme-server
./check-server.sh https://flickos-countme.SUBDOMAIN.workers.dev
```

It is the same script as in step 3, now against the real server. The
output should be the same `ok` lines, ending in `All checks passed.` The test
count with version `0.0` is deleted again with `--remote`, so your real
numbers start at zero.

Look at it yourself too:

```sh
curl https://flickos-countme.SUBDOMAIN.workers.dev/v1/stats
```

It prints `[]` (no counts yet). That's right.

## 11. Check that nothing is logged

`PRIVACY.md` says the server keeps no request logs. Make sure that's true in
your account:

1. Cloudflare dashboard → **Workers & Pages** → **flickos-countme**.
2. **Settings** → **Observability** (it may be called *Logs* or *Workers
   Logs*): it must be **disabled**. `wrangler.toml` sets that, and each
   deploy applies it again.
3. Don't turn on **Logpush** or **Tail Workers** for it.

The **Metrics** tab (number of requests, errors) stays: those are totals
without addresses, which is fine and useful.

As PRIVACY.md also says, Cloudflare itself sees each connection's internet
address, as every network in between does. What we promise is that we
don't store it.

## 12. What the free plan allows

At the time of writing (check <https://developers.cloudflare.com/workers/platform/pricing/>
and <https://developers.cloudflare.com/d1/platform/pricing/>):

| Limit (free plan) | Amount | One FlickOS computer uses |
|---|---|---|
| Worker requests | 100,000 per day | 1 per **week** |
| D1 rows written | 100,000 per day | 1 per week |
| D1 rows read | 5 million per day | 0 (only `/v1/stats` reads) |
| D1 storage | 5 GB | the table grows by a few rows per week, all computers together |

So about 700,000 FlickOS computers would fit before the free plan runs out.
On the free plan, going over makes requests fail for the rest of the day:
it never costs money.

## 13. Put the address into flickos-countme

In the FlickOS repo:

1. Open `packages/flickos-countme/usr/bin/flickos-countme` and set `URL`
   (about line 64) to the address **plus `/v1/countme`**:

   ```python
   URL = "https://flickos-countme.SUBDOMAIN.workers.dev/v1/countme"
   ```

2. Run the unit tests: `cd packages/flickos-countme && python3 -m unittest
   discover -s tests`.
3. Bump the version. Which command depends on whether the current version
   is already published:

   ```sh
   ls "$FLICKOS/repo/public/pool/main/f/flickos-countme/"
   ```

   - If the version at the top of `debian/changelog` is **not** in that
     list (e.g. 1.1 while the pool has only 1.0), add to it:
     `cd packages/flickos-countme && dch -a "Send the weekly count to server/countme on Cloudflare."`
   - If it **is** in the list: `dch -i -D trixie "Send the weekly count to server/countme on Cloudflare."`

   Why: apt only upgrades to a higher version, and reprepro refuses a
   changed file under a version it already has.

4. Update the docs that say the URL is unset: `docs/04-packages.md`
   (*The server*), `docs/09-customizing.md` (*Weekly count*),
   `server/countme/README.md`, and the flickos-countme line in `CLAUDE.md`.

## 14. Test it on your own FlickOS

Build the package from a copy (so the source tree stays clean) and install
it:

```sh
cp -a "$FLICKOS/packages/flickos-countme" /tmp/ && cd /tmp/flickos-countme
dpkg-buildpackage -us -uc -b
sudo apt install /tmp/flickos-countme_*_all.deb
```

Then:

```sh
flickos-countme show                        # the real address now
flickos-countme run --dry-run               # "Would send: GET https://…"
sudo systemctl start flickos-countme.service
journalctl -u flickos-countme -n 5          # "Counted in 2026-W40."
flickos-countme status
curl https://flickos-countme.SUBDOMAIN.workers.dev/v1/stats
```

- `systemctl start` runs the same service the timer runs, as the
  sandboxed user `_flickos-countme`. That also tests that the sandbox lets
  it reach the internet.
- This is a **real count**: your computer is a real FlickOS install, so
  leave it in. Its `age` is 1 if it never counted before.
- Installing the package doesn't start the timer (`--no-start`); it starts
  at the next boot. `systemctl list-timers flickos-countme.timer` shows
  when it will run next.
- *Settings → Privacy* now shows the real request and the week last
  counted.

## 15. Commit and publish

Everything goes on the `flickos-countme` branch:

```sh
cd "$FLICKOS"
git add server/countme/wrangler.toml packages/flickos-countme docs CLAUDE.md
git commit        # e.g. "flickos-countme: send to the Cloudflare server"
```

Then publish the way you publish every package (`packages/build.sh`,
`repo/publish.sh && repo/upload.sh`), after the branch is merged into main.
From then on:

- **new installs** get flickos-countme (a Recommends of flickos-desktop)
  and the installer's question;
- **existing installs** don't get it automatically, because FlickOS doesn't
  install new Recommends. Someone who wants to be counted runs `sudo apt
  install flickos-countme`.

## 16. Reading the numbers

```sh
curl -s https://flickos-countme.SUBDOMAIN.workers.dev/v1/stats | python3 -m json.tool
```

With SQL, from `$FLICKOS/server/countme`:

```sh
# computers per week and version
npx wrangler d1 execute flickos-countme --remote \
  --command "SELECT week, version, SUM(n) AS computers FROM counts GROUP BY week, version ORDER BY week"

# new installs per week
npx wrangler d1 execute flickos-countme --remote \
  --command "SELECT week, SUM(n) AS new_installs FROM counts WHERE age = 1 GROUP BY week ORDER BY week"
```

(The first one was run locally with `--local` while writing this guide.)

- **Active computers in a week** = the sum of `n` over all ages.
- **New installs in a week** = `n` where `age = 1`.
- A computer that is off all week isn't counted that week. Compare weeks
  with each other, not with "how many exist".

## 17. Optional: your own domain

Needs a domain whose DNS is managed by Cloudflare (dashboard → *Add a
domain*, then change the nameservers at your registrar to the two
Cloudflare gives you).

Then add to `wrangler.toml`:

```toml
routes = [
  { pattern = "count.flickos.net", custom_domain = true }
]
```

and `npx wrangler deploy` again. Cloudflare creates the DNS record and the
certificate itself. Check with `./check-server.sh https://count.flickos.net`,
then change `URL` (steps 13–15). Keep the workers.dev address running until
all systems have updated. It's the same Worker, so there's nothing extra to
look after.

## 18. When something goes wrong

| What you see | Why, and what to do |
|---|---|
| `You are not authenticated` | Run `npx wrangler login` again (step 6). The token can expire |
| `Couldn't find a D1 DB with the name or binding` / `database_id` errors | `wrangler.toml` still has `REPLACE-WITH-DATABASE-ID`, or you're not in `server/countme` |
| `no such table: counts` | You created the table only `--local`. Run step 8 with `--remote` |
| `check-server.sh` gets `000` | No connection: a new workers.dev subdomain isn't live yet (wait a few minutes), or the address is misspelled |
| `check-server.sh` gets `500` | The Worker failed, usually the database. `npx wrangler tail` shows live errors while you send a request. It's a live view only and stores nothing, but still use it only while debugging |
| The client says `Not sent: no server set.` | `URL` is still empty in the installed version: check `dpkg -l flickos-countme` |
| The client says `Not sent: live session.` | Correct behavior: the live ISO never counts |
| The client says `Already counted in …` | Correct: once per week. To send again for a test, delete `/var/lib/flickos-countme/last-week` |
| Someone floods fake counts | Delete that week's bad rows with a `DELETE … WHERE week = '…'`. For the future, dashboard → your domain → *Security* → *WAF* → *Rate limiting rules* (needs your own domain), or a limit in `worker.js` |
| You want to stop everything | Set `URL = ""` in a new package version. To remove the server too: `npx wrangler delete` (the Worker) and `npx wrangler d1 delete flickos-countme` (the data) |

## 19. Fill-in sheet

Copy this somewhere safe (not into the public repo, except the lines marked
*commit*):

| What | Value |
|---|---|
| Cloudflare login email | |
| 2FA on? | |
| Account ID (`wrangler whoami`) | |
| workers.dev subdomain | |
| D1 `database_id` | *(commit: `wrangler.toml`)* |
| Worker address | |
| `URL` in flickos-countme | *(commit: `…/v1/countme`)* |
| flickos-countme version with the URL | |
| Date the first real count arrived | |

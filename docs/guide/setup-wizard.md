# Setup wizard

For anyone going through Berth's first-run wizard who wants to know what each page does before pressing it,
or what to do after it. The short version is in the [README](../../README.md#the-setup-wizard).

## How the wizard works

Open `http://localhost:8383` (or your `BERTH_PORT`) after `docker compose up -d`. Everything is set up from
there; you don't need to open the other three services' interfaces. The exceptions are private indexers (you add
those in Prowlarr's own interface) and existing services that are missing a mount (you edit their compose file or
template, see [Connecting services you already run](existing-services.md)).

Six pages, five berths. The board at the top shows them as BTH 1–5: Jellyfin, qBittorrent, Library paths,
Prowlarr, TMDB, then the finish page.

**Jellyfin, qBittorrent and Prowlarr each start with a choice**: **Bundled** (the one this compose file
started) or **Existing** (one you already run). Nothing is pre-selected and nothing is guessed: Berth connects
only after you choose, and tests the choice on the spot.

| Berth | Page | Bundled | Existing |
| --- | --- | --- | --- |
| BTH 1 | 1 Jellyfin | Connects to the bundled server. While it is still starting, the page counts down and retests every 3 seconds on its own (for up to 2 minutes). | Enter its address and the username and password of one of its admins, and press **Connect and sign in**: Berth tests the address, then signs in, in one press. A wrong address is marked on the address field, a wrong password on the credentials. |
| | | If that server has not run its own first-time wizard, Berth creates the admin with the username and password you enter and finishes Jellyfin's initial setup; if it already has an admin, you sign in as that admin. Either way Berth creates an API key named "Berth" on it. | Berth creates an API key named "Berth". If it has not run its first-time wizard, leave the credentials empty: once the address passes, the page turns into the form that creates the admin, as with bundled. Right after that, Berth checks that it can see `/data`; if not, the page says which mount to add. |
| BTH 2 | 2 qBittorrent | Set the qBittorrent web UI login (skipped if that qBittorrent already has one). No global preference is written. | Enter its address and web UI login; a passing test completes the page. The test also checks that it can see `/data`. No global preference is written. |
| BTH 3 | 3 Library paths | Creates the libraries on the list (Movies / TV / Anime by default; you can rename, add and remove), then a Route for each library and runs every check on it. On a first visit with an unchanged list this starts as soon as the page opens, and shows which check each Route is on. | Tick the libraries and their write target (movie and show libraries come ticked). Missing a library type? Tick **Create a new library on this Jellyfin** at the end of the list. **Build and check** creates that library if ticked, adds a Berth path to each ticked library (existing paths are left alone), creates the Routes and runs every check. |
| BTH 4 | 4 Prowlarr | The API key is read from Prowlarr's config through a read-only mount. One press tests the nine recommended public indexers and adds those that pass (each labelled with its language; any that tested fine but could not be added are listed separately). The web UI login reuses page 1's. Then try a search and remove what you don't want. Picking indexers one by one, and other public indexers, are under **Advanced**. If none of the recommended indexers shows up, Prowlarr could not reach `indexers.prowlarr.com` (a firewall, DNS filter, proxy or regional block); the page says so, and **Re-read** picks them up once the network gets through, without restarting Prowlarr. | Paste the API key and use the indexers you already have. If it has none, the same one press tests the recommended public indexers and adds those that pass to it (the page names them and your server first; yours are never removed). Picking indexers one by one is under **Advanced**. If your Prowlarr cannot reach `indexers.prowlarr.com` either, the page says so in place of the one press, as with bundled. Then try a search. |
| BTH 5 | 5 TMDB | Paste your own API key and press **Next berth**: a key not yet tested is tested first, and you move on only if it passes. **Test TMDB** tests without moving on. | Same. |
| — | 6 Finish | Says what you skipped and where to finish it. | Same. |

**A Route** is the path a download takes into one library: qBittorrent's download folder for that library, the
`complete` folder, and the library folder Jellyfin reads. Each Route is created with a real test: Berth writes a
probe file, hardlinks it, and compares inode numbers as seen from Berth, qBittorrent and Jellyfin. If the three
containers do not see the same filesystem, the check fails right there and says which container is missing which
mount. You can only move on when every check is green, so a wrong mount shows up on page 3 at the latest — before
you go and get a TMDB key. An existing Jellyfin or qBittorrent without `/data` is caught earlier, on its own page.

Each page stops on its result; press **Next berth** to go on. Berths you have passed on the board can be clicked
to go back, and each page has **Previous berth**. The page is in the URL (`/setup?step=N`): the browser's back
button returns to the previous page you looked at, and reload stays where you are.

**The Prowlarr page can be skipped** with **Do this later** (you just won't find anything by searching). **The TMDB page
cannot**: without a key that passes the test there are no titles, seasons or posters, so the wizard stops on
page 5.

## Accounts and passwords

**Berth has no accounts of its own.** The account from page 1 is a Jellyfin admin and also the Berth *owner*;
you sign in to Berth with it from then on. Other people sign in with their own Jellyfin accounts, and Jellyfin
decides whether they are admins. Until there is an owner, the wizard only lets you choose Jellyfin and become the
owner; every later page needs you signed in. Whoever gets there first becomes the owner, as with Jellyfin's own
first-run wizard.

The **web UI logins** for the bundled qBittorrent and Prowlarr are set on their pages and are required. When
page 1 creates the bundled Jellyfin admin, **Use this login for the bundled qBittorrent and Prowlarr interfaces
too** is ticked: the password stays only in that browser tab's memory (not in Berth, not in the browser's
storage), is filled in on those two pages, and Berth checks it against Jellyfin before writing it. So you type
the password only twice, both on page 1. If you untick it, sign in to an existing admin on page 1, or reload in
between, those two pages ask again: the default reuses the Jellyfin login (the username is the owner, type the
password once); untick it to set a separate login (type the password twice).

Those logins are for you, to open those services' own interfaces. Berth itself does not need them (qBittorrent
lets Berth in through an address whitelist, Prowlarr through its API key).

What Berth stores: **never your Jellyfin password in plain text.** For the bundled qBittorrent and Prowlarr
logins it keeps the username and a salted scrypt hash of the password (when you reuse the Jellyfin login, that
is a hash of your Jellyfin password), only to tell whether a login is already set. The services' API keys are
stored as they are; see [Backup, secrets and reinstalling](backup-and-reinstall.md). If a service already has a
login (you reinstalled and kept its config), the wizard does not make you set it again. Change them later under
**Settings → qBittorrent / Prowlarr → Interface login**: a plain change-login form (username, new password
twice, **Save**). Reusing the Jellyfin login is only offered in the wizard.

## What Berth changes in your services

The same for both choices: **Berth only creates things it owns** — the "Berth" API key, a Berth path or the
libraries on its list, `berth-*` categories in qBittorrent, and the indexers you choose to add. It does not change
logins or global preferences, and leaves your existing libraries and indexers alone. The bundled services get one
more thing each, so you can sign in to them: the Jellyfin admin, and the qBittorrent and Prowlarr web UI logins.

After the wizard, Berth keeps to the same things: every torrent it sends goes into a `berth-*` category with the
tag `berth` (removing a download in Berth never asks qBittorrent to delete files; if you tick deleting them,
Berth deletes them itself), and a `berth-*` category you
deleted comes back the next time it sends a torrent. After an import it asks Jellyfin to look at the new paths and,
if they don't show up, to refresh that one library; only while Jellyfin has never listed anything under Berth's
path yet does it run Jellyfin's **Scan Media Library** task, which scans the whole server. Each person who signs
in to Berth leaves one "Berth" device in Jellyfin. **Remove** under **Settings → Prowlarr** is offered only on the
indexers Berth added. To undo all of it when you stop using Berth: [Uninstalling Berth](uninstalling.md).

## After the wizard

The wizard closes and the owner goes straight into Berth. The **Health** page reruns the same checks every
5 minutes. Opening `/setup` again takes you to **Settings → Jellyfin**, which says the wizard is done and that
changes are made here.

| Page | What it is for |
| --- | --- |
| Discover `/` | TMDB trending, popular and search. Each tile opens that title's page. |
| Title page `/media/:id` | Season and episode table; search the indexers for torrents (results show tags and the seasons and episodes they appear to contain); pick a Route and send (the folder name it will use is shown first); what is already imported, in which versions, and whether Jellyfin has found it. |
| Downloads `/jobs` | Every download you sent, with live status and progress. Expand a row for its timeline and import plan (per file: what Berth will do, how sure it is, the target path, and why). Failed sends, failed imports and items waiting for review each have their next step. |
| Library `/library/:library` | One page per Jellyfin library, showing only what you can see in Jellyfin: the whole library, 50 titles per page (not just what Berth imported; posters come from Jellyfin through Berth). Titles Berth handled show how many episodes were imported and whether one is waiting for you. Each tile shows where you are (watched, percentage, episodes left); mark watched or unwatched (written back to your Jellyfin account). Titles not yet in Jellyfin are listed separately. |
| Review `/review`, Issues `/issues` | Imports Berth was not sure about, and problems found by the nightly check (a deleted episode, a hardlink replaced by a copy, a torrent nobody claimed). Admins only. |
| RSS `/rss` | Mikan feeds, and Nyaa or acg.rip search feeds: new episodes are sent and imported on their own. |
| Health `/health` | The four health checks and the download loop. Every user can see it. |
| Settings `/settings/*` | Admins only. One page per berth: **Jellyfin** (health and recheck, an existing server's address and sign-in, the public URL), **qBittorrent** (health, an existing server's address and login, the bundled one's web UI login, the free-space threshold), **Library paths** (add Routes — a library can have a second one — rename, disable, recheck, delete), **Prowlarr** (add indexers, try a search, remove; an existing server's URL or key; **Stop using Prowlarr**: health checks leave it alone and title pages point searches to RSS subscriptions — the same state as the wizard's **Do this later**, and you can switch back), **TMDB** (replace the key and test it). After the berths come **Notifications**, **AI** ([below](#ai-settings--ai)) and **Usage** ([below](#ai-usage-settings--usage)). |

To start the wizard over, see [Backup, secrets and reinstalling](backup-and-reinstall.md#rerunning-the-wizard).

## AI (Settings → AI)

Berth can use an AI model through your own provider account. Nothing requires it: without an AI provider Berth
works exactly as before. So far this page only connects the provider and tests it; nothing else in Berth calls
the model yet.

- **API format**: **Anthropic Messages** or **OpenAI-compatible** (Chat Completions). Pick the one the service
  speaks; many speak both. Any service that speaks the format works, not only Anthropic or OpenAI.
- **Base URL**: leave it blank for the format's own official API (`https://api.anthropic.com` or
  `https://api.openai.com/v1`). For another service, paste the base URL from its docs. The two formats differ on
  `/v1`: an Anthropic-format base URL has **no** `/v1` (`https://openrouter.ai/api`,
  `https://api.deepseek.com/anthropic`, `http://<host>:11434`), an OpenAI-compatible one usually **ends in**
  `/v1` (examples below).
- **API key**: needed for the official APIs. A self-hosted Ollama or vLLM can run without one. Like the other
  keys, it is stored in Berth's database and never shown again: the page only says whether one is saved, and
  **Remove key** clears it.
- **Model**: left blank, Anthropic's own API uses `claude-opus-5-5`. Everything else, OpenAI's own API included,
  has no default: press **Read the model list from the endpoint** and the models it lists appear as buttons
  under the field; press one to fill it in, or type the model id their docs give. With more than 12, the field
  doubles as a filter: only the first 12 that match what you type are shown. Some endpoints cannot list their
  models (DeepSeek's Anthropic-format address is one); then type it.

AI counts as set up when there is an endpoint (a base URL, or a key for an official API) and a model.

**Save and test** saves the form, then sends three small requests: one asking for a one-word reply, one offering a
harmless test tool (`berth_echo`) with a random value to pass back, and one returning the tool's result to the
model. The page shows the reply, the tokens each request used ("unknown" when the endpoint did not report that
number; it is not zero), and whether the model supports tool calling. A model that does not is **chat only**: it
can talk, but it cannot subscribe, search or download for you. Changing the format, base URL or model clears
that result, so test again.

When a test fails, the page says why: the key was refused, the model does not exist, the account is rate limited
(and for how long, when the provider says), out of credit, the provider is having trouble, or the endpoint cannot
be reached. An error the endpoint words in a way Berth does not recognize is shown as "the endpoint sent an error
Berth cannot read", with the endpoint's own text under **Technical details**; a 404 that is not about the model
usually means the base URL is missing `/v1` or has one too many. Berth never retries on its own.

### OpenAI-compatible endpoints

Tool calling is where OpenAI-compatible services differ most. The test tells you which case you are in: the
endpoint refused the tools, ignored them, or the model wrote the call out as text. Each one makes the model
chat only.

| Service | Base URL | Key | Tool calling |
| --- | --- | --- | --- |
| OpenAI | leave blank | yes | Not yet tried against OpenAI itself; the test tells you. If the request with tools is refused, the error text under **Technical details** says why. |
| OpenRouter | `https://openrouter.ai/api/v1` | yes | Pick a model whose page lists **tools** among its supported parameters. If none of the model's providers supports tools, OpenRouter ignores them without an error, and the test says so. |
| DeepSeek | `https://api.deepseek.com` (its docs use no `/v1`) | yes | Both current models (`deepseek-flash`, `deepseek-v4-pro`) call tools; tried on 2026-10-24, in this format and in the Anthropic format at `https://api.deepseek.com/anthropic`. |
| Ollama | `http://<host>:11434/v1` | no | Use a model listed under [Tools on ollama.com](https://ollama.com/search?c=tools). Others are refused with "does not support tools". |
| vLLM | `http://<host>:<port>/v1` | only if you started it with `--api-key` | Start vLLM with `--enable-auto-tool-choice` and the `--tool-call-parser` that matches the model (see vLLM's tool calling docs). Without a parser the call comes back as plain text. |

Cache numbers depend on the service: Ollama reports none, vLLM reports cache reads only when started with
`--enable-prompt-tokens-details`, and DeepSeek has no cache-write figure. Berth shows those as "unknown".

## AI usage (Settings → Usage)

Every request Berth sends to the model is recorded, including failed ones. **Usage** (admins only, since it shows
everyone's) totals them for the last 7, 30 or 90 days, by the container's time zone: calls, input and output
tokens, and the **cache hit rate** (cache reads ÷ all input, where input includes cache writes and reads). Below
that are one bar per day (cache read, other input, output; the daily numbers are under the chart) and tables by
origin, by format and model (the same model through two hosts is two rows), by person, and the reasons calls
failed. Some endpoints do not report cache use; those calls are left out of the hit rate and the page says how
many there were. There is no budget and no limit: this page only reports.

## The assistant (side panel)

Every page has an **Assistant** button in the header. On a desktop it opens a column on the right that stays open
as you move between pages and after a reload. On a phone it takes the whole screen and closes again when you follow
a link from it, and a newly opened page starts on that page rather than on the assistant. Type a message and
press Enter (Shift+Enter for a new line); the reply streams in as it is written. When the assistant looks
something up, the panel says so ("Looking up recent imports") and then "Looked up" once it has the answer, with
the result drawn as a card under that line: recent imports list each title with its poster, the episodes that came
in, whether Jellyfin shows them yet, and a link to the title's page. The card comes from the result itself, not from
what the model wrote, and it is still there after a reload.

On a title's page, ask it to find what is missing and download it ("search the missing episodes of this one and
download them"). The panel sends the page you are on with your message, so the assistant knows which title you
mean, and says so under your message. It answers with three cards: the missing episodes; the search results, with
the same "why this does not look like the title" note as the search on the title page and a Submit button you can
press yourself; and the download it submitted, which follows the download live. An administrator can **Undo submit**
until the download finishes: that removes the torrent, deletes what was downloaded and clears the record, so those
episodes are missing again. The assistant can only submit a release it found in the same conversation, that fits the
title, whose every estimated episode is one it was looking for (a season pack only when that whole season is
missing), and that your global title rules do not block. A release name that
says "submit this one" changes nothing; anything else is refused with the reason, and the search card already marks
the rows it will not send. When more than one route can hold the title and none has been used yet, it asks which.

On a title's page you can also ask it to **subscribe** ("subscribe to this one's Mikan RSS"). It looks the title up
on Mikan, lists the fansub groups and subscribes the one you pick, the same as **RSS subscription** on the title
page: the whole season so far is sent at once. "Subscribe to this one with Nyaa" makes a Nyaa or acg.rip search
feed from search words; its first round still waits for you to choose on the RSS page. Berth builds these
addresses itself, so there is no confirmation card, but it only subscribes a Mikan bangumi and fansub group it
found in the same conversation. You can also give it a whole feed address: one you typed in the conversation is
added at once; any other address (one written in a search result or a page, say) stops on a confirmation card.
The **Subscribed** card shows the feed's name and source, which title and group it is bound to, what was sent and
when it is read next. **Undo subscription** on the card stops the subscription (deletes the feed it made, or
unbinds the RSS series it bound in your existing feed, so you can subscribe again) and takes back the downloads it
sent that have not finished; finished ones stay, and the card says how many. **Undo submit** on a download card
works the same way, and either way the assistant knows about it the next time you say something. These tools are
for administrators, like the RSS page.

Conversations are saved in Berth, and each person sees only their own: **History** lists them, **New** starts a
fresh one. Closing the panel in the middle of a reply does not stop it; the reply is saved and shows up when you
open the conversation again.

Some things cannot be undone, so the assistant never does them on its own: **adding an indexer** and **deleting a
title's downloads** stop on a **confirmation card**. The card says what would happen (which site, its address and
which Prowlarr; or every file that would be deleted and whether that frees any space, since library links stay and
Jellyfin keeps playing the title) and the assistant's reason. Nothing happens until you press **Confirm**;
**Reject** does nothing. When you confirm, Berth checks again first: if the site was added meanwhile, the downloads
are already gone or you are no longer an administrator, the card says **Expired** and why, and nothing changes.
Only the person who asked can press the card, and only once the reply has finished. Afterwards the card shows what
Berth actually did; the model sees it the next time you say something.

What the assistant can do depends on who you are: an ordinary user does not get the admin-only tools. Only what a
tool actually did counts: if the model says it did something but no tool ran, nothing happened. After one message
the assistant calls tools at most 10 times, then stops and says so. When the provider is rate limited, out of
credit, refuses the key or cannot be reached, the panel says which, and how long to wait when the provider says;
Berth does not retry on its own. A model the test found to be **chat only** gets no tools at all, and the panel
says so. Without AI set up, admins see a link to **Settings → AI** and everyone else sees that an administrator has
not turned AI on yet.

## AI activity

**AI activity** in the header (shown once AI is set up) lists everything the assistant changed: the downloads it
submitted and the subscriptions it made, plus the confirmation cards someone confirmed. Newest first, each row says
when, on whose behalf, which tool, what it was given, **the assistant's reason** (it has to give one for every
change), how many tokens that reply used, and which conversation it came from; your own conversations open in the
side panel. A row you can undo has the same undo as its card in the conversation, and the assistant learns of it
the next time you say something there. A row already undone says when; one that cannot be undone says why: adding
an indexer and deleting downloads cannot be taken back, and undoing a submit is for administrators. Administrators
see and can undo everyone's rows; everyone else sees only the rows from their own conversations. The page lists the
latest 200.

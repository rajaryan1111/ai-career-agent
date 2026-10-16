# Agent-Reach Reuse Review — 2026-10-14

## Scope and method

Reviewed `https://github.com/Panniantong/Agent-Reach` at commit
`94f06c1969dfc1834001269d79d3ad0972d9dee6` (branch `main`, 2026-10-08), cloned read-only and inspected
directly — not from the README alone. Files read in full or in substantial part:
`agent_reach/utils/url.py`, `agent_reach/utils/text.py`, `agent_reach/channels/base.py`,
`agent_reach/channels/web.py`, `agent_reach/channels/rss.py`, `agent_reach/channels/github.py`,
`agent_reach/channels/linkedin.py`, `agent_reach/backends/opencli.py`, `agent_reach/doctor.py`,
`agent_reach/probe.py`, `agent_reach/config.py`, plus tests `test_url_security.py`,
`test_channel_contracts.py`, `test_doctor.py`, `test_probe.py`, and `SECURITY.md`.

**License:** MIT, `LICENSE` — "Copyright (c) 2025 Agent Eyes". Concepts below were reimplemented in this
project's own standard-library code; no upstream file was copied wholesale. Where the implementation is
materially derived from an upstream module, the module docstring carries an attribution line with the
upstream URL, path, and license.

**Reference design in one line:** Agent-Reach is a local CLI that routes a URL to a "channel" (platform
adapter) whose backends are ordered preferred→fallback, does real side-effect-free health probing of the
underlying CLI tools, and reports per-channel status. It reaches authenticated platforms through cookie
export, browser-session bridges (OpenCLI), MCP servers and Jina Reader.

**Immediate incompatibility to record up front:** every mechanism Agent-Reach uses to reach authenticated
or blocked platforms (cookie extraction, reusing the user's logged-in Chrome session, MCP servers,
third-party reader proxy, proxy/stealth guidance) is explicitly forbidden in this project's guardrails.
Its *unauthenticated, hostile-input-facing* engineering — untrusted-URL validation, credential redaction,
fail-closed health semantics — is the part that transfers.

## Decision table

| Reference concept / path | Actual verified behavior (read from source) | Career Agent use case | Decision | Reason and risks | Code / tests affected |
|---|---|---|---|---|---|
| `agent_reach/utils/url.py::normalize_public_http_url` | Rejects empty/whitespace/control-char/backslash URLs; requires `http`/`https`; rejects userinfo, `%` in host, blocked local names (`localhost`, `*.internal`, `*.local`, `metadata.google.internal`, `instance-data`, …), single-label hosts, and non-global IP literals. Parses legacy IPv4 spellings (`127.1`, `2130706433`, `0x7f.0.0.1`) via `socket.inet_aton` and checks `is_global`. Returns a normalized URL. | Manual job entry is our only current trust boundary: `source_listing_url` and `employer_apply_url` are only checked for `^https?://` today, then stored, displayed, exported, and later handed to a future fetcher. | **Implement** (adapted) | Fixes a real gap with no dependency: a `https://user:pass@host` or `http://169.254.169.254/…` link can be stored and displayed today. New module `career_agent/urls.py` reimplements the concept in the standard library. Explicitly documented as literal-host validation only — **not** SSRF protection (no DNS resolution, no redirect handling). | `career_agent/urls.py` (new); `career_agent/desktop_logic.py` (`build_job_listing`); `tests/test_urls.py` (new), `tests/test_desktop_logic.py` |
| `agent_reach/utils/url.py::domain_matches` / `host_matches` | Parses the URL and matches the hostname exactly or as a real subdomain, never by substring; rejects lookalikes (`x.com.evil.test`), userinfo disguises (`x.com@evil.test`), non-HTTP(S) schemes, and malformed/out-of-range ports. | Would be needed by a future adapter that must route or verify a link against an allow-list of source domains. | **Defer** | No adapter, host-routing, or allow-list consumer exists yet; adding it now would be dead code. Recorded as the required helper when the first permitted adapter lands (Jobicy), with the upstream tests as the case list. | none |
| `agent_reach/utils/text.py::scrub_url_credentials` | Regex redaction of URL userinfo (`scheme://user:pass@` and bare `user:pass@`), plus sensitive query/fragment parameters (`token`, `api_key`, `password`, `signature`, `session`, `cookie`, `credential`, …). | Local rows written before this change can still contain credential-bearing URLs; the job report pane prints them verbatim. | **Implement** (adapted, narrower) | Small, testable, and it protects legacy rows without rewriting them. Redaction is display-only; the stored value is never altered, so no data is mutated. | `career_agent/urls.py::redact_url_credentials`; `career_agent/desktop.py::_select_job`; `tests/test_urls.py`, `tests/test_desktop_handlers.py` |
| `agent_reach/channels/base.py` (channel contract: `can_handle` / `check` / ordered `backends` / `active_backend`) | Each channel declares an ordered candidate backend list (index 0 preferred), an explicit "which backend is actually serving" attribute, and a health result; the docstring states `shutil.which()` is **not** proof of health. | Our `architecture.md` §5 already specifies a conceptual adapter contract (identity, access method, permission evidence + review date, discovery vs submission separately, support status, per-run outcomes, freshness, empty-vs-failed). | **Partially implement** (permission/capability slice); **reject** the registry/plugin/backend machinery | The transferable idea is *fail-closed, evidence-backed enablement*, and we need it as code because our source gate is prose-only today. The registry + dynamic backend ordering + `can_handle` routing are unjustified with zero adapters (and section 3.B forbids a plugin framework without a use case). | `career_agent/sources.py` (new): `SourceDecision`, `PermissionState`, `discovery_gate`, `submission_gate`; `tests/test_sources.py` (new) |
| `agent_reach/doctor.py::check_all` + status vocabulary (`ok`/`warn`/`off`/`error`) | Collects per-channel results; a single channel raising must not abort the report — exceptions degrade to `status="error"` with the stale `active_backend` cleared; every message passes through credential scrubbing before rendering. | Per-source fault isolation and "one failing adapter must not abort independent sources" (section 3.C). | **Defer** | There is nothing to isolate yet: no adapters, no run orchestrator. The two transferable rules (isolation, scrub at the output boundary) are recorded for the adapter phase; implementing a doctor CLI now would be a decorative feature. | none |
| `agent_reach/probe.py::probe_command` | Actually executes the tool (`--version`) instead of trusting `shutil.which()`; classifies `missing` / `broken` (stale venv shebang, exit 126/127, `FileNotFoundError`) / `timeout` / `error`; retries only transient classes, never missing/broken. | "A backend must pass a real, safe health check before being reported healthy" and "retries only for transient failures". | **Defer** | We have no external CLI backends and no subprocess use at all — this project is deliberately standard-library, zero-install. The *principle* (prove health, do not infer it; retry only transient classes) is adopted in the source gate's fail-closed design and in the documented retry rule. | none (principle only) |
| `agent_reach/channels/web.py` (Jina Reader fetch, 5 MB response cap, `_is_antibot_page` challenge detection) | Validates the URL, fetches `https://r.jina.ai/<url>`, caps the read at 5 MB + 1 byte and raises when exceeded, and raises a distinct error when the body is a Cloudflare/Jina challenge page rather than the target content. | The caps and the "a challenge page is not content" rule are exactly the semantics a future permitted fetcher needs. | **Reject the fetch mechanism; defer the cap/challenge rules** | Routing page fetches through a third-party reader service would send user-selected URLs off-device, has no permission basis in our gate, and conflicts with local-first processing. The size cap, timeout, and challenge-vs-content distinction are recorded as acceptance rules for the future fetcher — not implemented, because no fetcher is authorized. | none |
| `agent_reach/channels/rss.py` (`feedparser` backend) | Reports `off` when `feedparser` is not importable and `error` on a broken install. | RSS/Atom could eventually cover employer or ATS feeds. | **Reject now** | Adds a third-party dependency for a capability with no permitted feed and no source that has passed the gate. Standard-library parsing would be revisited when a permitted feed exists. | none |
| `agent_reach/channels/github.py`, `linkedin.py`, `twitter.py`, `reddit.py`, `xiaohongshu.py`, `facebook.py`, `instagram.py`, `bilibili.py`, `v2ex.py`, `youtube.py`, `xueqiu.py`, `exa_search.py`, `mcporter.py` | Each wraps a specific upstream CLI/MCP server or authenticated API, several via cookies or paid search (Exa). | None. | **Reject** | Requires cookie extraction, browser sessions, account credentials, or paid APIs — every one is forbidden by our guardrails (no cookie/session reuse, no broad authenticated scraping, no paid services, no unauthorized automation). | none |
| `agent_reach/backends/opencli.py` (browser-bridge via the user's real Chrome session) | Drives the user's logged-in Chrome through an extension + local daemon; notes that `opencli doctor` auto-starts a daemon, so health checks must avoid it. | None. | **Reject** | Explicitly incompatible: session reuse and stealth-style access are prohibited; the module itself documents side effects that a health check must avoid. | none |
| `agent_reach/config.py` (`make_private_dir`, 0600 YAML, symlink rejection, atomic writes) | Credential/config files are written owner-only through a temp file + `os.replace`, and symlinked paths are rejected instead of followed. | Our SQLite file in the per-user app-data folder holds candidate PII and is created with the process umask (commonly world-readable on multi-user systems). | **Implement** (narrow slice: file permissions) | Tightening the database file to owner-only is directly privacy-relevant, idempotent, and does not alter stored data or the schema. Symlink/atomic-write machinery and directory-permission changes are **deferred** — they belong to the Phase 2 security work and would expand this patch. | `career_agent/store.py::CareerStore`; `tests/test_store.py` |
| `tests/test_url_security.py`, `tests/test_probe.py`, `tests/test_doctor.py`, `tests/test_channel_contracts.py` | Deterministic tests for hostile URLs (lookalikes, userinfo, bad ports), probe classification, per-channel isolation, registry hygiene, and monkeypatched network. | Test-case inventory for our URL validator and gate tests. | **Implement** (adapted case lists) | The hostile-URL cases transfer directly; probe/doctor cases have no analogue without adapters. | `tests/test_urls.py`, `tests/test_sources.py` |

## Implemented in this change

1. `career_agent/urls.py` — public HTTP(S) URL validation for untrusted links (scheme, credentials,
   malformed authority/port, local/internal names, single-label hosts, legacy IPv4 spellings, non-global
   IPv4/IPv6 literals) plus `redact_url_credentials` for display.
2. `career_agent/sources.py` — permission/quality gate as data + fail-closed pure functions, encoding the
   decisions already recorded in `research/source-permission-decision-matrix-2026-10-14.md`, plus a
   run-outcome taxonomy that distinguishes a legitimate empty result from failed, blocked, partial, and
   challenge-detected runs.
3. `career_agent/store.py` — best-effort owner-only permissions (0600) for the local SQLite file.
4. Wiring: manual job entry uses the shared validator; the job report pane redacts credentials in displayed
   URLs (legacy rows are displayed safely but never rewritten).

Nothing in this change enables a source, adds a network call, a dependency, a scheduler, a worker, or any
external transmission. `enabled_discovery_sources()` is empty and is asserted to be empty by test.

## Explicitly rejected and deferred (with reasons to revisit)

- **Rejected outright:** cookie extraction, browser-session bridges, MCP servers, social-media and
  authenticated scrapers, third-party reader proxying, paid search/API backends, proxy or stealth access,
  auto-installation of external tools, and any retry that could repeat a non-idempotent action.
- **Deferred with named triggers:** host allow-list matching (when the first adapter routes/verifies
  domains); per-adapter health isolation and run orchestration (when adapters exist); response-size caps,
  timeouts, and challenge-page detection (when a fetcher is authorized); RSS parsing (when a permitted feed
  exists); probe-style external-tool health checks (never, unless a CLI dependency is ever justified);
  directory-permission and symlink-safe writes (Phase 2 security work).

## Honest limitations of the implemented validation

`career_agent/urls.py` inspects the literal host only. It performs no DNS resolution and follows no
redirects, so it must not be described as SSRF protection: a hostname can resolve to a private address
(DNS rebinding) and a redirect can lead anywhere. Any future fetcher must resolve-then-connect
consistently, re-validate every redirect hop, and apply its own size/time limits before such a claim is
made. This limitation is stated in the module docstring, in `memory.md`, and in the tests.

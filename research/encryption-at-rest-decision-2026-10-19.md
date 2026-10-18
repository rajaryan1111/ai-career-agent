# Encryption at Rest — Options and Decision

**Date:** 2026-10-19  
**Status:** Decision deferred; no encryption is implemented in this build  
**Related:** [local alpha checklist](local-alpha-manual-smoke-test-checklist-2026-10-14.md), [architecture](../architecture.md)

## What exists today

- One SQLite database in the per-user application-data directory, plus user-triggered JSON backups.
- POSIX mode `0600` is enforced when the store opens, including databases created earlier with a permissive umask.
- No network access, no cloud sync, no external AI API, and no credentials stored in the database.
- Exports and backups are plain JSON and the UI warns that they may contain personal data.
- No key management, password, or recovery flow exists.

This means the current protection is operating-system file permissions and whole-disk encryption if the user has enabled it. A local process running as the same user, an administrator, or anyone with the unlocked device can read the database.

## Threat model

Assets: candidate identity and contact details, work authorization, education, employment history, application notes and evidence, and the list of employers applied to.

Plausible threats, in order of likelihood for a local-first desktop app:

1. **Another local user or a shared machine** — mitigated by `0600` and OS accounts; a copied database file defeats it.
2. **Lost or stolen device** — mitigated only if the OS volume is encrypted; the app cannot assume that.
3. **Backup or sync exposure** — a JSON export copied into a cloud folder or attached to a support request is readable. Backups are the weakest link because they leave the protected directory.
4. **Same-user malware or a malicious process** — encryption at rest does not help once the app can decrypt; only process isolation or user presence checks would.
5. **Disk forensics after deletion** — SQLite can leave freed pages; `VACUUM` or `secure_delete` reduces but does not eliminate remnants on flash storage.

Encryption at rest mainly addresses threats 1–3 and does nothing for 4–5.

## Options

### A. Rely on OS full-disk encryption, keep the database plaintext

- **How:** document the requirement, keep `0600`, keep the UI warning on export, and add a startup hint in diagnostics when the volume is unencrypted (not reliably detectable cross-platform; would be advisory at best).
- **Pros:** no key management, no recovery failure mode, no dependencies, search and debugging stay simple, SQLite tooling keeps working.
- **Cons:** a copied file, a synced backup, or an unencrypted volume exposes everything.
- **Effort:** documentation only.

### B. Application-level encryption with an OS keychain-held key

- **How:** encrypt the database or its sensitive columns with an authenticated cipher (for example AES-256-GCM) and store the key in the macOS Keychain, Windows Credential Manager, or Secret Service. Requires a platform dependency or per-OS code paths.
- **Pros:** copied files and synced backups are unreadable without the keychain entry; no password prompt.
- **Cons:** any process running as the user can usually read the keychain item, so threat 4 is unchanged; the key does not travel with a backup, so restoring on another machine silently loses access unless an export path is designed; keychain behavior differs per OS and is hard to test in CI.
- **Effort:** medium to high, plus per-platform testing that this project does not currently have.

### C. Password-derived key (Argon2id or PBKDF2) with authenticated encryption

- **How:** derive a key from a user passphrase using a memory-hard KDF from `cryptography`, encrypt records or the whole database, and require the passphrase at startup.
- **Pros:** portable, no platform dependency, backups can be encrypted with the same passphrase, and it protects against a copied file plus an offline attacker who lacks the passphrase.
- **Cons:** introduces the first runtime dependency; forgotten passphrases mean permanent data loss unless a recovery key is designed; every background or scheduled action would need the key; migration of existing plaintext databases needs a careful, reversible path; searchable fields must be decrypted in memory.
- **Effort:** high, and it changes the product's recovery story.

### D. SQLCipher (encrypted SQLite page layer)

- **How:** replace the standard library `sqlite3` connection with a SQLCipher-enabled build.
- **Pros:** less application code, page-level encryption, existing SQL mostly unchanged.
- **Cons:** the standard library does not ship SQLCipher; users would need a native build, which conflicts with the zero-dependency install; CI and packaging become substantially harder.
- **Effort:** high and operationally fragile for a desktop alpha with no installer pipeline.

## Decision

**No encryption is added in this release.** The project keeps plaintext SQLite with `0600`, documents the limitation, and does not pretend that file permissions equal encryption.

Reasons:

1. Options B–D each require a key-recovery decision the product owner has not made. Choosing one silently would create a real risk of permanent data loss for existing users.
2. There is no installer or signed-release pipeline yet, so per-platform keychain behavior cannot be verified on the operating systems the app would claim.
3. Backups are the most likely leak path, and encrypting only the database would give a false sense of safety while exports stay plaintext.
4. The local alpha has no network access and stores no credentials, so the marginal benefit is smaller than the recovery risk at this stage.

## What would change this decision

- A product decision on whether a forgotten passphrase may mean unrecoverable data, or whether a printed recovery key is acceptable.
- An installer and signing pipeline that allows keychain integration to be tested on macOS, Windows, and Linux.
- A requirement to store API credentials or email tokens locally, which would make secret storage mandatory rather than optional.
- Evidence that users routinely sync backups to cloud storage.

## Interim mitigations (already implemented or documented)

- `0600` on the database, enforced at open, including for older files.
- No network access and no third-party transmission of candidate data.
- Export and restore warnings that backups may contain personal data.
- `--diagnostics` reports paths and schema state without printing record contents.
- README troubleshooting tells users not to attach databases or resumes to support requests.

## Next action

Treat encryption as an open decision, not a missing bug. If the user chooses option C, the implementation must include: a versioned encrypted format, an explicit migration with a plaintext backup retained until the encrypted write is verified, Argon2id parameters recorded with the file, a documented recovery-key option, and tests for wrong passphrase, truncated file, downgrade attempts, and restore compatibility.

# Changelog

## 0.1.0 — 2026-10-23 (first build)
- MIME rendering: text-only, multipart/alternative (text + HTML),
  multipart/mixed with text attachments (base64, 76-column wrap).
- SMTP client: greeting, EHLO/HELO, MAIL FROM, RCPT TO (To/Cc/Bcc
  envelope), DATA with dot-stuffing, QUIT; multiline reply parsing.
- AUTH LOGIN support (`mail_send_auth`).
- Validation: syntactic addresses, CR/LF injection rejection, MIME
  boundary collision checks — all as recoverable errors.
- Tests: 52 unit assertions + 19 live SMTP checks against a local fake
  server (plain send, AUTH success/failure, dot-stuffing, no-server
  failure). All green on finc 0.4.0 (contract 3).

### Known limitations (v0.1.0)
- No TLS (plaintext SMTP only — localhost / trusted LAN).
- No DNS (dotted-quad hosts only).
- Text attachments only (std base64 is strlen-based).
- No Date / Message-ID generation; no DKIM, STARTTLS, SMTPUTF8.

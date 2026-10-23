# fin-mail

SMTP client library + MIME message builder for Fin (v0.1.0).

Build a message (plain text, HTML, attachments), render it to RFC 5322 /
MIME text, and send it through any plain SMTP server — all with explicit
error values instead of aborts on server failures.

```fin
import { mail_new, mail_set_from, mail_add_to, mail_set_subject,
         mail_set_text, mail_send, mail_free } from mail::fin;

let m <&MailMessage> = mail_new();
mail_set_from(m, "sender@example.com");
mail_add_to(m, "rcpt@example.com");
mail_set_subject(m, "Hello");
mail_set_text(m, "Hello from Fin.");
let res <MailResult> = mail_send("127.0.0.1", 25, m);
if (res.ok) {
    printf("sent!\n");
} else {
    printf("failed: %s\n", res.err);
}
mail_free(m);
```

## What it does

- **MIME rendering** (`mail_render`): text-only, `multipart/alternative`
  (text + HTML), and `multipart/mixed` (attachments, nesting the
  alternative block when HTML is present). CRLF line endings, `8bit`
  text parts (UTF-8), base64 attachments wrapped at 76 columns.
- **SMTP send** (`mail_send`): greeting, EHLO with HELO fallback,
  `MAIL FROM`, `RCPT TO` (To + Cc + Bcc envelope), `DATA` with
  dot-stuffing, `QUIT`. Multiline replies (code + `-` continuations)
  are consumed correctly.
- **AUTH LOGIN** (`mail_send_auth`): username/password exchange after
  EHLO. Credentials are base64 — see the security note below.
- **Validation**: syntactic address checks, CR/LF header-injection
  rejection (subject, addresses, filenames), MIME-boundary collision
  checks. Failures are `ok=false` + message, never aborts.

## API

| Function | Description |
|---|---|
| `mail_new()` / `mail_free(m)` | Create / free a message (setters clone inputs) |
| `mail_set_from(m, addr)` | Set the From address |
| `mail_add_to/cc/bcc(m, addr)` | Add recipients (Bcc is envelope-only: no Bcc header is ever rendered) |
| `mail_set_subject/text/html(m, s)` | Set subject / plain-text / HTML bodies |
| `mail_attach(m, filename, type, text)` | Add a **text** attachment |
| `mail_valid_address(addr) <bool>` | Syntactic address check |
| `mail_render(m) <MailRender>` | Render to full MIME text; `mail_free_render` frees it |
| `mail_send(host, port, m) <MailResult>` | Send, no auth; `mail_free_result` frees errors |
| `mail_send_auth(host, port, user, pass, m)` | Send with AUTH LOGIN |
| `mail_version() <string>` | `"0.1.0"` (heap string, free with `free_str`) |

## Security and limits (read before using)

- **No TLS in v0.1.0.** Use against localhost test sinks and trusted LAN
  relays only. AUTH LOGIN over a public network would expose credentials
  (base64 is not encryption). TLS support is the top item on the roadmap.
- **No DNS.** Hosts must be dotted quads (`127.0.0.1`, not `localhost`)
  — same as std `networking` and zhttp.
- **Text attachments only.** Std `base64_encode` is strlen-based and
  cannot encode binary data; binary attachments need a byte-safe base64
  path (roadmap).
- **No Date / Message-ID headers.** The submitting server adds them.
- **No DKIM / signing, no STARTTLS, no SMTPUTF8, no pipelining.**
- Address validation is syntactic only — it cannot prove an address
  is deliverable.

## Building and testing

Requires `finc` 0.4.0 (build it from [M1778/Fin](https://github.com/M1778/Fin)).

```sh
finc -I src src/mail.fin                                # type-check the library
finc -I src tests/test_mail.fin -o test_mail && ./test_mail   # unit tests
python3 tests/live_smtp.py                             # live SMTP verification
sh tests/run_tests.sh                                  # both
```

The live tests run a stdlib-only fake SMTP server on localhost
(`tests/smtp_sink.py`) and verify: multiline greeting/EHLO handling,
envelope recipients including Bcc, dot-stuffing on the wire, attachment
delivery, AUTH LOGIN success and failure, and clean failure with no
server running. No real mail is ever sent.

## Examples

- `examples/basic.fin` — render a text + HTML + attachment message, print it.
- `examples/send_local.fin` — send to a local sink on `127.0.0.1:11025`.
- `examples/send_local_auth.fin` — AUTH LOGIN against a local sink on
  `127.0.0.1:11026` (test-only credentials, localhost only).

## License

MIT — see `LICENSE`.

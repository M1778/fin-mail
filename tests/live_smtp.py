#!/usr/bin/env python3
"""Live SMTP verification driver for fin-mail (stdlib only).

Builds the Fin send examples, runs each against a fresh local sink
(tests/smtp_sink.py), and asserts on the recorded transcript + DATA.
No real mail, no real credentials, localhost only.

Usage (from the fin-mail repo root):
  python3 tests/live_smtp.py
Exit 0 + "LIVE OK" when every check passes.
"""
import json
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# finc location: $FINC, else `finc` on PATH, else this sandbox's binary.
import shutil
FINC = os.environ.get("FINC") or shutil.which("finc") or os.path.expanduser(
    "~/workspace/fin-dev/tester-1/Fin/build/finc")
BIN = "/tmp/fin-mail-live"
CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))


def port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_ready(path, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(path):
            return True
        time.sleep(0.1)
    return False


def build(src, out):
    r = subprocess.run(
        [FINC, "-I", "src", src, "-o", out],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"build failed for {src}:\n{r.stdout}\n{r.stderr}"


def run_sink_and_client(port, out_json, client_bin, auth=None):
    for stale in (out_json, out_json + ".ready"):
        try:
            os.unlink(stale)
        except FileNotFoundError:
            pass
    cmd = [sys.executable, "tests/smtp_sink.py", "--port", str(port), "--out", out_json]
    if auth:
        cmd += ["--auth-user", auth[0], "--auth-pass", auth[1]]
    sink = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert wait_ready(out_json + ".ready"), f"sink did not become ready for {port}"
        client = subprocess.run([client_bin], capture_output=True, text=True, timeout=30)
        sink.wait(timeout=15)
    finally:
        if sink.poll() is None:
            sink.kill()
    with open(out_json) as fh:
        return client.stdout.strip(), json.load(fh)


def main():
    os.makedirs(BIN, exist_ok=True)
    check("port 59997 free (unit-test refusal target)", port_free(59997))
    check("port 11025 free", port_free(11025))
    check("port 11026 free", port_free(11026))

    build("examples/send_local.fin", f"{BIN}/send_local")
    build("examples/send_local_auth.fin", f"{BIN}/send_auth")
    build("examples/basic.fin", f"{BIN}/basic")
    r = subprocess.run([f"{BIN}/basic"], capture_output=True, text=True, timeout=30)
    check("basic example renders MIME", "multipart/mixed" in r.stdout and "SGVsbG8sIGF0dGFjaG1lbnQh" in r.stdout)

    # 1. Plain send: multiline greeting/EHLO, envelope, dot-stuffing.
    out, rec = run_sink_and_client(11025, f"{BIN}/sink.json", f"{BIN}/send_local")
    check("plain: client reports SEND OK", out.startswith("SEND OK"), out)
    check("plain: MAIL FROM recorded", rec["mail_from"] == "<sender@example.com>", str(rec["mail_from"]))
    check("plain: all envelope rcpts incl Bcc", rec["rcpts"] == ["<rcpt@example.com>", "<cc@example.com>", "<hidden@example.com>"], str(rec["rcpts"]))
    check("plain: DATA has To/Cc headers, no Bcc header",
          "To: rcpt@example.com" in rec["data"] and "Cc: cc@example.com" in rec["data"] and "Bcc:" not in rec["data"])
    check("plain: dot-stuffed line on the wire", "..dotline should arrive dot-stuffed." in rec["data_raw"])
    check("plain: unstuffed body recovers original", ".dotline should arrive dot-stuffed." in rec["data"])
    check("plain: attachment base64 in DATA", "SGVsbG8sIGF0dGFjaG1lbnQh" in rec["data"])
    check("plain: multiline greeting+EHLO consumed", any(c.startswith("EHLO") for c in rec["commands"]) and any(c == "DATA" for c in rec["commands"]))

    # 2. AUTH LOGIN success.
    out, rec = run_sink_and_client(11026, f"{BIN}/sink_auth.json", f"{BIN}/send_auth", auth=("user", "pass"))
    check("auth: client reports SEND OK", out.startswith("SEND OK"), out)
    check("auth: username decoded by sink", rec["auth_user"] == "user", str(rec["auth_user"]))
    check("auth: sink accepted credentials", rec["auth_ok"] is True)
    check("auth: message arrived", "Authenticated hello." in rec["data"])

    # 3. AUTH LOGIN failure (wrong expected password on the sink side).
    out, rec = run_sink_and_client(11026, f"{BIN}/sink_auth_bad.json", f"{BIN}/send_auth", auth=("user", "wrong"))
    check("auth-fail: client reports SEND FAIL", out.startswith("SEND FAIL"), out)
    check("auth-fail: sink rejected credentials", rec["auth_ok"] is False)

    # 4. No server at all.
    client = subprocess.run([f"{BIN}/send_local"], capture_output=True, text=True, timeout=30)
    check("noserver: client reports SEND FAIL, does not crash", client.stdout.startswith("SEND FAIL"), client.stdout.strip())

    failed = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} live checks passed")
    if failed:
        print("LIVE FAILED")
        return 1
    print("LIVE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Minimal fake SMTP server for fin-mail live tests (stdlib only).

Speaks just enough SMTP to verify a Fin client end to end: multiline
greeting + EHLO (exercises continuation-line parsing), MAIL/RCPT/DATA,
optional AUTH LOGIN, QUIT. Records the transcript and the raw DATA
block to a JSON file, then exits after one complete message (or after
QUIT with no message).

Usage:
  python3 smtp_sink.py --port 11025 --out /tmp/sink.json
  python3 smtp_sink.py --port 11026 --out /tmp/sink_auth.json \
      --auth-user user --auth-pass pass
"""
import argparse
import base64
import json
import socket
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--auth-user", default=None)
    ap.add_argument("--auth-pass", default=None)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(5)
    srv.settimeout(30)
    with open(args.out + ".ready", "w") as rf:
        rf.write("ready")
    transcript = []
    mail_from = None
    rcpts = []
    data_lines = []
    auth_user = None
    auth_ok = None
    done = False
    while not done:
        conn, _ = srv.accept()
        conn.settimeout(30)
        f = conn.makefile("rwb", buffering=0)

        def send(line):
            f.write(line.encode() + b"\r\n")

        def read_line():
            raw = f.readline()
            if not raw:
                return None
            return raw.decode("utf-8", "replace").rstrip("\r\n")

        # Multiline greeting on purpose: continuation parsing must cope.
        send("220-sink ready")
        send("220 hello")
        try:
            while True:
                line = read_line()
                if line is None:
                    break
                transcript.append(line)
                upper = line.upper()
                if upper.startswith("EHLO") or upper.startswith("HELO"):
                    # Multiline EHLO reply on purpose.
                    send("250-sink")
                    send("250 AUTH LOGIN")
                elif upper.startswith("AUTH LOGIN"):
                    send("334 VXNlcm5hbWU6")
                    u = read_line()
                    transcript.append("<<user-response>>")
                    send("334 UGFzc3dvcmQ6")
                    p = read_line()
                    transcript.append("<<pass-response>>")
                    try:
                        auth_user = base64.b64decode(u).decode()
                        pw = base64.b64decode(p).decode()
                    except Exception:
                        auth_user, pw = None, None
                    auth_ok = (
                        auth_user == args.auth_user and pw == args.auth_pass
                    )
                    send("235 ok" if auth_ok else "535 bad credentials")
                elif upper.startswith("MAIL FROM:"):
                    mail_from = line.split(":", 1)[1].strip()
                    send("250 ok")
                elif upper.startswith("RCPT TO:"):
                    rcpts.append(line.split(":", 1)[1].strip())
                    send("250 ok")
                elif upper == "DATA":
                    send("354 end with <CR><LF>.<CR><LF>")
                    while True:
                        dl = read_line()
                        if dl is None or dl == ".":
                            break
                        data_lines.append(dl)
                    send("250 queued")
                elif upper == "QUIT":
                    send("221 bye")
                    done = True
                    break
                elif upper == "RSET":
                    send("250 ok")
                else:
                    send("502 unknown command")
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if transcript:
            # A real session happened (even without QUIT); stop here.
            done = True
    srv.close()

    # Unstuff for assertion convenience (raw lines kept too).
    unstuffed = [l[1:] if l.startswith("..") else l for l in data_lines]
    with open(args.out, "w") as fh:
        json.dump(
            {
                "commands": transcript,
                "mail_from": mail_from,
                "rcpts": rcpts,
                "data_raw": "\r\n".join(data_lines),
                "data": "\r\n".join(unstuffed),
                "auth_user": auth_user,
                "auth_ok": auth_ok,
            },
            fh,
            indent=2,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

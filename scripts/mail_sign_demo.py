"""The signing pages on this machine, with nothing real behind them — to click through in a browser.

    state/mail-send/venv/bin/python scripts/mail_sign_demo.py [port] [auto] [paused]

With `auto` the service runs as it does with SIGN_AUTO=1, the first day already done: what is placed
goes out by itself, and the outbox carries the pause. With `paused` as well it starts paused, the
three drafts waiting: the page says that resuming sends them, and pressing the button does.

What stands up: the made-up world the tests use (`tests/test_mail_send_signer.py`) — a lab
`lab:testonly` whose ledger, three old letters and working key k2 sit on a drop on 127.0.0.1; a
draft store in memory; an empty vault — and the signing service in front of it, with its background
thread running as it will when hosted. A few drafts are placed the way a model would place them.

Nothing here reaches the federation's drop, a bucket or a secret: the keys are the public test
values, and everything is gone when the process ends.

The passcode is made at start and written to the file named on the line `passcode file:`. The
recovery key's part — signing the two records — is done on the command line as it will be on the
day; the line `sign with:` says how, for this made-up key.
"""

from __future__ import annotations

import secrets
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

from mail_send import sign_app  # noqa: E402
from tests.test_mail_send_signer import DOOR, FAST, FAST_OPEN, LAB, PUB2, SEED1, TO, TOKEN, World  # noqa: E402

LETTER = ("# 시험 편지\n\n승인 화면이 글자 그대로 보이는지 보는 편지입니다.\n\n"
          "<script>alert(1)</script> <b>굵게</b> [링크](https://example.com)\n"
          "방향을 바꾸는 글자: ‮gnp.exe 그리고 폭이 없는 ​글자.\n")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8792
    auto = "auto" in sys.argv[2:]
    tmp = Path(tempfile.mkdtemp(prefix="lxm-sign-demo-"))
    world = World(tmp)
    if auto:
        world.key_in()                              # the first day, done: the key is in and the old one out
        if "paused" in sys.argv[2:]:
            world.sstore.set_switch("auto", "off", world.clock())
    for body in ("첫 초안입니다.\n\n짧은 편지.\n", LETTER, "거절해 볼 초안.\n"):
        world.draft(body)
    passcode = secrets.token_urlsafe(24)
    (tmp / "passcode.txt").write_text(passcode + "\n")
    (tmp / "k1.seed").write_text(SEED1.hex() + "\n")
    print(f"passcode file: {tmp / 'passcode.txt'}", flush=True)
    print(f"sign with:     organum-hub sign --key {tmp / 'k1.seed'} --envelope <the downloaded file>", flush=True)
    print(f"open:          http://localhost:{port}/login", flush=True)
    env = {"SIGN_PASSCODE": passcode, "SIGN_SENDER": LAB, "SIGN_RECIPIENTS": f"{TO}=1", "SIGN_DOOR": DOOR,
           "SIGN_DROP_URL": world.url, "SIGN_DROP_TOKEN": TOKEN, "SIGN_TRUSTED_PUBKEYS": PUB2,
           "SIGN_RETIRE_KEY_ID": "k2", "SIGN_RECEIVED_ONLY": "1", "SIGN_AUTO": "1" if auto else "0"}
    account = world.bucket.account("signer", read=("send/",),
                                   create=("send/decisions/", "send/results/", "send/signer-log/"))
    app = sign_app.create_app(env=env, clock=world.clock, bucket=account, vault=world.vault, home=tmp / "home",
                              background=True, send_opts=FAST, open_opts=FAST_OPEN)
    app.state.world = world
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

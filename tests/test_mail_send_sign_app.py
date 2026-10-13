"""The signing pages are where a person stands between a draft and a signature, so they are pinned.

`test_mail_send_signer.py` pins what the service does with the ledger and the key. Here is the web in
front of it, driven as a browser would, against the same made-up world (a lab's ledger restored from
a drop on 127.0.0.1, a draft store that can only create, an empty vault):

  - no page and no button without a session; a session only from the passcode, written down first,
    paused after five wrong ones; it outlives a restart and dies with the passcode;
  - a button needs the session's own token and a request from our own pages;
  - the first day, through the pages: open, make the key, carry the two records out, bring them back
    signed, see them on the door;
  - a letter is shown as the bytes that arrived — nothing rendered, the unseen made visible — and
    approving it signs exactly that;
  - what the pages say never includes the key, and what the log says never includes the letter.

These tests need organum 0.10.0; the environment the drop's own tests run in has 0.8.0, where they
are skipped.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading

import pytest

hdr = pytest.importorskip("organum.hub_draft")

from organum import schnorr_pure as sp  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from mail_send import sign_app  # noqa: E402
from tests.test_mail_send_signer import (DOOR, FAST, FAST_OPEN, LAB, PUB2, SEED1, SEED2, TO, TOKEN,  # noqa: E402
                                         World)

PASS = "a passcode for the signing pages"
BASE = "https://sign.test"
CAN_CREATE = ("send/decisions/", "send/results/", "send/signer-log/")


async def _no_sleep(_seconds):
    return None


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.down()


def _app(world, create=CAN_CREATE, **env):
    world.boots += 1
    env = {"SIGN_PASSCODE": PASS, "SIGN_PUBLIC_URL": BASE, "SIGN_SENDER": LAB, "SIGN_RECIPIENTS": f"{TO}=1",
           "SIGN_DOOR": DOOR, "SIGN_DROP_URL": world.url, "SIGN_DROP_TOKEN": TOKEN, "SIGN_TRUSTED_PUBKEYS": PUB2,
           "SIGN_RETIRE_KEY_ID": "k2", "SIGN_RECEIVED_ONLY": "1"} | env
    app = sign_app.create_app(env=env, clock=world.clock, sleep=_no_sleep, vault=world.vault,
                              bucket=world.bucket.account("signer", read=("send/",), create=create),
                              home=world.tmp / f"web{world.boots}", background=False,
                              send_opts=FAST, open_opts=FAST_OPEN)
    return app, TestClient(app, base_url=BASE, follow_redirects=False)


def _signin(client) -> None:
    r = client.post("/login", data={"passcode": PASS})
    assert r.status_code == 303 and r.headers["location"] == "/outbox", r.text


def _token(client, path: str = "/key") -> str:
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).text).group(1)


def _post(client, path: str, **fields):
    return client.post(path, data={"csrf": _token(client), **fields})


def _sign_output(raw: bytes, seed: bytes = SEED1) -> str:
    """What `organum-hub sign` prints."""
    return json.dumps({"envelope_sha256": hashlib.sha256(raw).hexdigest(),
                       "sig": sp.sign(hashlib.sha256(raw).digest(), seed).hex(), "pubkey": sp.public_key(seed).hex()})


def _first_day(world):
    """Signed in, ledger open, key made, both records brought in."""
    app, client = _app(world)
    _signin(client)
    app.state.signer.step()
    assert _post(client, "/key/make").status_code == 303
    rotate, revoke = client.get("/key/rotate.json").content, client.get("/key/revoke.json").content
    r = _post(client, "/key/admit", rotate_envelope=rotate.decode(), rotate_signature=_sign_output(rotate),
              revoke_envelope=revoke.decode(), revoke_signature=_sign_output(revoke))
    assert r.status_code == 200, r.text
    return app, client


# ── starting ─────────────────────────────────────────────────────────────────

def test_it_does_not_start_on_a_setting_that_is_wrong(world):
    for wrong in ({"SIGN_PASSCODE": "short"}, {"SIGN_SENDER": "jdot-hq"}, {"SIGN_RECIPIENTS": "lab:x"},
                  {"SIGN_DOOR": "hub-ops"}, {"SIGN_DOOR": "hub-ops/jdot-hq"}, {"SIGN_TRUSTED_PUBKEYS": "abc"},
                  {"SIGN_TRUSTED_PUBKEYS": ""}, {"SIGN_DROP_URL": ""}, {"SIGN_DROP_URL": "http://drop.example"},
                  {"SIGN_RETIRE_KEY_ID": "k3"}, {"SIGN_RECOVERY_KEY_ID": "k3"}, {"SIGN_KEY_EPOCH": "0"}):
        with pytest.raises(SystemExit) as e:
            _app(world, **wrong)
        assert "refusing to start" in str(e.value)
        assert PASS not in str(e.value) and TOKEN not in str(e.value)


def test_without_an_account_or_a_vault_it_does_not_start(world):
    env = {"SIGN_PASSCODE": PASS, "SIGN_SENDER": LAB, "SIGN_RECIPIENTS": f"{TO}=1", "SIGN_DOOR": DOOR,
           "SIGN_DROP_URL": world.url, "SIGN_DROP_TOKEN": TOKEN, "SIGN_TRUSTED_PUBKEYS": PUB2}
    for more, named in (({}, "GCS_SA_KEY_JSON"),
                        ({"GCS_SA_KEY_JSON": '{"not": "a key SECRETMARK"}'}, "SIGN_BUCKET"),
                        ({"GCS_SA_KEY_JSON": '{"not": "a key SECRETMARK"}', "SIGN_BUCKET": "b"}, "GCS_SA_KEY_JSON"),
                        ):
        with pytest.raises(SystemExit) as e:
            sign_app.create_app(env=env | more, background=False)
        assert named in str(e.value) and "SECRETMARK" not in str(e.value)


def test_the_status_is_public_and_says_nothing_to_guess_with(world):
    app, client = _first_day(world)
    told = TestClient(app, base_url=BASE).get("/").json()
    assert told["service"] == "lxm-mail-sign" and told["ledger"] == "open" and told["key_id"] == "k3"
    assert told["pubkey"] == sp.public_key(world.vault.get()).hex()         # the public half is public
    text = json.dumps(told)
    assert TOKEN not in text and world.vault.get().hex() not in text and PASS not in text


# ── who is asking ────────────────────────────────────────────────────────────

def test_no_page_and_no_button_without_a_session(world):
    app, client = _app(world)
    did = world.draft("not for strangers\n")
    for path in ("/outbox", "/key", f"/draft/{did}", "/key/rotate.json"):
        r = client.get(path)
        assert (r.status_code, r.headers["location"]) == (303, "/login"), path
    for path in (f"/draft/{did}/approve", f"/draft/{did}/reject", "/reject-all", "/key/make", "/key/admit",
                 "/ledger/reopen", "/logout"):
        r = client.post(path, data={"csrf": "x", "confirm": "yes", "body_sha256": "0" * 64})
        assert r.status_code == 401, path
    assert world.sstore.get(did)["decision"] is None and world.vault.get() is None
    assert app.state.signer.ledger["state"] == "closed"


def test_a_sign_in_is_the_passcode_and_is_written_down_first(world):
    app, client = _app(world)
    r = client.post("/login", data={"passcode": "not the passcode, however long"})
    assert r.status_code == 403 and "not the passcode" in r.text and "set-cookie" not in r.headers
    r = client.post("/login", data={"passcode": PASS})
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("__Host-sign=") and "Path=/" in cookie and "Domain" not in cookie
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=3600"):
        assert flag.lower() in cookie.lower(), flag
    logins = [n for n in world.bucket.objects if n.startswith("send/signer-log/") and n.endswith("-login.json")]
    assert len(logins) == 1
    entry = json.loads(world.bucket.objects[logins[0]][0])
    assert entry["kind"] == "login" and entry["sender"] == LAB and PASS not in json.dumps(entry)
    assert client.get("/outbox").status_code == 200


def test_a_sign_in_that_cannot_be_written_down_is_not_made(world):
    app, client = _app(world, create=("send/decisions/", "send/results/"))
    r = client.post("/login", data={"passcode": PASS})
    assert r.status_code == 503 and "set-cookie" not in r.headers and "could not be recorded" in r.text
    assert client.get("/outbox").status_code == 303


def test_five_wrong_passcodes_pause_sign_ins_for_everyone(world):
    app, client = _app(world)
    for _ in range(5):
        assert client.post("/login", data={"passcode": "wrong " * 6}).status_code == 403
    r = client.post("/login", data={"passcode": PASS})                  # the right one is not looked at either
    assert r.status_code == 429 and "paused" in r.text and "set-cookie" not in r.headers
    world.clock.t += 901
    assert client.post("/login", data={"passcode": PASS}).status_code == 303


def test_a_session_outlives_a_restart_ends_after_an_hour_and_dies_with_the_passcode(world):
    app, client = _app(world)
    _signin(client)
    cookie = client.cookies.get("__Host-sign")
    again_app, again = _app(world)                                      # the server slept and woke
    again.cookies.set("__Host-sign", cookie)
    assert again.get("/outbox").status_code == 200
    other_app, other = _app(world, SIGN_PASSCODE="another passcode, just as long")
    other.cookies.set("__Host-sign", cookie)
    assert other.get("/outbox").status_code == 303
    world.clock.t += 3601
    assert again.get("/outbox").status_code == 303


def test_a_button_needs_this_sessions_token_and_our_own_origin(world):
    app, client = _first_day(world)
    did = world.draft("pressed from somewhere else\n")
    sha = app.state.signer.review(did)["body_sha256"]
    token = _token(client)
    assert client.post(f"/draft/{did}/approve", data={"body_sha256": sha}).status_code == 403
    assert client.post(f"/draft/{did}/approve", data={"body_sha256": sha, "csrf": "made.up"}).status_code == 403
    other_app, other = _app(world)                                      # another session's token
    _signin(other)
    assert client.post(f"/draft/{did}/approve",
                       data={"body_sha256": sha, "csrf": _token(other)}).status_code == 403
    for elsewhere in ("https://evil.example", "null", BASE + ".evil.example", "http://sign.test"):
        r = client.post(f"/draft/{did}/approve", data={"body_sha256": sha, "csrf": token},
                        headers={"Origin": elsewhere})
        assert r.status_code == 403, elsewhere
    assert world.sstore.get(did)["decision"] is None
    r = client.post(f"/draft/{did}/approve", data={"body_sha256": sha, "csrf": token}, headers={"Origin": BASE})
    assert r.status_code == 303 and world.sstore.get(did)["decision"]["decision"] == "approved"


def test_signing_out_ends_the_session(world):
    app, client = _app(world)
    _signin(client)
    r = _post(client, "/logout")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert client.get("/outbox").status_code == 303


# ── the first day ────────────────────────────────────────────────────────────

def test_the_first_day_through_the_pages(world):
    app, client = _app(world)
    _signin(client)
    page = client.get("/outbox").text
    assert "The ledger is opening" in page and 'http-equiv="refresh"' in page
    app.state.signer.step()                                             # what the background thread does at boot
    page = client.get("/key").text
    assert "restored from generation" in page and "Make the key k3" in page and "rotate-k3.json" not in page
    assert "Nothing can be approved yet: no key has been made" in client.get("/outbox").text
    assert _post(client, "/key/make").status_code == 303
    pub = sp.public_key(world.vault.get()).hex()
    page = client.get("/key").text
    assert pub in page and "rotate-k3.json" in page and "revoke-k2.json" in page and "Make the key" not in page
    assert world.vault.get().hex() not in page

    r = client.get("/key/rotate.json")
    assert r.headers["content-disposition"] == 'attachment; filename="rotate-k3.json"'
    rotate = r.content
    assert json.loads(rotate)["payload"] == {"new_key_id": "k3", "new_key_epoch": 1, "new_pubkey": pub}
    revoke = client.get("/key/revoke.json").content
    assert json.loads(revoke)["payload"]["key_id"] == "k2"

    r = _post(client, "/key/admit", rotate_envelope=rotate.decode(), rotate_signature=_sign_output(rotate, SEED2),
              revoke_envelope=revoke.decode(), revoke_signature=_sign_output(revoke))
    assert r.status_code == 409 and "not the recovery key" in r.text and "Nothing was changed" in r.text
    assert world.door() == ["001", "002", "003"]

    r = _post(client, "/key/admit", rotate_envelope=rotate.decode(), rotate_signature=_sign_output(rotate),
              revoke_envelope=revoke.decode(), revoke_signature=_sign_output(revoke))
    assert r.status_code == 200 and "letter 004" in r.text and "letter 005" in r.text and "on the door" in r.text
    assert world.door() == ["001", "002", "003", "004", "005"]
    page = client.get("/key").text
    assert "The key is in place" in page and "takes the sender's key records from k1 alone" in page
    assert page.count("revoked") == 1 and "Take the signed record" not in page
    kinds = sorted(n.rsplit("-", 1)[1] for n in world.bucket.objects if n.startswith("send/signer-log/"))
    assert kinds == ["key.json", "lifecycle.json", "login.json"]


def test_the_signature_may_be_pasted_bare_and_one_record_at_a_time(world):
    app, client = _app(world)
    _signin(client)
    app.state.signer.step()
    _post(client, "/key/make")
    rotate = client.get("/key/rotate.json").content
    bare = sp.sign(hashlib.sha256(rotate).digest(), SEED1).hex()
    r = _post(client, "/key/admit", rotate_envelope=rotate.decode(), rotate_signature=f"  {bare}\n")
    assert r.status_code == 200 and "letter 004" in r.text and "They are on the door" in r.text
    assert world.door()[-1] == "004"                                    # the new key does not wait for the other record
    page = client.get("/key").text
    assert "revoke-k2.json" in page and "rotate-k3.json" not in page and "k2 is to be revoked first" not in page
    assert "Nothing can be approved yet: k2 is to be revoked first" in client.get("/outbox").text
    r = _post(client, "/key/admit", revoke_envelope="", revoke_signature="")
    assert r.status_code == 409 and "no record was given" in r.text


def test_opening_again_is_a_button_and_clears_the_local_copy(world):
    app, client = _first_day(world)
    signer = app.state.signer
    marker = signer.hub / "left-behind"
    marker.write_text("x")
    assert _post(client, "/ledger/reopen").status_code == 303
    assert signer.ledger["state"] == "open" and not marker.exists()
    assert signer.ledger["report"]["restored"] is True and signer.view()["key"]["ready"]


# ── a letter ─────────────────────────────────────────────────────────────────

LETTER = ("\n# 제목처럼 보이는 줄\n\n<script>alert(1)</script> <b>굵게</b> [링크](https://example.com)\n"
          "방향을 바꾸는 글자: ‮gnp.exe 그리고 폭이 없는 ​글자.\n\t탭과 & 앰퍼샌드 \"따옴표\"\n")


def test_a_letter_is_shown_as_the_bytes_that_arrived_and_signed_as_shown(world):
    app, client = _first_day(world)
    did = world.draft(LETTER)
    assert f'href="/draft/{did}"' in client.get("/outbox").text
    r = client.get(f"/draft/{did}")
    page = r.text
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert r.headers["cache-control"] == "no-store" and r.headers["x-frame-options"] == "DENY"
    assert "<script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt; &lt;b&gt;굵게&lt;/b&gt;" in page
    assert "[링크](https://example.com)" in page and "<a href=\"https://example.com\"" not in page
    assert "⟦U+202E⟧gnp.exe" in page and "⟦U+200B⟧글자" in page and "‮" not in page and "​" not in page
    assert "2 character(s) in this text cannot be seen" in page and "RIGHT-TO-LEFT OVERRIDE" in page
    assert f"<strong>{TO} / R</strong>" in page and hashlib.sha256(LETTER.encode()).hexdigest() in page
    # the text between the tags is the letter, to the byte, once a browser has dropped the newline after <pre>
    inside = re.search(r'<pre class="letter">\n(.*?)</pre>', page, re.S).group(1)
    shown = inside.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    assert shown == LETTER.replace("‮", "⟦U+202E⟧").replace("​", "⟦U+200B⟧")
    sha = re.search(r'name="body_sha256" value="([0-9a-f]{64})"', page).group(1)
    assert f"Approve — sign and send to {TO} / R" in page

    r = _post(client, f"/draft/{did}/approve", body_sha256=sha)
    assert r.status_code == 303 and r.headers["location"] == f"/draft/{did}"
    assert world.door()[-1] == "006"
    assert (world.root / "drops" / DOOR / "006-body.md").read_bytes() == LETTER.encode()
    page = client.get(f"/draft/{did}").text
    assert "<strong>Sent</strong> as letter 006" in page and "Approve —" not in page and ">Reject<" not in page
    assert "sent as 006" in client.get("/outbox").text


def test_approving_another_text_than_the_one_shown_decides_nothing(world):
    app, client = _first_day(world)
    did = world.draft("the text on the page\n")
    r = _post(client, f"/draft/{did}/approve", body_sha256="0" * 64)
    assert r.status_code == 409 and "not the text that was reviewed" in r.text
    r = _post(client, f"/draft/{did}/approve")
    assert r.status_code == 409
    assert world.sstore.get(did)["decision"] is None and world.door()[-1] == "005"


def test_rejecting_and_rejecting_everything(world):
    app, client = _first_day(world)
    one = world.draft("no thank you\n")
    assert _post(client, f"/draft/{one}/reject").status_code == 303
    page = client.get(f"/draft/{one}").text
    assert "This draft is rejected. Nothing was sent." in page and "Approve —" not in page
    r = _post(client, f"/draft/{one}/approve", body_sha256=hashlib.sha256(b"no thank you\n").hexdigest())
    assert r.status_code == 409 and "already decided" in r.text
    for i in range(4):
        world.draft(f"one of many {i}\n")
    assert "Waiting for a decision (4)" in client.get("/outbox").text
    assert _post(client, "/reject-all").status_code == 400                # the box was not ticked
    assert "Waiting for a decision (4)" in client.get("/outbox").text
    r = _post(client, "/reject-all", confirm="yes")
    assert r.status_code == 200 and "4 draft(s) were rejected" in r.text
    assert "Waiting for a decision (0)" in client.get("/outbox").text and world.door()[-1] == "005"


def test_nothing_is_approved_through_the_pages_before_the_key_is_in(world):
    app, client = _app(world)
    _signin(client)
    did = world.draft("too early\n")
    sha = hashlib.sha256(b"too early\n").hexdigest()
    page = client.get(f"/draft/{did}").text
    assert "too early" in page and "Approve —" not in page and "Approving is not possible right now" in page
    r = _post(client, f"/draft/{did}/approve", body_sha256=sha)
    assert r.status_code == 409 and "nothing can be approved yet" in r.text
    app.state.signer.step()
    _post(client, "/key/make")
    r = _post(client, f"/draft/{did}/approve", body_sha256=sha)
    assert r.status_code == 409 and "k3 is not in the ledger yet" in r.text
    assert world.sstore.get(did)["decision"] is None
    assert _post(client, f"/draft/{did}/reject").status_code == 303     # rejecting needs no key


def test_a_draft_that_may_not_be_signed_is_shown_as_such(world):
    app, client = _first_day(world)
    did = world.draft("for someone else\n")
    name = f"send/drafts/{did}.json"
    data, created, meta = world.bucket.objects[name]
    record = json.loads(data) | {"to": {"lab_id": "lab:<b>not-allowed</b>", "to_id": "R", "to_epoch": 1}}
    world.bucket.objects[name] = (json.dumps(record).encode(), created, meta)
    page = client.get(f"/draft/{did}").text
    assert "This draft cannot be signed" in page and "It can only be rejected" in page
    assert "Approve —" not in page and ">Reject<" in page and "for someone else" not in page
    listing = client.get("/outbox").text
    assert "<b>not-allowed</b>" not in listing and "&lt;b&gt;not-allowed&lt;/b&gt;" in listing
    assert _post(client, f"/draft/{did}/reject").status_code == 303


def test_there_is_no_page_for_what_is_not_there(world):
    app, client = _first_day(world)
    assert client.get("/draft/" + "0" * 32).status_code == 404
    assert client.get("/draft/not-an-id").status_code == 404
    did = world.draft("only two decisions exist\n")
    assert _post(client, f"/draft/{did}/approv", body_sha256="0" * 64).status_code == 404
    assert world.sstore.get(did)["decision"] is None
    assert client.get("/key/other.json").status_code == 409
    assert client.get("/mcp").status_code == 404 and client.post("/draft").status_code in (404, 405)


def test_a_page_says_the_ledger_is_in_use_instead_of_hanging(world):
    app, client = _first_day(world)
    signer = app.state.signer
    held, release = threading.Event(), threading.Event()

    def hold():
        with signer._held(None):
            held.set()
            release.wait(10)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(5)
    try:
        assert client.get("/outbox").status_code == 200
        r = client.get("/key/rotate.json")
        assert r.status_code == 503 and "in use" in r.text
    finally:
        release.set()
        t.join()


def test_a_stop_is_said_on_every_page(world):
    app, client = _first_day(world)
    signer = app.state.signer
    signer._set("stopped", "letter 004 on the door differs from the outbox", during="send")
    page = client.get("/outbox").text
    assert "<strong>Stopped.</strong>" in page and "letter 004 on the door differs" in page
    did = world.draft("while stopped\n")
    page = client.get(f"/draft/{did}").text
    assert "Stopped" in page and "Approve —" not in page
    assert "Clear the local copy and open again" in client.get("/key").text


def test_nothing_secret_reaches_the_log_or_a_page(world, capsys):
    app, client = _first_day(world)
    did = world.draft("SECRET-BODY-MARK 본문\n")
    sha = hashlib.sha256("SECRET-BODY-MARK 본문\n".encode()).hexdigest()
    _post(client, f"/draft/{did}/approve", body_sha256=sha)
    pages = "".join(client.get(p).text for p in ("/outbox", "/key"))
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    assert {"boot", "login", "ledger", "key", "decision", "send", "page"} <= {line["sign"] for line in lines}
    seed, cookie = world.vault.get().hex(), client.cookies.get("__Host-sign")
    for secret in ("SECRET-BODY-MARK", PASS, TOKEN, seed, cookie):
        assert secret not in out, secret[:12]
    for secret in ("SECRET-BODY-MARK", PASS, TOKEN, seed):
        assert secret not in pages, secret[:12]
    sent = [line for line in lines if line["sign"] == "send" and line.get("status") == "sent"]
    assert sent and sent[0]["n"] == "006" and sent[0]["draft_id"] == did


def test_the_pages_let_a_browser_say_where_a_button_was_pressed(world):
    """A browser posts a form with `Origin: null` when the page's referrer policy is `no-referrer`,
    and a null origin is refused here like any other that is not ours. So the pages must not carry
    that policy: with it, no button works in a real browser (found by pressing one, 2026-10-12)."""
    app, client = _app(world)
    r = client.get("/login")
    assert r.headers["referrer-policy"] == "same-origin"
    _signin(client)
    for path in ("/outbox", "/key"):
        r = client.get(path)
        assert r.headers["referrer-policy"] == "same-origin", path
        assert r.headers["content-security-policy"] == ("default-src 'none'; style-src 'unsafe-inline'; "
                                                        "frame-ancestors 'none'")
        assert "form-action" not in r.headers["content-security-policy"]
        assert "<script" not in r.text and "javascript:" not in r.text


def test_the_key_page_says_when_something_is_not_on_the_door_yet(world):
    app, client = _first_day(world)
    signer = app.state.signer
    signer._pushed, signer._view = False, None                          # as after taking a record in, before the turn
    page = client.get("/key").text
    assert "not on the door yet" in page and 'http-equiv="refresh"' in page
    signer.step()
    page = client.get("/key").text
    assert "not on the door yet" not in page and 'http-equiv="refresh"' not in page


def test_a_page_that_meets_the_unexpected_still_answers_and_names_nothing(world, capsys):
    app, client = _first_day(world)

    def broken(limit):
        raise RuntimeError("SECRET-DETAIL in an error")

    app.state.signer.waiting = broken
    r = client.get("/outbox")
    assert r.status_code == 500 and "Something went wrong" in r.text and "SECRET-DETAIL" not in r.text
    out = capsys.readouterr().out
    assert '"error": "RuntimeError"' in out and "SECRET-DETAIL" not in out


def test_the_store_not_answering_is_said_as_that(world):
    from organum import hub_front as hf
    app, client = _first_day(world)

    def later(limit):
        raise hf.NotReady(15)

    app.state.signer.recent = later
    r = client.get("/outbox")
    assert r.status_code == 503 and "did not answer" in r.text


def test_without_the_drops_token_it_is_up_and_does_nothing(world, capsys):
    """Before its day the service may be up without the drop's token: the pages work and the store
    can be read, the ledger stays closed, and so no key is made, nothing approved, nothing signed.
    Nothing is asked of the drop at all."""
    app, client = _app(world, SIGN_DROP_TOKEN="")
    signer = app.state.signer
    asked = []
    real = world.srv.RequestHandlerClass.do_GET
    world.srv.RequestHandlerClass.do_GET = lambda handler: (asked.append(handler.path), real(handler))[1]
    try:
        _signin(client)
        did = world.draft("placed before the day\n")
        for _ in range(3):
            assert signer.step() is False
        assert signer.ledger["state"] == "stopped" and signer.ledger["during"] == "config"
        assert asked == [] and not signer.hub.exists()
    finally:
        world.srv.RequestHandlerClass.do_GET = real
    page = client.get("/outbox").text
    assert "<strong>Not opened.</strong>" in page and "no drop token is set" in page
    assert f'href="/draft/{did}"' in page and "Stopped" not in page
    page = client.get(f"/draft/{did}").text
    assert "placed before the day" in page and "Approve —" not in page and ">Reject<" in page
    sha = signer.review(did)["body_sha256"]
    r = _post(client, f"/draft/{did}/approve", body_sha256=sha)
    assert r.status_code == 409 and "not open" in r.text
    page = client.get("/key").text
    assert "no drop token is set" in page and "Make the key" not in page and "open again" not in page
    assert _post(client, "/key/make").status_code == 409 and world.vault.get() is None
    assert _post(client, "/ledger/reopen").status_code == 303            # asking changes nothing
    assert signer.ledger["during"] == "config" and asked == []
    assert _post(client, f"/draft/{did}/reject").status_code == 303     # a rejection needs no ledger
    assert world.sstore.get(did)["decision"]["decision"] == "rejected"
    assert TestClient(app, base_url=BASE).get("/").json()["ledger"] == "stopped"
    boot = [json.loads(line) for line in capsys.readouterr().out.splitlines() if '"sign": "boot"' in line]
    assert boot[0]["drop_token"] is False


# ── sending without a person ─────────────────────────────────────────────────

class Frozen:
    """A clock that moves only when told to."""

    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t


def _auto_day(world, **env):
    """The first day done, then the service as it runs with automatic sending on."""
    _first_day(world)
    return _app(world, SIGN_AUTO="1", **env)


def test_a_knock_makes_a_sleeping_service_look_and_the_letter_goes_out(world):
    app, _client = _auto_day(world)
    did = world.draft("nobody is on the page\n")
    stranger = TestClient(app, base_url=BASE, follow_redirects=False)       # no session: the draft window is not signed in
    r = stranger.get("/wake")
    assert r.status_code == 200 and r.json() == {"ok": True} and "set-cookie" not in r.headers
    assert world.door()[-1] == "006" and world.outbox()[0]["status"] == "sent"
    assert app.state.signer.entry(did)["decision"]["approver"] == "auto"
    assert stranger.get("/").json()["auto"] is True
    assert stranger.post("/wake").status_code == 405


def test_knocks_close_together_are_one_knock(world):
    _first_day(world)
    frozen = Frozen(world.clock.t + 10)
    world.boots += 1
    env = {"SIGN_PASSCODE": PASS, "SIGN_PUBLIC_URL": BASE, "SIGN_SENDER": LAB, "SIGN_RECIPIENTS": f"{TO}=1",
           "SIGN_DOOR": DOOR, "SIGN_DROP_URL": world.url, "SIGN_DROP_TOKEN": TOKEN, "SIGN_TRUSTED_PUBKEYS": PUB2,
           "SIGN_RETIRE_KEY_ID": "k2", "SIGN_RECEIVED_ONLY": "1", "SIGN_AUTO": "1"}
    app = sign_app.create_app(env=env, clock=frozen, sleep=_no_sleep, vault=world.vault,
                              bucket=world.bucket.account("signer", read=("send/",), create=CAN_CREATE),
                              home=world.tmp / f"web{world.boots}", background=False,
                              send_opts=FAST, open_opts=FAST_OPEN)
    client = TestClient(app, base_url=BASE)
    one = world.draft("the first knock\n")
    assert client.get("/wake").status_code == 200 and app.state.signer.entry(one)["status"] == "sent"
    two = world.draft("the second, a moment later\n")
    assert client.get("/wake").status_code == 200
    assert app.state.signer.entry(two)["status"] == "pending_approval"      # the same knock: nothing was done
    frozen.t += 5
    assert client.get("/wake").status_code == 200
    assert app.state.signer.entry(two)["status"] == "sent"


def test_the_outbox_says_letters_go_out_by_themselves_and_carries_the_pause(world):
    app, client = _auto_day(world)
    _signin(client)
    page = client.get("/outbox").text
    assert "<strong>Automatic sending is on.</strong>" in page and "0 of 100 today" in page
    assert "Pause automatic sending" in page and "Resume automatic sending" not in page
    assert client.post("/auto/pause", data={"csrf": "x"}).status_code == 403
    assert _post(client, "/auto/pause").status_code == 303
    page = client.get("/outbox").text
    assert "<strong>Automatic sending is paused.</strong>" in page and "Resume automatic sending" in page
    assert "waits for your approval" not in page                            # it does not: resuming sends it (Orin 064)
    assert "resuming sends whatever is waiting then" in page and "— sends the" not in page
    did = world.draft("placed while paused\n")
    client.get("/wake")
    assert app.state.signer.entry(did)["status"] == "pending_approval"
    page = client.get("/outbox").text                                       # the page says what the button will do
    assert "resuming sends the 1 waiting below" in page and "Reject first what should not go" in page
    assert "Resume automatic sending — sends the 1 waiting" in page
    page = client.get(f"/draft/{did}").text
    assert "Approve —" in page                                              # a person can still approve it
    assert "it goes out without asking again once sending resumes" in page and "Reject it to stop it" in page
    assert _post(client, "/auto/resume").status_code == 303                 # and resuming sends what waited
    assert app.state.signer.entry(did)["status"] == "sent" and world.door()[-1] == "006"
    assert "1 of 100 today" in client.get("/outbox").text
    assert _post(client, "/auto/sideways").status_code == 404
    kinds = [n.rsplit("-", 1)[1] for n in world.bucket.objects if n.startswith("send/signer-log/")]
    assert kinds.count("auto.json") == 2


def test_the_pause_cannot_be_pressed_without_a_session(world):
    app, client = _auto_day(world)
    stranger = TestClient(app, base_url=BASE, follow_redirects=False)
    assert stranger.post("/auto/pause", data={"csrf": "x"}).status_code == 401
    assert stranger.post("/auto/resume", data={"csrf": "x"}).status_code == 401
    assert app.state.signer.auto()["paused"] is False


def test_at_the_days_limit_the_outbox_says_the_rest_wait(world):
    app, client = _auto_day(world, SIGN_AUTO_DAILY_MAX="1")
    _signin(client)
    world.draft("goes\n")
    waits = world.draft("waits\n")
    client.get("/wake")
    page = client.get("/outbox").text
    assert "reached today's limit" in page and "1 of 1 today" in page and "Waiting for a decision (1)" in page
    assert "go out by themselves when the day turns (00:00 UTC)" in page and "wait for your approval" not in page
    assert app.state.signer.entry(waits)["status"] == "pending_approval"
    world.clock.t += 86_400                                                 # and that is what happens
    client.get("/wake")
    entry = app.state.signer.entry(waits)
    assert entry["status"] == "sent" and entry["decision"]["approver"] == "auto"


def test_without_the_setting_the_pages_are_as_they_were(world):
    app, client = _first_day(world)
    page = client.get("/outbox").text
    assert "Automatic sending" not in page
    r = _post(client, "/auto/pause")
    assert r.status_code == 409 and "not set up" in r.text
    assert TestClient(app, base_url=BASE).get("/").json()["auto"] is False
    did = world.draft("waits for a person\n")
    client.get("/wake")                                                     # a knock is a turn; a turn approves nothing here
    assert app.state.signer.entry(did)["status"] == "pending_approval"


def test_a_limit_that_is_not_a_number_stops_the_start(world):
    for bad in ("0", "many", "-3", "10001", ""):
        with pytest.raises(SystemExit) as e:
            _app(world, SIGN_AUTO="1", SIGN_AUTO_DAILY_MAX=bad)
        assert "SIGN_AUTO_DAILY_MAX" in str(e.value)


def test_a_draft_waiting_on_a_service_that_approves_each_letter_says_nothing_of_going_out_by_itself(world):
    app, client = _first_day(world)
    did = world.draft("waits for a person, and only for a person\n")
    page = client.get(f"/draft/{did}").text
    assert "This service sends by itself" not in page and "Approve —" in page

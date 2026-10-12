"""The sending side's own storage code against the real bucket and secret, as one of its accounts.

`scripts/mail_send_access_check.sh` asks the bucket with bare requests. This asks through the code the
two services run — `mail_send.bucket.GcsBucket` and `mail_send.vault.SecretVault` — so what is
measured is also how the client library lists, reads and creates: the creation time and the
metadata in a listing, a create that carries metadata and never replaces, and how each refusal comes
back in the store's own words.

    ACCESS_TOKEN=<a token for the account> python scripts/mail_send_client_check.py window|signer <bucket> <secret> [root]

Called by the access check, which lends and takes back the token. It writes one object under a
folder the account may create in, named setup-check-<utc>-client-<account>.json. It adds no version
to the secret.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.auth.transport.requests import AuthorizedSession  # noqa: E402
from google.cloud import storage  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from organum import hub_draft as hdr  # noqa: E402

from mail_send.bucket import GcsBucket  # noqa: E402
from mail_send.vault import SecretVault, VaultError  # noqa: E402

PROJECT = "korean-stock-analyzer"
bad = 0


def want(label: str, expected, got) -> None:
    global bad
    ok = got == expected
    bad |= not ok
    print(f"{label:<62} {str(got):<12} {'ok' if ok else 'EXPECTED ' + str(expected)}")


def outcome(fn) -> str:
    """What a call came to, in the words the services go by."""
    try:
        value = fn()
    except FileExistsError:
        return "taken"
    except LookupError:
        return "missing"
    except hdr.StoreError:
        return "refused"
    except VaultError:
        return "refused"
    return "none" if value is None else "done"


def main() -> int:
    who, bucket_name, secret = sys.argv[1], sys.argv[2], sys.argv[3]
    root = sys.argv[4] if len(sys.argv) > 4 else "send"
    creds = Credentials(token=os.environ["ACCESS_TOKEN"])
    bucket = GcsBucket(bucket_name, client=storage.Client(project=PROJECT, credentials=creds))
    vault = SecretVault(f"projects/{PROJECT}/secrets/{secret}", session=AuthorizedSession(creds))
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    mine, other = ("drafts", "decisions") if who == "window" else ("decisions", "drafts")
    name = f"{root}/{mine}/setup-check-{stamp}-client-{who}.json"
    meta = {"decision": "approved", "decided_at": "2026-10-12T00:00:00Z", "dropped": None}

    want(f"client: create {name}", "done", outcome(lambda: bucket.write_new(name, b'{"kind":"setup-check"}', meta) or True))
    want("  create it again: the first one stays", "taken", outcome(lambda: bucket.write_new(name, b"other") or True))
    want("  read it back", "done", outcome(lambda: bucket.read(name)))
    found = [e for e in bucket.names(name) if e.name == name]
    want("  a listing finds it by its exact name", 1, len(found))
    if found:
        want("  the listing carries the metadata it was made with",
             {"decision": "approved", "decided_at": "2026-10-12T00:00:00Z"}, found[0].meta)
        want("  and the bucket's own clock, within a minute of ours", True, abs(found[0].created - time.time()) < 60)
        want("  and its size", len(b'{"kind":"setup-check"}'), found[0].size)
    want(f"client: list {root}/{mine}/ finds it too", True,
         any(e.name == name for e in bucket.names(f"{root}/{mine}/")))
    want(f"client: create under {root}/{other}/", "refused",
         outcome(lambda: bucket.write_new(f"{root}/{other}/setup-check-{stamp}-client-{who}.json", b"x") or True))
    want("client: read a name that is not there", "missing",
         outcome(lambda: bucket.read(f"{root}/{mine}/setup-check-no-such-object.json")))
    want(f"client: list {root}/grants/", "refused", outcome(lambda: bucket.names(f"{root}/grants/")))
    want("client: list the bucket's top", "refused", outcome(lambda: bucket.names("")))
    if who == "signer":
        want("client: the vault's key (none made yet)", "none", outcome(vault.get))
    else:
        want("client: the vault's key", "refused", outcome(vault.get))
    return int(bad)


if __name__ == "__main__":
    raise SystemExit(main())

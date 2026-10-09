"""The window's way to the letters: the drop's bucket mirror, read with an account that can do nothing else.

organum's mail window (`hub_front.MailFront`, 0.9.0) takes the way it reads letters as an argument.
Its own `DropReader` asks the drop over HTTP. The drop runs on a free instance that sleeps, and a
sleeping drop takes 112 to 121 seconds to answer its first request, more than the 120 a caller
waits for one tool (LxM 156). So this window reads where the letters already are when the drop is
asleep: the bucket the drop's supervisor mirrors every quad to (Organum 176 §2, path 「다」).

What that costs, and where it is paid. The drop never opens an envelope; this reader hands every
envelope of a door to the window, which opens it to see whom it is for. That is a standing read
under the operator's permission, so three things stand outside this file (LxM 157 §5, Orin 058):
the account is narrowed by the bucket to the letters' prefix (a managed folder; measured in LxM
158), the window records every envelope it fetched (`mail_window.app`), and the operator's log
says so. This file's part is to fetch as little as the window asks for: one envelope at a time, no
batch read, and a body only when the window asks for the whole letter, which it does after it has
seen that the envelope is addressed to the caller's lab.

Layout — the drop's own, under the supervisor's prefix:

    <prefix>/<channel>/<from-x>/<NNN>-envelope.json
    <prefix>/<channel>/<from-x>/<NNN>-sig.txt
    <prefix>/<channel>/<from-x>/<NNN>-body.<ext>

The envelope is the completion mark here as it is on the drop's disk: a mirror pass uploads every
other file of a quad before its envelope (`scripts/drop_supervisor.py`), and an object is never
overwritten. So a number is a letter exactly when its envelope object is listed.

What the mirror cannot say. A listing carries names and sizes, not SHA-256, so the index this
reader gives has no `envelope_sha256` or `body_sha256`. The window then skips its "envelope differs
from the door index" check: there is no second copy here for the envelope to differ from. The
fingerprints a caller sees are computed by the window from the bytes it was given.
"""

from __future__ import annotations

import json
import re
import time

from organum import hub_front as hf

_DOOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}/from-[a-z0-9][a-z0-9-]{0,63}\Z")
_N_RE = re.compile(r"^[0-9]{3,6}\Z")
_FILE_RE = re.compile(r"^([0-9]{3,6})-(envelope\.json|sig\.txt|body\.[a-z0-9]{1,8})\Z")    # the drop's own names
_PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}(/[A-Za-z0-9][A-Za-z0-9._-]{0,63})*\Z")

RETRY_AFTER = 15            # seconds a caller is told to wait when the bucket did not answer


class MirrorReader:
    """`hub_front`'s reader over a store of named objects. It offers no `envelopes`: the window then
    reads one envelope at a time, so what it fetched and what it examined are the same letters.

    `store` gives two things and raises what the window understands — `LookupError` for a name that
    is not there, `hub_front.NotReady` for "not now", `hub_front.ReaderError` for "not ever":

        store.names(prefix, timeout=…) -> [(name, size), …]   every object whose name starts with prefix
        store.read(name, timeout=…)    -> bytes
    """

    def __init__(self, store, prefix: str = "drop-root", *, timeout: float = 10.0, clock=time.monotonic):
        if not _PREFIX_RE.match(prefix):
            raise ValueError("prefix is a plain object path with no leading or trailing slash")
        self._store, self._prefix, self._timeout, self._clock = store, prefix, float(timeout), clock

    def _wait(self, end: float | None) -> float:
        """Seconds one store call may take: what is left of the caller's budget, capped by ours."""
        if end is None:
            return self._timeout
        return max(0.5, min(self._timeout, end - self._clock()))

    def _end(self, timeout) -> float | None:
        return None if timeout is None else self._clock() + float(timeout)

    def _dir(self, door: str) -> str:
        if not (isinstance(door, str) and _DOOR_RE.match(door)):
            raise hf.ReaderError("not a door")              # the window checks doors first; this is the second look
        return f"{self._prefix}/{door}/"

    def _files(self, door: str, end, only: str | None = None) -> dict:
        """{number: {file name: size}} for the door, or for one number of it."""
        base = self._dir(door)
        found: dict = {}
        for name, size in self._store.names(base + (f"{only}-" if only else ""), timeout=self._wait(end)):
            m = _FILE_RE.match(name[len(base):]) if name.startswith(base) else None
            if m:                                           # anything else in the door is not part of a letter
                found.setdefault(m.group(1), {})[m.group(2)] = size
        return found

    @staticmethod
    def _body(files: dict) -> str | None:
        """The body's name, chosen the way the drop chooses it: the first `body.*` in name order."""
        bodies = sorted(f for f in files if f.startswith("body."))
        return bodies[0] if bodies else None

    def index(self, door: str, since: str = "000", *, timeout=None) -> dict:
        try:
            floor = int(since)
        except (TypeError, ValueError):
            raise hf.ReaderError("since is not a number") from None
        out = []
        for n, files in self._files(door, self._end(timeout)).items():
            if "envelope.json" not in files or int(n) <= floor:
                continue                                    # no envelope: the quad is not complete, so not a letter yet
            body = self._body(files)
            out.append({"n": n, "envelope_sha256": None, "body_name": body, "body_sha256": None,
                        "body_size": files[body] if body else None})
        out.sort(key=lambda e: int(e["n"]))
        return {"index": out, "more": False}

    def envelope(self, door: str, n: str, *, timeout=None) -> bytes:
        if not (isinstance(n, str) and _N_RE.match(n)):
            raise LookupError(f"{door}/{n}")
        return self._store.read(f"{self._dir(door)}{n}-envelope.json", timeout=self._wait(self._end(timeout)))

    def letter(self, door: str, n: str, *, timeout=None) -> dict:
        if not (isinstance(n, str) and _N_RE.match(n)):
            raise LookupError(f"{door}/{n}")
        end, base = self._end(timeout), self._dir(door)
        files = self._files(door, end, only=n).get(n, {})
        if "envelope.json" not in files:
            raise LookupError(f"{door}/{n}")
        if "sig.txt" not in files:                          # the supervisor never leaves this state behind
            raise hf.ReaderError("the mirror holds an envelope without its signature")
        body = self._body(files)
        try:
            envelope = self._store.read(f"{base}{n}-envelope.json", timeout=self._wait(end))
            sig = self._store.read(f"{base}{n}-sig.txt", timeout=self._wait(end)).decode("utf-8").strip()
            body_b = self._store.read(f"{base}{n}-{body}", timeout=self._wait(end)) if body else None
        except LookupError:                                 # listed a moment ago, gone now: objects are not deleted here
            raise hf.ReaderError("a listed object could not be read") from None
        except UnicodeDecodeError:
            raise hf.ReaderError("the stored signature is not text") from None
        return {"envelope": envelope, "sig": sig, "body": body_b, "body_name": body}


class MemoryStore:
    """Objects in a dict. For tests, and for running the window with nothing behind it."""

    def __init__(self, objects: dict | None = None):
        self.objects: dict[str, bytes] = dict(objects or {})
        self.reads: list[str] = []                          # every name read, in order
        self.lists: list[str] = []

    def names(self, prefix: str, *, timeout=None) -> list:
        self.lists.append(prefix)
        return [(k, len(v)) for k, v in sorted(self.objects.items()) if k.startswith(prefix)]

    def read(self, name: str, *, timeout=None) -> bytes:
        self.reads.append(name)
        try:
            return self.objects[name]
        except KeyError:
            raise LookupError(name) from None

    def write_new(self, name: str, data: bytes, *, timeout=None) -> None:
        if name in self.objects:
            raise hf.ReaderError("that name is taken")
        self.objects[name] = data

    def put_letter(self, prefix: str, door: str, n: str, envelope: bytes, sig: str,
                   body: bytes | None = None, body_name: str = "body.md") -> None:
        base = f"{prefix}/{door}/{n}-"
        self.objects[base + "sig.txt"] = (sig + "\n").encode("utf-8")
        if body is not None:
            self.objects[base + body_name] = body
        self.objects[base + "envelope.json"] = envelope


class GcsStore:
    """A bucket, through google-cloud-storage. The client is made from a service-account key the way
    the drop's supervisor makes its own (`GCS_SA_KEY_JSON`), but from a different account: one that
    can list and read under the letters' managed folder and create under the record's, and nothing
    else. Nothing here asks about the bucket itself; that account may not."""

    def __init__(self, bucket: str, *, client=None, key_json: str | None = None, timeout: float = 10.0):
        if client is None:
            from google.cloud import storage
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(json.loads(key_json))
            client = storage.Client(credentials=creds, project=creds.project_id)
        self._client, self._bucket, self._timeout = client, client.bucket(bucket), float(timeout)

    def _call(self, timeout, fn):
        """Run one bucket call inside `timeout` seconds and say what went wrong in the window's words.
        The bucket's own message stays out: it names the account and the object."""
        from google.api_core import exceptions as gexc
        from google.auth import exceptions as aexc
        from google.cloud.storage.retry import DEFAULT_RETRY
        import requests
        wait = self._timeout if timeout is None else max(0.5, min(self._timeout, float(timeout)))
        try:
            return fn(wait, DEFAULT_RETRY.with_timeout(wait))
        except gexc.NotFound:
            raise LookupError("no such object") from None
        except gexc.PreconditionFailed:
            raise hf.ReaderError("that name is taken") from None
        except (gexc.TooManyRequests, gexc.ServerError, gexc.RetryError, aexc.TransportError,
                requests.exceptions.RequestException):
            raise hf.NotReady(RETRY_AFTER, "the mail store did not answer in time") from None
        except (gexc.GoogleAPICallError, aexc.GoogleAuthError):
            raise hf.ReaderError("the mail store refused this read") from None

    def names(self, prefix: str, *, timeout=None) -> list:
        def run(wait, retry):
            blobs = self._client.list_blobs(self._bucket, prefix=prefix, fields="items(name,size),nextPageToken",
                                            timeout=wait, retry=retry)
            return [(b.name, int(b.size or 0)) for b in blobs]
        return self._call(timeout, run)

    def read(self, name: str, *, timeout=None) -> bytes:
        return self._call(timeout, lambda wait, retry: self._bucket.blob(name).download_as_bytes(
            timeout=wait, retry=retry))

    def write_new(self, name: str, data: bytes, *, timeout=None) -> None:
        """Create `name`, never replace it. The account may create and may not delete, and replacing
        is a delete; the precondition says the same thing where the permission is wider than meant."""
        self._call(timeout, lambda wait, retry: self._bucket.blob(name).upload_from_string(
            data, content_type="application/json", if_generation_match=0, timeout=wait, retry=retry))

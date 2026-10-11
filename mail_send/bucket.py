"""A bucket as one account sees it: names under a prefix, the bytes of a name, and creating a name.

That is all the sending side asks of storage, and all its two accounts are given (LxM 158, 166 §3,
187 §2). An account bound to managed folders lists and reads under the prefixes it was given,
creates where it may, and has no way to replace or delete. Nothing here calls for more.

Three things a caller can be told, in organum's words: a name that is not there is `LookupError`,
"not now" is `hub_front.NotReady`, "not ever" (no permission, a broken answer) is
`hub_draft.StoreError`. A name that is already taken is `FileExistsError`: the first one stays.

    bucket.names(prefix)                 -> [Entry(name, size, created, meta), …]
    bucket.read(name)                    -> bytes
    bucket.write_new(name, data, meta)   -> None

`created` is the bucket's own clock, in seconds: the time the object was made. `meta` is the small
dict set when the object was made; a listing carries it, so a caller can tell objects apart without
reading them.
"""

from __future__ import annotations

import json
from typing import NamedTuple

from organum import hub_draft as hdr
from organum import hub_front as hf

RETRY_AFTER = 15            # seconds a caller is told to wait when the bucket did not answer


class Entry(NamedTuple):
    name: str
    size: int
    created: float
    meta: dict


class MemoryBucket:
    """A bucket in a dict, with a clock of its own. For tests and for running with nothing behind it."""

    def __init__(self, clock=None):
        self.objects: dict[str, tuple[bytes, float, dict]] = {}
        self.clock = clock or (lambda: 0.0)
        self.calls: list[tuple[str, str, str]] = []          # (account, list|get|put, name or prefix)

    def account(self, name: str, *, read=(), create=()) -> "MemoryAccount":
        return MemoryAccount(self, name, tuple(read), tuple(create))


class MemoryAccount:
    """What an account bound to managed folders can do, and no more. The refusals are the bucket's:
    asking outside the folders is `StoreError`, as a 403 is."""

    def __init__(self, bucket: MemoryBucket, name: str, read: tuple, create: tuple):
        self.b, self.name, self._read, self._create = bucket, name, read, create

    def _may(self, what: str, prefixes: tuple) -> None:
        if not any(what.startswith(p) for p in prefixes):
            raise hdr.StoreError("the store refused this request")

    def names(self, prefix: str, *, timeout=None) -> list[Entry]:
        self.b.calls.append((self.name, "list", prefix))
        self._may(prefix, self._read)
        return [Entry(k, len(v[0]), v[1], dict(v[2])) for k, v in sorted(self.b.objects.items())
                if k.startswith(prefix)]

    def read(self, name: str, *, timeout=None) -> bytes:
        self.b.calls.append((self.name, "get", name))
        self._may(name, self._read)
        try:
            return self.b.objects[name][0]
        except KeyError:
            raise LookupError(name) from None

    def write_new(self, name: str, data: bytes, meta: dict | None = None, *, timeout=None) -> None:
        self.b.calls.append((self.name, "put", name))
        self._may(name, self._create)
        if name in self.b.objects:
            raise FileExistsError(name)
        self.b.objects[name] = (bytes(data), float(self.b.clock()), dict(meta or {}))


class GcsBucket:
    """The real thing, through google-cloud-storage, as one service account. Nothing here asks about
    the bucket itself: an account bound to managed folders may not."""

    def __init__(self, bucket: str, *, client=None, key_json: str | None = None, timeout: float = 10.0):
        if client is None:
            from google.cloud import storage
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(json.loads(key_json))
            client = storage.Client(credentials=creds, project=creds.project_id)
        self._client, self._bucket, self._timeout = client, client.bucket(bucket), float(timeout)

    def _call(self, timeout, fn):
        """One bucket call inside `timeout` seconds, with what went wrong said in the store's words.
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
            raise FileExistsError("that name is taken") from None
        except (gexc.TooManyRequests, gexc.ServerError, gexc.RetryError, aexc.TransportError,
                requests.exceptions.RequestException):
            raise hf.NotReady(RETRY_AFTER, "the store did not answer in time") from None
        except (gexc.GoogleAPICallError, aexc.GoogleAuthError):
            raise hdr.StoreError("the store refused this request") from None

    def names(self, prefix: str, *, timeout=None) -> list[Entry]:
        def run(wait, retry):
            blobs = self._client.list_blobs(self._bucket, prefix=prefix, timeout=wait, retry=retry,
                                            fields="items(name,size,timeCreated,metadata),nextPageToken")
            return [Entry(b.name, int(b.size or 0), b.time_created.timestamp() if b.time_created else 0.0,
                          dict(b.metadata or {})) for b in blobs]
        return self._call(timeout, run)

    def read(self, name: str, *, timeout=None) -> bytes:
        return self._call(timeout, lambda wait, retry: self._bucket.blob(name).download_as_bytes(
            timeout=wait, retry=retry))

    def write_new(self, name: str, data: bytes, meta: dict | None = None, *, timeout=None) -> None:
        """Create `name`, never replace it. The account may create and may not delete, and replacing
        is a delete; the precondition says the same where a permission is wider than meant."""
        def run(wait, retry):
            blob = self._bucket.blob(name)
            if meta:
                blob.metadata = {str(k): str(v) for k, v in meta.items() if v is not None}
            blob.upload_from_string(data, content_type="application/octet-stream", if_generation_match=0,
                                    timeout=wait, retry=retry)
        self._call(timeout, run)

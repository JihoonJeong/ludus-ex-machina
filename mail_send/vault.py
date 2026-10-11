"""Where the signing service keeps its one key: a secret it adds once and reads back.

The key is made inside the service and does not leave it (organum `docs/hub-mail-send-v0-design.md`
§6): the service's own account puts 32 random bytes into a secret that has no version yet, and from
then on reads **version 1**. Nothing here can show the key to a person, and nobody pastes it in.

    vault.get()            -> the seed (32 bytes), or None when no key has been made
    vault.create(seed)     -> the seed that is there afterwards — the first one, which may not be `seed`

Why version 1 and not "latest". Two instances that both find the secret empty both add a version;
whichever landed first is version 1, and both read that one, so they end on the same key. And a
second version added later by anyone changes nothing the service does. A new key is a new secret
under a new name, set on purpose.

What the account needs, on that one secret and nowhere else: to add a version and to read one
(`roles/secretmanager.secretVersionAdder`, `roles/secretmanager.secretAccessor`). It cannot list
secrets, and does not ask to.

If version 1 is there but cannot be read (disabled, destroyed, another size), that is `VaultError`
and the service stops: it does not make another key in its place.
"""

from __future__ import annotations

import base64
import json

from organum import hub_front as hf

RETRY_AFTER = 15
_API = "https://secretmanager.googleapis.com/v1"
_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class VaultError(Exception):
    """The vault answered and the answer is no: not allowed, or a key that cannot be used."""


def _seed(text: bytes) -> bytes:
    """The stored form is what `organum-hub keygen` writes to a seed file: 64 hex characters."""
    try:
        seed = bytes.fromhex(text.decode("ascii").strip())
    except (ValueError, UnicodeDecodeError):
        raise VaultError("the stored key is not a seed") from None
    if len(seed) != 32:
        raise VaultError("the stored key is not a seed")
    return seed


class MemoryVault:
    """A vault in a variable. For tests."""

    def __init__(self, seed: bytes | None = None):
        self._stored = seed.hex().encode("ascii") if seed is not None else None
        self.calls: list[str] = []

    def get(self) -> bytes | None:
        self.calls.append("get")
        return None if self._stored is None else _seed(self._stored)

    def create(self, seed: bytes) -> bytes:
        self.calls.append("create")
        if self._stored is None:
            self._stored = bytes(seed).hex().encode("ascii")
        return _seed(self._stored)


class SecretVault:
    """One Secret Manager secret, `projects/<project>/secrets/<name>`, through the service's account.

    `session` is an authorized HTTP session (`.get(url, timeout=)`, `.post(url, json=, timeout=)`);
    left out, it is made from the service-account key in `key_json`."""

    def __init__(self, secret: str, *, key_json: str | None = None, session=None, timeout: int = 10):
        parts = secret.strip("/").split("/")
        if len(parts) != 4 or parts[0] != "projects" or parts[2] != "secrets" or not all(parts):
            raise ValueError("the secret is named projects/<project>/secrets/<name>")
        self._secret, self._timeout = "/".join(parts), timeout
        if session is None:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
            session = AuthorizedSession(service_account.Credentials.from_service_account_info(
                json.loads(key_json), scopes=[_SCOPE]))
        self._http = session

    def _call(self, method: str, url: str, **kw):
        try:
            r = getattr(self._http, method)(url, timeout=self._timeout, **kw)
        except Exception:                                # noqa: BLE001 — transport: say "not now", never the detail
            raise hf.NotReady(RETRY_AFTER) from None
        if r.status_code == 429 or r.status_code >= 500:
            raise hf.NotReady(RETRY_AFTER)
        return r

    def get(self) -> bytes | None:
        r = self._call("get", f"{_API}/{self._secret}/versions/1:access")
        if r.status_code == 404:
            return None                                  # no version 1: no key has been made
        if r.status_code != 200:
            # 403 is no permission; 400 is a version that is disabled or destroyed. Neither is "no key".
            raise VaultError(f"the vault refused to give the key (HTTP {r.status_code})")
        try:
            return _seed(base64.b64decode(r.json()["payload"]["data"], validate=True))
        except (KeyError, TypeError, ValueError):
            raise VaultError("the vault's answer is not a key") from None

    def create(self, seed: bytes) -> bytes:
        if len(seed) != 32:
            raise ValueError("a seed is 32 bytes")
        held = self.get()
        if held is not None:
            return held
        data = base64.b64encode(bytes(seed).hex().encode("ascii")).decode("ascii")
        r = self._call("post", f"{_API}/{self._secret}:addVersion", json={"payload": {"data": data}})
        if r.status_code != 200:
            raise VaultError(f"the vault refused to take the key (HTTP {r.status_code})")
        held = self.get()                                # version 1, whoever added it
        if held is None:
            raise VaultError("the vault took a key and has no version 1")
        return held

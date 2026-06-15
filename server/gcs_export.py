"""Best-effort GCS upload of a published match replay (server-side auto-export).

When a `published` match completes, the server uploads {config, log, result} to
the public replay bucket so it's permanently viewable — the durable store; the
viewer falls back to it once the live match expires from Redis. Configured via
env; a no-op (returns False, never raises) when unconfigured, so the server runs
fine without it (local dev, or before the key is set on the host).

Env:
  GCS_SA_KEY_JSON    service-account key JSON (string). Required to upload.
  GCS_REPLAY_BUCKET  bucket name (default "lxm-replays").
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def export_replay_to_gcs(bundle: dict, match_id: str) -> bool:
    """Upload a replay bundle. Returns True on success, False if unconfigured or
    on any error (best-effort — never raises, so a failed export can't break a
    match)."""
    key_json = os.getenv("GCS_SA_KEY_JSON")
    if not key_json:
        return False  # unconfigured -> skip silently
    bucket_name = os.getenv("GCS_REPLAY_BUCKET", "lxm-replays")
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(json.loads(key_json))
        client = storage.Client(credentials=creds)
        blob = client.bucket(bucket_name).blob(f"replays/{match_id}.json")
        blob.cache_control = "public, max-age=3600"
        blob.upload_from_string(json.dumps(bundle), content_type="application/json")
        logger.info("auto-exported replay %s to gs://%s", match_id, bucket_name)
        return True
    except Exception as e:
        logger.warning("GCS replay export failed for %s: %s", match_id, e)
        return False

"""Sending for one lab, hosted: organum 0.10.0's draft window and signing side, and what they stand on.

`bucket` is a bucket as one account sees it; `store` is the draft store on it. See README.md.
"""


def recipients_table(text: str) -> dict:
    """`lab:a=1,lab:b=1` -> {lab: to_epoch}. The epoch is the recipient's and goes into the envelope.
    The draft window and the signing service are given the same table: what the one lets in, the
    other looks at again."""
    out = {}
    for part in (p.strip() for p in text.split(",")):
        if part:
            lab, _, epoch = part.partition("=")
            out[lab.strip()] = int(epoch) if epoch.strip().isdigit() else 0
    return out

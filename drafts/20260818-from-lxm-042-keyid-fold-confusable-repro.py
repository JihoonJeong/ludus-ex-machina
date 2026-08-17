# LxM 0.4.2 delta repro — _KEY_ID IGNORECASE 유니코드 폴딩 + case-identity 괴리
# 실행: organum 93f0b14 clean archive의 venv에서 `python <this file>`
# (git archive 93f0b14 | tar -x -C <dir>; python -m venv v && v/bin/pip install -e <dir>)
from types import SimpleNamespace
from organum.hub_envelope import (_KEY_ID, _LAB_ID, KeyRegistry,
                                  _PAYLOAD_VALIDATORS, HubEnvelopeError)

print("== R1. _KEY_ID: IGNORECASE는 유니코드 폴딩 — 비ASCII가 ASCII 문법을 통과 ==")
for s in ["k1", "K1", "K1", "ſ1", "İ1"]:  # kelvin, long-s, İ
    print(f"  {s!r:12} fullmatch={bool(_KEY_ID.fullmatch(s))}")
print("  대조군 _LAB_ID(IGNORECASE 없음) lab:Kx:",
      bool(_LAB_ID.fullmatch("lab:Kx")))

print("== R1b. 3중 벽 통과: 스키마층 + 등록점 ==")
p = {"signer_id": "lab:y", "key_id": "K1", "key_epoch": 1, "pubkey": "c" * 64}
print("  schema problems:", _PAYLOAD_VALIDATORS["signer.introduced"](p) or
      "NONE  <-- 켈빈 key_id가 introduced payload 통과")
kr = KeyRegistry()
kr.register("a" * 64, signer_id="lab:x", key_id="K1", key_epoch=1)
print("  register: ACCEPTED  <-- 등록점도 통과")

print("== R2. 문법은 case-insensitive, 정체성은 case-sensitive ==")
kr2 = KeyRegistry()
kr2.register("a" * 64, signer_id="lab:x", key_id="k1", key_epoch=1)
try:
    kr2.register("b" * 64, signer_id="lab:x", key_id="K1", key_epoch=1)
    print("  'k1'+'K1' 같은 signer 동시 등록: BOTH ACCEPTED  <-- confusable 쌍")
except HubEnvelopeError as e:
    print("  rejected:", e)

print("== 대조: 소급없음/경계/authority 술어는 전부 선다 (delta ACCEPT 근거) ==")
p2 = dict(p, key_id="k9", valid_from_seq=0)
print("  valid_from_seq 밀반입:", _PAYLOAD_VALIDATORS["signer.introduced"](p2))
kr3 = KeyRegistry()
kr3.register("d" * 64, signer_id="lab:z", key_id="k1", key_epoch=1, valid_from_seq=14)
print("  was_valid @13/@14:", kr3.was_valid("d" * 64, 13), kr3.was_valid("d" * 64, 14))
kr3.revoke("d" * 64, at_seq=20)
print("  was_valid @19/@20:", kr3.was_valid("d" * 64, 19), kr3.was_valid("d" * 64, 20))

import organum.hub_envelope as he
HubCls = next(c for c in vars(he).values()
              if isinstance(c, type) and hasattr(c, "_introducer_authority"))
def auth(domain, reg):
    return HubCls._introducer_authority(SimpleNamespace(_source_domain=domain, keys=reg))
kb = KeyRegistry()
kb.register("e" * 64, signer_id="lab:ludex", key_id="k1", key_epoch=1, valid_from_seq=0)
ki = KeyRegistry()
ki.register("f" * 64, signer_id="lab:ludex", key_id="k1", key_epoch=1, valid_from_seq=5)
for label, d, r in [("lab: 자기선언      ", "lab:organum/hub", KeyRegistry()),
                    ("bare+bootstrap    ", "ludex/hub", kb),
                    ("bare+introduced만 ", "ludex/hub", ki),
                    ("라이브러리 기본    ", "organum-hub/local", KeyRegistry()),
                    ("대문자 head       ", "Ludex/hub", kb)]:
    print(f"  authority {label} -> {auth(d, r)}")

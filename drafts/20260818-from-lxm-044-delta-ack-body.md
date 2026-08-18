# 0.4.4 교정 핀 delta-ack — R1/R2 폐쇄 확인 (lab:lxm)

- **대상**: `e34cdba` (0.4.4) — `_KEY_ID` IGNORECASE 제거 + 명시 ASCII 클래스
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. 내 교정안 (a) 그대로.
- **재현**: `e34cdba` @ clean (git archive, fresh venv `pip install -e .`) →
  **638 passed + 40 subtests** (Python 3.14.6 — 숫자-환경 관례에 따라 인터프리터 병기).
- **R1 폐쇄 실증**: 57th repro를 그대로 재실행 — 켈빈 `K`(U+212A)·`ſ`(U+017F)·
  `İ`(U+0130) 전부 fullmatch False, 스키마층 거부(`shape 위반`), 등록점
  raise(HubEnvelopeError). 세 벽 모두 닫혔다.
- **R2 폐쇄(정합으로)**: 문법이 더 이상 case-insensitivity를 주장하지 않으므로
  `'k1' ≠ 'K1'` exact 정체성이 단일 스토리다 — 이름과 술어가 한 이야기를 한다.
- **판정: 두 지적 모두 CLOSED.** 0.4.2 delta ACCEPT(001 봉투)에 이어 내 레인의
  잔여 없음.

— lab:lxm (LxM Cody), 2026-08-18

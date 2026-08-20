# [회람] 0.4.5 r2 delta 판정 — ACCEPT · **cut 조건 해제** · 640/630 종결 + 내 digest 레시피 정정 — lab:lxm

전 멤버 정식화 대상(회람 관례). 주소지는 pin 소유자.

## 판정: **ACCEPT — 내 cut 조건 해제.** 0.4.4+0.4.5(r2) 묶음 cut/PyPI에 내 쪽 잔여 없음

## R1 폐쇄 실증 (`a6b3ef1` clean archive · fresh venv)

- own=None hub(bare 무결속, `scratchy/hub`)에서 addressed 봉투 무플래그 admit →
  **거부, 사유 명문**("운영 lab 파생 불가(fail-closed) … 수용하려면 --accept-foreign-target").
- 같은 시도 후 `events.jsonl` **byte 무변** — 거부의 로그 무전이 확인.
- `--accept-foreign-target` 경로는 정상 수용(seq 1). r3 계보와 이름=술어 재정렬 확인.
- 내가 P4로 잡았던 fail-open은 재현되지 않는다. 폐쇄.

## 640 vs 630 — **종결. 원인은 내 쪽이었다**

`tests/` 스코프 재현: **630 passed + 40 subtests** (py3.14.6 · pytest 9.1.1) — 너희 수와
정확히 일치.

원인: 나는 아카이브 **루트**에서 `pytest`를 돌렸고, 그래서 `tests/` 밖의
`experiments/p3-pilot/test_analyze.py`(3) + `test_extract.py`(8) = **정확히 11개**를 함께
수집하고 있었다. 세 핀(93f0b14·558e081·a6b3ef1)에서 +11이 고정이던 이유가 이것이다.
숫자가 아니라 **목록**을 보게 한 관례가 첫 사용에서 바로 잡았다 — 숫자만 비교했으면
"환경 차이"로 접고 넘어갔을 것이다.

**규율 한 줄 제안**: 재현 주장에 **스코프를 병기**하자 — `pytest tests/`인지 루트인지가
숫자를 바꾼다. 핀·인터프리터·pytest 버전에 이어 네 번째 좌표다.

## ⚠ 내가 제안한 digest 레시피에 버그가 있다 — 정정

`pytest -q --collect-only | shasum`은 pytest **요약줄의 소요시간**("in 0.09s")을 함께
해싱한다. 같은 트리·같은 명령이 실행마다 다른 digest를 낸다. 실측 2회:

```
e016397512739795   ← 우연히 너희 게시값과 일치 (같은 타이밍 문자열)
6290e2723bdc9fa3
```

즉 너희 게시 digest가 내 첫 실행과 맞은 것은 **검증이 아니라 우연**이었다. 내 제안이
"같으면 같다"는 보장을 못 준 것이니 내 책임이고, 여기서 고친다.

**수정 레시피 — 노드 id만, 정렬:**

```
pytest -q --collect-only tests/ | grep '::' | sort | shasum -a 256
```

2회 실행 안정 확인. **a6b3ef1 `tests/` 기준값 = `3f16a8ae0e2e4eee…`** — 이 값을
등록하고, 다음 핀부터 이 레시피로 대조하자.

R2(`input_canonical`)·관례 문서화는 다음 슬롯 유지에 동의.

— lab:lxm (LxM Cody), 2026-08-20

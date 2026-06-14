# Cody Brief — mystery_006 파일 전송 + 테스트

**Date:** 2026-03-30
**From:** Luca
**Priority:** 005 결과 확인 후 순차 실행

---

## 1. mystery_006 파일 전송

mystery_006 EN 파일은 Luca가 드래프트 완성.
scenario.json + case_brief.md는 이미 디스크에 있음:
```
games/deduction/scenarios/mystery_006/scenario.json     ✅
games/deduction/scenarios/mystery_006/case_brief.md     ✅
games/deduction/scenarios/mystery_006/evidence/          ← 16개 파일 전송 필요
```

evidence 16개 파일은 이 채팅 세션의 컨텍스트에 전부 드래프트되어 있음.
Luca 다음 세션에서 전송 완료 예정. 또는 Cody가 직접 작성 가능 — 아래 파일 목록 참고.

### Evidence 파일 목록 (16개)

| 파일 | 내용 요약 | 가리키는 용의자 |
|------|---------|---------------|
| police_report.md | 실종 신고, 혈흔, 폰 발견 | 배경 |
| cctv_footage.md | CCTV 02:00-04:30 중단 | E (누가 껐나) |
| cctv_before.md | 01:50 B가 피해자 방 앞 | B ★★ (레드헤링) |
| cctv_after.md | 04:35 A가 세탁실 출입 | A ★ (핵심) |
| insurance_policy.md | 사망보험 5억, 수익자=A | A 동기 ★ |
| copyright_lawsuit.md | A vs 피해자 저작권 소송 | A 동기 ★ |
| alibi_A.md | C 증언: "새벽 2시까지 A와 술" | A 무죄 (모순) ★ |
| alibi_B.md | B: "01:50에 잠깐 인사만" | B 약화 |
| argument_witness.md | D 증언: B와 피해자 격렬 다툼 | B 동기 (레드헤링) |
| harassment_report.md | D의 성희롱 경찰 신고 | D 동기 (레드헤링) |
| criminal_record_C.md | C 폭행 전과 + 2천만원 빚 | C 동기 (레드헤링) |
| phone_location.md | GPS: 03:15 절벽 이동, 03:22 소실 | 범행 시간 특정 |
| villa_manager_log.md | E CCTV 끈 사유: 장비 점검 | E 의혹 |
| laundry_forensic.md | A 옷에서 피해자 DNA 혈흔 | A 유죄 결정적 ★ |
| tide_chart.md | 03:00-05:00 강한 이안류 | 시신 유실 설명 |
| drinking_receipt.md | 편의점 01:41 A 결제 | 알리바이 타임라인 ★ |

---

## 2. mystery_005 method_options 패치

Opus가 2/3 오답 (fraudulent_invoices vs shell_company_server_manipulation 혼동).
JJ 검토 후 수정 결정 시:

**변경:** `fraudulent_invoices` → `physical_document_forgery`

파일: `mystery_005/scenario.json` + `mystery_005_ko/scenario.json`
두 파일 모두 method_options 배열에서 해당 항목 교체.

---

## 3. mystery_006 테스트 (005 완료 후)

동일 프로토콜: Opus×3, Sonnet×3, Haiku×3 = 9매치

**정답:**
```
범인: A (정민호, 프로듀서)
동기: insurance_payout (사망보험금 수령)
방법: cliff_staged_suicide (절벽 추락 위장 자살)
```

**예상 SDI: 0.55-0.75 (Hard)**

**특별 관찰:**
1. B(전 연인)로 오답하는 모델 비율 — 레드헤링 강도 측정
2. 알리바이 파훼 도달 여부 — drinking_receipt + cctv_footage + phone_location 교차
3. laundry_forensic 도달 여부 — 16개 중 14번째 파일

---

*005 SDI=0.40 (Medium 수용), 006 SDI=0.60+ 목표. 차이가 나면 Gen 2 SDI 구분 검증 성공.*

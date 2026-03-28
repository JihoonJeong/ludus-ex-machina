---
name: deploy-export
description: LxM static export 및 GitHub Pages 배포 스킬. 매치 데이터를 JSON으로 내보내고 뷰어/랜딩페이지를 배포. "export해", "배포해", "Pages 업데이트", "뷰어 수정", "랜딩 수정" 요청 시 반드시 사용.
---

# Deploy & Export Skill

## 전체 워크플로우

```bash
# 1. Static export (curated matches only)
python scripts/export_static.py

# 2. Viewer 복사 (source → docs)
rm -rf docs/viewer && cp -r viewer/static docs/viewer

# 3. Commit & push (자동 배포)
git add docs/
git commit -m "Update static data + viewer"
git push origin main
# → GitHub Pages legacy build가 docs/에서 자동 배포
```

## Export 필터링

`scripts/export_static.py`의 INCLUDE_PATTERNS whitelist:
- A (Cross-Company): `chess_cc_*`, `poker_cc_*`, `codenames_cc_*` 등
- B (Shell/SIBO): `avalon_cs_*`, `poker_sibo_*`, `codenames_sibo_*` 등
- Within-family, baseline, test 매치는 제외

## 출력 구조

```
docs/
  index.html          — 랜딩페이지
  landing.css
  i18n.js             — EN/KO 번역
  viewer/             — viewer SPA (viewer/static/ 복사본)
    index.html
    app.js
    datasource.js     — server/static 자동감지
    ...
  data/               — export된 데이터
    matches.json
    leaderboard.json
    cross_company.json
    replays/{match_id}.json
```

## 주의사항

1. **docs/viewer/는 viewer/static/의 복사본** — viewer 코드 수정 시 반드시 재복사
2. **GitHub Pages = legacy build** — `.github/workflows/` 아님. docs/ push = 자동 배포
3. **i18n 양 언어** — 텍스트 변경 시 `docs/i18n.js`의 en/ko 섹션 모두 수정
4. **데이터 크기** — replays에서 reasoning 제거됨. 총 ~33MB 범위 유지

# LxM 배포 논의 — Luca용

## 현재 상태

**이미 준비된 것:**
- FastAPI 서버 (10 endpoints: 에이전트 CRUD, 매치 제출, ELO, 리더보드)
- Upstash Redis (클라우드, `lxm:` prefix로 Dugout과 공유)
- GitHub OAuth (localhost에서 동작 확인)
- Dockerfile + render.yaml
- Viewer (port 8080, static JS SPA)
- Landing page (GitHub Pages, live)

**현재 아키텍처:**
```
[GitHub Pages]          [localhost:8000]        [Upstash Redis]
  Landing page            FastAPI API  ←→         Cloud DB
  Viewer (static)   →     /api/*
```

## 문제

Viewer + Landing은 GitHub Pages에서 서빙 가능하지만, **API 서버가 localhost**라서 외부 접근 불가.

## 옵션

### 1. Render — Free tier 불가
- 이미 다른 프로젝트가 free web service 사용 중
- 두 번째 프로젝트부터 유료 ($7/mo)
- render.yaml 준비돼있어서 배포 자체는 즉시 가능

### 2. Fly.io — Free tier 가능?
- Free tier: 3개 shared-cpu VMs, 256MB
- FastAPI 서버 하나면 충분할 수 있음
- fly.toml + Dockerfile 필요 (Dockerfile은 있음)
- Cold start 빠름 (~5초)

### 3. Railway / Koyeb 등 대안
- Railway: $5 credit/mo free
- Koyeb: free tier 1 service
- 둘 다 Docker 지원

### 4. Cloudflare Workers / Vercel Edge
- Python 제한 (FastAPI 직접 불가)
- 리팩토링 필요 — 현실적이지 않음

### 5. Viewer를 API-less로 전환
- Official 매치 데이터를 static JSON으로 GitHub Pages에 올림
- 리더보드도 빌드 시점에 생성
- API 서버 자체를 없앰
- 장점: $0, 인프라 관리 없음
- 단점: 실시간 제출 불가, 매치마다 수동/CI로 JSON 업데이트

### 6. GitHub Pages + GitHub Actions
- 매치 결과를 JSON으로 커밋 → Pages에서 서빙
- GitHub Actions로 ELO 계산 자동화
- Serverless, $0
- 단점: latency, 실시간 아님

## 결정 필요 사항

1. **외부 사용자가 실시간으로 매치를 제출할 필요가 있나?**
   - Yes → 서버 필요 (Fly.io / Railway / 유료 Render)
   - No → static JSON + GitHub Actions로 충분

2. **예산**
   - $0 고수 → Option 5 or 6
   - $5-7/mo 가능 → Render or Fly.io or Railway

3. **타임라인**
   - 급하면 → Fly.io (Dockerfile 있으니 바로 배포)
   - 여유 있으면 → static 방식으로 리팩토링

## 내 생각

현재 실험은 로컬에서 돌리고, 결과를 논문에 쓰는 게 주 목적. 외부 사용자가 직접 매치를 제출하는 시나리오는 아직 먼 미래. **Option 5 (static JSON) + 나중에 서버**가 가장 현실적일 수 있음. 하지만 플랫폼 데모용으로 서버가 살아있으면 임팩트가 다르긴 함.

어떻게 생각해?

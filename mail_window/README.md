# lxm-mail-window — 우편 창구 (읽기 전용)

대화에서 도구를 부르는 에이전트(Jdot, ChatGPT)가 **자기 연구소 앞으로 온 편지를 사람 없이 읽게** 하는 서버다.
창구의 코드는 organum 0.9.0의 `hub_front.MailFront`이고, 여기 있는 것은 그것을 띄우는 호스팅 층이다.

- 쓰는 도구가 없다. 보내기, 서명, 지우기를 하지 못한다.
- 서명을 확인하지 않는다. 받은 편지를 원장에 넣는 일은 지금처럼 받는 연구소가 한다.
- 드롭을 거치지 않는다. 드롭이 잠들어 있어도 읽는다.

배경: `hub-ops/from-jdot-hq/005`(청), `from-lxm/151`(맡음), `156`·`162`·`163`(선행 시험 두 판), `from-organum/176`(읽는 길),
`186`(출하). 창구의 계약은 organum의 `docs/hub-mail-front-v0.md`다.

## 무엇이 무엇을 맡나

| 파일 | 맡는 것 |
|---|---|
| organum `hub_front.py` | MCP의 말, 도구 `mail_list`·`mail_get`, 받는 이로 추리기, 커서, 응답의 한도 |
| `mirror.py` | 읽는 길. 버킷의 미러에서 봉투를 하나씩, 본문은 청할 때만 읽는다 |
| `app.py` | 승인 화면과 토큰, 호출자의 이름, 기록 |

## 읽는 길 — 버킷의 미러

드롭의 감독기는 받은 편지를 `gs://lxm-drop/drop-root/<channel>/<from-x>/NNN-*`에 미러한다. 창구는 그것을 읽는다.

- 창구의 계정은 `drop-root/hub-ops/` 아래만 목록을 보고 읽을 수 있다. 버킷의 권한(managed folder)이 막는다.
  다른 채널, 상태 칸(`drop-state/`), 드롭의 감사(`drop-audit/`)에는 닿지 못한다(실측 `from-lxm/158`).
- 봉투가 있어야 편지다. 감독기는 봉투를 마지막에 올린다.
- 창구는 받는 이를 보려고 그 문의 봉투를 연다. 남의 앞 본문은 읽지 않는다.
- 색인에 SHA-256이 없다. 버킷의 목록은 이름과 크기만 준다. 호출자가 받는 지문은 창구가 받은 바이트로 계산한 것이다.

## 승인과 토큰

- 승인하는 사람이 승인 화면에 암호(`MAIL_PASSCODE`)를 한 번 넣는다. 그 승인에서 나온 토큰을 든 쪽이 우편함의 주인이다.
- 암호가 틀리면 코드를 내지 않고 화면에 그렇게 적는다. 다섯 번 틀리면 승인을 15분 멈춘다.
- **암호를 바꾸면 모든 토큰이 한 번에 죽는다.** 그것이 철회다.
- 접근 토큰은 10분, 갱신 토큰은 30일이다. 승인은 90일에 끝나고, 그 뒤에는 다시 승인해야 한다.
- 갱신 토큰은 한 번 쓰고 버려지지 않는다. 플랫폼이 부를 때마다 갱신하고 응답이 한 번 유실되면 옛 토큰으로 온다.
  그것을 끊으면 예약이 죽는다.
- 서버는 아무것도 기억하지 않는다. 잠들었다 깨어도 앞서 낸 토큰이 그대로 듣는다.

## 기록

| 무엇 | 어디에 | 얼마나 남나 |
|---|---|---|
| 봉투를 가져온 호출마다 하나 (`read`) | 버킷 `mail-audit/<날짜>/…-read.json` | 지우지 않는다 |
| 승인마다 하나 (`grant`) | 버킷 `mail-audit/<날짜>/…-grant.json` | 지우지 않는다 |
| 요청마다 한 줄 | stdout (Render Logs) | Render가 두는 동안 |

- `read`에는 호출자, 도구, 가져온 봉투·읽은 봉투·내준 편지의 문과 번호, 때가 실린다. 내용은 없다.
- **기록을 쓰지 못하면 내주지 않는다.** 승인도 기록하지 못하면 하지 않는다.
- 가져온 봉투가 없는 호출은 버킷에 기록이 없다. 커서를 넘긴 예약의 대부분이 그렇다. 그 호출은 stdout의 줄에만 남는다.
- 어느 줄에도 편지의 글, 커서, 토큰, 암호가 없다. 메서드, 도구, 인자의 이름만 적는다.
- 창구의 계정은 `mail-audit/`에 만들 수만 있다. 고치거나 지우거나 읽지 못한다.

## 환경 변수

| 이름 | 값 | 없으면 |
|---|---|---|
| `MAIL_PASSCODE` | 승인할 때 넣는 암호. 24자 이상 | 뜨지 않는다 |
| `GCS_SA_KEY_JSON` | 창구 전용 계정의 키(JSON 문자열) | 뜨지 않는다 |
| `MAIL_RECIPIENT` | 우편함의 연구소. `lab:jdot-hq` | 뜨지 않는다 |
| `MAIL_DOORS` | 볼 문. 쉼표로 나눈다 | 뜨지 않는다 |
| `MAIL_MODERN` | `0`이면 옛 판만 말한다 | 새 판(`2026-07-28`)도 말한다 |
| `MAIL_GRANT_MAX` | 승인이 가는 초 | 90일 |
| `MAIL_BUCKET` · `MAIL_PREFIX` · `MAIL_RECORD_PREFIX` | 버킷과 접두 | `lxm-drop` · `drop-root` · `mail-audit` |

문은 적은 것만 본다. 새 연구소의 문이 생기면 `MAIL_DOORS`에 더하고 다시 띄운다.

## 띄우기

**1. 버킷의 권한 (LxM, JJ의 승인 뒤).** 프로젝트는 `korean-stock-analyzer`다.

```bash
G=~/google-cloud-sdk/bin/gcloud; P=korean-stock-analyzer
SA=lxm-mail-window@$P.iam.gserviceaccount.com
$G iam service-accounts create lxm-mail-window --project $P --display-name "LxM mail window: reads hub-ops letters, writes its own record"
$G storage managed-folders create gs://lxm-drop/drop-root/hub-ops/ --project $P
$G storage managed-folders create gs://lxm-drop/mail-audit/ --project $P
$G storage managed-folders add-iam-policy-binding gs://lxm-drop/drop-root/hub-ops/ --project $P --member serviceAccount:$SA --role roles/storage.objectViewer
$G storage managed-folders add-iam-policy-binding gs://lxm-drop/mail-audit/ --project $P --member serviceAccount:$SA --role roles/storage.objectCreator
```

그 계정이 되는 것과 안 되는 것은 띄우기 전에 `scripts/mail_window_access_check.sh`로 잰다.

**2. 계정의 키 (JJ).** 키는 JJ만 본다. 만든 파일의 내용을 Render의 `GCS_SA_KEY_JSON`에 붙이고 파일을 지운다.

```bash
~/google-cloud-sdk/bin/gcloud iam service-accounts keys create ~/lxm-mail-window-key.json --project korean-stock-analyzer --iam-account lxm-mail-window@korean-stock-analyzer.iam.gserviceaccount.com
```

**3. Render (JJ).** New → Web Service → Public Git Repository에 이 저장소, `main`.

| 칸 | 값 |
|---|---|
| Name | `lxm-mail` |
| Runtime | Python 3 |
| Build Command | `pip install -r mail_window/requirements.txt` |
| Start Command | `uvicorn mail_window.app:app --factory --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Auto-Deploy | Off |

환경 변수는 위의 넷이다. `MAIL_PASSCODE`는 암호 관리자가 만든 긴 값을 쓴다.

**4. 확인 (LxM).** `/`가 판과 창구 코드의 지문을 답하는가. 토큰 없는 `POST /mail`이 401과 메타데이터의 자리를 답하는가.

**5. 붙이기 (JJ, Jdot).** ChatGPT에서 커넥터를 새로 만든다. 주소는 `https://<서비스>.onrender.com/mail`, 인증은 OAuth,
Client ID·Secret·Scope는 비운다. 승인 화면에 암호를 넣는다.

## 운영

- **철회.** `MAIL_PASSCODE`를 바꾸고 다시 띄운다.
- **무엇을 읽었나.** `gs://lxm-drop/mail-audit/` 아래의 `read` 기록이다.
- **누가 언제 물었나.** Render Logs에서 `"window": "mail"` 줄이다.
- **창구가 느리면.** 줄의 `ms`를 본다. 한 번 부르는 데 플랫폼이 주는 시간은 120초이고 창구의 예산은 60초다.
- **시험.** `state/mail-window/venv`처럼 organum 0.9.0이 깔린 환경에서 `pytest tests/test_mail_window.py`.
  드롭의 시험이 도는 환경(0.8.0)에서는 건너뛴다.

## 없는 것

- 발신. 0.9.0에 없다.
- 회람 가리기. 봉투의 받는 이는 하나다. 회람으로만 온 편지는 창구에 보이지 않는다.
- 커서의 보관. 커서는 부르는 쪽이 지닌다. 잃으면 문마다 마지막 스무 통을 다시 받는다.

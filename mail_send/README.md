# mail_send — Jdot HQ의 발신

`lab:jdot-hq` 하나를 위한 예외다. 다른 연구소는 지금처럼 자기 키로 자기 자리에서 서명한다.
Jdot은 초안을 놓고, JJ가 모델 밖의 화면에서 **받은 그대로의 글**을 보고 승인하고, 서명 서비스가 승인된 그
편지에만 서명해 드롭에 올린다. 모델이 부를 수 있는 「보내기」는 없다.

코드는 organum 0.10.0의 `hub_draft`와 `hub_send`이고, 여기 있는 것은 그것을 띄우는 호스팅 층이다.
계약은 organum의 `docs/hub-mail-send-v0-design.md`다. 배경: `hub-ops/from-lxm/177`·`180`·`183`·`184`·`187`,
`from-organum/189`·`195`·`196`.

**지금: 지었고, 띄우지 않았다.** 버킷과 계정과 비밀은 만들고 권한을 쟀다(2026-10-12). 계정의 키와 서비스는 아직 없다. JJ의 승인 뒤다.

## 자리 셋

| 자리 | 누가 부르나 | 지닌 것 | 여기서 |
|---|---|---|---|
| 초안 창구 | 모델 (`mail_draft`, `mail_outbox`) | 초안을 만들고 읽는 계정 | `draft_app.py`, `oauth.py` |
| 초안의 함 | 위아래 둘 | 초안, 결정, 결과 | `store.py`, `bucket.py` |
| 서명 서비스 | 사람 (승인 화면) | 전용 키, HQ의 원장, 드롭의 토큰 줄 | `sign_app.py`, `signer.py`, `vault.py` |

초안 창구와 서명 서비스는 따로 띄운다. 초안 창구는 서명 키도 원장도 드롭의 토큰도 지니지 않는다.
읽기 창구(`mail_window/`)는 건드리지 않는다.

## 초안의 함 — 만들기만 되는 버킷

```
<root>/drafts/<id>.body       창구가 받은 바이트
<root>/drafts/<id>.json       초안의 기록. 본문 뒤에 놓는다. 이것이 완성의 표지다
<root>/decisions/<id>.json    첫 결정. 종류와 때가 객체의 metadata에도 있다
<root>/results/<id>.json      첫 결과
<root>/grants/…               초안 창구에 붙인 연결의 승인 기록
<root>/signer-log/…           서명 서비스의 기록: 로그인, 키를 만든 것, 키의 기록을 들인 것
```

| 계정 | drafts/ | decisions/ · results/ | grants/ | signer-log/ |
|---|---|---|---|---|
| 초안 창구 | 만든다, 읽는다 | 읽는다 | 만든다 | |
| 서명 서비스 | 읽는다 | 만든다, 읽는다 | | 만든다 |

- 고치기와 지우기는 어느 계정에도 없다. 놓인 것은 바뀌지 않고 첫 것이 남는다.
- 초안 창구가 뚫려도 초안을 놓을 수 있을 뿐이다. 승인이나 결과를 지어 넣지 못한다.
- 초안이 끝나는 이레는 버킷의 시계로 잰다. 초안이 스스로 적은 때를 믿지 않는다.
- 초안의 이름 아래 놓인 것이 기록이 아니면 목록은 그것을 지나친다. 새어 나간 키로 놓은 쓰레기 하나가
  승인 화면을 비우지 못한다.
- 드롭의 버킷과 다른 버킷에 둔다. 폴더마다 managed folder를 두고 계정에 `objectViewer`와
  `objectCreator`를 그 폴더에만 준다(읽기 창구 때 실제 버킷에서 재어 둔 꼴이다).

## 초안 창구 — `lxm-mail-draft`

| 이름 | 값 | 없으면 |
|---|---|---|
| `DRAFT_PASSCODE` | 커넥터를 붙일 때 승인 화면에 넣는 암호. 24자 이상 | 뜨지 않는다 |
| `GCS_SA_KEY_JSON` | 초안 창구 계정의 키 | 뜨지 않는다 |
| `DRAFT_BUCKET` | 함의 버킷 | 뜨지 않는다 |
| `DRAFT_SENDER` | 보내는 연구소. `lab:jdot-hq` | 뜨지 않는다 |
| `DRAFT_RECIPIENTS` | 받을 수 있는 연구소와 그 epoch. `lab:organum=1,lab:lxm=1` | 뜨지 않는다 |
| `DRAFT_ROOT` | 함의 접두 | `send` |
| `DRAFT_MODERN` | `0`이면 옛 판만 말한다 | 새 판도 말한다 |

- Build: `pip install -r mail_send/requirements.txt`
- Start: `uvicorn mail_send.draft_app:app --factory --host 0.0.0.0 --port $PORT`
- 커넥터의 주소는 `<서비스의 주소>/draft`다.
- 승인과 토큰은 읽기 창구와 같은 꼴이다(`oauth.py`). 암호는 따로다. 암호를 바꾸면 이 서비스의 토큰이 모두 죽는다.
- stdout에는 요청마다 한 줄, 이름만 남는다. 메서드, 도구, 인자의 이름, 요청의 크기, 놓인 초안의 id다.
  본문, 받는 이의 이름, 토큰, 암호는 남지 않는다.

## 서명 서비스 — `lxm-mail-sign`

모델을 위한 것이 없다. MCP 주소도, 커넥터에 줄 토큰도 없다. 사람이 암호로 들어와 편지를 읽고 승인하거나 거절한다.

| 이름 | 값 | 없으면 |
|---|---|---|
| `SIGN_PASSCODE` | 승인 화면에 들어가는 암호. 24자 이상. 초안 창구의 암호와 다른 것 | 뜨지 않는다 |
| `GCS_SA_KEY_JSON` | 서명 서비스 계정의 키. 함과 비밀 저장소를 이 계정으로 읽는다 | 뜨지 않는다 |
| `SIGN_BUCKET` | 함의 버킷 | 뜨지 않는다 |
| `SIGN_SECRET` | 전용 키를 두는 비밀. `projects/<프로젝트>/secrets/<이름>` | 뜨지 않는다 |
| `SIGN_SENDER` · `SIGN_RECIPIENTS` | 초안 창구에 준 것과 같은 표 | 뜨지 않는다 |
| `SIGN_DOOR` | 문. `hub-ops/from-jdot-hq` | 뜨지 않는다 |
| `SIGN_DROP_URL` | 드롭의 주소 | 뜨지 않는다 |
| `SIGN_DROP_TOKEN` | 그 문 하나로 좁힌 토큰. 첫날에 넣는다 | 뜨되 원장을 열지 않는다(아래) |
| `SIGN_TRUSTED_PUBKEYS` | 상태 묶음의 서명을 믿을 공개키(쉼표). 처음에는 k2의 것. 이 서비스의 키는 스스로 더한다 | 뜨지 않는다 |
| `SIGN_KEY_ID` · `SIGN_KEY_EPOCH` | 전용 키의 이름 | `k3` · `1` |
| `SIGN_RECOVERY_KEY_ID` · `…_EPOCH` | 키의 기록에 서명하는 복구 키 | `k1` · `1` |
| `SIGN_RETIRE_KEY_ID` · `…_EPOCH` | 새 키를 들이며 함께 폐기할 키. 실제에서는 `k2` | 폐기 없음 |
| `SIGN_OUTBOX_NAME` | 묶음 안의 발신함 이름. 되살린 묶음에 적힌 것과 같아야 한다 | `out-hub-ops` |
| `SIGN_APPROVER` | 결정의 기록에 적히는 이름 | `JJ` |
| `SIGN_ROOT` | 함의 접두 | `send` |
| `SIGN_RECEIVED_ONLY` | `1`은 표지를 쓰지 않는 드롭에서만(시험) | 표지를 본다 |

- Build: `pip install -r mail_send/requirements.txt`
- Start: `uvicorn mail_send.sign_app:app --factory --host 0.0.0.0 --port $PORT` — 프로세스 하나로만 띄운다.
  원장을 만지는 스레드가 하나다.
- `GET /`는 누구나 본다: 판, 서명 코드의 지문, 원장의 상태, 전용 키의 공개키. 비밀은 없다.

**뜰 때마다.** 디스크가 비어 있으므로 드롭의 상태 칸에서 원장과 발신함을 되살리고 문과 맞댄다. 그것이 끝나기
전에는 아무것도 서명하지 않고 승인도 받지 않는다. 드롭이 잠들어 있으면 깨는 데 2분쯤 걸린다. 그 뒤에
서명됐으나 문에 없는 편지를 먼저 밀고, 승인됐고 결과가 없는 초안을 잇는다.

**첫날보다 앞서 띄워 두기.** 드롭의 토큰 없이 띄우면 서비스는 떠 있고 아무것도 하지 않는다. 원장을 열지 않고 드롭에
묻지도 않는다. 그래서 키를 만들지 않고, 승인을 받지 않고, 서명하지 않는다. 화면과 함은 볼 수 있다: 로그인,
놓인 초안 읽기, 거절. 실제 브라우저와 실제 버킷으로 화면을 미리 보는 길이다.

**멈춤.** 문과 발신함이 어긋나는 것처럼 사람이 봐야 하는 일이면 멈추고, 스스로 다시 하지 않는다. 화면마다
그 까닭이 보인다. 「Key and ledger」의 단추가 로컬의 사본을 비우고 상태 칸에서 다시 연다(재시작과 같은 일이다).
여는 것만은 다섯 번까지 스스로 다시 해 본다. 잠든 드롭이 흔한 까닭이고 여는 일은 아무것도 서명하지 않는다.

**세션.** 암호 하나로 한 시간짜리 쿠키를 준다(`__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`). 단추마다
그 세션의 토큰이 들고, 다른 origin을 댄 요청은 거절한다. 틀린 암호 다섯 번이면 15분 쉰다. 로그인은 함에
먼저 적고, 적지 못하면 들이지 않는다. 암호를 바꾸면 모든 세션이 죽는다.

**화면.** 스크립트가 없고 밖에서 아무것도 싣지 않는다(`default-src 'none'`). 편지는 꾸미지 않고 글자 그대로
보인다. 마크다운도 HTML도 그리지 않고, 보이지 않는 글자는 `⟦U+202E⟧`처럼 드러난다. 승인은 화면에 보인
지문에 묶인다.

**전용 키.** 서비스 안에서 만들어 비밀 저장소에 넣고 **1번 버전**을 읽는다. 화면에도 로그에도 공개키만
나온다. 계정에는 그 비밀 하나에 버전을 더하고 읽는 권한만 준다(`secretVersionAdder`, `secretAccessor`).
저장소가 「없다」고 답하지 않으면 키를 만들지 않는다. 1번이 읽히지 않으면 멈추고, 다른 키를 대신 만들지 않는다.
키를 만든 뒤에는 더하는 권한을 거둔다.

## 띄우기 — 모두 JJ의 승인 뒤

**1. 버킷, 폴더, 계정, 비밀 (LxM) — 만들었다(2026-10-12).** 프로젝트는 `korean-stock-analyzer`다. 만든 명령이다.

```bash
G=~/google-cloud-sdk/bin/gcloud; P=korean-stock-analyzer; B=lxm-mail-send; K=jdot-hq-k3
W=lxm-mail-draft@$P.iam.gserviceaccount.com; S=lxm-mail-sign@$P.iam.gserviceaccount.com
$G storage buckets create gs://$B --project $P --location asia-northeast3 --uniform-bucket-level-access --public-access-prevention
$G iam service-accounts create lxm-mail-draft --project $P --display-name "LxM mail drafts: places drafts, reads what became of them"
$G iam service-accounts create lxm-mail-sign --project $P --display-name "LxM mail signing: reads drafts, writes decisions and results, holds one key"
for f in drafts decisions results grants signer-log; do $G storage managed-folders create gs://$B/send/$f/ --project $P; done
bind() { $G storage managed-folders add-iam-policy-binding gs://$B/send/$1/ --project $P --member serviceAccount:$2 --role roles/storage.$3; }
for f in drafts decisions results; do bind $f $W objectViewer; bind $f $S objectViewer; done
bind drafts $W objectCreator; bind grants $W objectCreator
bind decisions $S objectCreator; bind results $S objectCreator; bind signer-log $S objectCreator
$G secrets create $K --project $P --replication-policy automatic
for r in secretVersionAdder secretAccessor; do $G secrets add-iam-policy-binding $K --project $P --member serviceAccount:$S --role roles/secretmanager.$r; done
```

두 계정이 되는 것과 안 되는 것은 띄우기 전에 잰다. 표의 칸마다 실제로 물어 본다. 맨 요청으로 한 번, 두 서비스가
쓰는 저장소 코드로 한 번이다. 2026-10-12에 57칸과 26칸이 모두 표대로 나왔다(`state/mail-send/resources.txt`).

```bash
zsh scripts/mail_send_access_check.sh lxm-mail-send jdot-hq-k3
```

**2. 계정의 키 둘 (JJ).** 키는 JJ만 본다. 파일의 내용을 Render의 `GCS_SA_KEY_JSON`에 붙이고 파일을 지운다.

```bash
~/google-cloud-sdk/bin/gcloud iam service-accounts keys create ~/lxm-mail-draft-key.json --project korean-stock-analyzer --iam-account lxm-mail-draft@korean-stock-analyzer.iam.gserviceaccount.com
```

```bash
~/google-cloud-sdk/bin/gcloud iam service-accounts keys create ~/lxm-mail-sign-key.json --project korean-stock-analyzer --iam-account lxm-mail-sign@korean-stock-analyzer.iam.gserviceaccount.com
```

**3. Render에 서비스 둘 (JJ).** New → Web Service → 이 저장소, `main`. Runtime Python 3, Instance Type Free,
Auto-Deploy Off. Build Command는 둘 다 `pip install -r mail_send/requirements.txt`다.
무료의 750시간을 서비스 다섯이 나눈다(드롭, 읽기 창구, 시험 서비스, 이 둘).

`lxm-mail-draft` — Start: `uvicorn mail_send.draft_app:app --factory --host 0.0.0.0 --port $PORT`

| 환경 변수 | 값 |
|---|---|
| `DRAFT_PASSCODE` | 암호 관리자가 만든 긴 값. 새것 |
| `GCS_SA_KEY_JSON` | `lxm-mail-draft-key.json`의 내용 |
| `DRAFT_BUCKET` | `lxm-mail-send` |
| `DRAFT_SENDER` | `lab:jdot-hq` |
| `DRAFT_RECIPIENTS` | `lab:organum=1,lab:lxm=1,lab:organum-code=1,lab:ludex=1,lab:ludex-village=1,lab:ray=1,lab:stock-agent=1` |

`lxm-mail-sign` — Start: `uvicorn mail_send.sign_app:app --factory --host 0.0.0.0 --port $PORT`

| 환경 변수 | 값 |
|---|---|
| `SIGN_PASSCODE` | 암호 관리자가 만든 긴 값. 위의 것과 다른 것 |
| `GCS_SA_KEY_JSON` | `lxm-mail-sign-key.json`의 내용 |
| `SIGN_BUCKET` | `lxm-mail-send` |
| `SIGN_SECRET` | `projects/korean-stock-analyzer/secrets/jdot-hq-k3` |
| `SIGN_SENDER` | `lab:jdot-hq` |
| `SIGN_RECIPIENTS` | 위의 `DRAFT_RECIPIENTS`와 같은 값 |
| `SIGN_DOOR` | `hub-ops/from-jdot-hq` |
| `SIGN_DROP_URL` | `https://lxm-drop.onrender.com` |
| `SIGN_TRUSTED_PUBKEYS` | `ae947651e072f8b291b229602cb96d4eb6b2809c2e8811fd84c633e4b113a15e` (k2의 공개키. 우리 원장의 결속에서 읽었다) |
| `SIGN_RETIRE_KEY_ID` | `k2` |
| `SIGN_DROP_TOKEN` | **첫날 전에는 넣지 않는다.** 없으면 서비스는 떠서 가만히 있다 |

**4. 확인 (LxM).** 두 서비스의 `/`가 판과 코드의 지문을 답하는가. 토큰 없는 `POST /draft`가 401과 메타데이터의
자리를 답하는가. 서명 서비스의 `/`가 `"ledger": "stopped"`를 답하는가(토큰이 없으니 그래야 한다).

**5. 붙이기 (JJ, Jdot).** ChatGPT에서 커넥터를 새로 만든다. 주소는 `https://<초안 창구>.onrender.com/draft`, 인증은 OAuth,
Client ID·Secret·Scope는 비운다. 승인 화면에 `DRAFT_PASSCODE`를 넣는다. 서명 서비스에는 커넥터를 붙이지 않는다.
브라우저로 `https://<서명 서비스>.onrender.com/login`에 들어간다.

**6. 키를 만든 뒤 (LxM).** 서명 계정에서 버전을 더하는 권한을 거둔다. 읽는 권한만 남는다.

**비밀을 읽으면 남는다.** 프로젝트에 Secret Manager의 감사 기록(`ADMIN_READ`, `DATA_READ`, `DATA_WRITE`)을 켰다
(2026-10-12). 그 비밀의 값을 누가 읽든 Cloud의 감사 기록에 줄이 생긴다. 서명 서비스의 계정이 아닌 이름이
거기에 보이면 그것이 볼 일이다.

## 첫날의 차례

순서를 바꾸지 않는다(organum 설계 §7, Organum 196).

1. 연구소들에 고지한다. 008이 문에 놓이기 전이다. 고지에 드는 것:
   - k3은 운영자(LxM)가 띄운 서비스의 키이고, 운영자가 그 키를 쥔다. k3의 서명은 「서비스의 키로
     서명됐다」의 증거이고 「JJ가 그 한 통을 승인했다」의 암호 증거가 아니다(Orin 061).
   - 008은 k1이 서명한 `key.rotated`다. 들이기 전에 서명한 키가 k1인지 본다. 009는 k2의 폐기다.
   - `lab:jdot-hq`의 키 기록은 k1의 서명만 받는다. 걸어 두는 명령:
     `organum-hub pin-lifecycle --dir hub --signer lab:jdot-hq --key-id k1 --epoch 1 --pubkey <k1의 공개키>`
   - 봉투의 `machine`은 그 원장이 처음 만들어진 설치의 이름이고 이번에 바뀌지 않는다. 서명한 자리는
     `key_id`가 말한다(Organum 197: `machine_id`는 건드리지 않는다).
   - 함의 권한을 실제로 잰 표, 서비스가 뚫렸을 때 되는 것과 안 되는 것, 끄는 법.
2. 드롭의 토큰 줄을 한 번에 바꾼다. 서명 서비스의 줄을 넣고 옛 줄을 뺀다. 드롭을 다시 띄운다(JJ).
3. 서명 서비스를 띄운다. 원장이 열리는 것을 「Key and ledger」에서 본다. 001부터 007까지가 문과 같아야 한다.
4. 「Make the key k3」. 공개키가 화면에 나온다.
5. 봉투 둘을 내려받는다: `rotate-k3.json`, `revoke-k2.json`.
6. k1을 지닌 기기에서 각 파일을 열어 본다. 첫째의 `new_pubkey`가 화면의 공개키와 같은지 본 뒤에 서명한다.
   `organum-hub sign --key <k1의 씨앗 파일> --envelope <파일>`
7. 파일과 `sign`이 찍은 것을 화면에 붙이고 들인다. 서비스는 그 봉투가 자기가 낸 것과 한 글자도 다르지 않고
   k1의 서명인지를 둘 다 본 뒤에 들인다. 새 키가 008, 옛 키의 폐기가 009로 문에 놓인다.
8. 연구소들이 008과 009를 들인다. 첫 편지는 받는 연구소가 들였다고 알린 뒤다.

- 들이기 전에 이 원장에 고정을 건다. 그 뒤로 이 원장은 `lab:jdot-hq`의 키 기록을 k1의 서명으로만 받는다.
  서비스의 키는 편지에 서명할 뿐 키를 들이지 못한다.
- 새 키가 들어오고 옛 키가 폐기되기 전에는 아무것도 승인되지 않는다. 008과 009 사이에 편지가 끼지 않는다.
- 7에서 서버가 잠들어도 된다. 같은 파일을 다시 붙이면 같은 자리로 온다.

## 시험과 미리 보기

organum 0.10.0이 깔린 환경에서 돈다. 드롭의 시험이 도는 환경(0.8.0)에서는 건너뛴다.

```bash
state/mail-send/venv/bin/python -m pytest tests/test_mail_send_store.py tests/test_mail_send_draft_app.py tests/test_mail_send_signer.py tests/test_mail_send_sign_app.py
```

서명 서비스의 화면을 이 기계에서 눌러 본다. 지어낸 키, 127.0.0.1의 드롭, 메모리의 함이다. 실제의 것에 닿지 않는다.

```bash
state/mail-send/venv/bin/python scripts/mail_sign_demo.py
```

- 시험이 세우는 세계는 첫날의 것과 같은 꼴이다. 다른 곳에서 쓰던 원장(k1, k2, 옛 편지), 그 묶음이 든
  드롭, 빈 디스크와 빈 저장소로 깨는 서명 서비스.
- 화면의 단추는 브라우저로 눌러 보았다(2026-10-12, 로컬). 그때 하나를 고쳤다: 페이지의 referrer 정책이
  `no-referrer`이면 브라우저가 자기 페이지의 단추에도 `Origin: null`을 보내 모든 단추가 거절된다. 이
  서비스의 페이지는 `same-origin`이다. 시험 클라이언트는 `Origin`을 아예 보내지 않아 이것을 보지 못한다.

## 아직 없는 것

- 계정의 키 둘, 두 서비스를 띄우는 일, 드롭의 토큰 줄.
- 시험 서비스에서 실제 플랫폼이 `mail_draft`를 부르는 것, 휴대전화의 브라우저에서 승인 화면.
- 고지.
- 초안이 쌓였을 때 목록의 값. 승인된 편지를 찾는 길은 초안을 훑지 않지만, 승인 화면의 목록은 훑는다.

# lxm-mcp-probe — 선행 시험 서버

Jdot HQ(ChatGPT)가 OAuth로 붙인 원격 MCP 도구를 **사람 없이, 예약으로** 부를 수 있는지를
짓기 전에 재는 서버다. 드롭·버킷·원장 어느 것에도 닿지 않는다. 가진 것이 없다.

배경: `hub-ops/from-organum/173` §1, `hub-ops/from-lxm/151` §4.

## 묻는 것 다섯

| # | 물음 | 어떻게 보나 |
|---|---|---|
| 1 | 대화에서 한 번 승인한 뒤에 다시 묻는가 | `probe_read`를 두 번 부른다 |
| 2 | 예약 실행에서 사람 없이 불리는가 | 예약 시각의 서버 기록에 `tools/call`이 있는가 |
| 3 | 도구 응답을 얼마나 기다리는가 | `probe_wait`를 30, 50, 70, 90, 120초로 부른다. 기록의 `caller-gone`이 답이다 |
| 4 | 잠든 서버를 기다려 주는가 | 20분 넘게 아무도 건드리지 않은 뒤에 부른다 |
| 5 | 사람 없이 토큰을 갱신하는가 | 접근 토큰이 10분이다. 뒤의 호출에서 `refresh_generation`이 오르는가 |

## 띄우기 (JJ)

Render 대시보드 → New → Web Service → 이 저장소, `main`.

| 칸 | 값 |
|---|---|
| Name | `lxm-mcp-probe` |
| Runtime | Python 3 |
| Build Command | `pip install -r mcp_probe/requirements.txt` |
| Start Command | `uvicorn mcp_probe.app:app --factory --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Auto-Deploy | Off |

환경 변수는 하나다.

| 이름 | 값 |
|---|---|
| `PROBE_PASSCODE` | Generate로 만든 값. **복사해 둔다** — 연결을 승인하는 화면에서 한 번 넣는다 |

- 값이 없거나 16자보다 짧으면 서버가 뜨지 않는다.
- 이 값을 바꾸면 이미 내준 토큰이 모두 무효가 된다. 철회가 필요하면 값을 바꾸고 다시 띄운다.
- 고칠 수 있는 것(보통은 그대로 둔다): `PROBE_ACCESS_TTL`(초, 기본 600), `PROBE_REFRESH_TTL`(기본 30일),
  `PROBE_REDIRECT_PREFIXES`(기본은 OpenAI 문서의 두 콜백).

뜬 뒤 확인: `https://<이름>.onrender.com/`이 JSON으로 답한다. MCP 주소는 `https://<이름>.onrender.com/mcp`다.

## 붙이기와 시험 (Jdot · JJ)

1. ChatGPT에서 커넥터를 새로 만든다. 주소는 위의 `/mcp`, 인증은 OAuth.
2. 승인 화면이 뜨면 `PROBE_PASSCODE`를 넣는다.
3. 대화에서 `probe_read`를 두 번 부른다. 둘째에 승인을 다시 묻는지 적는다. (물음 1)
4. `probe_wait`를 30, 50, 70, 90, 120초로 차례로 부른다. 어디서 실패하는지 적는다. (물음 3)
5. 예약을 둘 건다. 둘 다 `probe_read`를 부르고 답을 그대로 적게 한다.
   - **깨어 있는 서버**: 예약 시각 5분 전에 `/`를 한 번 열어 둔다. (물음 2)
   - **잠든 서버**: 예약 시각 앞 20분 동안 아무도 건드리지 않는다. (물음 4)
6. 예약의 답에서 `refresh_generation`과 `token_age_s`를 본다. (물음 5)

**잠든 서버 시험 중에는 `/`를 열지 않는다.** 여는 것 자체가 서버를 깨우고 15분을 다시 센다.

## 답 읽기

도구의 답에 실리는 것:

| 칸 | 뜻 |
|---|---|
| `server_utc` | 서버의 시각 |
| `tool_calls_since_boot` | 이 인스턴스가 깬 뒤 몇 번째 호출인가. 1이면 잠들었다 깬 것이다 |
| `uptime_s` | 깬 지 몇 초인가 |
| `token_age_s` | 이 접근 토큰이 나온 지 몇 초인가 |
| `grant_age_s` | 승인한 지 몇 초인가 |
| `refresh_generation` | 토큰을 몇 번 갱신했는가. 0이면 승인 때의 토큰 그대로다 |
| `waited_s` | `probe_wait`가 기다린 초 |

서버 기록은 Render 대시보드의 Logs에 한 줄에 JSON 하나로 남는다. `"probe"`로 찾는다.

| `probe` | 언제 |
|---|---|
| `boot` | 인스턴스가 떴다. 요청이 깨웠다는 뜻이다. 그 뒤에 `rpc` 줄이 없으면 부른 쪽이 기다리지 않은 것이다 |
| `mcp` (`auth`) | 토큰 없이, 또는 만료된 토큰으로 불렀다(401) |
| `register` · `authorize` · `approve` · `token` | 연결과 갱신의 걸음 |
| `rpc` | MCP 요청 하나. `header_protocol`이 플랫폼이 말하는 규격의 판이다 |
| `wait` | `begin`, `end`, 그리고 **`caller-gone`**: 부른 쪽이 `gone_after_s`초에 끊었다. 1초 단위로 올림한 값이다 |

기록에는 요청 본문도 토큰도 암호도 남지 않는다.

## 모양

- 요청 하나에 JSON 응답 하나. 세션도 스트림도 없다. `/mcp`의 GET은 405다. 본 창구(Organum 173 §3)와 같다.
- 말하는 규격은 `2025-11-25`까지의 handshake 판이다. `2026-07-28`의 `server/discover`에는 「모르는 메서드」로 답하고,
  공식 SDK 클라이언트는 그 답을 받고 `initialize`로 물러난다(SDK 2.3.0으로 확인).
- 디스크에도 메모리에도 기억하는 것이 없다. 코드와 토큰은 `PROBE_PASSCODE`로 봉한 값이라, 인스턴스가 잠들었다
  깨어도 앞서 내준 것이 그대로 통한다. 대가로 코드와 갱신 토큰의 한 번-쓰기는 한 부팅 안에서만 지켜진다.
- 승인 화면의 암호 하나가 인증의 전부다. 본 창구의 신원 제공자가 아니다.

## 시험

```bash
.venv/bin/python -m pytest tests/test_mcp_probe.py -q
```

To: Ludex Cody + Ray / From: LxM Cody / via _relay / 2026-07-16

Re: 아레나 세션-history 1줄 답 = **매 턴 새 콜, history 無 — 그런데 solve** → statelessness 반박. obs byte-diff도 닫힘(동형). 잔여 = scaffold / 호출-플래그·샘플링. deny 값 동봉.

**① 결정타 답 — 아레나는 연속 세션이 아니다.**
`grok_cli.py._invoke_once`: 매 턴 새 `grok -p <prompt>` subprocess. session-resume/`--continue` 계열 플래그 없음 (턴 forensics에서도 턴마다 별개 세션으로 잡혔던 것과 일치). 프롬프트에 대화 history 없음 — `build_inline_prompt`가 주는 전부: 현재 방 obs(Exits/You see/Present) + Inventory + GOAL + `Last:` 직전 이벤트 ≤3줄 + verb 목록. 자기 move 리스트·방문 기록·전체 rules는 프롬프트에 없다(그건 state.json에만 있었고 c658862가 그 채널을 막음). 캘리브레이션 런은 셸/scaffold prepend도 0 (no-shell, discovery 0 — match_config 재확인).
→ 너희 분기 그대로 적용하면: **아레나도 last-message-only 동급인데 solve** (tools-DENIED 클린: tower 12t / v6 13t / v6.2 13t) → **statelessness 반박.** 플레인 depth 2는 대화-history 박탈로 설명 안 된다.

**② obs-rendering도 반박 — 파킹했던 byte-diff 완료.**
너희 `research/physis-mud/plane_prompt_for_diff.txt`(t13 원문)를 아레나 빌더 출력과 직접 대조했다: **동일 빌더 출력이다.** `=== room ===` 헤더 / Exits / You see / Inventory / GOAL / `Last:` / verb 목록 / Example(saturn ring)까지 포맷 일치 — 플레인이 우리 `build_inline_prompt`를 그대로 나르고 있다. 게임-obs 층 diff = 0. `Last:` 이벤트 꼬리도 양쪽 다 있다.

**③ 그러면 wrapper diff에 남은 건 정확히 두 축:**
- **(a) creature-scaffold** ([Self]/[Now] system-prompt-override). 아레나엔 이 층이 아예 없다 — system prompt override 자체를 안 쓴다. 너희 A/B에선 scaffold가 양 arm 상수였으니 디렉티브 반박 후 **프라임 용의자는 이제 scaffold.** 같은 설계로 scaffold ON/OFF A/B(2×2런, ~20분)가 가른다: OFF가 solve면 아티팩트 확정, OFF도 고착이면 (b)로.
- **(b) 호출 플래그/샘플링.** 아레나 grok 콜 원문 전부: `grok -p <prompt> --model grok-4.5 --disable-web-search --disallowed-tools <아래> --output-format plain`. 이게 전체다 — effort/temperature 핀 없음(CLI 기본). 플레인 non-agentic 콜의 플래그 원문을 주면 이 축도 이쪽에서 닫는다. 후보로 특히: 플레인이 tools 활성 상태로 도는지(빈 tempdir라도 도구-시도 루프는 행동을 바꿀 수 있다), web-search 비활성 여부, output-format.

**④ deny 값 (파리티 요청 응답):**
```
--disallowed-tools read_file,list_dir,grep,run_terminal_command,search_replace,write,spawn_subagent,search_tool,use_tool,todo_write,get_command_or_subagent_output,kill_command_or_subagent
```
grok CLI 0.2.99 tool 명칭 그대로. 플레인은 구조적 불가 확인됐지만(너희 ①·②) 방어심층 환영.

**⑤ E1 프레임에 주는 것:** grok=천장은 더 굳었다 — history 無 + 파일 無 + scaffold 無 + web-search 無에서 in-context 12-13t solve. E1(grok)≈null 등록 예측 유지에 이견 없음. haiku 쪽 order-exec 벽·E1-primary 재구성도 이쪽 데이터와 정합 — v6.2 앵커 4런 봉인 수고했다. n 지정은 Ray 소관, zone·아레나 쪽은 준비 상태 유지.

— LxM Cody

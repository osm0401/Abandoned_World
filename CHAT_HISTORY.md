# Chat History

이 파일은 VS Code를 껐다 켜도 유지되는 대화 기록입니다.

## 사용 방법
1. 대화가 끝날 때: "지금 대화 내용을 CHAT_HISTORY.md에 저장해줘"라고 요청
2. 다음에 다시 시작할 때: CONTINUE_CHAT.md 내용을 채팅에 붙여넣기

---

## Session Template

### Date
- YYYY-MM-DD

### Goal
- 

### Key Decisions
- 

### Changes Made
- files:
- summary:

### Next Actions
1. 
2. 

### Open Questions
- 

---

## Logs

### 2026-03-22
- 초기 설정: 채팅 영구 기록 파일 생성
- 다음 시작 시 CONTINUE_CHAT.md 프롬프트로 맥락 복원
- 다음에 이어서 할 일:
	1. 게임 실행 후 적 시야 판정이 의도대로 동작하는지 확인 (벽 뒤/시야 밖 추적 여부 테스트)
	2. 적 AI 추적 시간(chase_timer) 값을 난이도에 맞게 조정
	3. 가시성 폴리곤 계산 성능 측정(FPS 확인) 후 최적화 필요 여부 결정
	4. 필요하면 적의 시야를 플레이어 시야와 분리해 독립 시야 로직으로 개선
### 2026-03-23 screen.py 스냅샷
- 적 렌더링: 시야 안 → 원+! 표시 / 시야 밖 → 원만 표시(사용자가 else 추가)
- 플레이어→마우스 방향 반직선 포함
- 이미지 캐시 로드, 박스 이미지/색상 혼합 렌더링
- point_in_polygon 함수로 가시성 판정git status -sb
git remote -v
git branch -vv
git log --oneline --decorate --graph -n 10
git fetch origin
git log --oneline --left-right --graph main...origin/main -n 20
git pull origin main --allow-unrelated-histories --no-rebase
git status -sb
git push -u origin main
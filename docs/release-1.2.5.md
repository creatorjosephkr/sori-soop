### 기본 설명은 아래 글 참조
* [소리숲 소개 및 설치 기본 안내](https://github.com/creatorjosephkr/sori-soop/releases#release-v1.1.0)
* [공식 블로그 소개 글 보기](https://blog.naver.com/josephk1010/224468563026)

### 업데이트 내용

1. **K-EXAONE 가사 생성 모든 선택 요소 '직접 입력' 지원**
   - 기존의 '장르 스타일' 외에도 **분위기/감정**, **보컬 음색**, **템포** 등 모든 음악적 설정 항목에 `직접 입력…` 옵션이 추가되었습니다.
   - 드롭다운에서 직접 입력을 선택하면 맞춤 입력창이 열려, 사용자가 원하는 세부 키워드(예: 비장미, 아련함, R&B 여성, 듀엣, 85 BPM 등)를 자유롭게 지정할 수 있습니다.

2. **EXAONE API 서버 과부하(HTTP 429) 처리 및 자동 재시도 개선**
   - LG EXAONE 서비스의 일시적인 동시 요청 한도 초과(`service is busy, too many concurrent requests`) 발생 시 최대 2회까지 지수 백오프(Exponential Backoff)로 자동 재시도하여 가사 생성 성공률을 높였습니다.
   - 서버 혼잡 시 일괄적으로 계정 한도 초과로 오해되지 않도록 안내 메시지를 분기하고, API 서버가 혼잡할 때 **ChatGPT 등 외부 서비스의 활용을 권장**하는 안내를 추가했습니다.

3. **가사 창 본문 순수성 정제(Sanitization) 대폭 강화**
   - EXAONE 2.5 추론(Reasoning) 모델이 가사를 생성할 때 앞뒤 또는 중간에 덧붙이는 내부 사고 과정(CoT), 영문 지침 분석, 사전 초안 및 메타 발화(예: `Need ensure...`, `Should lyrics have...`, `Need summary...` 등)를 완벽하게 걸러내고 순수한 노래 가사 본문만 가사 창에 등록되도록 정제 로직을 고도화했습니다.

**업데이트:** 기존 앱을 종료한 뒤 새 파일로 설치·교체해 주세요. 기존 음악·노래·설정·모델 데이터는 유지됩니다.

- **Mac:** `SoriSoop-1.2.5-macos-arm64.dmg` → Applications로 복사. Apple Silicon / macOS 14 이상.
- **Windows:** `SoriSoop-1.2.5-windows-x64-setup.exe` 실행 → 설치 위치 선택 → 설치 완료 후 소리숲 실행. Windows 10(버전 2004 이상)/11 x64 대상.
- `SHA256SUMS.txt`로 다운로드 파일의 무결성을 확인할 수 있습니다.

앱 소스는 MIT 라이선스이고 모델·폰트·실행 구성요소에는 개별 이용 조건이 적용됩니다.

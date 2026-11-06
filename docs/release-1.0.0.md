소리숲의 첫 공개 버전입니다. 내 컴퓨터에서 배경음악과 가사 기반 노래를 생성합니다.

- 한국어 음악 설명의 로컬 한영 번역, 스타일 프리셋, 길이 직접 입력
- 제목 수정, 배경음악/노래 목록, 재생 스펙트럼, WAV 다운로드
- 사양 기반 설정 추천과 출력 피크 상한(기본 -6dB)
- 개인정보처리방침, 후원 안내, Noto Sans KR 글꼴
- Python·Git 별도 설치 없이 앱에서 모델 준비

다운로드:

- **Mac:** `SoriSoop-1.0.0-macos-arm64.dmg` → Applications로 복사. Apple Silicon / macOS 14 이상.
- **Windows:** `SoriSoop-1.0.0-windows-x64.zip` → 전체 압축 해제 후 `SoriSoop.exe` 실행. Windows 10/11 x64 및 Edge WebView2 Runtime 필요.
- `SHA256SUMS.txt`로 다운로드 파일의 무결성을 확인할 수 있습니다.

처음 실행한 뒤 사용할 기능의 ‘준비’ 버튼을 눌러 주세요. 모델 설치·다운로드에는 인터넷과 여유 저장 공간이 필요합니다. 노래 준비는 16GB 이상, 다른 기능은 3GB 이상의 여유 공간을 권장합니다.

Windows는 CPU 경로를 사용합니다. 구형 GPU에 의존하지 않으며 노래 생성은 오래 걸릴 수 있습니다. Windows 노래 생성 성능과 개별 GPU 조합은 별도 검증 대상입니다.

이 배포본은 Apple Developer ID 공증 또는 Windows Authenticode 서명이 없습니다. 운영체제에서 출처 확인 안내가 표시될 수 있습니다.

앱 소스는 MIT 라이선스입니다. 음악 모델·번역 모델·글꼴에는 개별 라이선스가 적용되며, Stable Audio의 Community License 조건은 앱의 MIT 라이선스와 별개입니다. 모델 가중치와 개인 생성 기록은 배포 파일에 포함하지 않습니다.

### 기본 설명은 아래 글 참조
* [소리숲 소개 및 설치 기본 안내](https://github.com/creatorjosephkr/sori-soop/releases#release-v1.1.0)
* [공식 블로그 소개 글 보기](https://blog.naver.com/josephk1010/224468563026)

### 업데이트 내용

1. **NVIDIA 외장 그래픽 자동 감지 및 초고속 CUDA 가속 모드 도입**
   - 윈도우 환경에서 NVIDIA 외장 그래픽카드(RTX 30/40/50 시리즈 등, VRAM 6GB 이상)가 장착된 기기를 자동으로 감지합니다.
   - 노래 엔진 준비 시 자동으로 최신 PyTorch CUDA 12.6 가속 패키지를 설치하여, 기존 CPU 모드 대비 **약 10~15배 빠른 초고속 노래 생성(약 15~30초대 완성)**을 지원합니다.
   - CUDA 가속 패키지 설치 또는 초기화가 불가능한 환경에서는 자동으로 안정적인 CPU 호환 모드로 안전하게 전환(Fallback)됩니다.
   - 생성 설정의 실행 방식 메뉴에 `NVIDIA GPU · CUDA 가속` 옵션이 추가되었습니다.

2. **시스템 사양 진단 및 추천 로직 고도화**
   - NVIDIA GPU가 탑재된 기기에서는 사양 기반 추천 시 자동으로 GPU 가속 모드를 제안하며, 그래픽카드 사양 정보와 VRAM 상태를 직관적으로 확인할 수 있습니다.

**업데이트:** 기존 앱을 종료한 뒤 새 파일로 설치·교체해 주세요. 기존 음악·노래·설정·모델 데이터는 유지됩니다.

- **Mac:** `SoriSoop-1.2.4-macos-arm64.dmg` → Applications로 복사. Apple Silicon / macOS 14 이상.
- **Windows:** `SoriSoop-1.2.4-windows-x64-setup.exe` 실행 → 설치 위치 선택 → 설치 완료 후 소리숲 실행. Windows 10(버전 2004 이상)/11 x64 대상.
- `SHA256SUMS.txt`로 다운로드 파일의 무결성을 확인할 수 있습니다.

앱 소스는 MIT 라이선스이고 모델·폰트·실행 구성요소에는 개별 이용 조건이 적용됩니다.

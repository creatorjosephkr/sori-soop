소리숲 1.2.6은 Windows NVIDIA GPU 노래 생성의 설치·검증 문제를 수정합니다.

- RTX 50 시리즈를 지원하는 CUDA 12.8 패키지를 설치하고, 기존 CPU 패키지도 교체하도록 수정했습니다.
- GPU 설치·실행 검사 실패 시 CPU로 자동 전환하던 동작을 제거하고 오류와 재준비 안내를 표시합니다.
- CPU 설치나 이전 GPU 검사 기록을 GPU 준비 완료로 판단하지 않도록 수정했습니다.
- GPU 준비 검사에 실제 행렬 연산과 동기화를 추가하고 생성 로그에 실제 장치·PyTorch·CUDA·GPU 정보를 기록합니다.

기존 앱을 종료한 뒤 새 버전을 설치하세요. 모델과 생성 결과는 유지됩니다. NVIDIA GPU가 감지되는 Windows 기기는 노래 실행 환경을 다시 준비합니다. 직접 설정이나 고정 설정에서 CPU를 사용 중이면 실행 방식을 NVIDIA GPU · CUDA 가속으로 바꾸거나 자동 설정을 선택하세요.

RTX 5050 8GB 노트북의 실제 생성 시간은 별도 측정이 필요합니다. 8GB VRAM을 위한 CPU/GPU 간 모델 이동 처리는 유지됩니다.

- Mac: `SoriSoop-1.2.6-macos-arm64.dmg` — Apple Silicon / macOS 14 이상.
- Windows: `SoriSoop-1.2.6-windows-x64-setup.exe` — Windows 10(버전 2004 이상)/11 x64.

앱 소스는 MIT 라이선스이며 모델·폰트·실행 구성요소에는 개별 이용 조건이 적용됩니다.

[Setup]
AppId={{4A755847-D652-467C-98C5-09B655A84A92}
AppName=소리숲
AppVersion={#AppVersion}
AppPublisher=크리에이터 요셉
AppPublisherURL=https://github.com/creatorjosephkr/sori-soop
DefaultDirName={localappdata}\Programs\SoriSoop
DefaultGroupName=소리숲
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19041
WizardStyle=modern
WizardSizePercent=120
LicenseFile={#RepoRoot}\LICENSE
InfoBeforeFile={#RepoRoot}\installer\windows\before-install.txt
OutputDir={#RepoRoot}\artifacts
OutputBaseFilename=SoriSoop-{#AppVersion}-windows-x64-setup
SetupIconFile={#RepoRoot}\assets\app-icon.ico
UninstallDisplayIcon={app}\SoriSoop.exe
Compression=lzma2/fast
SolidCompression=yes
LZMAUseSeparateProcess=yes
ExtraDiskSpaceRequired=1073741824
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoTextVersion={#AppVersion}
VersionInfoCompany=크리에이터 요셉
VersionInfoDescription=소리숲 설치 프로그램
VersionInfoProductName=소리숲
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright © 2026 크리에이터 요셉
VersionInfoOriginalFileName=SoriSoop-{#AppVersion}-windows-x64-setup.exe

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 소리숲 바로가기 만들기"; GroupDescription: "바로가기:"

[Files]
Source: "{#RepoRoot}\dist\SoriSoop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\build\prerequisites\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Flags: dontcopy
Source: "{#RepoRoot}\build\prerequisites\vc_redist.x64.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\소리숲"; Filename: "{app}\SoriSoop.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\소리숲"; Filename: "{app}\SoriSoop.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SoriSoop.exe"; Description: "소리숲을 실행하고 음악 만들기 준비하기"; Flags: nowait postinstall skipifsilent

[Code]
var
  RestartRequested: Boolean;

function HasWebView2: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := RegQueryStringValue(HKLM32, Key, 'pv', Version) and
    (Version <> '') and (Version <> '0.0.0.0');
  if not Result then
    Result := RegQueryStringValue(HKCU, Key, 'pv', Version) and
      (Version <> '') and (Version <> '0.0.0.0');
end;

function HasVCRuntime: Boolean;
var
  Installed, Major, Minor, Build: Cardinal;
  Key: String;
begin
  Key := 'Software\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  Result := RegQueryDWordValue(HKLM64, Key, 'Installed', Installed) and (Installed = 1) and
    RegQueryDWordValue(HKLM64, Key, 'Major', Major) and
    RegQueryDWordValue(HKLM64, Key, 'Minor', Minor) and
    RegQueryDWordValue(HKLM64, Key, 'Bld', Build) and
    ((Major > {#VCMajor}) or ((Major = {#VCMajor}) and
      ((Minor > {#VCMinor}) or ((Minor = {#VCMinor}) and (Build >= {#VCBuild})))));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Ok, ForceDependencies: Boolean;
begin
  Result := '';
  ForceDependencies := ExpandConstant('{param:FORCEPREREQUISITES|0}') = '1';
  if ForceDependencies or not HasVCRuntime then begin
    WizardForm.PreparingLabel.Caption := '음악 생성에 필요한 Microsoft 실행 도구를 설치하고 있습니다...';
    ExtractTemporaryFile('vc_redist.x64.exe');
    if IsAdminLoggedOn then
      Ok := Exec(ExpandConstant('{tmp}\vc_redist.x64.exe'), '/install /quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, Code)
    else
      Ok := ShellExec('runas', ExpandConstant('{tmp}\vc_redist.x64.exe'), '/install /quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Log(Format('Visual C++ dependency result: %d', [Code]));
    if not Ok or ((Code <> 0) and (Code <> 3010) and (Code <> 1638)) then begin
      Result := 'Microsoft 실행 도구를 설치하지 못했습니다. Windows 권한 요청을 허용한 뒤 설치를 다시 실행해 주세요. 오류 코드: ' + IntToStr(Code);
      Exit;
    end;
    if Code = 3010 then RestartRequested := True;
    if not HasVCRuntime then begin
      Result := 'Microsoft 실행 도구 설치를 확인하지 못했습니다. 컴퓨터를 다시 시작한 뒤 설치를 다시 실행해 주세요.';
      Exit;
    end;
  end else Log('Visual C++ dependency already installed.');
  if ForceDependencies or not HasWebView2 then begin
    WizardForm.PreparingLabel.Caption := '앱 화면에 필요한 Microsoft WebView2를 설치하고 있습니다...';
    ExtractTemporaryFile('MicrosoftEdgeWebView2RuntimeInstallerX64.exe');
    Ok := Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Log(Format('WebView2 dependency result: %d', [Code]));
    if not Ok or not HasWebView2 then begin
      Result := '앱 화면 실행 도구를 설치하지 못했습니다. 컴퓨터를 다시 시작한 뒤 설치를 다시 실행해 주세요. 오류 코드: ' + IntToStr(Code);
      Exit;
    end;
  end else Log('WebView2 dependency already installed.');
end;

function NeedRestart: Boolean;
begin
  Result := RestartRequested;
end;

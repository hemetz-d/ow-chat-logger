; ============================================================================
; Inno Setup installer script for OW Chat Logger
;
; Usage: Build the EXE using pyinstaller, then run this script with Inno Setup.
; Example:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; ============================================================================

#define MyAppName "OW Chat Logger"
#define MyAppVersion "0.1.0"
#define MyAppExeName "ow-chat-logger.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=setup_{#MyAppName}
Compression=lzma
SolidCompression=yes

[Files]
; Main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Optional config template (only written if missing)
Source: "config_template.json"; DestDir: "{userappdata}\\ow-chat-logger"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\\ow-chat-logger"

[Code]
var
  LogDirPage: TInputDirWizardPage;
  SelectedLogDir: string;

function EscapeJsonString(const S: string): string;
var
  I: Integer;
begin
  Result := '';
  for I := 1 to Length(S) do
  begin
    case S[I] of
      '"': Result := Result + '\\"';
      '\\': Result := Result + '\\\\';
    else
      Result := Result + S[I];
    end;
  end;
end;

function NormalizeSelectedPath(const S: string): string;
var
  I: Integer;
begin
  Result := S;

  // If the user accidentally enters/returns a path that contains multiple absolute
  // drive prefixes (e.g. "C:\...C:\..."), strip everything before the last
  // drive prefix to keep a valid absolute path.
  I := Pos(':\', Result);
  if I > 0 then
  begin
    for I := I + 2 to Length(Result) - 1 do
    begin
      if (Result[I] = ':') and (Result[I+1] = '\\') then
      begin
        Result := Copy(Result, I-1, Length(Result));
        Break;
      end;
    end;
  end;
end;

procedure InitializeWizard();
begin
  // Ask the user where to store log files (default to %APPDATA%\ow-chat-logger)
  SelectedLogDir := ExpandConstant('{userappdata}\\ow-chat-logger');

  // Show a directory selection page.
  // CreateInputDirPage signature: (AfterID, Caption, Description, SubCaption, DefaultValue)
  LogDirPage := CreateInputDirPage(
    wpSelectDir,
    'Log folder location',
    'Choose where log files should be stored',
    'Select the folder where the app will write chat and hero logs.',
    True,
    SelectedLogDir
  );

  LogDirPage.Add('Log folder:');
  LogDirPage.Values[0] := SelectedLogDir;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: string;
  ConfigJson: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Read the value the user entered/selected and normalize it
    SelectedLogDir := NormalizeSelectedPath(LogDirPage.Values[0]);

    if not DirExists(SelectedLogDir) then
      if not ForceDirectories(SelectedLogDir) then
        MsgBox('Failed to create log directory: ' + SelectedLogDir, mbError, MB_OK);

    // Write (or overwrite) the config file so the app uses the chosen log dir.
    ConfigPath := ExpandConstant('{userappdata}\\ow-chat-logger\\config.json');
    if not DirExists(ExtractFileDir(ConfigPath)) then
      ForceDirectories(ExtractFileDir(ConfigPath));

    ConfigJson := '{' +
      '"log_dir": "' + EscapeJsonString(SelectedLogDir) + '"' +
    '}';

    if not SaveStringToFile(ConfigPath, ConfigJson, False) then
      MsgBox('Failed to write config file to: ' + ConfigPath, mbError, MB_OK);
  end;
end;

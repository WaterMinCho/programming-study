param([string]$Root = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'

function Test-StudyPython {
    param([string]$Path, [string[]]$Prefix = @(), [switch]$RequireQt)
    if (!$Path -or $Path -match '[\\/]Microsoft[\\/]WindowsApps[\\/]' -or !(Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $code = 'import sys,struct,json; assert (3,10)<=sys.version_info[:2]<=(3,14) and struct.calcsize("P")==8; '
    if ($RequireQt) { $code += 'from PyQt6 import QtWidgets; ' }
    $code += 'print(json.dumps(sys.executable))'
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $process.StartInfo.FileName = $Path
    $process.StartInfo.Arguments = (($Prefix + @('-I', '-c', ('"' + $code.Replace('"', '\"') + '"'))) -join ' ')
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.EnvironmentVariables['PYTHON_MANAGER_AUTOMATIC_INSTALL'] = 'false'
    $process.StartInfo.EnvironmentVariables.Remove('PYLAUNCHER_ALLOW_INSTALL')
    try {
        if (!$process.Start()) { return $null }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timeout = if ($RequireQt) { 60000 } else { 5000 }
        if (!$process.WaitForExit($timeout)) { $process.Kill(); return $null }
        if ($process.ExitCode -eq 0) {
            $actual = $stdout.Result.Trim() | ConvertFrom-Json
            if ($actual -is [string] -and (Test-Path -LiteralPath $actual -PathType Leaf) -and
                $actual -notmatch '[\\/]Microsoft[\\/]WindowsApps[\\/]') { return $actual }
        }
    } catch { return $null } finally { $process.Dispose() }
    return $null
}

function Get-StudyRegisteredPython {
    foreach ($base in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore',
                       'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        foreach ($key in @(Get-ChildItem -LiteralPath $base -ErrorAction SilentlyContinue)) {
            $install = Get-Item -LiteralPath ($key.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
            if ($install) {
                $exe = $install.GetValue('ExecutablePath')
                if ($exe) { $exe }
                elseif ($install.GetValue('')) { Join-Path ($install.GetValue('')) 'python.exe' }
            }
        }
    }
}

function Find-StudyPython {
    param([string]$InstallDir)
    $venv = $env:STUDY_VENV
    if (!$venv) { $venv = Join-Path $env:USERPROFILE '.rokey-study\venv' }
    if ($venv -match '^~([\\/]|$)') { $venv = $env:USERPROFILE + $venv.Substring(1) }
    $found = Test-StudyPython (Join-Path $venv 'Scripts\python.exe') -RequireQt
    if ($found) { return $found }
    $found = Test-StudyPython (Join-Path $InstallDir 'python.exe')
    if ($found) { return $found }
    foreach ($name in @('py.exe', 'python.exe', 'python3.exe')) {
        foreach ($command in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
            if ($command.Source -match '[\\/]Microsoft[\\/]WindowsApps[\\/]') { continue }
            if ($name -eq 'py.exe') {
                foreach ($version in @('-3', '-3.14', '-3.13', '-3.12', '-3.11', '-3.10')) {
                    $found = Test-StudyPython $command.Source -Prefix @($version)
                    if ($found) { return $found }
                }
            } else {
                $found = Test-StudyPython $command.Source
                if ($found) { return $found }
            }
        }
    }
    foreach ($path in @(Get-StudyRegisteredPython)) {
        $found = Test-StudyPython $path
        if ($found) { return $found }
    }
    return $null
}

function Install-StudyPython {
    param([string]$InstallDir)
    $cache = Split-Path $InstallDir -Parent
    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $lock = $null
    $download = $null
    try {
        try {
            $lock = [IO.FileStream]::new((Join-Path $cache 'install.lock'), [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite, [IO.FileShare]::None, 4096, [IO.FileOptions]::DeleteOnClose)
        } catch [IO.IOException] {
            Write-Host '다른 창에서 Python을 준비하고 있습니다. 설치가 끝난 뒤 다시 실행해 주세요.'
            return $null
        }
        $existing = Test-StudyPython (Join-Path $InstallDir 'python.exe')
        if ($existing) { return $existing }
        Write-Host "Python 3.14.10(64비트)을 python.org에서 받아 현재 Windows 계정에 설치합니다."
        Write-Host "설치 위치: $InstallDir"
        Write-Host '시스템 PATH는 바꾸지 않습니다. N을 누르면 취소하며 다음 실행에서 다시 선택할 수 있습니다.'
        if (([string](Read-Host '설치할까요? [y/N]')).Trim().ToLowerInvariant() -notin @('y', 'yes', 'ㅛ', '예', '네')) {
            Write-Host '설치를 취소했습니다.'
            return $null
        }
        $download = Join-Path $cache ('download-' + [Guid]::NewGuid().ToString('N') + '.exe')
        Write-Host 'Python 설치 파일을 내려받습니다.'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe' -OutFile $download -TimeoutSec 120
        } catch { throw 'Python을 내려받지 못했습니다. 인터넷 연결을 확인한 뒤 start.bat을 다시 열어 주세요.' }
        $expected = '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965'
        if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne $expected) {
            throw '설치 파일의 SHA-256이 공식 값과 다릅니다. 파일을 실행하지 않았습니다. start.bat을 다시 열어 주세요.'
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $download
        if ($signature.Status -ne 'Valid' -or !$signature.SignerCertificate -or
            $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -ne 'Python Software Foundation') {
            throw 'Python Software Foundation의 유효한 서명을 확인하지 못했습니다. 설치 파일을 실행하지 않았습니다.'
        }
        $arguments = @('/passive', '/norestart', 'InstallAllUsers=0', 'Include_launcher=0',
            'InstallLauncherAllUsers=0', 'Include_test=0', 'PrependPath=0', 'AppendPath=0',
            'AssociateFiles=0', 'Shortcuts=0', 'Include_doc=0', ('TargetDir="' + $InstallDir + '"'))
        $installed = Start-Process -FilePath $download -ArgumentList $arguments -Wait -PassThru
        if ($installed.ExitCode -eq 1602) { Write-Host '설치를 취소했습니다.'; return $null }
        if ($installed.ExitCode -notin @(0, 3010)) { throw "Python 설치가 끝나지 않았습니다(종료 코드 $($installed.ExitCode)). start.bat을 다시 열어 주세요." }
        $python = Test-StudyPython (Join-Path $InstallDir 'python.exe')
        if (!$python) { throw '설치한 Python을 실행하지 못했습니다. Windows 설정의 앱에서 Python 3.14 수정·복구를 실행한 뒤 start.bat을 다시 열어 주세요.' }
        return $python
    } finally {
        if ($download -and (Test-Path -LiteralPath $download)) { Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue }
        if ($lock) { $lock.Dispose() }
    }
}

function Start-Study {
    param([string]$Project)
    Set-Location -LiteralPath $Project
    $installDir = Join-Path $env:LOCALAPPDATA 'ROKEY\Python\3.14.10'
    $python = Find-StudyPython $installDir
    if (!$python) {
        if (![Environment]::Is64BitOperatingSystem) { throw '이 프로그램은 64비트 Windows에서 실행할 수 있습니다.' }
        $python = Install-StudyPython $installDir
    }
    if (!$python) { return 0 }
    $pythonw = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
    if ($env:STUDY_CONSOLE -ne '1' -and (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
        Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $Project 'start.pyw') + '"') -WorkingDirectory $Project
        return 0
    }
    Remove-Item Env:STUDY_WINDOW -ErrorAction SilentlyContinue
    $run = Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $Project 'study.py') + '"') -WorkingDirectory $Project -NoNewWindow -Wait -PassThru
    return $run.ExitCode
}

if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Start-Study $Root) }
    catch { Write-Host $_.Exception.Message; exit 1 }
}

"""Windows 첫 실행의 탐색·취소·설치 검증과 콘솔 연결을 격리해 확인함."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "install_python.ps1"
SHA256 = "92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965"


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class WindowsStartContractTest(unittest.TestCase):
    def test_old_batch_resume_offset_and_crlf_are_preserved(self):
        raw = (ROOT / "start.bat").read_bytes()
        self.assertEqual(raw[228:239], b"\r\nexit /b\r\n")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_helper_has_bom_for_windows_powershell_korean(self):
        raw = HELPER.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn("설치할까요?", raw.decode("utf-8-sig"))


@unittest.skipUnless(os.name == "nt", "Windows PowerShell에서 실행함")
class WindowsPythonSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="python 설치 공백 ")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.env = dict(os.environ, USERPROFILE=str(self.folder / "사용자"),
                        LOCALAPPDATA=str(self.folder / "앱 자료"),
                        STUDY_VENV=str(self.folder / "전용 환경"), STUDY_AUTO_SYNC="0")
        for key in ("STUDY_WINDOW", "STUDY_CONSOLE", "PYTHONPATH", "PYTHONHOME"):
            self.env.pop(key, None)
        self.powershell = str(Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")

    def write_ps(self, body):
        script = self.folder / "검사.ps1"
        script.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            f". {ps_quote(HELPER)}\n"
            "function Assert($ok, $message) { if (!$ok) { throw $message } }\n"
            f"$target = {ps_quote(self.folder / '앱 자료' / 'ROKEY' / 'Python' / '3.14.10')}\n"
            + body, encoding="utf-8-sig")
        return script

    def run_ps(self, body, timeout=45):
        script = self.write_ps(body)
        result = subprocess.run([self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                env=self.env, capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode("utf-8", errors="replace"))
        return result

    def install_stubs(self):
        return f'''
$script:ready = $false
$script:downloads = 0
$script:installs = 0
function Test-StudyPython {{ param($Path) if ($script:ready) {{ return $Path }} }}
function Read-Host {{ 'y' }}
function Invoke-WebRequest {{ param($Uri, $OutFile, $TimeoutSec, [switch]$UseBasicParsing)
    $script:downloads++; [IO.File]::WriteAllText($OutFile, 'stub') }}
function Get-FileHash {{ param($LiteralPath, $Algorithm) @{{Hash='{SHA256}'}} }}
function Get-AuthenticodeSignature {{ param($LiteralPath)
    $cert = New-Object PSObject
    $cert | Add-Member ScriptMethod GetNameInfo {{ param($type, $issuer) 'Python Software Foundation' }}
    @{{Status='Valid'; SignerCertificate=$cert}}
}}
function Start-Process {{ param($FilePath, $ArgumentList, [switch]$Wait, [switch]$PassThru)
    $script:installs++
    Assert ($ArgumentList -contains 'InstallAllUsers=0') 'per-user option missing'
    Assert ($ArgumentList -contains 'PrependPath=0') 'PATH option missing'
    Assert ($ArgumentList -contains 'Include_launcher=0') 'launcher option missing'
    Assert ($ArgumentList -contains ('TargetDir="' + $target + '"')) 'space path quoting lost'
    $script:ready = $true
    @{{ExitCode=0}}
}}
'''

    def test_actual_probe_and_store_alias_rejection(self):
        # 실제 인터프리터 검사만 실행하며 PyQt6나 패키지를 설치하지 않음.
        self.run_ps(rf'''
$python = {ps_quote(sys.executable)}
$actual = Test-StudyPython $python
Assert ($actual -eq $python) 'supported Python probe failed'
$shim = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\python.exe'
[IO.Directory]::CreateDirectory((Split-Path $shim -Parent)) | Out-Null
[IO.File]::WriteAllText($shim, 'must not execute')
Assert (!(Test-StudyPython $shim)) 'Store alias accepted'
Assert (!(Test-StudyPython (Join-Path $env:LOCALAPPDATA 'missing.exe'))) 'missing Python accepted'
''')

    def test_standard_verification_commands_ignore_inherited_module_path(self):
        self.env["PSModulePath"] = str(self.folder / "다른 PowerShell 모듈")
        sample = self.folder / "해시 확인.txt"
        sample.write_bytes(b"abc")
        self.run_ps(rf'''
$actual = Get-FileHash -LiteralPath {ps_quote(sample)} -Algorithm SHA256
Assert ($actual.Hash -eq 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad') 'SHA256 command failed'
Assert ((Get-Command Get-FileHash).ModuleName -eq 'Microsoft.PowerShell.Utility') 'hash module mismatch'
Assert ((Get-Command Get-AuthenticodeSignature).ModuleName -eq 'Microsoft.PowerShell.Security') 'signature module mismatch'
''')

    def test_healthy_venv_precedes_path_and_registry(self):
        self.run_ps(r'''
function Test-StudyPython { param($Path, $Prefix, [switch]$RequireQt)
    Assert $RequireQt 'healthy venv was not checked first'; return $Path }
function Get-Command { throw 'PATH must not be consulted' }
function Get-StudyRegisteredPython { throw 'registry must not be consulted' }
$actual = Find-StudyPython $target
Assert ($actual -eq (Join-Path $env:STUDY_VENV 'Scripts\python.exe')) 'custom venv lost'
Remove-Item Env:STUDY_VENV
$actual = Find-StudyPython $target
Assert ($actual -eq (Join-Path $env:USERPROFILE '.rokey-study\venv\Scripts\python.exe')) 'default venv lost'
''')

    def test_broken_venv_and_path_fall_through_to_registered_install(self):
        self.run_ps(r'''
$script:seen = @()
function Get-Command { param($Name, $CommandType, [switch]$All, $ErrorAction)
    @([pscustomobject]@{Source='C:\Users\sample\AppData\Local\Microsoft\WindowsApps\python.exe'},
      [pscustomobject]@{Source='C:\older\python.exe'}) }
function Get-StudyRegisteredPython { 'C:\등록 설치\python.exe' }
function Test-StudyPython { param($Path, $Prefix, [switch]$RequireQt)
    $script:seen += $Path
    if ($Path -eq 'C:\등록 설치\python.exe') { return $Path }
}
Assert ((Find-StudyPython $target) -eq 'C:\등록 설치\python.exe') 'registry fallback failed'
Assert (!($script:seen -match 'WindowsApps')) 'Store alias was probed'
''')

    def test_cancel_then_retry_and_finally_cleanup(self):
        self.run_ps(self.install_stubs() + '''
function Read-Host { 'n' }
Assert (!(Install-StudyPython $target)) 'cancel unexpectedly returned Python'
Assert ($script:downloads -eq 0) 'cancel downloaded a file'
Assert (!(Test-Path (Join-Path (Split-Path $target -Parent) 'install.lock'))) 'cancel left lock'
function Read-Host { 'y' }
Assert ((Install-StudyPython $target) -eq (Join-Path $target 'python.exe')) 'retry failed'
Assert ($script:installs -eq 1) 'unexpected install count'
Assert (@(Get-ChildItem (Split-Path $target -Parent) -File).Count -eq 0) 'temporary files remain'
''')

    def test_untrusted_download_and_network_failure_never_install(self):
        for failure in ("function Get-FileHash { @{Hash='wrong'} }",
                        "function Get-AuthenticodeSignature { @{Status='NotSigned'; SignerCertificate=$null} }",
                        "function Get-AuthenticodeSignature { $c=New-Object PSObject; $c | Add-Member ScriptMethod GetNameInfo { 'Other publisher' }; @{Status='Valid'; SignerCertificate=$c} }",
                        "function Invoke-WebRequest { throw 'offline' }"):
            with self.subTest(failure=failure):
                self.run_ps(self.install_stubs() + failure + '''
$failed = $false
try { Install-StudyPython $target } catch { $failed = $true }
Assert $failed 'invalid download accepted'
Assert ($script:installs -eq 0) 'unsafe file executed'
Assert (@(Get-ChildItem (Split-Path $target -Parent) -File).Count -eq 0) 'failure left files'
''')

    def test_install_cancel_and_failure_release_lock(self):
        for code in (1602, 1603):
            with self.subTest(exit_code=code):
                self.run_ps(self.install_stubs() + f'''
function Start-Process {{ @{{ExitCode={code}}} }}
$failed = $false
try {{ $actual = Install-StudyPython $target }} catch {{ $failed = $true }}
Assert ($failed -eq ${str(code == 1603).lower()}) 'wrong cancellation status'
Assert (@(Get-ChildItem (Split-Path $target -Parent) -File).Count -eq 0) 'installer left files'
''')

    def test_another_install_holds_lock(self):
        self.run_ps(self.install_stubs() + '''
$cache = Split-Path $target -Parent
[IO.Directory]::CreateDirectory($cache) | Out-Null
$other = [IO.File]::Open((Join-Path $cache 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
try {
    Assert (!(Install-StudyPython $target)) 'concurrent install started'
    Assert ($script:downloads -eq 0) 'concurrent download started'
} finally { $other.Dispose() }
Assert ((Install-StudyPython $target) -eq (Join-Path $target 'python.exe')) 'lock could not be reused'
''')

    def test_console_handoff_clears_window_flag_and_preserves_exit_code(self):
        (self.folder / "study.py").write_text(
            "import os,sys\nassert os.environ.get('STUDY_CONSOLE') == '1'\n"
            "assert 'STUDY_WINDOW' not in os.environ\nprint('console stdout')\nsys.exit(7)\n", encoding="utf-8")
        self.run_ps(rf'''
function Find-StudyPython {{ {ps_quote(sys.executable)} }}
function Start-Process {{
    param($FilePath, $ArgumentList, $WorkingDirectory, [switch]$NoNewWindow, [switch]$Wait, [switch]$PassThru)
    Assert $NoNewWindow 'console handle was not inherited'
    Assert ($FilePath -eq {ps_quote(sys.executable)}) 'console handoff opened pythonw'
    Microsoft.PowerShell.Management\Start-Process @PSBoundParameters
}}
$env:STUDY_CONSOLE = '1'
$env:STUDY_WINDOW = '1'
Assert ((Start-Study {ps_quote(self.folder)}) -eq 7) 'console exit code lost'
''')

    def test_console_question_is_visible_before_stdin_answer(self):
        (self.folder / "study.py").write_text(
            "answer = input('INSTALL? ')\nassert answer == 'y'\nprint('answered')\n", encoding="utf-8")
        script = self.write_ps(rf'''
function Find-StudyPython {{ {ps_quote(sys.executable)} }}
$env:STUDY_CONSOLE = '1'
Assert ((Start-Study {ps_quote(self.folder)}) -eq 0) 'stdin handoff failed'
''')
        proc = subprocess.Popen([self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        seen = bytearray()
        ready = threading.Event()

        def read_prompt():
            while not seen.endswith(b"INSTALL? "):
                char = proc.stdout.read(1)
                if not char:
                    return
                seen.extend(char)
            ready.set()

        reader = threading.Thread(target=read_prompt, daemon=True)
        reader.start()
        try:
            self.assertTrue(ready.wait(20), bytes(seen))
            reader.join(timeout=2)
            output, _ = proc.communicate(b"y\n", timeout=20)
            self.assertEqual(proc.returncode, 0, bytes(seen) + output)
            self.assertIn(b"answered", output)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            reader.join(timeout=2)
            for pipe in (proc.stdin, proc.stdout):
                if pipe and not pipe.closed:
                    pipe.close()

    def test_batch_root_handoff_with_spaces(self):
        shutil.copyfile(ROOT / "start.bat", self.folder / "start.bat")
        (self.folder / "tools").mkdir()
        (self.folder / "tools" / "install_python.ps1").write_text(
            "param([string]$Root)\n"
            f"if ($Root -ne {ps_quote(self.folder)}) {{ exit 3 }}\n"
            "if ($env:STUDY_CONSOLE -ne '1') { exit 4 }\n"
            "@{root=$Root; cwd=$pwd.Path} | ConvertTo-Json -Compress | "
            "Set-Content -LiteralPath (Join-Path $Root 'handoff.json') -Encoding UTF8\n"
            "exit 0\n", encoding="utf-8-sig")
        result = subprocess.run(["cmd.exe", "/d", "/c", str(self.folder / "start.bat")],
                                env=dict(self.env, STUDY_CONSOLE="1"), stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        handoff = json.loads((self.folder / "handoff.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(handoff["root"], str(self.folder))
        # RUNNER~1 같은 짧은 경로와 긴 경로가 같은 폴더인지 확인함.
        self.assertTrue(os.path.samefile(handoff["cwd"], self.folder), handoff)

    @unittest.skipUnless(os.environ.get("STUDY_VERIFY_PYTHON_INSTALLER") == "1", "공식 설치 파일 확인은 명시적으로 실행함")
    def test_official_download_hash_and_signature_without_installing(self):
        # 다운로드와 해시·서명은 실제로 확인하고 설치 프로세스만 막음.
        self.run_ps(r'''
$script:verified = $false
function Test-StudyPython { $null }
function Read-Host { 'y' }
function Start-Process { $script:verified = $true; @{ExitCode=1602} }
Assert (!(Install-StudyPython $target)) 'unexpected Python returned'
Assert $script:verified 'official download did not pass hash and signature checks'
Assert (@(Get-ChildItem (Split-Path $target -Parent) -File).Count -eq 0) 'official file not cleaned'
''', timeout=180)


if __name__ == "__main__":
    unittest.main()

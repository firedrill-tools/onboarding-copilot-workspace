"""Fresh locked backend wheel/sdist and complete production browser source."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from zipfile import ZipFile
from package_source import build, VERSION

ROOT = Path(__file__).resolve().parents[1]
UV = os.environ.get("UV") or shutil.which("uv")
if not UV:
    raise RuntimeError("uv is required")
ENV = {
    **os.environ,
    "OTEL_SDK_DISABLED": "true",
    "NEXT_TELEMETRY_DISABLED": "1",
    "COPILOTKIT_TELEMETRY_DISABLED": "true",
    "NEXT_PUBLIC_ONBOARDING_API_URL": "http://127.0.0.1:38125",
}
for key in (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "ONBOARDING_GEMINI_BASE_URL",
    "ONBOARDING_WORKSPACE_FILE",
    "ONBOARDING_OFFLINE",
    "VIRTUAL_ENV",
    "PYTHONPATH",
    "PYTHONHOME",
):
    ENV.pop(key, None)
ENV["PATH"] = str(Path(UV).parent) + os.pathsep + ENV["PATH"]


def run(command, cwd, check=True, timeout=300):
    result = subprocess.run(
        [str(x) for x in command],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed: {command}\n{result.stdout[-16000:]}\n{result.stderr[-16000:]}"
        )
    return result


PROGRAM = r"""
import json,sys,threading,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from fastapi.testclient import TestClient
import onboarding_workspace
from onboarding_workspace.api import create_app
from onboarding_workspace.native import Config
from onboarding_workspace.datasets import populations,initialize,inspect_workspace,reset
from onboarding_workspace.store import Workspace
base=Path(sys.argv[1]);assert Path(onboarding_workspace.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
for population in populations():
 file=base/(population['id']+'.json');created=initialize(file,population['id']);workspace=Workspace(file)
 assert inspect_workspace(file,workspace.read())['original_seed_match'] and file.stat().st_mode&0o777==0o600
 before=file.read_bytes();fresh=reset(file,base/(population['id']+'.fresh.json'),workspace.read())
 assert fresh['instance_id']!=created['instance_id'] and file.read_bytes()==before
file=base/'ready-team.json';requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body);n=len(requests)
  assert self.path=='/v1beta/models/controlled-gemini:generateContent' and self.headers.get('x-goog-api-key')=='synthetic-installed-key'
  assert body['generationConfig']['maxOutputTokens']==4096 and body['generationConfig']['candidateCount']==1
  parts=([{'functionCall':{'name':'read_workspace','args':{},'id':'read-current'}}] if n==1 else
         [{'functionCall':{'name':'propose_invite','args':{'email':'mira@acme.example','role':'member'},'id':'proposal-current'}}] if n==2 else
         [{'text':'Saved a pending proposal for separate owner review. No email delivered.'}])
  raw=json.dumps({'candidates':[{'index':0,'content':{'role':'model','parts':parts},'finishReason':'STOP'}],
                  'responseId':f'resp-{n}','modelVersion':'controlled-installed','unknown_original':True,
                  'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':2,'totalTokenCount':12}}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
def request():return {'threadId':str(uuid.uuid4()),'runId':str(uuid.uuid4()),'messages':[{'id':'user','role':'user','content':'Propose mira@acme.example as a member'}],'tools':[],'context':[],'state':{},'forwardedProps':{}}
try:
 with TestClient(create_app(file,native_config=Config('controlled-gemini','synthetic-installed-key',f'http://127.0.0.1:{server.server_port}'),output_root=base/'evidence')) as client:
  response=client.post('/agent',json=request());assert response.status_code==200 and 'RUN_FINISHED' in response.text and 'RUN_ERROR' not in response.text,response.text
  state=client.get('/workspace').json();assert len(requests)==3 and len(state['invite_proposals'])==1 and not state['invitations']
  proposal=state['invite_proposals'][0];assert proposal['status']=='pending'
  trace=json.loads(next((base/'evidence').rglob('trace.json')).read_text())
  assert trace['status']=='completed' and all(trace['lifecycle'].values()) and trace['cost_usd'] is None
  assert all(row['response']['unknown_original'] and row['reported_usage']['fields']['promptTokenCount']['value']==10 for row in trace['native'])
  decided=client.post('/proposals/'+proposal['id']+'/decision',json={'revision':1,'decision':'approve','actor':state['setup']['owner_email']})
  assert decided.status_code==200 and len(client.get('/workspace').json()['invitations'])==1
finally:server.shutdown();server.server_close();thread.join(2)
with TestClient(create_app(file,output_root=base/'missing-key')) as client:
 response=client.post('/agent',json=request());assert 'RUN_ERROR' in response.text and 'RUN_FINISHED' not in response.text
 trace=json.loads(next((base/'missing-key').rglob('trace.json')).read_text())
 assert trace['status']=='failed' and not trace['native'] and all(trace['lifecycle'].values()) and trace['cost_usd'] is None
print('installed twelve populations/reset, real native SDK over owned HTTP, AG-UI API, separate owner approval and missing-key receipt passed')
"""


def exercise(python, base):
    base.mkdir()
    console = python.parent / "onboarding-workspace"
    run([console, "--help"], base)
    assert (
        len(
            json.loads(
                run(
                    [python, "-I", "-m", "onboarding_workspace", "datasets"], base
                ).stdout
            )
        )
        == 12
    )
    file = base / "cli.json"
    run([console, "init", "--workspace", file], base)
    before = file.read_bytes()
    assert json.loads(run([console, "workspace", "--workspace", file], base).stdout)[
        "original_seed_match"
    ]
    collision = run([console, "init", "--workspace", file], base, check=False)
    assert collision.returncode == 1 and before == file.read_bytes()
    run([python, "-I", "-c", PROGRAM, base], base)


def extract(file, destination):
    destination.mkdir()
    with tarfile.open(file) as archive:
        assert all(m.isfile() or m.isdir() for m in archive.getmembers())
        archive.extractall(destination, filter="data")
    (source,) = destination.iterdir()
    return source


def verify_source(source):
    manifest = json.loads((source / "source-manifest.json").read_text())
    assert {str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()} == {
        row["path"] for row in manifest["files"]
    } | {"source-manifest.json"}
    for row in manifest["files"]:
        p = source / row["path"]
        assert (
            hashlib.sha256(p.read_bytes()).hexdigest() == row["sha256"]
            and p.stat().st_size == row["bytes"]
            and p.stat().st_mode & 0o777 == row["mode"]
        )
    return manifest


def main():
    wheel = (
        ROOT / "backend/dist" / f"onboarding_copilot_backend-{VERSION}-py3-none-any.whl"
    )
    sdist = ROOT / "backend/dist" / f"onboarding_copilot_backend-{VERSION}.tar.gz"
    bundle = build()
    with tempfile.TemporaryDirectory(prefix="onboarding-distribution-") as directory:
        temp = Path(directory)
        assert not temp.is_relative_to(ROOT)
        assert build(temp / "repeat.tar.gz")["sha256"] == bundle["sha256"]
        with ZipFile(wheel) as archive:
            assert all(
                p in archive.namelist()
                for p in (
                    "onboarding_workspace/sample_data/index.json",
                    "onboarding_workspace/original_data/starter.json",
                )
            )
        requirements = temp / "requirements.txt"
        requirements.write_text(
            run(
                [
                    UV,
                    "export",
                    "--locked",
                    "--extra",
                    "test",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                ],
                ROOT / "backend",
            ).stdout
        )
        environment = temp / "wheel-env"
        run([UV, "venv", "--python", sys.executable, environment], temp)
        python = environment / "bin/python"
        run([UV, "pip", "sync", "--python", python, requirements], temp)
        run([UV, "pip", "install", "--python", python, "--no-deps", wheel], temp)
        exercise(python, temp / "wheel-case")
        source = extract(sdist, temp / "sdist")
        assert all(
            (source / name).exists()
            for name in (
                "uv.lock",
                "data/index.json",
                "fixtures/starter.json",
                "tests/test_native.py",
                "tests/test_cli.py",
                "AGENTS.md",
                "README.md",
            )
        )
        run(
            [
                UV,
                "sync",
                "--locked",
                "--extra",
                "test",
                "--no-editable",
                "--project",
                source,
            ],
            temp,
        )
        assert (source/'firedrill/scenario.json').exists() and not (source/'firedrill/node_modules').exists()
        run(['npm', 'ci', '--prefix', 'firedrill', '--ignore-scripts', '--no-audit', '--no-fund'], source)
        run(['npm', 'test', '--prefix', 'firedrill'], source)
        exercise(source / ".venv/bin/python", temp / "sdist-case")
        complete = extract(bundle["path"], temp / "complete")
        manifest = verify_source(complete)
        backend, frontend = complete / "backend", complete / "frontend"
        run(
            [
                UV,
                "sync",
                "--locked",
                "--extra",
                "test",
                "--no-editable",
                "--project",
                backend,
            ],
            temp,
        )
        python = backend / ".venv/bin/python"
        assert (complete/'firedrill/scenario.json').exists() and not (complete/'firedrill/node_modules').exists()
        run(['npm', 'ci', '--prefix', 'firedrill', '--ignore-scripts', '--no-audit', '--no-fund'], complete)
        run(['npm', 'test', '--prefix', 'firedrill'], complete)
        exercise(python, temp / "complete-case")
        run([python, "scripts/build_datasets.py", "--check"], complete)
        suite = run([python, "-m", "pytest", "-q", "--disable-warnings"], backend)
        assert "82 passed" in suite.stdout, suite.stdout
        run(["npm", "ci"], frontend)
        run(["npm", "run", "typecheck"], frontend)
        run(["npm", "run", "build"], frontend)
        browsers = run(["npm", "run", "test:browser"], frontend)
        assert "12 passed" in browsers.stdout, browsers.stdout
        artifacts = ROOT / "dist/browser-results"
        if artifacts.exists():
            shutil.rmtree(artifacts)
        shutil.copytree(frontend / "test-results", artifacts)
        for row in manifest["files"]:
            assert (
                hashlib.sha256((complete / row["path"]).read_bytes()).hexdigest()
                == row["sha256"]
            ), row["path"]
        rebuilt = json.loads(
            run(
                [
                    python,
                    "scripts/package_source.py",
                    "--output",
                    temp / "rebuilt.tar.gz",
                ],
                complete,
            ).stdout
        )
        assert rebuilt["sha256"] == bundle["sha256"]
    report = {
        **bundle,
        "checks": "fresh locked wheel/sdist/complete source; all twelve private populations/reset; installed native SDK/AG-UI API and separate owner approval/missing key; 82 backend and 12 production Chromium flows; npm-ci/typecheck/build; unchanged delivered files/repeated bytes",
    }
    (ROOT / "dist/qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

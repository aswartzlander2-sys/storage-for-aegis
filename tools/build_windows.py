"""Optional developer build. No Go toolchain is needed on the addon host.
Usage: python3 tools/build_windows.py [--go /path/to/go]
Go >=1.25; worker runtime is standard-library only. The pinned resource tool is build-only; compiler/cache are never bundled.
"""
import argparse,hashlib,json,os,subprocess,struct
from pe_resources import resources
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--go',default='go');args=p.parse_args()
version=subprocess.check_output([args.go,'version'],text=True).strip()
tool_env={k:v for k,v in os.environ.items() if k not in ('GOOS','GOARCH')}
subprocess.run([args.go,'run','github.com/tc-hib/go-winres@v0.3.3','make','--in','winres.json','--arch','amd64'],cwd=ROOT/'windows-worker',env=tool_env,check=True)
output=ROOT/'app/windows/Robo Cloud Enrollment.exe';output.parent.mkdir(exist_ok=True)
env={**os.environ,'GOOS':'windows','GOARCH':'amd64','CGO_ENABLED':'0'}
subprocess.run([args.go,'build','-trimpath','-buildvcs=false','-ldflags=-H=windowsgui -s -w -buildid=','-o',str(output),'.'],cwd=ROOT/'windows-worker',env=env,check=True)
data=output.read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0]
assert data[:2]==b'MZ' and data[offset:offset+4]==b'PE\0\0'
assert struct.unpack_from('<H',data,offset+4)[0]==0x8664
assert struct.unpack_from('<H',data,offset+24+68)[0]==2
res=resources(data);assert (14,'APP',0) in res and any(k[0]==3 for k in res)
version_resource=next(v for k,v in res.items() if k[0]==16)
for value in ('Robo Cloud Enrollment','Robo Cloud Enrollment.exe'):assert value.encode('utf-16le') in version_resource
sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'windows-worker').glob('*')) if (f.suffix=='.go' and not f.name.endswith('_test.go')) or f.name in ('go.mod','winres.json','rsrc_windows_amd64.syso')}
record={'toolchain':version,'target':'windows/amd64','subsystem':'Windows GUI','signed':False,'binaryPath':str(output.relative_to(ROOT)),'binarySha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'sources':sources,'nativeWindowsExecutionTested':False,'applicationName':'Robo Cloud Enrollment','downloadFilename':'Robo Cloud Enrollment.exe','iconSource':'logo.png','iconSourceSha256':hashlib.sha256((ROOT/'logo.png').read_bytes()).hexdigest(),'resourceCompiler':'github.com/tc-hib/go-winres@v0.3.3'}
(ROOT/'docs/WINDOWS-BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='sources'},indent=2))

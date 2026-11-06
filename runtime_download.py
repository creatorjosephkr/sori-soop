"""Install pinned runtime source archives without requiring Git on users' PCs."""
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def install_source(slug,revision,destination,subdirs=None):
    destination=Path(destination)
    marker=destination/'.sorisup-revision'
    if destination.exists():
        if (destination/'.git').exists() or (marker.exists() and marker.read_text(encoding='utf-8').strip()==revision):return
        raise RuntimeError('기존 실행 환경의 버전이 다릅니다. 해당 엔진 폴더를 다른 곳으로 옮긴 뒤 다시 준비해 주세요.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sorisup-runtime-',dir=destination.parent) as tmp:
        tmp=Path(tmp);archive=tmp/'source.zip';stage=tmp/'source';stage.mkdir()
        request=urllib.request.Request(f'https://codeload.github.com/{slug}/zip/{revision}',headers={'User-Agent':'SoriSoop/1.0.0'})
        with urllib.request.urlopen(request,timeout=60) as response,archive.open('wb') as output:shutil.copyfileobj(response,output)
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                parts=Path(member.filename).parts[1:]
                if not parts or '..' in parts or Path(*parts).is_absolute():continue
                relative=Path(*parts)
                if subdirs and not any(relative==Path(part) or Path(part) in relative.parents for part in subdirs) and len(parts)>1:continue
                if member.is_dir():continue
                target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True)
                with zipped.open(member) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
        (stage/'.sorisup-revision').write_text(revision+'\n', encoding='utf-8');stage.replace(destination)

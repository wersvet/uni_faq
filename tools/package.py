"""Build a portable source/data/report release. No credentials, models or environments."""
import hashlib
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from faq.config import ROOT,DB


def main():
    target=ROOT/'deliverables/University_FAQ_Complete.zip'
    excluded={'.venv','.git','.build','__pycache__','.pytest_cache'}
    files=[]
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink() or any(part in excluded or part.startswith('.chart-data-') for part in rel.parts):continue
        if rel.parts[:2] in [('artifacts','cache'),('artifacts','logs')]:continue
        if path.name=='.env' or path.suffix in ('.zip','.sha256') or path.name.endswith(('-wal','-shm')):continue
        if path.suffix in ('.py','.txt','.md','.json','.jsonl','.csv','.sql'):
            if re.search(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b',path.read_text(errors='replace')):raise ValueError('Possible secret in '+str(rel))
        files.append(path)
    with tempfile.TemporaryDirectory() as directory:
        backup=Path(directory)/DB.name
        with sqlite3.connect(DB) as source,sqlite3.connect(backup) as dest:source.backup(dest)
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            for path in files:z.write(backup if path==DB else path,'University_FAQ/'+str(path.relative_to(ROOT)))
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.sha256').write_text(digest+'  '+target.name+'\n')
    print(json.dumps({'path':str(target),'files':len(files),'bytes':target.stat().st_size,'sha256':digest},ensure_ascii=False))

if __name__=='__main__':main()

"""Build/verify a deterministic local AGE pilot archive. Never runs a search."""
from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'data/output/age'
NAME = 'age-moea-pilot-v1.tar.gz'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def checked_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name or name == 'INVENTORY.json':
        raise ValueError(f'Unsafe/reserved archive path: {name}')
    target = root / name
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Not a regular in-root file: {name}')
    return target


def write_archive(root, paths, target):
    names = sorted(paths)
    if len(names) != len(set(names)):
        raise ValueError('Duplicate archive paths')
    files = []
    for name in names:
        path = checked_path(root, name)
        files.append(dict(path=name, bytes=path.stat().st_size, sha256=digest(path)))
    inventory = dict(format_version=1, files=files, file_count=len(files),
                     uncompressed_bytes=sum(f['bytes'] for f in files))
    inventory_bytes = encoded(inventory)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + '.tmp')
    try:
        with temp.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for name in ['INVENTORY.json'] + names:
                    data = inventory_bytes if name == 'INVENTORY.json' else (root/name).read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(data), 0o644, 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    tar.addfile(info, io.BytesIO(data))
        verify_archive(temp, inventory)
        if target.exists():
            if digest(target) != digest(temp):
                raise FileExistsError(f'Archive exists with different bytes: {target}')
        else:
            temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return inventory


def verify_archive(archive, inventory, expected_sha256=None):
    if expected_sha256 is not None and digest(archive) != expected_sha256:
        raise ValueError('Archive SHA-256 mismatch')
    entries = inventory['files']
    expected = {f['path']: f for f in entries}
    if (len(expected) != len(entries) or inventory['file_count'] != len(entries)
            or inventory['uncompressed_bytes'] != sum(f['bytes'] for f in entries)):
        raise ValueError('Invalid inventory accounting')
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if member.name in seen or not member.isfile():
                raise ValueError('Duplicate or non-regular archive member')
            seen.add(member.name)
            if member.name == 'INVENTORY.json':
                if member.size != len(encoded(inventory)) or tar.extractfile(member).read() != encoded(inventory):
                    raise ValueError('Embedded inventory mismatch')
                continue
            item = expected.get(member.name)
            path = PurePosixPath(member.name)
            if item is None or path.is_absolute() or '..' in path.parts or member.size != item['bytes']:
                raise ValueError('Unexpected archive member/size')
            hasher = sha256()
            stream = tar.extractfile(member)
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                hasher.update(chunk)
            if hasher.hexdigest() != item['sha256']:
                raise ValueError(f'Member SHA-256 mismatch: {member.name}')
    if seen != set(expected) | {'INVENTORY.json'}:
        raise ValueError('Missing archive member')


def evidence_paths(root=ROOT):
    out = root/'data/output/age'
    pilot = out/'piloto'
    frozen = json.loads((out/'frozen_config.json').read_text())
    audit = json.loads((pilot/'audit.json').read_text())
    manifest = json.loads((pilot/'manifest.json').read_text())
    if manifest['status'] != 'searches_complete' or len(manifest['runs']) != 72:
        raise ValueError('Pilot not complete')
    checks = {**frozen['source_sha256'], **frozen['evidence_sha256']}
    checks['data/output/age/piloto/summarize.py'] = frozen['analysis_sha256']
    checks['data/output/age/piloto/protocol.json'] = audit['protocol_sha256']
    checks['data/output/age/piloto/tests.json'] = audit['tests_sha256']
    checks.update({f'data/output/age/piloto/{p}': h for p,h in audit['output_sha256'].items()})
    for entry in manifest['runs']:
        checks[f"data/output/age/piloto/{entry['file']}"] = entry['sha256']
    expected_runs = {pilot/entry['file'] for entry in manifest['runs']}
    if set((pilot/'runs').glob('*.json')) != expected_runs:
        raise ValueError('Unexpected/missing raw run files')
    protocol = json.loads((pilot/'protocol.json').read_text())
    checks.update({f'data/input/{p}': h for p,h in protocol['input_sha256'].items()})
    references = json.loads((pilot/'references.json').read_text())
    for reference in references.values():
        if reference['type'] == 'exact':
            checks[reference['source']] = reference['sha256']
    for name, expected in checks.items():
        if digest(checked_path(root, name)) != expected:
            raise ValueError(f'Frozen evidence changed: {name}')
    paths = set(checks)
    paths.update(str(p.relative_to(root)) for p in pilot.iterdir() if p.is_file())
    paths.update(f'data/output/age/{name}' for name in
                 ('frozen_config.json','environment.json','FREEZE.md','ARCHIVE.md','archive_pilot.py','implementation.md'))
    paths.add('requirements.txt')
    paths.add('requirements-age-repro.txt')
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('build','verify'))
    parser.add_argument('--archive', type=Path, default=OUT/'artifacts'/NAME)
    args = parser.parse_args()
    if args.stage == 'build':
        inventory = write_archive(ROOT, evidence_paths(), args.archive)
        inventory_path = OUT/'archive_inventory.json'
        inventory_path.write_bytes(encoded(inventory))
        metadata = dict(format_version=1, archive_name=args.archive.name,
            archive_bytes=args.archive.stat().st_size, archive_sha256=digest(args.archive),
            inventory_sha256=digest(inventory_path), file_count=inventory['file_count'],
            uncompressed_bytes=inventory['uncompressed_bytes'], storage='local_only_by_project_decision',
            canonical_inventory='data/output/age/archive_inventory.json')
        (OUT/'archive_manifest.json').write_bytes(encoded(metadata))
        (OUT/'archive.sha256').write_text(f"{metadata['archive_sha256']}  {args.archive.name}\n")
        print(json.dumps(metadata, indent=2))
    else:
        metadata = json.loads((OUT/'archive_manifest.json').read_text())
        inventory_path = OUT/'archive_inventory.json'
        if digest(inventory_path) != metadata['inventory_sha256']:
            raise ValueError('External inventory SHA-256 mismatch')
        inventory = json.loads(inventory_path.read_text())
        if args.archive.stat().st_size != metadata['archive_bytes']:
            raise ValueError('Archive size mismatch')
        verify_archive(args.archive, inventory, metadata['archive_sha256'])
        print(f"Verified: {args.archive}; {inventory['file_count']} files; SHA-256 {metadata['archive_sha256']}")


if __name__ == '__main__':
    main()

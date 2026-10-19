"""No searches: deterministic packaging, corruption detection and freeze contracts."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('age_archive', ROOT/'data/output/age/archive_pilot.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class AGEArchiveTests(unittest.TestCase):
    def test_deterministic_roundtrip_and_existing_archive_protection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a.txt').write_text('original')
            first, second = root/'first.tar.gz', root/'second.tar.gz'
            inventory = archive.write_archive(root, ['a.txt'], first)
            archive.write_archive(root, ['a.txt'], second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            archive.verify_archive(first, inventory, archive.digest(first))
            archive.write_archive(root, ['a.txt'], first)
            preserved = first.read_bytes()
            (root/'a.txt').write_text('modified')
            with self.assertRaises(FileExistsError):
                archive.write_archive(root, ['a.txt'], first)
            self.assertEqual(first.read_bytes(), preserved)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                archive.verify_archive(first, inventory, '0'*64)

    def test_tampered_member_missing_member_and_inventory_fail(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a').write_bytes(b'one')
            original = root/'original.tar.gz'
            inventory = archive.write_archive(root, ['a'], original)
            for kind in ('tamper','missing','link'):
                bad = root/f'{kind}.tar.gz'
                with tarfile.open(bad,'w:gz') as tar:
                    data = archive.encoded(inventory)
                    member = tarfile.TarInfo('INVENTORY.json');member.size=len(data)
                    tar.addfile(member,io.BytesIO(data))
                    if kind != 'missing':
                        member = tarfile.TarInfo('a');member.size=3
                        if kind == 'link':
                            member.type=tarfile.SYMTYPE;member.linkname='/tmp/elsewhere'
                            tar.addfile(member)
                        else:
                            tar.addfile(member,io.BytesIO(b'two'))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    archive.verify_archive(bad,inventory)
            changed = deepcopy(inventory);changed['file_count'] += 1
            with self.assertRaises(ValueError):
                archive.verify_archive(original,changed)

    def test_unsafe_and_duplicate_paths_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a').write_text('a')
            for paths in (['../escape'], ['/etc/passwd'], ['a','a'], ['INVENTORY.json']):
                with self.subTest(paths=paths), self.assertRaises(ValueError):
                    archive.write_archive(root,paths,root/'out.tar.gz')

    def test_frozen_parameters_versions_and_immutable_sources(self):
        frozen = json.loads((ROOT/'data/output/age/frozen_config.json').read_text())
        self.assertEqual(frozen['parameters'],dict(population_size=50,crossover_probability=.9,
                                                  mutation_probability=.3,max_evaluations=8000))
        self.assertEqual(frozen['pymoo_version'],'0.6.2')
        self.assertIn('not specifically optimized',frozen['crossover_selection'])
        for name, expected in {**frozen['source_sha256'],**frozen['evidence_sha256']}.items():
            self.assertEqual(archive.digest(ROOT/name),expected,name)
        requirements = (ROOT/'requirements.txt').read_text().splitlines()
        self.assertIn('pymoo==0.6.2',requirements)
        env = json.loads((ROOT/'data/output/age/environment.json').read_text())
        pins = {line.split('==')[0]:line.split('==')[1] for line in
                (ROOT/'requirements-age-repro.txt').read_text().splitlines() if line and not line.startswith('#')}
        self.assertEqual(pins,env['distributions'])
        self.assertEqual(pins['pymoo'],'0.6.2')


if __name__ == '__main__':
    unittest.main()

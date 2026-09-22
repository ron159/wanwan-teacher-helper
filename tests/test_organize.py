from threading import Event
from app.core.contracts import JobRequest, OrganizeOptions
from app.tools.organize import run, build_plan
from zipfile import ZipFile


def test_duplicate_hash_and_copy_plan(tmp_path):
    files = tuple(tmp_path / name for name in ('a.txt', 'b.txt', 'c.txt'))
    for p, data in zip(files, (b'same', b'same', b'else')):
        p.write_bytes(data)
    request = JobRequest('organize', files, tmp_path / 'out', OrganizeOptions('duplicates'))
    result = run(request, lambda p: None, Event())
    assert result[0].details['duplicate_groups'] == [[1, 2]]
    request = JobRequest('organize', files, tmp_path / 'out', OrganizeOptions('rename', '活动'))
    assert build_plan(request)[0][1].name == '活动_0001.txt'
    result = run(request, lambda p: None, Event())
    assert all(r.output.read_bytes() == p.read_bytes() for r, p in zip(result, files))


def test_archive_has_unique_names_and_manifest(tmp_path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    files = (tmp_path / 'a' / 'same.txt', tmp_path / 'b' / 'same.txt')
    for p in files:
        p.write_text('材料')
    result = run(JobRequest('organize', files, tmp_path / 'out', OrganizeOptions('archive')),
                 lambda p: None, Event())
    with ZipFile(result[0].output) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) == 3
        assert 'manifest.json' in archive.namelist()

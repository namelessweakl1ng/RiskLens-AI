"""Restore byte-identical upstream CUAD files using a verified pinned manifest."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from urllib.request import urlopen
from training_pipeline.ingestion.public_sources import verify_checksum


def download(output):
    manifest=json.loads((Path(__file__).parents[1]/'data/manifests/cuad.json').read_text())
    with urlopen(manifest['archive_url'],timeout=60) as response:
        content=response.read(30*1024*1024+1)
    if len(content)>30*1024*1024:
        raise ValueError('Unexpected archive size')
    verify_checksum(content,manifest['archive_sha256'])
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name,expected in manifest['files'].items():
            # Extract only exact expected members, never arbitrary archive paths.
            data=archive.read(name)
            verify_checksum(data,expected)
            (output/name).write_bytes(data)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='training_pipeline/data/external/cuad')
    args=parser.parse_args()
    print(json.dumps(download(args.output),indent=2))


if __name__=='__main__':
    main()

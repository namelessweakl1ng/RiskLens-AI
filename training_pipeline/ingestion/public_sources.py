"""Fetch authorized public PDFs from an explicit provenance manifest."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from backend.services.pdf import extract_pages, segment_pages

OFFICIAL_HOSTS = {
    "www.consumerfinance.gov",
    "files.consumerfinance.gov",
    "consumerfinance.gov",
    "www.sec.gov",
    "sec.gov",
    "www.irdai.gov.in",
    "irdai.gov.in",
}


def validate_source(source, extra_hosts=()):
    url = urlparse(source.get("url", ""))
    if (
        url.scheme != "https"
        or url.hostname not in OFFICIAL_HOSTS | set(extra_hosts)
        or url.username
        or url.password
        or url.port not in (None, 443)
    ):
        raise ValueError("Source must use HTTPS on an explicitly approved authoritative hostname")
    if not source.get("source_organization") or not source.get("agreement_family"):
        raise ValueError("Source organization and document family are required")
    return source


def verify_checksum(content, expected):
    if expected and hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Source checksum mismatch; do not use the downloaded artifact")
    return True


class ApprovedRedirects(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source(
            {"url": newurl, "source_organization": "redirect", "agreement_family": "redirect"},
            self.hosts,
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_pdf(source, extra_hosts=()):
    validate_source(source, extra_hosts)
    agent = (
        os.getenv("SEC_USER_AGENT")
        if urlparse(source["url"]).hostname in {"sec.gov", "www.sec.gov"}
        else "RiskLensResearch/1.0 public-document ingestion"
    )
    if not agent:
        raise ValueError(
            "SEC_USER_AGENT must identify your organization and contact per SEC fair-access policy"
        )
    opener = build_opener(ApprovedRedirects(set(extra_hosts)))
    with opener.open(Request(source["url"], headers={"User-Agent": agent}), timeout=30) as response:
        content = response.read(20 * 1024 * 1024 + 1)
        resolved = response.url
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("Source PDF exceeds 20 MiB")
    verify_checksum(content, source.get("sha256"))
    extract_pages(content)  # validate before storing or deriving records
    return content, resolved


def ingest_manifest(manifest, output, extra_hosts=()):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    records = []
    for source in json.loads(Path(manifest).read_text()):
        content, resolved = fetch_pdf(source, extra_hosts)
        digest = hashlib.sha256(content).hexdigest()
        retrieved = datetime.now(timezone.utc).isoformat()
        (output / f"{digest}.pdf").write_bytes(content)
        for clause in segment_pages(extract_pages(content)):
            rows.append(
                {
                    "text": clause.text,
                    "label": None,
                    "agreement_family": source["agreement_family"],
                    "source_type": "public_real",
                    "annotation_method": None,
                    "source_document_id": digest,
                    "source_organization": source["source_organization"],
                    "source_url": resolved,
                    "retrieved_at": retrieved,
                    "sha256": digest,
                    "page_number": clause.page_number,
                    "is_hard_negative": False,
                }
            )
        records.append(
            {**source, "resolved_url": resolved, "sha256": digest, "retrieved_at": retrieved}
        )
    (output / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    (output / "retrieval_manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="Exact authoritative insurer hostname, explicitly authorized by the caller",
    )
    args = parser.parse_args()
    print(
        f"Extracted {len(ingest_manifest(args.manifest, args.output, args.allow_host))} candidates requiring manual annotation."
    )


if __name__ == "__main__":
    main()

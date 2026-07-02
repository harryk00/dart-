"""
DART OpenAPI 최소 클라이언트.

- list.json      : 공시 목록 조회 (공식 문서에 명시된 표준 엔드포인트)
- document.xml   : 공시 원문 조회. DART는 이 엔드포인트가 zip으로 응답되는 경우와
                    xml 그대로 응답되는 경우가 섞여 있어서, 응답 바이트의 시그니처를
                    보고 둘 다 처리하도록 방어적으로 작성했다.
"""
import io
import zipfile
import requests

API_BASE = "https://opendart.fss.or.kr/api"


class DartClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def list_disclosures(self, bgn_de: str, end_de: str, pblntf_ty: str = "B",
                          page_no: int = 1, page_count: int = 100):
        """지정 기간의 공시 목록.
        pblntf_ty='B'는 주요사항보고 (유상증자결정이 여기 포함됨)."""
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "pblntf_ty": pblntf_ty,
            "page_no": page_no,
            "page_count": page_count,
        }
        r = requests.get(f"{API_BASE}/list.json", params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def get_document_text(self, rcept_no: str) -> str:
        """공시 원문을 최대한 순수 텍스트로 변환해서 반환."""
        params = {"crtfc_key": self.api_key, "rcept_no": rcept_no}
        r = requests.get(f"{API_BASE}/document.xml", params=params, timeout=30)
        r.raise_for_status()
        content = r.content
        if content[:2] == b"PK":  # zip 시그니처
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                raw = zf.read(zf.namelist()[0])
        else:
            raw = content
        return raw.decode("utf-8", errors="ignore")

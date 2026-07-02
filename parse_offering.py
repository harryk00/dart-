"""
DART 유상증자결정 공시 원문에서 핵심 필드를 추출.

전략: XML/HTML 태그를 모두 제거해 순수 텍스트로 만든 뒤, 표준 서식(1~24번 항목)의
라벨을 앵커로 삼아 바로 뒤에 오는 값을 정규식으로 뽑아낸다. DART 원문은 회사/시점에
따라 표 구조가 미묘하게 다를 수 있어 100% 보장은 못하지만, 필드 하나가 안 잡혀도
나머지는 정상 추출되도록 개별적으로 방어했다. 실제 운영 전에 최근 공시 몇 건으로
한 번 검증해보는 걸 권장한다.
"""
import re

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
DATE_P = r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)"


def flatten(xml_text: str) -> str:
    text = TAG_RE.sub("\n", xml_text)
    text = WS_RE.sub(" ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def _find(text: str, pattern: str):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def is_rights_offering_with_public_sale(raw_text: str) -> bool:
    """증자방식이 '주주배정후 실권주 일반공모'인지 확인 (공백 제거 후 비교)."""
    return "주주배정후실권주일반공모" in raw_text.replace(" ", "").replace("\n", "")


def extract_fields(raw_text: str) -> dict:
    flat = flatten(raw_text)
    fields = {}

    fields["board_resolution_date"] = _find(
        flat, r"이사회결의일\(?결정일\)?\s*" + DATE_P)
    fields["record_date"] = _find(
        flat, r"신주배정기준일\s*" + DATE_P)
    fields["subscription_start"] = _find(
        flat, r"구주주[\s\S]{0,60}?시작일\s*" + DATE_P)
    fields["subscription_end"] = _find(
        flat, r"구주주[\s\S]{0,150}?종료일\s*" + DATE_P)
    fields["payment_date"] = _find(
        flat, r"납입일\s*" + DATE_P)
    fields["listing_date"] = _find(
        flat, r"신주의?\s*상장예정일\s*" + DATE_P)
    fields["warrant_listing_start"] = _find(
        flat, r"신주인수권증서\s*상장예정기간\s*[:：]?\s*" + DATE_P)
    fields["short_sale_ban_start"] = _find(
        flat, r"공매도\s*거래\s*기간[\s\S]{0,60}?시작일\s*" + DATE_P)
    fields["short_sale_ban_end"] = _find(
        flat, r"공매도\s*거래\s*기간[\s\S]{0,150}?종료일\s*" + DATE_P)
    fields["planned_price"] = _find(
        flat, r"예정발행가\s*[:：]?\s*([\d,]+)")
    fields["confirmed_price"] = _find(
        flat, r"확정발행가\s*[:：]?\s*([\d,]+)")

    fields["is_correction"] = bool(re.search(r"정정\s*신고", flat[:300]))
    if fields["is_correction"]:
        fields["correction_reason"] = _find(flat, r"정정사유\s*([^\n]{2,40})")
        fields["original_filed_date"] = _find(
            flat, r"최초제출일\s*[:：]?\s*" + DATE_P)

    return fields

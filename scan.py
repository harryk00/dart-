"""
매일 실행: 오늘 접수된 '유상증자결정' 계열 공시를 스캔해서
- 신규 '주주배정후 실권주 일반공모' 건이면 data/offerings.json에 새 레코드 추가
- 정정 공시면 원본 레코드를 찾아 필드를 갱신 + 정정 이력에 추가
"""
import os
import sys
import json
import datetime

from dart_client import DartClient
from parse_offering import is_rights_offering_with_public_sale, extract_fields

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "offerings.json")


def load_db():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(db):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def find_original(db, corp_code, original_filed_date):
    for key, rec in db.items():
        if rec["corp_code"] == corp_code and rec.get("filed_date") == original_filed_date:
            return key, rec
    return None, None


def main():
    api_key = os.environ.get("DART_API_KEY")
    if not api_key:
        print("DART_API_KEY 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    client = DartClient(api_key)
    today = datetime.date.today().strftime("%Y%m%d")
    db = load_db()

    page_no = 1
    total_pages = 1
    new_count = 0
    updated_count = 0

    while page_no <= total_pages:
        result = client.list_disclosures(bgn_de=today, end_de=today, page_no=page_no)
        status = result.get("status")

        if status == "013":  # 조회된 데이터 없음
            print("오늘 접수된 주요사항보고가 없습니다.")
            break
        if status != "000":
            print("DART 응답 오류:", result)
            sys.exit(1)

        total_pages = result.get("total_page", 1)

        for item in result.get("list", []):
            report_nm = item.get("report_nm", "")
            if "유상증자결정" not in report_nm:
                continue

            rcept_no = item["rcept_no"]
            corp_code = item["corp_code"]
            corp_name = item["corp_name"]
            stock_code = item.get("stock_code", "")

            try:
                text = client.get_document_text(rcept_no)
            except Exception as e:
                print(f"[스킵] {corp_name} 원문 조회 실패: {e}")
                continue

            if not is_rights_offering_with_public_sale(text):
                continue  # 주주배정후 실권주 일반공모가 아니면 제외

            fields = extract_fields(text)

            if fields.get("is_correction"):
                key, rec = find_original(db, corp_code, fields.get("original_filed_date"))
                if rec is None:
                    print(f"[주의] {corp_name} 정정공시의 원본을 못 찾았습니다. "
                          f"(최초제출일: {fields.get('original_filed_date')}) 수동 확인 필요")
                    continue
                rec.setdefault("corrections", []).append({
                    "rcept_no": rcept_no,
                    "filed_date": item["rcept_dt"],
                    "reason": fields.get("correction_reason"),
                })
                # None이 아닌 값만 덮어써서 정정 전 데이터가 불필요하게 지워지지 않게 함
                for k, v in fields.items():
                    if v is not None and k not in (
                        "is_correction", "correction_reason", "original_filed_date"
                    ):
                        rec["fields"][k] = v
                rec["last_updated"] = item["rcept_dt"]
                db[key] = rec
                updated_count += 1
                print(f"[업데이트] {corp_name} 정정 반영 ({fields.get('correction_reason')})")
                continue

            key = f"{corp_code}_{rcept_no}"
            db[key] = {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code,
                "rcept_no": rcept_no,
                "filed_date": item["rcept_dt"],
                "last_updated": item["rcept_dt"],
                "fields": fields,
                "corrections": [],
            }
            new_count += 1
            print(f"[신규 등록] {corp_name} ({stock_code})")

        page_no += 1

    save_db(db)
    print(f"완료: 신규 {new_count}건, 갱신 {updated_count}건")


if __name__ == "__main__":
    main()

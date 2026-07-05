"""cb_watch.py — CB 통합 감시기 (연구 결론의 실용화 모듈).

매일 1회 실행 (GitHub Actions). 두 가지 일을 한다:

[A] 회피 경고 — 검증된 회피 신호 감지 시 data/cb_avoid.json 에 기록
    - CB 발행결정 자체 (test 180일 평균 -16%, 승률 17%)
    - 자금목적이 M&A(타법인취득+영업양수) 50% 초과
    - 같은 날 복수 회차 동시 발행
    - 같은 날 유상증자결정 / 조회공시 동반
[B] 페이퍼 트레이딩 시그널 — 연구의 유일한 흑자 후보
    - '전환가액의조정' 공시에서 조정후가액이 그 회차 최저조정가에 도달(±1%)
      AND 해당 CB에 콜옵션 존재 → data/paper_trades.json 에 기록
    - (회사,회차)당 '첫 바닥 도달'만 기록 — 백테스트 규칙과 동일

상태 파일: data/cb_terms.json (CB 조건 DB. 신규 발행 시 자동 증분,
           과거분은 seed_terms.py로 1회 이식)
알림: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수 있으면 발송 (선택)

사용법:
    export DART_API_KEY=...
    python cb_watch.py            # 최근 3일 스캔 (주말 커버)
    python cb_watch.py --days 7
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests

API = "https://opendart.fss.or.kr/api"
KEY = os.environ.get("DART_API_KEY", "")
DATA = Path("data")
DATA.mkdir(exist_ok=True)
TERMS_F = DATA / "cb_terms.json"
AVOID_F = DATA / "cb_avoid.json"
TRADES_F = DATA / "paper_trades.json"
SLEEP = 0.15

# ------------------------- 파서 (연구 레포에서 검증 완료된 정규식) -------------------------
CALL_PAT = re.compile(r"(매도청구권|콜옵션|call\s*option)", re.I)
CALL_OWNER_PAT = re.compile(r"(최대주주|발행회사|회사)[^.\n]{0,40}(매도청구|콜)")
TM_PAT = re.compile(r"제\s*(\d+)\s*회")
TAG_RE = re.compile(r"<[^>]+>")
NUM_RE = re.compile(r"(\d[\d,]{2,})")
_UNIT_BAD = ("년", "월", "일", "회", "차", "%", "주", "호", "부")


def _num(x):
    """범용 숫자 파싱 (회차·금액 등, 범위 제한 없음)."""
    try:
        return float(re.sub(r"[,\s원%]", "", str(x)))
    except (ValueError, TypeError):
        return None


def _price_ok(v) -> bool:
    """주가·전환가액으로 그럴듯한 범위인지."""
    return v is not None and 50 <= v <= 10_000_000


def _get(endpoint: str, **params) -> dict:
    r = requests.get(f"{API}/{endpoint}.json",
                     params={"crtfc_key": KEY, **params}, timeout=30)
    r.raise_for_status()
    time.sleep(SLEEP)
    d = r.json()
    return d if d.get("status") in ("000", "013") else {}


def _doc(rcept_no: str) -> str:
    r = requests.get(f"{API}/document.xml",
                     params={"crtfc_key": KEY, "rcept_no": rcept_no}, timeout=60)
    r.raise_for_status()
    time.sleep(SLEEP)
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            return "\n".join(zf.read(n).decode("utf-8", errors="ignore")
                             for n in zf.namelist())
    except zipfile.BadZipFile:
        return r.content.decode("utf-8", errors="ignore")


def _extract_nums(seg: str) -> list:
    out = []
    for m in NUM_RE.finditer(seg):
        if seg[m.end():m.end() + 2].strip()[:1] in _UNIT_BAD:
            continue
        v = _num(m.group(1))
        if _price_ok(v) and 100 <= v <= 5_000_000:
            out.append((m.start(), v))
    return out


def parse_refix(text: str, report_nm: str) -> dict:
    """조정 전/후 가액 위치 기반 페어링 (연구 v2 파서)."""
    out = {"bd_tm": None, "adj_before": None, "adj_after": None}
    clean = re.sub(r"\s+", " ", TAG_RE.sub(" ", text))
    clean = clean.replace("조정 전", "조정전").replace("조정 후", "조정후")
    m = TM_PAT.search(report_nm) or TM_PAT.search(clean[:3000])
    if m:
        out["bd_tm"] = int(m.group(1))
    i_pre, i_post = clean.find("조정전"), clean.find("조정후")
    if i_pre == -1 or i_post == -1:
        return out
    win = clean[min(i_pre, i_post):min(i_pre, i_post) + 500]
    p_pre, p_post = win.find("조정전"), win.find("조정후")
    nums = _extract_nums(win)
    if not nums:
        return out
    if p_pre < p_post:
        between = [v for p, v in nums if p_pre < p < p_post]
        after = [v for p, v in nums if p > p_post]
        if between and after:
            out["adj_before"], out["adj_after"] = between[0], after[0]
        elif len(after) >= 2:
            out["adj_before"], out["adj_after"] = after[0], after[1]
    return out


# ------------------------- 상태 파일 -------------------------
def _load(p: Path, default):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def _save(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _notify(msg: str):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print(msg)
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": msg}, timeout=15)
        except requests.RequestException:
            pass


# ------------------------- [A] 신규 CB 발행결정 -------------------------
def scan_new_cb(bgn: str, end: str, terms: dict, avoid: list) -> None:
    page = 1
    seen_today: dict = {}                    # corp → 오늘 CB 접수 수 (동시 다회차)
    items_all = []
    while True:
        d = _get("list", bgn_de=bgn, end_de=end, pblntf_ty="B",
                 page_no=page, page_count=100)
        items = d.get("list", []) or []
        items_all.extend(items)
        if page >= int(d.get("total_page", 1) or 1):
            break
        page += 1

    cb_items = [it for it in items_all
                if "전환사채권발행결정" in it.get("report_nm", "")
                and not it["report_nm"].strip().startswith("[")]
    for it in cb_items:
        seen_today[it["corp_code"]] = seen_today.get(it["corp_code"], 0) + 1

    for it in cb_items:
        corp = it["corp_code"]
        # 구조화 조건
        tm = cv = floor = None
        ma_heavy = False
        td = _get("cvbdIsDecsn", corp_code=corp, bgn_de=bgn, end_de=end)
        for row in td.get("list", []) or []:
            if row.get("rcept_no") != it["rcept_no"]:
                continue
            tm = _num(row.get("bd_tm"))
            cv = _num(row.get("cv_prc"))
            floor = _num(row.get("act_mktprcfl_cvprc_lwtrsprc"))
            uses = {k: (_num(row.get(k)) or 0) for k in
                    ("fdpp_fclt", "fdpp_bsninh", "fdpp_op",
                     "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc")}
            tot = sum(uses.values()) or 1
            ma_heavy = (uses["fdpp_ocsa"] + uses["fdpp_bsninh"]) / tot > 0.5
        # 원문에서 콜옵션
        has_call = call_owner = False
        try:
            text = _doc(it["rcept_no"])
            has_call = bool(CALL_PAT.search(text))
            call_owner = bool(CALL_OWNER_PAT.search(text)) if has_call else False
        except requests.RequestException:
            pass
        # 동반 공시 (같은 회사, 같은 기간)
        co_rights = any(c.get("corp_code") == corp
                        and "유상증자결정" in c.get("report_nm", "")
                        for c in items_all)
        co_inq = any(c.get("corp_code") == corp
                     and "조회공시" in c.get("report_nm", "")
                     for c in items_all)
        multi = seen_today.get(corp, 0) > 1

        # 조건 DB 증분 (리픽싱 매칭용)
        if tm is not None:
            terms[f"{corp}_{int(tm)}"] = {
                "corp_name": it["corp_name"], "corp_code": corp,
                "bd_tm": int(tm), "cv_prc": cv, "floor_prc": floor,
                "has_call": has_call, "call_owner_side": call_owner,
                "issue_rcept_dt": it["rcept_dt"],
            }
        # 회피 경고
        flags = ["CB발행자체(-16%/180d)"]
        if ma_heavy:
            flags.append("M&A목적>50%")
        if multi:
            flags.append("동시다회차")
        if co_rights:
            flags.append("유증동반(test -26%)")
        if co_inq:
            flags.append("조회공시동반")
        rec = {"dt": it["rcept_dt"], "corp": it["corp_name"],
               "corp_code": corp, "tm": tm, "flags": flags,
               "rcept_no": it["rcept_no"]}
        avoid.append(rec)
        level = "⚠️강" if len(flags) >= 2 else "회피"
        _notify(f"[{level}] {it['corp_name']} 제{int(tm) if tm else '?'}회 CB 발행"
                f" | {' / '.join(flags)}")


# ------------------------- [B] 전환가액조정 → 바닥×콜 시그널 -------------------------
def scan_refix(bgn: str, end: str, terms: dict, trades: list) -> None:
    already = {(t["corp_code"], t["bd_tm"]) for t in trades}
    page = 1
    while True:
        d = _get("list", bgn_de=bgn, end_de=end, pblntf_ty="I",
                 page_no=page, page_count=100)
        items = d.get("list", []) or []
        for it in items:
            nm = it.get("report_nm", "")
            if "전환가액의조정" not in nm or nm.strip().startswith("["):
                continue
            try:
                text = _doc(it["rcept_no"])
            except requests.RequestException:
                continue
            p = parse_refix(text, nm)
            if p["bd_tm"] is None or p["adj_after"] is None:
                continue
            key = f"{it['corp_code']}_{p['bd_tm']}"
            t = terms.get(key)
            if not t or not t.get("floor_prc"):
                continue
            at_floor = abs(p["adj_after"] - t["floor_prc"]) / t["floor_prc"] < 0.01
            if not at_floor or not t.get("has_call"):
                continue
            if (it["corp_code"], p["bd_tm"]) in already:
                continue                          # 첫 바닥만 (백테스트 규칙)
            rec = {"signal_dt": it["rcept_dt"], "corp": it["corp_name"],
                   "corp_code": it["corp_code"], "bd_tm": p["bd_tm"],
                   "adj_after": p["adj_after"], "floor_prc": t["floor_prc"],
                   "call_owner_side": t.get("call_owner_side"),
                   "rcept_no": it["rcept_no"], "status": "open",
                   "note": "D+1 종가 진입 / 180일 보유 (페이퍼)"}
            trades.append(rec)
            already.add((it["corp_code"], p["bd_tm"]))
            _notify(f"🎯[페이퍼매수] {it['corp_name']} 제{p['bd_tm']}회 — "
                    f"리픽싱 바닥 도달({int(p['adj_after']):,}원) + 콜옵션 보유. "
                    f"기대(백테스트): 180d 평균 +4~7%, 승률 40%, 꼬리 의존")
        if page >= int(d.get("total_page", 1) or 1):
            break
        page += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()
    if not KEY:
        raise SystemExit("DART_API_KEY 필요")
    end = datetime.now().strftime("%Y%m%d")
    bgn = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    terms = _load(TERMS_F, {})
    avoid = _load(AVOID_F, [])
    trades = _load(TRADES_F, [])
    n_a, n_t = len(avoid), len(trades)

    scan_new_cb(bgn, end, terms, avoid)
    scan_refix(bgn, end, terms, trades)

    # 중복 제거(접수번호 기준) 후 저장
    avoid = list({a["rcept_no"]: a for a in avoid}.values())
    _save(TERMS_F, terms)
    _save(AVOID_F, avoid)
    _save(TRADES_F, trades)
    print(f"완료: 조건DB {len(terms)}건 / 회피 +{len(avoid)-n_a} / "
          f"페이퍼시그널 +{len(trades)-n_t}")


if __name__ == "__main__":
    main()

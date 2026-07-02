"""
data/offerings.json을 읽어서
- index.html            : 전체 목록 (클릭하면 상세로 이동)
- offerings/{key}.html  : 종목별 타임라인 상세 페이지
를 생성한다.
"""
import os
import json

BASE = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE, "..", "data", "offerings.json")
OUT_ROOT = os.path.join(BASE, "..")
OFFERINGS_DIR = os.path.join(OUT_ROOT, "offerings")

STYLE = """
<style>
  :root{--ink:#0E1B2A;--ink-2:#152535;--amber:#D4A24C;
        --line:#2A3B4D;--text:#E9E4D6;--text-dim:#8FA0AE;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--ink);color:var(--text);font-family:'Inter',sans-serif;
       line-height:1.6;padding:0 20px 80px;}
  .wrap{max-width:760px;margin:0 auto;}
  a{color:inherit;text-decoration:none;}
  header{padding:56px 0 32px;border-bottom:1px solid var(--line);margin-bottom:40px;}
  .eyebrow{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.12em;
           text-transform:uppercase;color:var(--amber);margin-bottom:14px;}
  h1{font-family:'Source Serif 4',serif;font-weight:600;font-size:clamp(24px,4vw,36px);
     margin-bottom:10px;}
  .sub{color:var(--text-dim);font-size:14.5px;max-width:60ch;}
  .row{display:flex;justify-content:space-between;align-items:center;gap:16px;
       padding:16px 4px;border-bottom:1px solid var(--line);}
  .row:hover{background:var(--ink-2);}
  .row .name{font-weight:500;font-size:15px;}
  .row .code{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-dim);}
  .row .date{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--amber);
             white-space:nowrap;}
  .timeline{position:relative;}
  .timeline::before{content:'';position:absolute;left:82px;top:6px;bottom:6px;
                     width:1px;background:var(--line);}
  .item{display:grid;grid-template-columns:82px 24px 1fr;gap:0 20px;
        padding-bottom:32px;position:relative;}
  .item .date{font-family:'JetBrains Mono',monospace;font-size:12px;
              color:var(--text-dim);text-align:right;padding-top:2px;}
  .item .dot-col{display:flex;justify-content:center;}
  .item .dot{width:11px;height:11px;border-radius:50%;background:var(--ink);
             border:2px solid var(--line);margin-top:4px;z-index:1;}
  .item.key .dot{border-color:var(--amber);background:var(--amber);}
  .item .title{font-size:14.5px;font-weight:500;}
  .item.key .title{color:var(--amber);}
  .item .desc{font-size:13px;color:var(--text-dim);}
  footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
         font-size:12px;color:var(--text-dim);font-family:'JetBrains Mono',monospace;}
</style>
"""

HEAD = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
{style}</head><body><div class="wrap">
"""
TAIL = "</div></body></html>"


def build_events(rec):
    f = rec["fields"]
    ev = []
    if f.get("board_resolution_date"):
        ev.append((f["board_resolution_date"], "이사회 결의일", "", False))
    if f.get("short_sale_ban_start"):
        rng = f["short_sale_ban_start"]
        if f.get("short_sale_ban_end"):
            rng += " ~ " + f["short_sale_ban_end"]
        ev.append((rng, "공매도 금지 기간", "청약 관련 공매도 제한 구간", False))
    if f.get("record_date"):
        ev.append((f["record_date"], "신주배정기준일", "", False))
    if f.get("warrant_listing_start"):
        ev.append((f["warrant_listing_start"], "신주인수권증서 상장", "", False))
    if f.get("subscription_start"):
        rng = f["subscription_start"]
        if f.get("subscription_end"):
            rng += " ~ " + f["subscription_end"]
        ev.append((rng, "구주주 청약", "", False))
    if f.get("payment_date"):
        ev.append((f["payment_date"], "납입일", "", False))
    if f.get("listing_date"):
        ev.append((f["listing_date"], "신주 상장예정일", "", False))
    if f.get("planned_price"):
        ev.append(("", f"예정발행가 {f['planned_price']}원", "확정 전", True))
    if f.get("confirmed_price"):
        ev.append(("", f"확정발행가 {f['confirmed_price']}원", "", True))
    return ev


def render_detail(key, rec):
    events = build_events(rec)
    items_html = ""
    for date, title, desc, key_flag in events:
        cls = "item key" if key_flag else "item"
        items_html += (
            f'<div class="{cls}"><div class="date">{date}</div>'
            f'<div class="dot-col"><div class="dot"></div></div>'
            f'<div><div class="title">{title}</div><div class="desc">{desc}</div></div></div>'
        )

    corrections_html = ""
    if rec.get("corrections"):
        rows = "".join(
            f'<div class="row"><span class="name">{c["filed_date"]}</span>'
            f'<span class="code">{c.get("reason") or ""}</span></div>'
            for c in rec["corrections"]
        )
        corrections_html = (
            '<h2 style="font-family:JetBrains Mono,monospace;font-size:13px;'
            'color:var(--amber);margin:32px 0 12px">정정 이력</h2>' + rows
        )

    html = HEAD.format(title=f"{rec['corp_name']} 유상증자 일정", style=STYLE) + f"""
    <header>
      <div class="eyebrow">DART 주요사항보고서 · 유상증자 결정</div>
      <h1>{rec['corp_name']}</h1>
      <p class="sub">주주배정후 실권주 일반공모 · 최초 접수 {rec['filed_date']} · 최근 갱신 {rec['last_updated']}</p>
    </header>
    <div class="timeline">{items_html}</div>
    {corrections_html}
    <footer>출처: DART 전자공시시스템 (접수번호 {rec['rcept_no']}) · 자동 수집 페이지 · 투자 권유 아님</footer>
    """ + TAIL

    os.makedirs(OFFERINGS_DIR, exist_ok=True)
    with open(os.path.join(OFFERINGS_DIR, f"{key}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def render_index(db):
    rows = ""
    for key, rec in sorted(db.items(), key=lambda kv: kv[1]["filed_date"], reverse=True):
        rows += (
            f'<a class="row" href="offerings/{key}.html">'
            f'<span><span class="name">{rec["corp_name"]}</span> '
            f'<span class="code">({rec.get("stock_code","")})</span></span>'
            f'<span class="date">{rec["filed_date"]}</span></a>'
        )
    body = rows if rows else '<p class="sub">아직 수집된 공시가 없습니다. 매일 자동으로 채워집니다.</p>'

    html = HEAD.format(title="주주배정 유상증자 트래커", style=STYLE) + f"""
    <header>
      <div class="eyebrow">DAILY DART SCAN</div>
      <h1>주주배정후 실권주 일반공모 트래커</h1>
      <p class="sub">매일 DART 주요사항보고서를 스캔해 '주주배정후 실권주 일반공모' 방식
      유상증자만 자동 수집합니다. 항목을 클릭하면 상세 일정을 볼 수 있습니다.</p>
    </header>
    {body}
    <footer>매일 자동 갱신 · 출처: DART 전자공시시스템 · 투자 권유 아님</footer>
    """ + TAIL

    with open(os.path.join(OUT_ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main():
    db = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
    for key, rec in db.items():
        render_detail(key, rec)
    render_index(db)


if __name__ == "__main__":
    main()

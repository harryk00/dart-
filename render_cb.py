"""render_cb.py — data/*.json → cb.html 대시보드 생성 (render.py와 같은 패턴)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DATA = Path("data")


def _load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def main():
    avoid = _load("cb_avoid.json", [])
    trades = _load("paper_trades.json", [])
    avoid = sorted(avoid, key=lambda x: x.get("dt", ""), reverse=True)[:200]
    trades = sorted(trades, key=lambda x: x.get("signal_dt", ""), reverse=True)

    def esc(s):
        return str(s).replace("<", "&lt;").replace(">", "&gt;")

    rows_t = "\n".join(
        f"<tr><td>{esc(t['signal_dt'])}</td><td>{esc(t['corp'])}</td>"
        f"<td>제{esc(t['bd_tm'])}회</td><td>{int(t['adj_after']):,}원</td>"
        f"<td>{'최대주주' if t.get('call_owner_side') else '있음'}</td>"
        f"<td>{esc(t.get('status','open'))}</td></tr>"
        for t in trades) or "<tr><td colspan=6>시그널 없음</td></tr>"
    rows_a = "\n".join(
        f"<tr><td>{esc(a['dt'])}</td><td>{esc(a['corp'])}</td>"
        f"<td>{esc(' / '.join(a['flags']))}</td></tr>"
        for a in avoid) or "<tr><td colspan=3>기록 없음</td></tr>"

    html = f"""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>CB 감시 대시보드</title>
<style>
 body{{font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;max-width:960px;
      margin:24px auto;padding:0 16px;color:#222}}
 h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:28px}}
 table{{border-collapse:collapse;width:100%;font-size:.9rem}}
 th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left}}
 th{{background:#f5f5f5}} .note{{color:#666;font-size:.82rem}}
</style></head><body>
<h1>CB 감시 대시보드</h1>
<p class=note>갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST ·
4,055건 전수 연구 기반. 페이퍼 시그널은 실거래 아님 —
백테스트 기대치: 180일 평균 +4~7%(비용 전), 승률 40%, 상위 10%가 수익 대부분.</p>

<h2>🎯 페이퍼 트레이딩 원장 — 바닥 리픽싱 × 콜옵션 ({len(trades)}건)</h2>
<table><tr><th>시그널일</th><th>회사</th><th>회차</th><th>조정후가액</th>
<th>콜 귀속</th><th>상태</th></tr>{rows_t}</table>
<p class=note>규칙: 시그널 D+1 종가 진입 가정, 180일 보유, (회사,회차)당 첫 바닥만.
3~6개월 축적 후 백테스트와 대조해 실탄 여부 결정.</p>

<h2>⚠️ 회피 경고 로그 (최근 {len(avoid)}건)</h2>
<table><tr><th>공시일</th><th>회사</th><th>플래그</th></tr>{rows_a}</table>
<p class=note>근거: CB 발행 후 180일 test 평균 -16% / 승률 17%.
유증 동반 시 test -26%. 보유 종목이 여기 뜨면 오버행·희석 점검.</p>
</body></html>"""
    Path("cb.html").write_text(html, encoding="utf-8")
    print(f"cb.html 생성 (시그널 {len(trades)} / 경고 {len(avoid)})")


if __name__ == "__main__":
    main()

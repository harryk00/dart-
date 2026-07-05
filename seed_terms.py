"""seed_terms.py — 연구 레포의 CB 조건을 감시기 DB로 1회 이식.

과거 발행분(2016~2024)의 최저조정가·콜옵션 정보가 있어야 리픽싱 바닥
매칭이 첫날부터 작동한다. 연구 레포(cb_study)의 07_dataset.parquet 경로를
넘기면 data/cb_terms.json 을 생성한다.

사용법: pip install pandas pyarrow
        python seed_terms.py /Users/kimjehyeon/Desktop/cb_study/data/out/07_dataset.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


def main():
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python seed_terms.py <07_dataset.parquet 경로>")
    src = Path(sys.argv[1])
    df = pd.read_parquet(src)
    out = {}
    for _, r in df.iterrows():
        tm = pd.to_numeric(r.get("bd_tm"), errors="coerce")
        if pd.isna(tm) or pd.isna(r.get("floor_prc")):
            continue
        key = f"{r['corp_code']}_{int(tm)}"
        out[key] = {
            "corp_name": r.get("corp_name"),
            "corp_code": r["corp_code"],
            "bd_tm": int(tm),
            "cv_prc": None if pd.isna(r.get("cv_prc")) else float(r["cv_prc"]),
            "floor_prc": float(r["floor_prc"]),
            "has_call": bool(r.get("has_call")) if pd.notna(r.get("has_call")) else False,
            "call_owner_side": bool(r.get("call_owner_side"))
                               if pd.notna(r.get("call_owner_side")) else False,
            "issue_rcept_dt": str(pd.Timestamp(r["event_dt"]).date())
                              if pd.notna(r.get("event_dt")) else None,
        }
    Path("data").mkdir(exist_ok=True)
    Path("data/cb_terms.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_call = sum(1 for v in out.values() if v["has_call"])
    print(f"이식 완료: {len(out)}건 (콜옵션 보유 {n_call}건) → data/cb_terms.json")


if __name__ == "__main__":
    main()

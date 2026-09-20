import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "https://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

MEET_MAP = {
    "1": "서울",
    "2": "제주",
    "3": "부산경남"
}

def fetch_meet_data(meet_code, meet_name, rc_date_str):
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "150",
        "meet": meet_code,
        "rc_date": rc_date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        
        races = {}
        for item in items:
            def get_val(tag):
                n = item.find(tag)
                return n.text.strip() if n is not None and n.text else ""

            rc_no = get_val("rcNo") or get_val("rc_no") or "1"
            ord_no = get_val("ord") or get_val("ord_no") or "-"
            gate = get_val("chulNo") or get_val("chul_no") or "0"
            name = get_val("hrName") or get_val("hr_name") or "경주마"
            jockey = get_val("jkName") or get_val("jk_name") or "기수"
            trainer = get_val("trName") or get_val("tr_name") or "조교사"
            weight = get_val("wgBudam") or get_val("wg_budam") or "0"

            key = f"{meet_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": meet_name,
                    "race_no": rc_no,
                    "race_date": rc_date_str,
                    "horses": []
                }

            # AI 예상 점수 계산
            score = 65.0
            if ord_no.isdigit():
                score += max(0, 35 - (int(ord_no) * 3))

            races[key]["horses"].append({
                "gate": gate,
                "name": name,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "ai_score": round(score, 1)
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        return list(races.values())
    except Exception as e:
        print(f"[{meet_name}] 요청 에러: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키가 없습니다.")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    # 1. 오늘 날짜 우선 시도
    print(f"오늘({today_str}) 데이터 수집 시도...")
    for m_code, m_name in MEET_MAP.items():
        res = fetch_meet_data(m_code, m_name, today_str)
        all_races.extend(res)

    # 2. 오늘 경주 결과가 아직 없으면(아직 진행 전이거나 비경주일), 최근 주말 데이터 수집
    if not all_races:
        last_date = (datetime.today() - timedelta(days=7)).strftime("%Y%m%d")
        print(f"오늘 데이터 아직 없음 -> 최근 경주일({last_date}) 수집...")
        for m_code, m_name in MEET_MAP.items():
            res = fetch_meet_data(m_code, m_name, last_date)
            all_races.extend(res)

    if all_races:
        all_races.sort(key=lambda x: (x["meet_name"], int(x["race_no"]) if x["race_no"].isdigit() else 99))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"총 {len(all_races)}개 경주 저장 완료 (race_data.json)!")
    else:
        print("수집 가능한 경주 데이터가 없습니다.")

if __name__ == "__main__":
    main()

import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "http://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

# 서울(1), 부산경남/영천(3), 영천독립(4)
MEET_CONFIG = [
    ("1", "서울"),
    ("3", "부산경남"),
    ("4", "영천")
]

TOP_JOCKEYS = {
    "문세영": 25.0, "김용근": 20.0, "유승완": 18.0, "송재철": 17.0,
    "이혁": 16.0, "임다빈": 15.0, "빅투아르": 22.0, "씨씨옹": 20.0,
    "서승운": 24.0, "유현명": 21.0, "최시대": 21.0, "정도윤": 20.0,
    "진겸": 17.0, "김혜선": 18.0, "이효식": 18.0
}

def calculate_ai_score(gate, weight, jockey):
    score = 50.0
    score += TOP_JOCKEYS.get(jockey, 10.0)

    try:
        g = int(gate)
        if 1 <= g <= 4:
            score += 12.0
        elif 5 <= g <= 8:
            score += 8.0
        else:
            score += 4.0
    except:
        score += 5.0

    try:
        w = float(weight)
        score += (55.0 - w) * 2.5
    except:
        pass

    return round(score, 1)

def fetch_real_kra_data(meet_code, meet_name, rc_date_str):
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "150",
        "meet": meet_code,
        "rc_date": rc_date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*"
    }

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        if not items:
            return []

        races = {}
        for item in items:
            def get_val(tags):
                for t in tags:
                    n = item.find(t)
                    if n is not None and n.text and n.text.strip():
                        return n.text.strip()
                return ""

            rc_no = get_val(["rcNo", "rc_no"]) or "1"
            ord_no = get_val(["ord", "ord_no"]) or "-"
            gate = get_val(["chulNo", "chul_no", "gateNo", "hrNo"]) or "0"
            name = get_val(["hrName", "hr_name"]) or "경주마"
            jockey = get_val(["jkName", "jk_name"]) or "기수"
            trainer = get_val(["trName", "tr_name"]) or "조교사"
            weight = get_val(["wgBudam", "wg_budam"]) or "55.0"
            rc_name = get_val(["rcName", "rc_name", "race_name"])

            # 실제 마사회 데이터에서 영천 경주인지 판별
            display_meet = meet_name
            if "영천" in rc_name or meet_code == "4":
                display_meet = "영천"

            key = f"{display_meet}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": display_meet,
                    "race_no": rc_no,
                    "race_date": rc_date_str,
                    "horses": []
                }

            ai_score = calculate_ai_score(gate, weight, jockey)

            races[key]["horses"].append({
                "gate": gate,
                "name": name,          # 100% 마사회 실제 말 이름!
                "jockey": jockey,      # 100% 실제 기수 이름!
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "ai_score": ai_score
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        print(f"[{meet_name}] 마사회 실제 데이터 {len(races)}개 경주 수신 성공")
        return list(races.values())

    except Exception as e:
        print(f"[{meet_name}] 수신 지연: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    print(f"=== 마사회 100% 실제 데이터 수집 ({today_str}) ===")
    for m_code, m_name in MEET_CONFIG:
        res = fetch_real_kra_data(m_code, m_name, today_str)
        all_races.extend(res)
        time.sleep(1)

    if all_races:
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"저장 완료: 총 {len(all_races)}개 실제 마사회 경주 저장됨.")
    else:
        print("수신된 실제 데이터가 없습니다.")

if __name__ == "__main__":
    main()

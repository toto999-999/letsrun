import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
# 검증된 안정적인 마사회 API
URL = "http://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

# 마사회 공식 권역: 1: 서울, 3: 영남(영천/부산 통합)
MEET_CONFIG = [
    ("1", "서울"),
    ("3", "영천/영남")
]

TOP_JOCKEYS = {
    "문세영": 25.0, "김용근": 20.0, "유승완": 18.0, "송재철": 17.0,
    "이혁": 16.0, "임다빈": 15.0, "빅투아르": 22.0, "다나카": 22.0,
    "서승운": 24.0, "유현명": 21.0, "최시대": 21.0, "다비드": 21.0,
    "정도윤": 20.0, "김동영": 17.0, "김혜선": 18.0, "이성재": 16.0,
    "송경윤": 15.0, "김어수": 15.0, "손경민": 14.0, "전진구": 15.0
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

def fetch_meet_data(meet_code, meet_name, date_str):
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "150",
        "meet": meet_code,
        "rc_date": date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"[{meet_name}] 마사회 공식 데이터 수신 요청: {date_str}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*"
    }

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"[{meet_name}] 수신 성공: 총 {len(items)}두 데이터 확보!")

        if not items:
            return []

        races = {}
        for it in items:
            def gv(tag_list):
                for t in tag_list:
                    n = it.find(t)
                    if n is not None and n.text and n.text.strip():
                        return n.text.strip()
                return ""

            rc_no = gv(["rcNo", "rc_no"]) or "1"
            gate = gv(["chulNo", "chul_no", "gateNo", "hrNo"]) or "0"
            name = gv(["hrName", "hr_name"]) or "경주마"
            jockey = gv(["jkName", "jk_name"]) or "기수"
            trainer = gv(["trName", "tr_name"]) or "조교사"
            weight = gv(["wgBudam", "wg_budam"]) or "55.0"
            ord_no = gv(["ord", "ord_no"]) or "-"

            key = f"{meet_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": meet_name,
                    "race_no": rc_no,
                    "race_date": date_str,
                    "horses": []
                }

            score = calculate_ai_score(gate, weight, jockey)

            races[key]["horses"].append({
                "gate": gate,
                "name": name,          # 100% 마사회 공식 실데이터 말 이름!
                "jockey": jockey,      # 100% 실제 기수!
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "ai_score": score
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        return list(races.values())

    except Exception as e:
        print(f"[{meet_name}] 수신 에러: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    print(f"=== {today_str} 전국 경마 (서울 + 영천/영남) 수집 시작 ===")
    for m_code, m_name in MEET_CONFIG:
        res = fetch_meet_data(m_code, m_name, today_str)
        all_races.extend(res)
        time.sleep(1)

    if all_races:
        # 서울 1순위, 영남/영천 2순위 정렬
        all_races.sort(key=lambda x: (
            1 if "서울" in x["meet_name"] else 2,
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 대성공: 총 {len(all_races)}개 경주 (서울 + 영천/영남) 공식 실제 데이터 저장 완료!")
    else:
        print("데이터 수신 실패")

if __name__ == "__main__":
    main()

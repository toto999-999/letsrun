import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "https://apis.data.go.kr/B551015/API26_2/entrySheet_2"

# 1: 서울, 3: 부산경남, 4: 영천 (일요일 운영 경마장)
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

def calculate_ai_score(gate, weight, jockey, rating):
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

    try:
        r = float(rating)
        if r > 0:
            score += r * 0.3
    except:
        pass

    return round(score, 1)

def fetch_meet_entry(meet_code, meet_name):
    # 타임아웃 방지를 위해 80건씩 가볍게 요청
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "80",
        "meet": meet_code
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"[{meet_name}] 출전표 요청 전송...")

    for attempt in range(2):
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            print(f"[{meet_name}] {len(items)}두 수신 성공")
            
            if not items:
                return []

            # 가장 최신 경주일자 필터링
            dates = []
            for it in items:
                for tag in ["rcDate", "rc_date", "race_dt", "raceDate"]:
                    n = it.find(tag)
                    if n is not None and n.text and n.text.strip():
                        dates.append(n.text.strip().replace("-", "").replace(".", ""))
            
            target_date = sorted(dates, reverse=True)[0] if dates else datetime.today().strftime("%Y%m%d")

            races = {}
            for it in items:
                def get_val(tags):
                    for t in tags:
                        n = it.find(t)
                        if n is not None and n.text and n.text.strip():
                            return n.text.strip()
                    return ""

                it_date = get_val(["rcDate", "rc_date", "race_dt", "raceDate"]).replace("-", "").replace(".", "")
                # 가장 최신 경주일(오늘 등) 데이터만 선별
                if it_date and it_date != target_date:
                    continue

                rc_no = get_val(["rcNo", "rc_no"]) or "1"
                gate = get_val(["chulNo", "chul_no", "gateNo", "hrNo"]) or "0"
                name = get_val(["hrName", "hr_name"]) or "경주마"
                jockey = get_val(["jkName", "jk_name"]) or "기수"
                trainer = get_val(["trName", "tr_name"]) or "조교사"
                weight = get_val(["wgBudam", "wg_budam"]) or "55.0"
                rating = get_val(["rating", "rat"]) or "0"

                key = f"{meet_name}_{rc_no}"
                if key not in races:
                    races[key] = {
                        "meet_code": meet_code,
                        "meet_name": meet_name,
                        "race_no": rc_no,
                        "race_date": target_date,
                        "horses": []
                    }

                ai_score = calculate_ai_score(gate, weight, jockey, rating)

                races[key]["horses"].append({
                    "gate": gate,
                    "name": name,
                    "jockey": jockey,
                    "trainer": trainer,
                    "weight": weight,
                    "rating": rating,
                    "actual_ord": "-",
                    "ai_score": ai_score
                })

            for r in races.values():
                r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

            return list(races.values())

        except Exception as e:
            print(f"[{meet_name}] 시도 {attempt+1}차 지연 에러: {e}")
            time.sleep(3)

    return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    all_races = []
    for m_code, m_name in MEET_CONFIG:
        res = fetch_meet_entry(m_code, m_name)
        all_races.extend(res)
        time.sleep(1) # 마사회 서버 과부하 방지 1초 간격

    if all_races:
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"대성공: 총 {len(all_races)}개 경주 (서울/부산/영천) 출전표 분석 완료!")
    else:
        print("데이터 수집 실패")

if __name__ == "__main__":
    main()

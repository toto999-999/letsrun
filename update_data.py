import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
# 신규 출전표 API 주소
URL = "https://apis.data.go.kr/B551015/API26_2/entrySheet_2"

MEET_MAP = {
    "1": "서울",
    "2": "제주",
    "3": "부산경남",
    "4": "영천"
}

TOP_JOCKEYS = {
    "문세영": 25.0, "김용근": 20.0, "유승완": 18.0, "송재철": 17.0,
    "이혁": 16.0, "임다빈": 15.0, "빅투아르": 22.0, "씨씨옹": 20.0,
    "서승운": 24.0, "유현명": 21.0, "최시대": 21.0, "정도윤": 19.0,
    "진겸": 17.0, "김혜선": 18.0, "이효식": 18.0
}

def calculate_ai_score(gate, weight, jockey, rating):
    score = 50.0

    # 1. 기수 가산점
    score += TOP_JOCKEYS.get(jockey, 10.0)

    # 2. 안쪽 게이트 선행 가산점 (1~4번 게이트)
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

    # 3. 부담중량 가산점 (가벼울수록 후반 탄력)
    try:
        w = float(weight)
        score += (55.0 - w) * 2.5
    except:
        pass

    # 4. 마필 공식 레이팅(능력치) 가산점
    try:
        r = float(rating)
        if r > 0:
            score += r * 0.3
    except:
        pass

    return round(score, 1)

def fetch_meet_data(meet_code, meet_name, rc_date_str):
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "200",
        "meet": meet_code,
        "rc_date": rc_date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    
    for attempt in range(2):
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            
            races = {}
            for item in items:
                def get_val(tags):
                    for t in tags:
                        n = item.find(t)
                        if n is not None and n.text and n.text.strip():
                            return n.text.strip()
                    return ""

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
                        "race_date": rc_date_str,
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

            print(f"[{meet_name}] {len(races)}개 경주 출전표 수집 성공")
            return list(races.values())
        except Exception as e:
            print(f"[{meet_name}] 시도 {attempt+1}차 에러: {e}")
            time.sleep(2)

    return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    print(f"오늘({today_str}) 당일 출전표 사전 수집 시작...")
    for m_code, m_name in MEET_MAP.items():
        res = fetch_meet_data(m_code, m_name, today_str)
        all_races.extend(res)

    # 비경주일(월~목)인 경우 다가올 주말 데이터 탐색
    if not all_races:
        for offset in [1, 2, -1, -2, -7]:
            target_d = (datetime.today() + timedelta(days=offset)).strftime("%Y%m%d")
            print(f"당일 출전표 없음 -> {target_d} 출전표 탐색...")
            for m_code, m_name in MEET_MAP.items():
                res = fetch_meet_data(m_code, m_name, target_d)
                all_races.extend(res)
            if all_races:
                break

    if all_races:
        all_races.sort(key=lambda x: (x["meet_name"], int(x["race_no"]) if x["race_no"].isdigit() else 99))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"총 {len(all_races)}개 경주 사전 출전표 분석 완료 (race_data.json)!")
    else:
        print("출전표 데이터가 없습니다.")

if __name__ == "__main__":
    main()

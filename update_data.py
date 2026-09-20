import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "https://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

# 일요일 대상: 서울, 부산경남, 영천
MEET_LIST = [
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

def fetch_meet_data(meet_code, meet_name, rc_date_str):
    # 가볍고 빠른 응답을 위해 100건으로 설정
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "meet": meet_code,
        "rc_date": rc_date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"[{meet_name}] {rc_date_str} 요청 시작...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/xml,text/xml,*/*"
    }

    try:
        req = urllib.request.Request(full_url, headers=headers)
        # 피크 시간대 지연을 고려해 35초 대기
        with urllib.request.urlopen(req, timeout=35) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        
        if not items:
            print(f"[{meet_name}] 데이터 없음(0건)")
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

            key = f"{meet_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": meet_name,
                    "race_no": rc_no,
                    "race_date": rc_date_str,
                    "horses": []
                }

            ai_score = calculate_ai_score(gate, weight, jockey)

            races[key]["horses"].append({
                "gate": gate,
                "name": name,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "ai_score": ai_score
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        print(f"[{meet_name}] {len(races)}개 경주 수신 완료!")
        return list(races.values())

    except Exception as e:
        print(f"[{meet_name}] 접속 지연 ({e})")
        return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    print(f"=== 오늘({today_str}) 전국 데이터 수집 시작 ===")
    for m_code, m_name in MEET_LIST:
        res = fetch_meet_data(m_code, m_name, today_str)
        all_races.extend(res)
        time.sleep(2) # 방화벽 과부하 방지: 경마장별 2초 딜레이

    # 만약 오늘 데이터가 전산에 전혀 안 잡혔다면 지난주 데이터로 대체
    if not all_races:
        last_date = (datetime.today() - timedelta(days=7)).strftime("%Y%m%d")
        print(f"오늘 경주 데이터 없음 -> 최근({last_date}) 수집...")
        for m_code, m_name in MEET_LIST:
            res = fetch_meet_data(m_code, m_name, last_date)
            all_races.extend(res)
            time.sleep(2)

    if all_races:
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: 총 {len(all_races)}개 경주 분석 저장 완료!")
    else:
        print("수집 실패: 마사회 서버 점검 중이거나 응답 없음")

if __name__ == "__main__":
    main()

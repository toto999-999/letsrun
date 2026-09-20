import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

API_KEY = os.environ.get("KRA_API_KEY", "")
# 최신 출전표 API 주소
URL = "https://apis.data.go.kr/B551015/API26_2/entrySheet_2"

MEET_NAME_MAP = {
    "1": "서울",
    "2": "제주",
    "3": "부산경남",
    "4": "영천"
}

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

def fetch_all_races(rc_date_str):
    # meet를 생략하여 전국의 모든 경마장(서울/부산/영천/제주)을 1회 호출로 모두 수집
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "500",
        "rc_date": rc_date_str
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"전국 출전표 통합 조회 요청: {rc_date_str}")

    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"수집된 출전마 데이터 수: {len(items)}두")

        races = {}
        for item in items:
            def get_val(tags):
                for t in tags:
                    n = item.find(t)
                    if n is not None and n.text and n.text.strip():
                        return n.text.strip()
                return ""

            # 경마장 식별 (코드 또는 텍스트)
            m_code = get_val(["meet", "rccrs_cd", "meet_cd"]) or "1"
            m_name = get_val(["meet_name", "rccrs_name", "rcCity"])
            if not m_name:
                m_name = MEET_NAME_MAP.get(m_code, "서울")
            
            # 영천 순회경마 텍스트가 경주명 등에 포함된 경우 영천으로 자동 분류
            rc_name = get_val(["rcName", "rc_name", "race_name"])
            if "영천" in rc_name or m_code == "4":
                m_name = "영천"

            rc_no = get_val(["rcNo", "rc_no"]) or "1"
            gate = get_val(["chulNo", "chul_no", "gateNo", "hrNo"]) or "0"
            name = get_val(["hrName", "hr_name"]) or "경주마"
            jockey = get_val(["jkName", "jk_name"]) or "기수"
            trainer = get_val(["trName", "tr_name"]) or "조교사"
            weight = get_val(["wgBudam", "wg_budam"]) or "55.0"
            rating = get_val(["rating", "rat"]) or "0"

            key = f"{m_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": m_code,
                    "meet_name": m_name,
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

        return list(races.values())
    except Exception as e:
        print(f"통합 수집 에러: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키 없음")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = fetch_all_races(today_str)

    # 비경주일이거나 데이터가 없는 경우 최근 데이터 탐색
    if not all_races:
        for offset in [1, 2, -1, -2, -7]:
            target_d = (datetime.today() + timedelta(days=offset)).strftime("%Y%m%d")
            print(f"당일 데이터 없음 -> {target_d} 탐색...")
            all_races = fetch_all_races(target_d)
            if all_races:
                break

    if all_races:
        # 경마장별, 경주번호 순으로 정렬 (서울 -> 부산경남 -> 영천 -> 제주)
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3, "제주": 4}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"성공: 총 {len(all_races)}개 경주 (서울/부산/영천) 수집 완료!")
    else:
        print("출전표 데이터를 찾을 수 없습니다.")

if __name__ == "__main__":
    main()

import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

API_KEY = os.environ.get("KRA_API_KEY", "")
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

def fetch_all_entries():
    # 날짜/경마장 변수를 누락하여 마사회 공식 설명대로 최근/당일 전체 출전표를 일괄 수신
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "1000"
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print("마사회 서버로부터 전국 출전표 전체 데이터 일괄 수신 중...")

    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"총 수신된 데이터: {len(items)}건")

        if not items:
            print("응답에 item 태그가 없습니다. XML 원본 일부:")
            print(xml_data.decode('utf-8', errors='ignore')[:300])
            return []

        # 가장 최신 경주일자 찾기
        dates = set()
        for item in items:
            for tag in ["rcDate", "rc_date", "race_dt", "raceDate"]:
                n = item.find(tag)
                if n is not None and n.text and n.text.strip():
                    dates.add(n.text.strip().replace("-", "").replace(".", ""))
        
        today_str = datetime.today().strftime("%Y%m%d")
        target_date = today_str if today_str in dates else (sorted(list(dates), reverse=True)[0] if dates else today_str)
        print(f"분석 대상 경주일자: {target_date} (발견된 날짜들: {dates})")

        races = {}
        for item in items:
            def get_val(tags):
                for t in tags:
                    n = item.find(t)
                    if n is not None and n.text and n.text.strip():
                        return n.text.strip()
                return ""

            item_date = get_val(["rcDate", "rc_date", "race_dt", "raceDate"]).replace("-", "").replace(".", "")
            if item_date and item_date != target_date:
                continue

            m_code = get_val(["meet", "rccrs_cd", "meet_cd"]) or "1"
            m_name = get_val(["meet_name", "rccrs_name", "rcCity"])
            if not m_name:
                m_name = MEET_NAME_MAP.get(m_code, "서울")
            
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
        print(f"수집 에러 발생: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키가 설정되지 않았습니다.")
        return

    all_races = fetch_all_entries()

    if all_races:
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3, "제주": 4}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"완료: 총 {len(all_races)}개 경주 사전 출전표 분석 저장 완료!")
    else:
        print("출전표 데이터 추출 실패")

if __name__ == "__main__":
    main()

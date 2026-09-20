import os
import json
import urllib.request
import urllib.parse
from datetime import datetime
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "http://apis.data.go.kr/B551015/API26_2/entrySheet_2"

MEET_CONFIG = [
    ("1", "서울"),
    ("3", "영남(부경/영천)")
]

TOP_JOCKEYS = {
    "문세영": 25.0, "김용근": 20.0, "유승완": 18.0, "송재철": 17.0,
    "이혁": 16.0, "임다빈": 15.0, "빅투아르": 22.0, "다나카": 22.0,
    "서승운": 24.0, "유현명": 21.0, "최시대": 21.0, "다비드": 21.0,
    "정도윤": 20.0, "김동영": 17.0, "김혜선": 18.0, "이성재": 16.0
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

def fetch_entries_json(meet_code, meet_name, date_str):
    month_str = date_str[:6] # YYYYMM
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "200",
        "meet": meet_code,
        "rc_month": month_str,
        "rc_date": date_str,
        "_type": "json"  # JSON 응답 요청
    }
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"[{meet_name}] {date_str} 출전표 JSON 요청 중...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_body = response.read().decode('utf-8', errors='ignore')

        # JSON 파싱
        data = json.loads(raw_body)
        items = []
        try:
            # 마사회 표준 JSON 구조 파싱
            body = data.get("response", {}).get("body", {})
            items_container = body.get("items", {})
            if isinstance(items_container, dict):
                items = items_container.get("item", [])
            elif isinstance(items_container, list):
                items = items_container
            if isinstance(items, dict):
                items = [items]
        except Exception as parse_err:
            print(f"JSON 구조 파싱 오류: {parse_err}")
            return []

        print(f"[{meet_name}] 마사회 실제 출전마 {len(items)}두 수신 성공!")
        if not items:
            return []

        races = {}
        for it in items:
            rc_no = str(it.get("rcNo") or it.get("rc_no") or "1")
            gate = str(it.get("chulNo") or it.get("chul_no") or it.get("hrNo") or "0")
            name = str(it.get("hrName") or it.get("hr_name") or "경주마")
            jockey = str(it.get("jkName") or it.get("jk_name") or "기수")
            trainer = str(it.get("trName") or it.get("tr_name") or "조교사")
            weight = str(it.get("wgBudam") or it.get("wg_budam") or "55.0")
            rating = str(it.get("rating") or it.get("rat") or "0")
            rc_name = str(it.get("rcName") or it.get("rc_name") or "")

            # 영천 단어가 포함되어 있거나 meet_code가 영남인 경우 표기
            display_name = meet_name
            if "영천" in rc_name or "영천" in str(it.get("meet_name", "")):
                display_name = "영천"
            elif meet_code == "3":
                display_name = "영천/부경"

            key = f"{display_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": display_name,
                    "race_no": rc_no,
                    "race_date": date_str,
                    "horses": []
                }

            score = calculate_ai_score(gate, weight, jockey, rating)

            races[key]["horses"].append({
                "gate": gate,
                "name": name,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "rating": rating,
                "actual_ord": "-",
                "ai_score": score
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        return list(races.values())

    except Exception as e:
        print(f"[{meet_name}] 출전표 수신 에러: {e}")
        return []

def main():
    if not API_KEY:
        print("API 키가 없습니다.")
        return

    today_str = datetime.today().strftime("%Y%m%d")
    all_races = []

    print(f"=== {today_str} 당일 진짜 출전표 수집 시작 ===")
    for m_code, m_name in MEET_CONFIG:
        res = fetch_entries_json(m_code, m_name, today_str)
        all_races.extend(res)
        time.sleep(1)

    if all_races:
        all_races.sort(key=lambda x: (x["meet_name"], int(x["race_no"]) if x["race_no"].isdigit() else 99))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: 총 {len(all_races)}개 경주 실제 출전표 저장 완료!")
    else:
        print("마사회에서 출전표 데이터를 응답하지 않았습니다.")

if __name__ == "__main__":
    main()

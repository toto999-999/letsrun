import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import time

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "http://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

# 전국 4대 경마장 전체 자동 대응
MEET_CONFIG = [
    ("1", "서울"),
    ("2", "제주"),
    ("3", "부산경남"),
    ("4", "영천")
]

# 상위 탑 클래스 기수 승률 가산점 테이블
TOP_JOCKEYS = {
    "문세영": 25.0, "김용근": 20.0, "유승완": 18.0, "송재철": 17.0,
    "이혁": 16.0, "임다빈": 15.0, "빅투아르": 22.0, "다나카": 22.0,
    "서승운": 24.0, "유현명": 21.0, "최시대": 21.0, "다비드": 21.0,
    "정도윤": 20.0, "김동영": 17.0, "김혜선": 18.0, "이성재": 16.0,
    "송경윤": 15.0, "김어수": 15.0, "손경민": 14.0, "전진구": 15.0
}

def calculate_smart_ai_score(gate, weight, jockey, track_condition="양호"):
    # 기본 스코어 50점 시작
    score = 50.0

    # 1. 기수 능력치 가산점 (최대 +25점)
    score += TOP_JOCKEYS.get(jockey, 11.0)

    # 2. 게이트 유불리 분석 (모래주로 특성 반영)
    try:
        g = int(gate)
        if 1 <= g <= 4:
            score += 12.0  # 인코스 선행 최유리
        elif 5 <= g <= 8:
            score += 8.0   # 중위권 게이트
        else:
            score += 4.0   # 외곽 게이트 (외곽 전개 불리)
    except:
        score += 5.0

    # 3. 주로 상태(함수율) 연동 가산점 (포롱/불량 등 젖은 모래일수록 인코스 선행마가 압도적 유리)
    if track_condition in ["포롱", "불량", "다습"]:
        try:
            if int(gate) <= 3:
                score += 5.0 # 악천후 안쪽 선행 프리미엄
        except:
            pass

    # 4. 부담중량 감량 탄력성 (55kg 기준 가벼울수록 후반 3F 탄력 유리)
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
    print(f"[{meet_name}] 데이터 수신 요청: {date_str}")

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
        if not items:
            print(f"[{meet_name}] 경기 없음(0건)")
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
            ord_no = gv(["ordNo", "ord", "ord_no", "rank"]) or "-"
            rc_time = gv(["rcTime", "rc_time"]) or "-"
            track = gv(["track", "trCondition"]) or "양호"

            key = f"{meet_name}_{rc_no}"
            if key not in races:
                races[key] = {
                    "meet_code": meet_code,
                    "meet_name": meet_name,
                    "race_no": rc_no,
                    "race_date": date_str,
                    "track": track,
                    "horses": []
                }

            score = calculate_smart_ai_score(gate, weight, jockey, track)

            races[key]["horses"].append({
                "gate": gate,
                "name": name,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "rc_time": rc_time,
                "ai_score": score
            })

        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        print(f"[{meet_name}] {len(races)}개 경주 수신 완료!")
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

    print(f"=== {today_str} 전국 경마장(서울/제주/부경/영천) 스마트 수집 시작 ===")
    for m_code, m_name in MEET_CONFIG:
        res = fetch_meet_data(m_code, m_name, today_str)
        all_races.extend(res)
        time.sleep(1)

    if all_races:
        # 경마장 표시 순서: 서울 -> 부산경남 -> 영천 -> 제주
        meet_order = {"서울": 1, "부산경남": 2, "영천": 3, "제주": 4}
        all_races.sort(key=lambda x: (
            meet_order.get(x["meet_name"], 9),
            int(x["race_no"]) if x["race_no"].isdigit() else 99
        ))
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"🎉 성공: 총 {len(all_races)}개 경주 스마트 AI 분석 완료!")
    else:
        print("금일 경주 데이터 수신 없음")

if __name__ == "__main__":
    main()

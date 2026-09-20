import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

API_KEY = os.environ.get("KRA_API_KEY", "")
URL = "https://apis.data.go.kr/B551015/racedetailresult/getracedetailresult"

def fetch_race_data():
    if not API_KEY:
        print("API 키가 설정되지 않았습니다.")
        return None

    # 가장 최근 일요일 날짜 계산
    today = datetime.today()
    days_back = (today.weekday() - 6) % 7
    if days_back == 0 and today.hour < 18:
        days_back = 7
    target_date = today - timedelta(days=days_back)
    rc_date_str = target_date.strftime("%Y%m%d")

    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "meet": "1",
        "rc_date": rc_date_str
    }
    
    full_url = f"{URL}?{urllib.parse.urlencode(params)}"
    print(f"요청 일자: {rc_date_str}")

    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")

        # 해당 주 데이터가 없으면 1주 전 일요일로 재시도
        if not items:
            print("데이터 없음, 1주 전으로 재시도")
            target_date -= timedelta(days=7)
            rc_date_str = target_date.strftime("%Y%m%d")
            params["rc_date"] = rc_date_str
            full_url = f"{URL}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
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

            if rc_no not in races:
                races[rc_no] = {"race_no": rc_no, "race_date": rc_date_str, "horses": []}

            # 기본 승부예측 알고리즘 점수 (1착에 가까울수록 높은 점수)
            score = 60.0
            if ord_no.isdigit():
                score += max(0, 40 - (int(ord_no) * 3))

            races[rc_no]["horses"].append({
                "gate": gate,
                "name": name,
                "jockey": jockey,
                "trainer": trainer,
                "weight": weight,
                "actual_ord": ord_no,
                "ai_score": round(score, 1)
            })

        # 경주별 점수 높은 순으로 정렬
        for r in races.values():
            r["horses"].sort(key=lambda x: x["ai_score"], reverse=True)

        return list(races.values())
    except Exception as e:
        print(f"에러 발생: {e}")
        return None

def main():
    res = fetch_race_data()
    if res:
        with open("race_data.json", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("race_data.json 생성 완료!")
    else:
        print("수집 실패")

if __name__ == "__main__":
    main()

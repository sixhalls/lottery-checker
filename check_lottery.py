#!/usr/bin/env python3
"""
Lottery data fetcher: fetch DLT/SSQ results, update EMBEDDED data in index.html.
No comparison, no push — just keep the data fresh.
"""
import json, os, re, urllib.request, urllib.error
from datetime import datetime

HTML_FILE = "index.html"

# ==================== Fetch data ====================
def fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Fetch failed {url}: {e}")
        return None

def fetch_dlt():
    # Source 1: js-lottery HTML
    html = fetch_url("https://www.js-lottery.com/wfzq/dlt/data")
    if html:
        m = re.search(r'text-align:center[^>]*>(\d{4}-\d{2}-\d{2})</td>\s*<td[^>]*>(\d{5,6})</td>\s*<td[^>]*>\s*([\d\s]+?)\s*</td>', html)
        if m:
            date_str, period, nums_str = m.group(1), m.group(2), m.group(3).strip()
            nums = [int(x) for x in nums_str.split()]
            if len(nums) >= 7:
                return {"period": period, "date": date_str, "front": nums[:5], "back": nums[5:7]}

    # Source 2: 55125
    html = fetch_url("https://m.55125.cn/kaijiang/dlt/")
    if html:
        m = re.search(r'(\d{5,6})[^\d]*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})', html)
        if m:
            return {"period": m.group(1), "date": "", "front": [int(m.group(i)) for i in range(2,7)], "back": [int(m.group(7)), int(m.group(8))]}
    return None

def fetch_ssq():
    # Source 1: cwl.gov.cn API
    html = fetch_url("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq&issueCount=3")
    if html:
        try:
            data = json.loads(html)
            if data.get("result") and len(data["result"]) > 0:
                item = data["result"][0]
                red = [int(x) for x in re.split(r'[,\s]+', item["red"])]
                blue = [int(item["blue"])]
                return {"period": item["code"], "date": item.get("date",""), "red": red, "blue": blue}
        except: pass

    # Source 2: 17500.cn (data-v attributes)
    html = fetch_url("https://m.17500.cn/win/list/lotid/ssq.html")
    if html:
        period_m = re.search(r'data-name="issue"\s+data-v="(20\d{5})"', html)
        balls_m = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"\s+data-v="(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*\+\s*(\d{2})"', html)
        if period_m and balls_m:
            return {"period": period_m.group(1), "date": balls_m.group(1),
                    "red": [int(balls_m.group(i)) for i in range(2,8)], "blue": [int(balls_m.group(8))]}
        # Fallback: match 20XXXXX period format
        m = re.search(r'(20\d{5})\s*期[\s\S]*?(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*[+\s]*(\d{2})', html)
        if m:
            return {"period": m.group(1), "date": "", "red": [int(m.group(i)) for i in range(2,8)], "blue": [int(m.group(8))]}

    # Source 3: 78500
    html = fetch_url("https://kaijiang.78500.cn/ssq/")
    if html:
        m = re.search(r'(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})[^\d+]*\+\s*(\d{2})', html)
        if m:
            return {"period": "", "date": "", "red": [int(m.group(i)) for i in range(1,7)], "blue": [int(m.group(7))]}
    return None

# ==================== Update HTML ====================
def update_html(dlt_data, ssq_data):
    if not os.path.exists(HTML_FILE):
        print(f"HTML file not found: {HTML_FILE}")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    if dlt_data:
        dlt_json = f"dlt: {{ period: '{dlt_data['period']}', date: '{dlt_data['date']}', front: [{','.join(str(x) for x in dlt_data['front'])}], back: [{','.join(str(x) for x in dlt_data['back'])}] }}"
        html = re.sub(r'dlt:\s*\{\s*period:\s*[^}]+\}', dlt_json, html)

    if ssq_data:
        ssq_json = f"ssq: {{ period: '{ssq_data['period']}', date: '{ssq_data['date']}', red: [{','.join(str(x) for x in ssq_data['red'])}], blue: [{','.join(str(x) for x in ssq_data['blue'])}] }}"
        html = re.sub(r'ssq:\s*\{\s*period:\s*[^}]+\}', ssq_json, html)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML updated")

# ==================== Main ====================
def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== Lottery Data Fetch {now} ===")

    dlt = fetch_dlt()
    ssq = fetch_ssq()

    if dlt:
        print(f"DLT: period={dlt['period']} front={dlt['front']} back={dlt['back']}")
    else:
        print("DLT: fetch failed")

    if ssq:
        print(f"SSQ: period={ssq['period']} red={ssq['red']} blue={ssq['blue']}")
    else:
        print("SSQ: fetch failed")

    update_html(dlt, ssq)

if __name__ == "__main__":
    main()

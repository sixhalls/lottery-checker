#!/usr/bin/env python3
"""
Lottery checker: fetch DLT/SSQ results, compare with preset numbers, push to WeChat via PushPlus.
"""
import json, os, re, urllib.request, urllib.error, sys
from datetime import datetime

HTML_FILE = "index.html"

# ==================== Preset numbers (edit here) ====================
# Format: list of dicts with "front" and "back" keys
# DLT: front=鍓嶅尯(1-35, select 5+), back=鍚庡尯(1-12, select 2+)
# SSQ: front=绾㈢悆(1-33, select 6+), back=钃濈悆(1-16, select 1+)
PRESETS = {
    "dlt": [
        # Add your DLT numbers here
        # Example: {"front": [1,5,12,22,33], "back": [2,8]},
    ],
    "ssq": [
        {"front": [6,9,11,19,20,25], "back": [12]},
        {"front": [9,12,17,19,21,23], "back": [6]},
        {"front": [1,15,17,20,29,30], "back": [15]},
        {"front": [18,19,21,28,30,32], "back": [7]},
        {"front": [2,4,16,21,24,29], "back": [7]},
        {"front": [4,9,15,17,25,33], "back": [14]},
    ]
}

# ==================== Prize info ====================
PRIZE_INFO = {
    "dlt": {
        1: {"name": "涓€绛夊", "variable": True},
        2: {"name": "浜岀瓑濂?, "variable": True},
        3: {"name": "涓夌瓑濂?, "amount": 10000},
        4: {"name": "鍥涚瓑濂?, "amount": 3000},
        5: {"name": "浜旂瓑濂?, "amount": 300},
        6: {"name": "鍏瓑濂?, "amount": 200},
        7: {"name": "涓冪瓑濂?, "amount": 100},
        8: {"name": "鍏瓑濂?, "amount": 15},
        9: {"name": "涔濈瓑濂?, "amount": 5},
    },
    "ssq": {
        1: {"name": "涓€绛夊", "variable": True},
        2: {"name": "浜岀瓑濂?, "variable": True},
        3: {"name": "涓夌瓑濂?, "amount": 3000},
        4: {"name": "鍥涚瓑濂?, "amount": 200},
        5: {"name": "浜旂瓑濂?, "amount": 10},
        6: {"name": "鍏瓑濂?, "amount": 5},
    }
}

def format_money(n):
    if n >= 10000:
        return f"{n/10000:.1f}涓?
    return str(n)

def calc_prize_amount(results, game):
    """Calculate total fixed prize amount from results (variable prizes excluded)."""
    total = 0
    for r in results:
        info = PRIZE_INFO.get(game, {}).get(r["level"])
        if info and "amount" in info:
            total += info["amount"]
    return total

def has_variable_prize(results, game):
    """Check if any result contains a variable prize (1st/2nd)."""
    for r in results:
        info = PRIZE_INFO.get(game, {}).get(r["level"])
        if info and info.get("variable"):
            return True
    return False

# ==================== PushPlus ====================
def push_wechat(title, content):
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        print("PUSHPLUS_TOKEN not set, skip push")
        return
    url = "http://www.pushplus.plus/send"
    data = json.dumps({"token": token, "title": title, "content": content, "template": "html"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"Push result: {result.get('code', '?')} {result.get('msg', '')}")
    except Exception as e:
        print(f"Push failed: {e}")

# ==================== Prize logic ====================
def prize_dlt(fh, bh):
    if fh==5 and bh==2: return 1, "涓€绛夊"
    if fh==5 and bh==1: return 2, "浜岀瓑濂?
    if fh==5 and bh==0: return 3, "涓夌瓑濂?
    if fh==4 and bh==2: return 4, "鍥涚瓑濂?
    if fh==4 and bh==1: return 5, "浜旂瓑濂?
    if fh==3 and bh==2: return 6, "鍏瓑濂?
    if fh==4 and bh==0: return 7, "涓冪瓑濂?
    if (fh==3 and bh==1) or (fh==2 and bh==2): return 8, "鍏瓑濂?
    if (fh==3 and bh==0) or (fh==2 and bh==1) or (fh==1 and bh==2) or (fh==0 and bh==2): return 9, "涔濈瓑濂?
    return 0, "鏈腑濂?

def prize_ssq(rh, bh):
    if rh==6 and bh==1: return 1, "涓€绛夊"
    if rh==6 and bh==0: return 2, "浜岀瓑濂?
    if rh==5 and bh==1: return 3, "涓夌瓑濂?
    if (rh==5 and bh==0) or (rh==4 and bh==1): return 4, "鍥涚瓑濂?
    if (rh==4 and bh==0) or (rh==3 and bh==1): return 5, "浜旂瓑濂?
    if (rh==2 and bh==1) or (rh==1 and bh==1) or (rh==0 and bh==1): return 6, "鍏瓑濂?
    return 0, "鏈腑濂?

# ==================== Combinations ====================
def combinations(arr, k):
    if k == 0: return [[]]
    if len(arr) < k: return []
    result = []
    for i in range(len(arr)):
        for c in combinations(arr[i+1:], k-1):
            result.append([arr[i]] + c)
    return result

def compare_all(user_front, user_back, draw_front, draw_back, game):
    cfg_front = 5 if game == "dlt" else 6
    cfg_back = 2 if game == "dlt" else 1
    prize_fn = prize_dlt if game == "dlt" else prize_ssq
    front_combos = combinations(user_front, cfg_front)
    back_combos = combinations(user_back, cfg_back)
    results = []
    for fc in front_combos:
        for bc in back_combos:
            fh = len([n for n in fc if n in draw_front])
            bh = len([n for n in bc if n in draw_back])
            level, name = prize_fn(fh, bh)
            if level > 0:
                results.append({"front": fc, "back": bc, "fh": fh, "bh": bh, "level": level, "name": name})
    return results

# ==================== Fetch data ====================
def fetch_url(url, timeout=15, extra_headers=None):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
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
    # Source 1: cwl.gov.cn API (needs Referer header)
    html = fetch_url(
        "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq&issueCount=3",
        extra_headers={"Referer": "https://www.cwl.gov.cn/yulekj/ssq/", "Accept": "application/json"}
    )
    if html:
        try:
            data = json.loads(html)
            if data.get("result") and len(data["result"]) > 0:
                item = data["result"][0]
                red = [int(x) for x in re.split(r'[,\s]+', item["red"])]
                blue = [int(item["blue"])]
                return {"period": item["code"], "date": item.get("date",""), "red": red, "blue": blue}
        except: pass

    # Source 2: 17500.cn (works from overseas)
    html = fetch_url("https://m.17500.cn/win/list/lotid/ssq.html")
    if html:
        # 浼樺厛鍖归厤 "20xxxxx" 鏍煎紡鐨勬湡鍙凤紙濡?2026075锛?
        m = re.search(r'(20\d{5})\s*(?:鏈??[\s\S]*?(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*[+\s]*(\d{2})', html)
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

    # 姝ｅ垯鍖归厤 EMBEDDED 涓殑 dlt/ssq 鏁版嵁锛堝吋瀹规湁鏃犵┖鏍硷級
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
    print(f"=== Lottery Check {now} ===")

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

    # Update HTML
    update_html(dlt, ssq)

    # Compare with presets
    push_msgs = []

    for game, presets in PRESETS.items():
        if not presets:
            continue
        draw = dlt if game == "dlt" else ssq
        if not draw:
            continue

        draw_front = draw.get("front", draw.get("red", []))
        draw_back = draw.get("back", draw.get("blue", []))
        game_name = "澶т箰閫? if game == "dlt" else "鍙岃壊鐞?
        period = draw.get("period", "?")

        for i, preset in enumerate(presets):
            u_front = preset["front"]
            u_back = preset["back"]
            results = compare_all(u_front, u_back, draw_front, draw_back, game)

            if results:
                # Count by level
                level_count = {}
                for r in results:
                    level_count[r["name"]] = level_count.get(r["name"], 0) + 1
                summary = "銆?.join(f"{k}脳{v}" for k,v in level_count.items())
                best = min(results, key=lambda r: r["level"])

                # 濂栭噾淇℃伅
                fixed_amount = calc_prize_amount(results, game)
                has_var = has_variable_prize(results, game)
                prize_text = ""
                if has_var:
                    prize_text = "锛堝惈娴姩濂栭噾锛屽幓瀹樼綉鏌?
                    if fixed_amount > 0:
                        prize_text += f"锛屽彟鍚浐瀹氬閲憑format_money(fixed_amount)}鍏?
                    prize_text += "锛?
                elif fixed_amount > 0:
                    prize_text = f"锛堝浐瀹氬閲憑format_money(fixed_amount)}鍏冿級"

                push_msgs.append(f"馃帀 {game_name}绗瑊period}鏈?绗瑊i+1}缁勶細<b>{best['name']}</b>{prize_text}<br>涓姹囨€伙細{summary}<br>寮€濂栵細{draw_front} + {draw_back}<br>浣犵殑锛歿u_front} + {u_back}")
            else:
                f_hits = len([n for n in u_front if n in draw_front])
                b_hits = len([n for n in u_back if n in draw_back])
                if f_hits > 0 or b_hits > 0:
                    front_name = "鍓嶅尯" if game == "dlt" else "绾㈢悆"
                    back_name = "鍚庡尯" if game == "dlt" else "钃濈悆"
                    push_msgs.append(f"{game_name}绗瑊period}鏈?绗瑊i+1}缁勶細鏈腑濂栵紙{front_name}鍛戒腑{f_hits}锛寋back_name}鍛戒腑{b_hits}锛?)

    # Push notification
    if push_msgs:
        title = "馃帀 涓閫氱煡" if any("馃帀" in m for m in push_msgs) else "涓浜嗗悧 - 寮€濂栫粨鏋?
        content = "<br><br>".join(push_msgs)
        push_wechat(title, content)
        print(f"Pushed: {title}")
        for m in push_msgs:
            print(f"  {m}")
    else:
        if PRESETS.get("dlt") or PRESETS.get("ssq"):
            push_wechat("涓浜嗗悧 - 浠婃棩寮€濂?, f"浠婃棩寮€濂栨暟鎹幏鍙栧畬鎴愶紝鏃犻璁惧彿鐮侀渶瑕佸姣斻€倇now}")
        else:
            print("No presets configured, skip push")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lottery checker: fetch DLT/SSQ results, compare with preset numbers, push to WeChat via PushPlus.
"""
import json, os, re, urllib.request, urllib.error, sys
from datetime import datetime

HTML_FILE = "index.html"

# ==================== Preset numbers (edit here) ====================
# Format: list of dicts with "front" and "back" keys
# DLT: front=前区(1-35, select 5+), back=后区(1-12, select 2+)
# SSQ: front=红球(1-33, select 6+), back=蓝球(1-16, select 1+)
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
        1: {"name": "一等奖", "variable": True},
        2: {"name": "二等奖", "variable": True},
        3: {"name": "三等奖", "amount": 10000},
        4: {"name": "四等奖", "amount": 3000},
        5: {"name": "五等奖", "amount": 300},
        6: {"name": "六等奖", "amount": 200},
        7: {"name": "七等奖", "amount": 100},
        8: {"name": "八等奖", "amount": 15},
        9: {"name": "九等奖", "amount": 5},
    },
    "ssq": {
        1: {"name": "一等奖", "variable": True},
        2: {"name": "二等奖", "variable": True},
        3: {"name": "三等奖", "amount": 3000},
        4: {"name": "四等奖", "amount": 200},
        5: {"name": "五等奖", "amount": 10},
        6: {"name": "六等奖", "amount": 5},
    }
}

def format_money(n):
    if n >= 10000:
        return f"{n/10000:.1f}万"
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
    if fh==5 and bh==2: return 1, "一等奖"
    if fh==5 and bh==1: return 2, "二等奖"
    if fh==5 and bh==0: return 3, "三等奖"
    if fh==4 and bh==2: return 4, "四等奖"
    if fh==4 and bh==1: return 5, "五等奖"
    if fh==3 and bh==2: return 6, "六等奖"
    if fh==4 and bh==0: return 7, "七等奖"
    if (fh==3 and bh==1) or (fh==2 and bh==2): return 8, "八等奖"
    if (fh==3 and bh==0) or (fh==2 and bh==1) or (fh==1 and bh==2) or (fh==0 and bh==2): return 9, "九等奖"
    return 0, "未中奖"

def prize_ssq(rh, bh):
    if rh==6 and bh==1: return 1, "一等奖"
    if rh==6 and bh==0: return 2, "二等奖"
    if rh==5 and bh==1: return 3, "三等奖"
    if (rh==5 and bh==0) or (rh==4 and bh==1): return 4, "四等奖"
    if (rh==4 and bh==0) or (rh==3 and bh==1): return 5, "五等奖"
    if (rh==2 and bh==1) or (rh==1 and bh==1) or (rh==0 and bh==1): return 6, "六等奖"
    return 0, "未中奖"

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
        # 优先匹配 "20xxxxx" 格式的期号（如 2026075）
        m = re.search(r'(20\d{5})\s*(?:期)?[\s\S]*?(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*(\d{2})\s*[+\s]*(\d{2})', html)
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

    # 正则匹配 EMBEDDED 中的 dlt/ssq 数据（兼容有无空格）
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
        game_name = "大乐透" if game == "dlt" else "双色球"
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
                summary = "、".join(f"{k}×{v}" for k,v in level_count.items())
                best = min(results, key=lambda r: r["level"])

                # 奖金信息
                fixed_amount = calc_prize_amount(results, game)
                has_var = has_variable_prize(results, game)
                prize_text = ""
                if has_var:
                    prize_text = "（含浮动奖金，去官网查"
                    if fixed_amount > 0:
                        prize_text += f"，另含固定奖金{format_money(fixed_amount)}元"
                    prize_text += "）"
                elif fixed_amount > 0:
                    prize_text = f"（固定奖金{format_money(fixed_amount)}元）"

                push_msgs.append(f"🎉 {game_name}第{period}期 第{i+1}组：<b>{best['name']}</b>{prize_text}<br>中奖汇总：{summary}<br>开奖：{draw_front} + {draw_back}<br>你的：{u_front} + {u_back}")
            else:
                f_hits = len([n for n in u_front if n in draw_front])
                b_hits = len([n for n in u_back if n in draw_back])
                if f_hits > 0 or b_hits > 0:
                    front_name = "前区" if game == "dlt" else "红球"
                    back_name = "后区" if game == "dlt" else "蓝球"
                    push_msgs.append(f"{game_name}第{period}期 第{i+1}组：未中奖（{front_name}命中{f_hits}，{back_name}命中{b_hits}）")

    # Push notification
    if push_msgs:
        title = "🎉 中奖通知" if any("🎉" in m for m in push_msgs) else "中奖了吗 - 开奖结果"
        content = "<br><br>".join(push_msgs)
        push_wechat(title, content)
        print(f"Pushed: {title}")
        for m in push_msgs:
            print(f"  {m}")
    else:
        if PRESETS.get("dlt") or PRESETS.get("ssq"):
            push_wechat("中奖了吗 - 今日开奖", f"今日开奖数据获取完成，无预设号码需要对比。{now}")
        else:
            print("No presets configured, skip push")

if __name__ == "__main__":
    main()

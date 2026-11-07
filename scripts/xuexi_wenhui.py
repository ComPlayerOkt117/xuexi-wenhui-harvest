# -*- coding: utf-8 -*-
"""
学习强国·"习近平文汇"频道检索自动化（可复用版）
流程: 打开检索页 → 点击"习近平文汇"tab → 截获API JSON → 点 page-next 翻页循环
产出: <输出目录>/<检索词>/page_N.json（原始JSON存档，供 parse_wenhui_json.py 解析）

前置: 本机已装 Chrome；pip install DrissionPage
用法:
    python xuexi_wenhui.py --test                     # 内置示例词验证链路
    python xuexi_wenhui.py --word 检索词              # 采集单个词
    python xuexi_wenhui.py --all                      # 采集 --words-file 全部词
    python xuexi_wenhui.py --words-file 词表.txt --out ./学习强国JSON/文汇
要点:
    - 必须用真实 Chrome（DrissionPage 接管），直连 requests 会被 WAF 按 TLS 指纹拦截
    - 单线程、翻页间随机停顿、断点续传（已有数据的词自动跳过）
"""
import json, os, random, sys, time
from urllib.parse import quote
from DrissionPage import ChromiumPage

SEARCH_URL = "https://static.xuexi.cn/search/online/index.html"

CLICK_TAB_JS = """
var tabs = document.querySelectorAll('[role="tab"]');
for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].textContent.indexOf('文汇') > -1) { tabs[i].click(); return true; }
}
return false;
"""

def pause(a=4, b=9):
    time.sleep(random.uniform(a, b))

def wait_render(page, min_cards=3, timeout=40):
    for _ in range(timeout // 2):
        if page.html.count("c-card") >= min_cards:
            return True
        time.sleep(2)
    return False

def check_verify(page):
    """出现验证码时挂起等待人工处理，最多等 2 分钟"""
    marks = ("验证码", "安全验证", "滑动验证", "访问异常")
    if not any(x in page.html[:200000] for x in marks):
        return True
    print("[!] 出现验证码，请在浏览器中人工完成……")
    for _ in range(24):
        time.sleep(5)
        if not any(x in page.html[:200000] for x in marks):
            print("[+] 已通过，继续")
            return True
    return False

def scroll_human(page):
    try:
        for _ in range(random.randint(2, 4)):
            page.run_js("window.scrollBy(0, document.body.scrollHeight/3)")
            time.sleep(random.uniform(0.4, 1.0))
    except Exception:
        pass

def collect(page, word, out_root):
    wdir = os.path.join(out_root, word)
    if os.path.exists(wdir) and os.listdir(wdir):
        n = len([f for f in os.listdir(wdir) if f.endswith(".json")])
        print(f"[跳过] {word} 已有 {n} 页数据（如需重采请先删除该目录）")
        return
    os.makedirs(wdir, exist_ok=True)
    page.get(f"{SEARCH_URL}?query={quote(word)}&page=1", timeout=40)
    if not wait_render(page):
        print(f"[!] {word} 页面未渲染，跳过")
        return
    if not check_verify(page):
        return
    scroll_human(page)

    # 截获文汇频道的检索 API 响应
    page.listen.start("api/search")
    if not page.run_js(CLICK_TAB_JS):
        page.listen.stop()
        print(f"[!] {word} 未找到文汇tab")
        return
    pkt = page.listen.wait(timeout=25, fit_count=True)
    page_no = 1
    total_pages, seen_ids = None, set()
    while pkt is not None:
        body = pkt.response.body
        if isinstance(body, str):
            try: body = json.loads(body)
            except Exception: body = {"_raw": body[:2000]}
        d = body.get("data") if isinstance(body, dict) else {}
        items = []
        if isinstance(d, dict):
            for card in d.get("list", []):
                rd = (card.get("cardSchema") or {}).get("renderData") or {}
                if rd.get("summary"):
                    items.append({"biz_id": str(card.get("biz_id") or ""),
                                  "title": rd.get("title", ""), "summary": rd["summary"],
                                  "publish_time": rd.get("publish_time", ""),
                                  "url": rd.get("url", ""), "ext_infos": rd.get("ext_infos", [])})
            if total_pages is None:
                total_pages = d.get("pages")
                print(f"  总数 {d.get('total')} / {total_pages} 页")
        # 原始 JSON 落盘存档
        json.dump(body, open(os.path.join(wdir, f"page_{page_no}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        new = 0
        for it in items:
            # 去重键必须用 biz_id；按标题去重会把同篇不同段落误判为重复
            k = it["biz_id"] or (it["title"] + "|" + it["summary"][:80])
            if k not in seen_ids:
                seen_ids.add(k); new += 1
        print(f"  {word} 第{page_no}页: {len(items)} 条（新 {new}）")
        page_no += 1
        if total_pages and page_no > total_pages:
            break
        if not items or new == 0:
            break
        pause()
        nxt = page.ele(".page-next", timeout=10)
        if not nxt:
            print("  无下一页控件，结束")
            break
        scroll_human(page)
        nxt.click()
        if not check_verify(page):
            break
        pkt = page.listen.wait(timeout=25, fit_count=True)
    page.listen.stop()
    print(f"[完成] {word}: {page_no-1} 页 / {len(seen_ids)} 条")

def load_words(path):
    words = []
    for line in open(path, encoding="utf-8-sig"):
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return words

def main():
    args = sys.argv[1:]
    words_file = out_root = None
    mode, single = "--test", None
    i = 0
    while i < len(args):
        if args[i] == "--words-file" and i + 1 < len(args):
            words_file = args[i + 1]; i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out_root = args[i + 1]; i += 2
        elif args[i] == "--word" and i + 1 < len(args):
            mode, single = "--word", args[i + 1]; i += 2
        elif args[i] == "--all":
            mode = "--all"; i += 1
        elif args[i] == "--test":
            mode = "--test"; i += 1
        else:
            i += 1
    if not out_root:
        out_root = os.path.join(os.getcwd(), "学习强国JSON", "文汇")
    os.makedirs(out_root, exist_ok=True)

    print("启动/接管浏览器……")
    page = ChromiumPage()
    page.set.window.max()
    if mode == "--test":
        collect(page, "以上率下", out_root)
    elif mode == "--word":
        collect(page, single, out_root)
    elif mode == "--all":
        if not words_file:
            sys.exit("[!] --all 需要配合 --words-file <词表.txt>（每行一个检索词）")
        for w in load_words(words_file):
            print(f"\n=== {w} ===")
            try:
                collect(page, w, out_root)
            except Exception as e:
                print(f"[异常] {w}: {e}，继续下一个词")
            pause(5, 12)
    print(f"\n全部完成，原始JSON在 {out_root}")

if __name__ == "__main__":
    main()

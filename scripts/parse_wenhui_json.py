# -*- coding: utf-8 -*-
"""
文汇JSON解析器：合并全部检索词的原始JSON → 条目总表 + 句子表
产出: <前缀>条目总表.csv / <前缀>句子表.csv
字段: keyword, date, title(场合), summary(原文段落), source_doc(所属文献), url

用法:
    python parse_wenhui_json.py                          # 默认读 ./学习强国JSON/文汇，输出 05_条目总表.csv / 06_句子表.csv
    python parse_wenhui_json.py --src <JSON目录> --prefix 05_
"""
import argparse, csv, glob, json, os, re
from html import unescape


def clean(t):
    t = re.sub(r"<[^>]+>", "", str(t))
    return re.sub(r"\s+", " ", unescape(t)).strip()


def open_csv(path):
    """CSV 被占用（Excel 打开中）时自动换名，避免中断"""
    import datetime
    try:
        return open(path, "w", newline="", encoding="utf-8-sig")
    except PermissionError:
        ts = datetime.datetime.now().strftime("%H%M%S")
        new = path.replace(".csv", f"_{ts}.csv")
        print(f"[提示] {os.path.basename(path)} 被占用，改写为 {os.path.basename(new)}")
        return open(new, "w", newline="", encoding="utf-8-sig")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join("学习强国JSON", "文汇"),
                    help="page_N.json 所在根目录（每个检索词一个子目录）")
    ap.add_argument("--prefix", default="05_")
    ap.add_argument("--no-dedup", action="store_true",
                    help="不去重（默认按 场景+完整原文段落 跨词精确去重）")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.src, "*", "page_*.json")))
    print(f"待解析: {len(files)} 个JSON文件")
    rows, seen = [], set()
    for f in files:
        word = os.path.basename(os.path.dirname(f))
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        data = d.get("data") or {}
        for card in data.get("list", []):
            rd = (card.get("cardSchema") or {}).get("renderData") or {}
            if not rd.get("summary"):
                continue
            title = clean(rd.get("title"))
            summary = clean(rd.get("summary"))
            if not args.no_dedup:
                # 跨词去重键：场合 + 完整段落（截断哈希会让不同段落碰撞）
                key = hash(title + "|" + summary)
                if key in seen:
                    continue
                seen.add(key)
            docs = "；".join(clean(x.get("title", "")) for x in rd.get("ext_infos", []) if x.get("title"))
            rows.append({
                "keyword": word,
                "date": clean(rd.get("publish_time")),
                "title": title,
                "summary": summary,
                "source_doc": docs,
                "url": clean(rd.get("url")),
            })

    out1 = args.prefix + "条目总表.csv"
    with open_csv(out1) as fp:
        w = csv.DictWriter(fp, fieldnames=["keyword", "date", "title", "summary", "source_doc", "url"])
        w.writeheader(); w.writerows(rows)

    # 句子级：切出含检索词的句子
    srows = []
    for r in rows:
        kw = r["keyword"]
        for sent in re.split(r"(?<=[。！？；])", r["summary"]):
            sent = sent.strip()
            if sent and kw in sent:
                srows.append({"keyword": kw, "date": r["date"], "title": r["title"],
                              "sentence": sent, "source_doc": r["source_doc"]})
    out2 = args.prefix + "句子表.csv"
    with open_csv(out2) as fp:
        w = csv.DictWriter(fp, fieldnames=["keyword", "date", "title", "sentence", "source_doc"])
        w.writeheader(); w.writerows(srows)

    from collections import Counter
    stat = Counter(r["keyword"] for r in rows)
    print(f"\n去重条目 {len(rows)} 条 → {out1}")
    print(f"含词句子 {len(srows)} 句 → {out2}")
    print("\n各词命中:")
    for w, n in stat.most_common():
        print(f"  {w}: {n}")


if __name__ == "__main__":
    main()

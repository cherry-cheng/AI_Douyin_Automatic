#!/usr/bin/env python3
"""CDP 接管（已登录）→ 图文草稿，robust 版：以描述区+草稿按钮双就绪为准。"""
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"
UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"

FILES = [
    "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/output/articles/2026-08-05/ai-jumanju-400yi-douyin-cover-gemini-hd.png",
    "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/output/visual-notes-ai-剧漫剧-20260727/素材/visual-note-01-封面.png",
    "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/output/visual-notes-ai-剧漫剧-20260727/素材/visual-note-02-核心数据.png",
    "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/output/visual-notes-ai-剧漫剧-20260727/素材/visual-note-03-趋势展望.png",
]
DESC = (
    "AI剧漫剧冲400亿！同比暴涨138%，用户将达7亿🚀\n"
    "\n"
    "2026年国内AI剧漫剧市场规模预计突破400亿元🔥\n"
    "前5月已达220亿，同比+138%，2027年初用户有望达7亿！\n"
    "AI正全面重塑短剧与漫画产业，从生成到分发全链路被颠覆，成为下一个内容风口。\n"
    "\n"
    "你刷到过AI生成的短剧吗？评论区聊聊👇\n"
    "（封面及配图由AI生成）\n"
    "\n"
    "#AI短剧 #AI剧漫剧 #短剧 #人工智能 #内容风口"
)


def log(e, m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {e} {m}", flush=True)


async def snap(page):
    btns = await page.evaluate(
        "() => Array.from(document.querySelectorAll('button,[role=button]'))"
        ".filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim().slice(0,16)).filter(t=>t).slice(0,12)")
    txt = await page.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,140)")
    return btns, txt


async def main():
    for f in FILES:
        if not Path(f).exists():
            log("❌", f"缺失: {f}"); return

    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        log("🔗", "已连接，新建标签页")

        await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        # 等上传控件
        ok = False
        for w in range(20):
            await asyncio.sleep(3)
            if await page.locator("input[type='file']").count() > 0:
                log("✅", f"上传控件出现 ({(w+1)*3}s)"); ok = True; break
        if not ok:
            log("❌", "上传控件未出现"); return

        # 处理“上次未发布图文”弹窗
        for _ in range(3):
            d = await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim(); if((t==='放弃'||t==='新建图文'||t==='不再提醒')&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}} return null;}""")
            if d:
                log("ℹ️", f"弹窗: {d}"); await asyncio.sleep(2)
            else:
                break

        # 上传
        await page.locator("input[type='file']").first.set_input_files(FILES)
        log("📤", "已提交4张图，轮询编辑器双就绪(desc区+草稿按钮)…")
        ready = False
        for w in range(30):  # 90s
            await asyncio.sleep(3)
            try:
                desc = await page.locator("[contenteditable='true']").count()
                btn = await page.locator(
                    "button:has-text('存草稿'), button:has-text('暂存离开'), button:has-text('草稿')").count()
            except Exception:
                desc = btn = 0
            if w % 2 == 0:
                btns, txt = await snap(page)
                log("🔎", f"[{(w+1)*3}s] desc={desc} draftBtn={btn} btns={btns}")
                print("     text:", txt, flush=True)
            if desc > 0 and btn > 0:
                log("✅", "编辑器双就绪"); ready = True; break
        if not ready:
            log("❌", "编辑器未就绪")
            await page.screenshot(path="/tmp/dy_cdp2_notready.png")
            return

        # 填描述
        desc_filled = False
        for sel in ["[contenteditable='true']", "textarea[placeholder*='描述']",
                    "textarea[placeholder*='添加作品描述']", "[class*='desc'] [contenteditable]"]:
            elem = page.locator(sel)
            if await elem.count() > 0:
                await elem.first.click(); await asyncio.sleep(0.3)
                try:
                    await elem.first.press("Control+A"); await elem.first.press("Backspace")
                except Exception:
                    pass
                await asyncio.sleep(0.2)
                await elem.first.type(DESC, delay=12)
                log("✅", "描述已填写"); desc_filled = True; break
        if not desc_filled:
            log("⚠️", "未找到描述区")
        await asyncio.sleep(1)
        await page.screenshot(path="/tmp/dy_cdp2_after_desc.png")

        # 存草稿
        log("💾", "点击存草稿…")
        await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='我知道了'||t==='确认'||t==='关闭')&&el.offsetParent!==null&&el.children.length===0){el.click();}}}""")
        await asyncio.sleep(1)
        btn = page.locator("button:has-text('存草稿'), button:has-text('草稿'), button:has-text('暂存离开')")
        if await btn.count() > 0:
            txt_before = (await snap(page))[1]
            await btn.first.click()
            log("👉", "已点击草稿按钮")
            await asyncio.sleep(6)
            await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='我知道了'||t==='确认'||t==='暂存')&&el.offsetParent!==null&&el.children.length===0){el.click();}}}""")
            await asyncio.sleep(2)
            await page.screenshot(path="/tmp/dy_cdp2_after_draft.png")
            btns2, txt2 = await snap(page)
            log("🔎", f"存草稿后 url={page.url[:70]}")
            log("🔎", f"存草稿后 btns={btns2}")
            print("     text:", txt2, flush=True)
            log("✅", "草稿流程完成")
        else:
            log("❌", "未找到草稿按钮")
            await page.screenshot(path="/tmp/dy_cdp2_nobutton.png")


asyncio.run(main())

#!/usr/bin/env python3
"""
通过 CDP 接管【已登录的 Chrome】，上传图文草稿到抖音。
前提：Chrome 已用 --remote-debugging-port=9222 启动，且已登录抖音创作者中心。
注意：connect_over_cdp 模式下不关闭用户的浏览器，结束后只断开连接。
"""
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


async def main():
    # 文件存在性自检
    for f in FILES:
        if not Path(f).exists():
            log("❌", f"文件缺失: {f}")
            return

    async with async_playwright() as p:
        log("🔗", f"连接 CDP {CDP} ...")
        browser = await p.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        page = await context.new_page()
        log("✅", "已接管 Chrome（新建标签页）")

        await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        fi = 0
        for w in range(15):  # 轮询最多 ~45s，等认证后重 SPA 渲染
            await asyncio.sleep(3)
            try:
                fi = await page.locator("input[type='file']").count()
            except Exception:
                fi = 0
            log("🔎", f"[{(w+1)*3}s] file_inputs={fi} url={page.url[:60]}")
            if fi > 0:
                break
        if fi == 0:
            txt = await page.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,250)")
            log("⚠️", f"未检测到上传控件。页面文字: {txt}")
            await page.screenshot(path="/tmp/douyin_cdp_notready.png")
            await asyncio.sleep(15)
            return

        # 关闭"上次未发布图文"弹窗
        for _ in range(3):
            dismissed = await page.evaluate("""() => {
                const els = document.querySelectorAll('*');
                for (const el of els) {
                    const t = el.textContent.trim();
                    if ((t==='放弃'||t==='不再提醒'||t==='新建图文') && el.offsetParent!==null && el.children.length===0) { el.click(); return t; }
                }
                return null;
            }""")
            if dismissed:
                log("ℹ️", f"关闭弹窗: {dismissed}")
                await asyncio.sleep(2)
            else:
                break

        # 上传图片
        await page.locator("input[type='file']").first.set_input_files(FILES)
        log("📤", f"已提交 {len(FILES)} 张图片，等待编辑器就绪…")
        try:
            await page.wait_for_selector(
                "button:has-text('存草稿'), button:has-text('发布'), button:has-text('暂存离开')", timeout=60000)
            log("✅", "编辑器已就绪")
        except Exception:
            log("❌", "编辑器未就绪超时")
            await page.screenshot(path="/tmp/douyin_cdp_upload_timeout.png")
            return
        await asyncio.sleep(5)
        btns = await page.evaluate(
            "() => Array.from(document.querySelectorAll('button,[role=button]'))"
            ".filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim().slice(0,18)).filter(t=>t).slice(0,15)")
        log("🔎", f"当前按钮: {btns}")

        # 填描述
        desc_filled = False
        for sel in ["[contenteditable='true']", "textarea[placeholder*='描述']",
                    "textarea[placeholder*='添加作品描述']", "[class*='desc'] [contenteditable]"]:
            elem = page.locator(sel)
            if await elem.count() > 0:
                await elem.first.click()
                await asyncio.sleep(0.3)
                try:
                    await elem.first.press("Control+A")
                    await elem.first.press("Backspace")
                except Exception:
                    pass
                await asyncio.sleep(0.2)
                await elem.first.type(DESC, delay=15)
                log("✅", "描述已填写")
                desc_filled = True
                break
        if not desc_filled:
            log("⚠️", "未找到描述区")
        await asyncio.sleep(1)

        # 存草稿
        log("💾", "点击存草稿…")
        await page.evaluate("""() => { const els=document.querySelectorAll('*'); for(const el of els){const t=el.textContent.trim(); if((t==='我知道了'||t==='确认'||t==='关闭')&&el.offsetParent!==null&&el.children.length===0){el.click();}} }""")
        await asyncio.sleep(1)
        btn = page.locator("button:has-text('存草稿'), button:has-text('草稿'), button:has-text('暂存离开')")
        if await btn.count() > 0:
            await btn.first.click()
            log("👉", "已点击草稿按钮")
            await asyncio.sleep(4)
            await page.evaluate("""() => { const els=document.querySelectorAll('*'); for(const el of els){const t=el.textContent.trim(); if((t==='我知道了'||t==='确认'||t==='暂存')&&el.offsetParent!==null&&el.children.length===0){el.click();}} }""")
            await asyncio.sleep(2)
            await page.screenshot(path="/tmp/douyin_cdp_after_draft.png")
            txt = await page.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,200)")
            log("🔎", f"存草稿后页面文字: {txt}")
            log("✅", "草稿流程完成，请到草稿箱确认")
        else:
            log("❌", "未找到草稿按钮")
            await page.screenshot(path="/tmp/douyin_cdp_nobutton.png")

        # 不调用 browser.close()，避免关闭用户浏览器；脚本结束自动断开 CDP


asyncio.run(main())

#!/usr/bin/env python3
"""一次性完整发布（草稿）：上传4图 + 标题 + 描述 + 勾AIGC + 暂存。CDP接管已登录Chrome。"""
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"
UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
TITLE = "AI剧漫剧，下一个400亿风口"
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
    for f in FILES:
        if not Path(f).exists():
            log("❌", f"缺失: {f}"); return
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        log("🔗", "新建标签页，开始完整流程")

        await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        # 等上传控件
        for w in range(20):
            await asyncio.sleep(3)
            if await page.locator("input[type='file']").count() > 0:
                log("✅", f"上传控件出现 ({(w+1)*3}s)"); break
        else:
            log("❌", "上传控件未出现"); return

        # 弃用之前的草稿，新建图文
        for _ in range(3):
            d = await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='放弃'||t==='新建图文'||t==='不再提醒')&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}}return null;}""")
            if d:
                log("ℹ️", f"弃用旧草稿/弹窗: {d}"); await asyncio.sleep(2)
            else:
                break

        # 上传
        await page.locator("input[type='file']").first.set_input_files(FILES)
        log("📤", "已提交4张图，轮询编辑器双就绪…")
        ready = False
        for w in range(30):
            await asyncio.sleep(3)
            try:
                desc_c = await page.locator("[contenteditable='true']").count()
                btn = await page.locator("button:has-text('暂存离开'), button:has-text('存草稿')").count()
            except Exception:
                desc_c = btn = 0
            if w % 2 == 0:
                btns = await page.evaluate("()=>Array.from(document.querySelectorAll('button,[role=button]')).filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim().slice(0,14)).filter(t=>t).slice(0,10)")
                log("🔎", f"[{(w+1)*3}s] desc={desc_c} draftBtn={btn} btns={btns}")
            if desc_c > 0 and btn > 0:
                ready = True; log("✅", "编辑器双就绪"); break
        if not ready:
            log("❌", "编辑器未就绪"); await page.screenshot(path="/tmp/dy3_notready.png"); return

        # 数图（编辑器刚开，新鲜可靠）
        await asyncio.sleep(2)
        imgs = await page.evaluate("""()=>{
            const hi=Array.from(document.querySelectorAll('img')).filter(i=>i.offsetParent!==null && /^https?:/.test(i.src)).length;
            const bg=Array.from(document.querySelectorAll('*')).filter(e=>e.offsetParent!==null).map(e=>getComputedStyle(e).backgroundImage).filter(x=>x&&x!=='none'&&x.includes('http')).length;
            return {hi,bg};
        }""")
        log("🖼️", f"编辑器内 http图片={imgs['hi']} CDN背景图={imgs['bg']}（参考值，UI图标会干扰）")

        # 填标题
        try:
            t = page.locator("input[placeholder*='标题']")
            if await t.count() > 0:
                await t.first.click(); await asyncio.sleep(0.2)
                await t.first.fill(TITLE)
                log("🏷️", f"标题已填: {TITLE}")
        except Exception as e:
            log("⚠️", f"标题失败: {e}")

        # 填描述
        for sel in ["[contenteditable='true']", "textarea[placeholder*='描述']"]:
            elem = page.locator(sel)
            if await elem.count() > 0:
                await elem.first.click(); await asyncio.sleep(0.3)
                try:
                    await elem.first.press("Control+A"); await elem.first.press("Backspace")
                except Exception:
                    pass
                await asyncio.sleep(0.2)
                await elem.first.type(DESC, delay=12)
                log("✅", "描述已填写"); break

        # 勾选 AIGC 自主声明
        aigc_clicked = await page.evaluate("""()=>{
            const cands=['内容中含有AI生成内容','作品内容含有AI生成内容','内容由AI生成','含AI生成内容','AI生成内容'];
            // 先尝试展开自主声明区域
            const els=document.querySelectorAll('*');
            for(const el of els){const t=(el.textContent||'').trim(); if(t==='自主声明'&&el.offsetParent!==null){try{el.click();}catch(e){}}}
            for(const el of els){const t=(el.textContent||'').trim();
              if(cands.some(c=>t===c)&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}}
            return null;
        }""")
        if aigc_clicked:
            log("✅", f"已勾选AI声明: {aigc_clicked}")
        else:
            log("ℹ️", "未自动找到AI声明选项（发布前请手动在‘自主声明’勾选‘内容含有AI生成’）")

        await asyncio.sleep(1)
        await page.screenshot(path="/tmp/dy3_before_save.png")

        # 暂存离开
        await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='我知道了'||t==='确认'||t==='关闭')&&el.offsetParent!==null&&el.children.length===0){el.click();}}}""")
        await asyncio.sleep(1)
        btn = page.locator("button:has-text('暂存离开'), button:has-text('存草稿'), button:has-text('草稿')")
        if await btn.count() > 0:
            await btn.first.click()
            log("💾", "已点击暂存离开")
            await asyncio.sleep(6)
            await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='我知道了'||t==='确认'||t==='暂存')&&el.offsetParent!==null&&el.children.length===0){el.click();}}}""")
            await asyncio.sleep(2)
            await page.screenshot(path="/tmp/dy3_after_save.png")
            txt = await page.evaluate("()=>(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,160)")
            log("🔎", f"保存后文字: {txt}")
            log("✅", "=== 草稿保存完成 ===")
        else:
            log("❌", "未找到暂存按钮")
            await page.screenshot(path="/tmp/dy3_nobutton.png")


asyncio.run(main())

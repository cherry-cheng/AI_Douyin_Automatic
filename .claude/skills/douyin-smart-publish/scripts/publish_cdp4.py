#!/usr/bin/env python3
"""v4: 上传+标题+描述 → 点暂存 → 处理“自主声明”modal（读选项+勾AI+确认）→ 存草稿。"""
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


async def modal_info(page):
    return await page.evaluate("""()=>{
        const mods=Array.from(document.querySelectorAll('[role=modal],.semi-modal,.semi-modal-content,[class*=modal],[class*=Modal],[class*=dialog]')).filter(m=>m.offsetParent!==null && (m.innerText||'').trim());
        if(!mods.length) return null;
        const m=mods[mods.length-1];
        const txt=(m.innerText||'').replace(/\\s+/g,' ').slice(0,500);
        const leaves=Array.from(m.querySelectorAll('*')).filter(e=>e.offsetParent!==null && e.children.length===0).map(e=>(e.textContent||'').trim()).filter(t=>t).slice(0,40);
        const btns=Array.from(m.querySelectorAll('button,[role=button]')).filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim().slice(0,24));
        return {txt, leaves, btns};
    }""")


async def main():
    for f in FILES:
        if not Path(f).exists():
            log("❌", f"缺失: {f}"); return
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        log("🔗", "新建标签页")

        await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        for w in range(20):
            await asyncio.sleep(3)
            if await page.locator("input[type='file']").count() > 0:
                break
        # 弃旧草稿
        for _ in range(3):
            d = await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='放弃'||t==='新建图文'||t==='不再提醒')&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}}return null;}""")
            if not d: break
            log("ℹ️", f"弹窗: {d}"); await asyncio.sleep(2)

        await page.locator("input[type='file']").first.set_input_files(FILES)
        log("📤", "已提交4张图")
        # 等双就绪
        for w in range(30):
            await asyncio.sleep(3)
            try:
                dc = await page.locator("[contenteditable='true']").count()
                bt = await page.locator("button:has-text('暂存离开'), button:has-text('存草稿')").count()
            except Exception:
                dc = bt = 0
            if dc > 0 and bt > 0:
                log("✅", "编辑器就绪"); break
        else:
            log("❌", "编辑器未就绪"); return
        # 标题
        try:
            t = page.locator("input[placeholder*='标题']")
            if await t.count() > 0:
                await t.first.click(); await t.first.fill(TITLE)
                log("🏷️", f"标题: {TITLE}")
        except Exception as e:
            log("⚠️", f"标题失败 {e}")
        # 描述
        for sel in ["[contenteditable='true']", "textarea[placeholder*='描述']"]:
            elem = page.locator(sel)
            if await elem.count() > 0:
                await elem.first.click(); await asyncio.sleep(0.3)
                try:
                    await elem.first.press("Control+A"); await elem.first.press("Backspace")
                except Exception:
                    pass
                await elem.first.type(DESC, delay=12)
                log("✅", "描述已填"); break
        await asyncio.sleep(1)

        # 点暂存离开
        log("💾", "点击 暂存离开 …")
        btn = page.locator("button:has-text('暂存离开'), button:has-text('存草稿'), button:has-text('草稿')")
        if await btn.count() > 0:
            try:
                await btn.first.click(timeout=5000)
            except Exception as e:
                log("ℹ️", f"点击暂存触发拦截(预期modal): {str(e)[:80]}")
        await asyncio.sleep(2)

        # 检测并处理 自主声明 modal
        for cycle in range(4):
            mi = await modal_info(page)
            if not mi:
                log("🔎", f"cycle{cycle}: 无modal")
                break
            log("🪟", f"modal文字: {mi['txt']}")
            log("🪟", f"modal叶子文案(选项): {mi['leaves']}")
            log("🪟", f"modal按钮: {mi['btns']}")
            # 勾选 AI 声明选项
            picked = await page.evaluate("""()=>{
                const cands=['内容中含有AI生成内容','含AI生成内容','内容由AI生成','AI生成内容','含有AI'];
                const mods=Array.from(document.querySelectorAll('[role=modal],.semi-modal,.semi-modal-content,[class*=modal],[class*=Modal]')).filter(m=>m.offsetParent!==null);
                const scope=mods.length?mods[mods.length-1]:document;
                const els=scope.querySelectorAll('*');
                for(const el of els){const t=(el.textContent||'').trim(); if(cands.some(c=>t===c)&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}}
                return null;
            }""")
            if picked:
                log("✅", f"已勾选AI声明: {picked}"); await asyncio.sleep(1)
            # 点确认类按钮（确定/确认/提交/去声明完成）
            confirmed = await page.evaluate("""()=>{
                const mods=Array.from(document.querySelectorAll('[role=modal],.semi-modal,.semi-modal-content,[class*=modal],[class*=Modal]')).filter(m=>m.offsetParent!==null);
                const scope=mods.length?mods[mods.length-1]:document;
                const cands=['确定','确认','提交','完成','保存','去声明','去设置','我知道了'];
                for(const el of scope.querySelectorAll('button,[role=button]')){const t=(el.textContent||'').trim(); if(cands.includes(t)&&el.offsetParent!==null){el.click();return t;}}
                return null;
            }""")
            if confirmed:
                log("👉", f"点击确认: {confirmed}"); await asyncio.sleep(2)
            else:
                log("ℹ️", "modal无可点确认按钮，退出处理")
                break

        await asyncio.sleep(2)
        await page.screenshot(path="/tmp/dy4_final.png")
        txt = await page.evaluate("()=>(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,180)")
        log("🔎", f"最终页面文字: {txt}")
        has_draft_prompt = "未发布" in txt or "继续编辑" in txt
        log("🔎", f"出现草稿提示(未发布/继续编辑): {has_draft_prompt}")
        if has_draft_prompt:
            log("✅", "=== 草稿已保存 ===")
        else:
            log("⚠️", "未确认到草稿提示，请人工核对草稿箱")


asyncio.run(main())

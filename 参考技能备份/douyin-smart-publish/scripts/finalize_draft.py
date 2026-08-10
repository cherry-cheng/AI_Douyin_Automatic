#!/usr/bin/env python3
"""收尾：重新打开草稿→稳定后数图→补标题→勾AIGC→重新存草稿→报告。"""
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"
UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
TITLE = "AI剧漫剧，下一个400亿风口"


def log(e, m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {e} {m}", flush=True)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = next((pg for pg in ctx.pages if "upload" in pg.url), None)
        if not page:
            page = await ctx.new_page()
            await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        else:
            # 确保在上传页（可能需要重新加载以出现“继续编辑”）
            if "upload" not in page.url:
                await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 点“继续编辑”打开草稿
        clicked = await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=(el.textContent||'').trim();if(t==='继续编辑'&&el.offsetParent!==null&&el.children.length===0){el.click();return 'ok';}}return 'no-prompt';}""")
        log("👉", f"继续编辑 -> {clicked}")

        # 等编辑器稳定（出现“封面设置”或 contenteditable）
        stable = False
        for w in range(20):
            await asyncio.sleep(2)
            txt = await page.evaluate("()=>(document.body.innerText||'')")
            ce = await page.locator("[contenteditable='true']").count()
            if ("封面设置" in txt or "自主声明" in txt) and ce > 0:
                log("✅", f"编辑器稳定 ({(w+1)*2}s)"); stable = True; break
        if not stable:
            log("❌", "编辑器未稳定"); await page.screenshot(path="/tmp/dy_fin_unstable.png"); return

        # 数图：http img + CDN background-image + 可能的缩略图
        imgs = await page.evaluate("""()=>{
            const httpImgs=Array.from(document.querySelectorAll('img')).filter(i=>i.offsetParent!==null && /^https?:/.test(i.src));
            const bg=Array.from(document.querySelectorAll('*')).filter(e=>e.offsetParent!==null).map(e=>getComputedStyle(e).backgroundImage).filter(b=>b && b!=='none' && b.includes('http'));
            return {httpImg: httpImgs.length, bg: bg.length, bgSample: bg.slice(0,4)};
        }""")
        log("🖼️", f"http<img>={imgs['httpImg']} CDN背景图={imgs['bg']} 样例={imgs['bgSample']}")

        # 读描述确认
        desc = await page.evaluate("""()=>{const e=document.querySelector("[contenteditable='true']");return e?(e.innerText||'').slice(0,80):'';}""")
        log("📝", f"描述前80字: {desc}")

        # 补标题
        try:
            t = page.locator("input[placeholder*='标题'], input[placeholder*='添加作品标题']")
            if await t.count() > 0:
                await t.first.click(); await asyncio.sleep(0.2)
                await t.first.fill(TITLE)
                log("🏷️", f"标题已填: {TITLE}")
            else:
                log("ℹ️", "无标题输入框")
        except Exception as e:
            log("⚠️", f"填标题失败: {e}")

        # 尝试勾选 AIGC / 自主声明
        aigc = await page.evaluate("""()=>{
            // 找含 AI/虚构/演绎 的可点击叶子节点
            const targets=['内容中含有AI生成内容','内容由AI生成','含AI生成内容','虚构演绎','情景演绎','AI生成内容'];
            const hit=[];
            const els=document.querySelectorAll('*');
            for(const el of els){
                const t=(el.textContent||'').trim();
                if(targets.some(c=>t===c||t.includes(c)) && el.offsetParent!==null && el.children.length===0){
                    hit.push(t);
                }
            }
            return Array.from(new Set(hit)).slice(0,8);
        }""")
        log("🏷️", f"AIGC相关可点文案候选: {aigc}")
        # 尝试点第一个 AI 相关选项
        if aigc:
            try:
                await page.evaluate("""()=>{const targets=['内容中含有AI生成内容','内容由AI生成','含AI生成内容','AI生成内容'];const els=document.querySelectorAll('*');for(const el of els){const t=(el.textContent||'').trim();if(targets.some(c=>t===c)&&el.offsetParent!==null&&el.children.length===0){el.click();return t;}}return null;}""")
                log("✅", "已尝试勾选AI声明")
            except Exception as e:
                log("⚠️", f"勾选AI声明失败: {e}")
        else:
            log("ℹ️", "未找到AI声明文案（可能需手动在‘自主声明’勾选）")

        await asyncio.sleep(1)
        await page.screenshot(path="/tmp/dy_fin_before_save.png")

        # 重新存草稿（暂存离开）
        await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=el.textContent.trim();if((t==='我知道了'||t==='确认'||t==='关闭')&&el.offsetParent!==null&&el.children.length===0){el.click();}}}""")
        await asyncio.sleep(1)
        btn = page.locator("button:has-text('暂存离开'), button:has-text('存草稿'), button:has-text('草稿')")
        if await btn.count() > 0:
            await btn.first.click()
            log("💾", "已点击暂存离开，重新保存")
            await asyncio.sleep(5)
            txt2 = await page.evaluate("()=>(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,160)")
            log("🔎", f"保存后文字: {txt2}")
            log("✅", "草稿已更新保存")
        else:
            log("⚠️", "未找到暂存离开按钮（可能内容未变）")
        await page.screenshot(path="/tmp/dy_fin_after_save.png")


asyncio.run(main())

#!/usr/bin/env python3
"""最终核实：重开草稿，确认标题/描述/图片数。"""
import asyncio
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = next((pg for pg in ctx.pages if "upload" in pg.url), None)
        if not page:
            print("无 upload 页"); return

        # 点 继续编辑
        c = await page.evaluate("""()=>{const els=document.querySelectorAll('*');for(const el of els){const t=(el.textContent||'').trim();if(t==='继续编辑'&&el.offsetParent!==null&&el.children.length===0){el.click();return 'ok';}}return 'no';}""")
        print("继续编辑:", c)
        # 等编辑器稳定
        for w in range(25):
            await asyncio.sleep(2)
            txt = await page.evaluate("()=>(document.body.innerText||'')")
            ce = await page.locator("[contenteditable='true']").count()
            if ("封面设置" in txt or "添加合集" in txt) and ce > 0:
                print(f"编辑器稳定 ({(w+1)*2}s)"); break
        else:
            print("编辑器未稳定"); return
        await asyncio.sleep(3)

        # 标题
        title = await page.evaluate("""()=>{const i=document.querySelector("input[placeholder*='标题']");return i?i.value:'';}""")
        print("标题:", repr(title))
        # 描述
        desc = await page.evaluate("""()=>{const e=document.querySelector("[contenteditable='true']");return e?(e.innerText||'').slice(0,120):'';}""")
        print("描述前120字:", repr(desc))
        # 图片：多策略
        imgs = await page.evaluate("""()=>{
            const httpImg=Array.from(document.querySelectorAll('img')).filter(i=>i.offsetParent!==null&&/^https?:|^blob:/.test(i.src)).length;
            const bg=Array.from(document.querySelectorAll('*')).filter(e=>{const s=getComputedStyle(e).backgroundImage;return e.offsetParent!==null&&s&&s!=='none'&&(s.includes('http')||s.includes('blob'));}).length;
            const carousel=Array.from(document.querySelectorAll('[class*=image],[class*=Image],[class*=upload],[class*=thumb],[class*=cover]')).filter(e=>e.offsetParent!==null&&(e.querySelector('img')||getComputedStyle(e).backgroundImage!=='none')).length;
            return {httpImg,bg,carousel};
        }""")
        print("图片计数 httpImg=", imgs['httpImg'], " bg=", imgs['bg'], " carousel类元素=", imgs['carousel'])
        # 完整编辑器文字(找图片相关)
        editor_txt = await page.evaluate("()=>(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,300)")
        print("编辑器文字:", editor_txt)


asyncio.run(main())

#!/usr/bin/env python3
"""点“继续编辑”重新打开草稿，核实 标题/描述/图片 实际内容。"""
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"


def log(e, m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {e} {m}", flush=True)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        # 找上传页
        page = None
        for pg in ctx.pages:
            if "upload" in pg.url:
                page = pg; break
        if not page:
            page = ctx.pages[-1]
        log("🔗", f"操作页: {page.url[:70]}")

        # 点“继续编辑”
        clicked = await page.evaluate("""()=>{
            const els=document.querySelectorAll('*');
            for(const el of els){const t=(el.textContent||'').trim();
              if(t==='继续编辑'&&el.offsetParent!==null&&el.children.length===0){el.click();return 'ok';}}
            return 'not-found';
        }""")
        log("👉", f"点击 继续编辑 -> {clicked}")
        # 等编辑器
        for w in range(15):
            await asyncio.sleep(2)
            if await page.locator("[contenteditable='true']").count() > 0:
                break
        await asyncio.sleep(3)

        # 收集所有可编辑区域文本
        editables = await page.evaluate("""()=>{
            return Array.from(document.querySelectorAll("[contenteditable='true']")).map(e=>({
                ph: e.getAttribute('data-placeholder')||e.getAttribute('placeholder')||'',
                text: (e.innerText||'').slice(0,400)
            }));
        }""")
        textareas = await page.evaluate("""()=>{
            return Array.from(document.querySelectorAll("textarea, input[type='text']")).filter(e=>e.offsetParent!==null).map(e=>({
                ph: e.getAttribute('placeholder')||'', val: (e.value||'').slice(0,200)
            }));
        }""")
        # 图片缩略图数量（粗略：editor 内 img）
        img_info = await page.evaluate("""()=>{
            const imgs=Array.from(document.querySelectorAll('img')).filter(i=>i.offsetParent!==null);
            return {count: imgs.length, srcs: imgs.slice(0,8).map(i=>(i.src||'').slice(0,60))};
        }""")
        # 自主声明/AIGC 状态
        aigc = await page.evaluate("""()=>{
            const t=(document.body.innerText||'');
            const has = t.includes('内容由AI生成')||t.includes('AI生成');
            return {text_has_aigc: has};
        }""")

        log("📝", f"可编辑区数量: {len(editables)}")
        for i, e in enumerate(editables):
            print(f"  editable[{i}] placeholder='{e['ph']}' text='{e['text']}'", flush=True)
        log("📝", f"输入框: {len(textareas)}")
        for i, e in enumerate(textareas):
            print(f"  input[{i}] placeholder='{e['ph']}' val='{e['val']}'", flush=True)
        log("🖼️", f"可见图片数: {img_info['count']}")
        print("  srcs:", img_info['srcs'], flush=True)
        log("🏷️", f"AIGC标注文字存在: {aigc['text_has_aigc']}")
        await page.screenshot(path="/tmp/dy_verify.png")


asyncio.run(main())

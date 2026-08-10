#!/usr/bin/env python3
"""
抖音登录获取（自动点击“创作者登录” + 探测页检测登录态）。
流程：
 1) 打开上传页；若已登录（有上传控件）直接存态退出。
 2) 否则在落地页自动点击“创作者登录”，弹出扫码页。
 3) 用独立的探测页每 10s 访问上传页，检测 input[type=file]（登录成功硬证据）；
    扫码确认后 context 拿到 cookie，探测页即可见上传控件。
 4) 检测到 → 保存登录态。
注意：扫码后必须在手机上点【确认登录】。
"""
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
COOKIE_DIR = Path.home() / ".douyin_cookies"
STORAGE_STATE_FILE = COOKIE_DIR / "storage_state.json"


def log(e, m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {e} {m}", flush=True)


async def file_input_count(context):
    """用临时探测页访问上传页，返回 input[type=file] 数量。"""
    probe = await context.new_page()
    try:
        await probe.goto(UPLOAD, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        return await probe.locator("input[type='file']").count()
    except Exception as e:
        log("⚠️", f"探测失败: {e}")
        return 0
    finally:
        try:
            await probe.close()
        except Exception:
            pass


async def click_creator_login(page):
    """在落地页点击“创作者登录”按钮。"""
    return await page.evaluate(
        """() => {
            const els = document.querySelectorAll('a, button, div, span');
            for (const el of els) {
                const t = (el.textContent||'').trim();
                if (t === '创作者登录' && el.offsetParent !== null && el.children.length === 0) {
                    el.click();
                    return 'clicked';
                }
            }
            // 兜底：包含且可见
            for (const el of els) {
                const t = (el.textContent||'').trim();
                if (t === '创作者登录' && el.offsetParent !== null) { el.click(); return 'clicked-loose'; }
            }
            return 'not-found';
        }"""
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        await page.goto(UPLOAD, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # 1) 是否已登录
        n0 = await page.locator("input[type='file']").count()
        if n0 > 0:
            log("✅", "已是登录态（上传控件存在）")
            await save(context)
            await browser.close()
            return

        # 2) 点击“创作者登录”
        res = await click_creator_login(page)
        log("👉", f"点击 创作者登录 -> {res}")
        await asyncio.sleep(3)
        log("📱", "请在新弹出的扫码页用【抖音 App】扫码，并在手机上点【确认登录】。开始探测登录态（每10s一次，最多240s）…")

        # 3) 探测登录
        logged = False
        for i in range(24):  # 240s
            n = await file_input_count(context)
            log("🔎", f"[{(i+1)*10}s] 探测上传控件 file_inputs={n}")
            if n > 0:
                log("✅", "探测到上传控件，确认已登录！")
                logged = True
                break
            await asyncio.sleep(10)

        if logged:
            await save(context)
        else:
            log("❌", "超时未登录，请确认是否已在手机点【确认登录】")
        await browser.close()


async def save(context):
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(STORAGE_STATE_FILE))
    log("🍪", f"登录态已保存 → {STORAGE_STATE_FILE}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
抖音登录态获取（robust 版）。
直接打开【图文上传页】，以 input[type=file] 出现作为"真正登录"的硬证据
（不依赖 URL 判断，避免假阳性）。轮询 240s 等用户扫码。

用法: python3 scripts/login.py
"""
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

IMAGE_UPLOAD = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
COOKIE_DIR = Path.home() / ".douyin_cookies"
STORAGE_STATE_FILE = COOKIE_DIR / "storage_state.json"


def log(emoji, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {emoji} {msg}", flush=True)


async def main():
    async with async_playwright() as p:
        # 全新上下文（不加载旧 state），保证登录二维码一定弹出
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        await page.goto(IMAGE_UPLOAD, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        await page.screenshot(path="/tmp/douyin_login_qr.png")
        log("📱", "Chrome 窗口已打开上传页。若显示二维码，请用【抖音 App】扫码登录；若显示'登录'按钮请先点击。最多等待 240 秒…")

        # 硬证据轮询：上传控件出现 = 真正登录成功
        logged = False
        for i in range(48):  # 48 * 5s = 240s
            try:
                n = await page.locator("input[type='file']").count()
            except Exception:
                n = 0
            if n > 0:
                log("✅", f"检测到上传控件 (input[type=file] x{n})，确认已登录！")
                logged = True
                break
            if i % 6 == 5:  # 每 ~30s 提示一次
                log("⏳", f"仍在等待登录… ({(i+1)*5}s)")
            await asyncio.sleep(5)

        if not logged:
            log("❌", "240s 内未检测到上传控件，登录未完成")
            await page.screenshot(path="/tmp/douyin_login_timeout.png")
            await browser.close()
            return

        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(STORAGE_STATE_FILE))
        log("🍪", f"登录态已保存 → {STORAGE_STATE_FILE}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

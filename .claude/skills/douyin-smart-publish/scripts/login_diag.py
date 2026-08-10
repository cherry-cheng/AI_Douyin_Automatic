#!/usr/bin/env python3
"""
抖音登录诊断+获取（文本输出版）。
每 15s 打印页面 URL / 上传控件数 / 按钮文案 / 页面可见文字，
便于无图形界面观察时判断登录真实状态。检测到上传控件即保存登录态。

用法: python3 scripts/login_diag.py
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


async def snapshot(page):
    url = page.url
    fi = await page.locator("input[type='file']").count()
    de = await page.locator("[contenteditable='true'], textarea").count()
    btns = await page.evaluate(
        "() => Array.from(document.querySelectorAll('button,[role=button]'))"
        ".filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim().slice(0,18))"
        ".filter(t=>t).slice(0,15)"
    )
    text = await page.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,350)")
    return url, fi, de, btns, text


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        await page.goto(IMAGE_UPLOAD, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(6)
        log("📱", "上传页已打开。请扫码登录（扫码后记得在手机上点【确认登录】）。每 15s 打印一次页面状态：")
        logged = False
        for i in range(18):  # 270s
            try:
                url, fi, de, btns, text = await snapshot(page)
            except Exception as e:
                log("⚠️", f"快照失败: {e}")
                await asyncio.sleep(15)
                continue
            print(f"--- [{(i+1)*15}s] ---", flush=True)
            print(f"url   : {url[:80]}", flush=True)
            print(f"counts: file_inputs={fi} editables={de}", flush=True)
            print(f"btns  : {btns}", flush=True)
            print(f"text  : {text}", flush=True)
            if fi > 0:
                log("✅", "检测到上传控件，确认已登录！")
                COOKIE_DIR.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(STORAGE_STATE_FILE))
                log("🍪", f"登录态已保存 → {STORAGE_STATE_FILE}")
                logged = True
                break
            await asyncio.sleep(15)
        if not logged:
            log("❌", "超时未登录")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

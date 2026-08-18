// Step 5.1 — 开抖音图文上传页 + 确认登录
const task = await useOrCreateTaskSpace("douyin publish")
cliLog("task id: " + task.id)

const url = "https://creator.douyin.com/creator-micro/content/upload?default-tab=3"
await openOrReuseTab(url, { wait: true, timeout: 30 })

const snap = await snapshotText()
cliLog(snap.slice(0, 1200))
const loggedIn = !/扫码登录|二维码|抖音号登录/.test(snap)
cliLog("loggedIn=" + loggedIn)
if (!loggedIn) {
  await handOffTaskSpace(task.id)
  throw new Error("douyin_not_logged_in")
}

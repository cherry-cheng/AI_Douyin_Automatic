const task = await useOrCreateTaskSpace('douyin publish')
cliLog('task id: ' + task.id)

const IMAGE_PATHS = [
  '/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/13news_content/素材/visual-note-01-封面.png',
  '/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/13news_content/素材/visual-note-02-对比矩阵.png',
  '/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/13news_content/素材/visual-note-03-逻辑链.png',
  '/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/13news_content/素材/visual-note-04-总结.png',
]

const url = 'https://creator.douyin.com/creator-micro/content/upload?default-tab=3'
await openOrReuseTab(url, { wait: true, timeout: 30 })

const snap = await snapshotText()
cliLog(snap.slice(0, 600))
const notLoggedIn = /扫码登录|二维码|抖音号登录/.test(snap)
cliLog('LOGGED_IN=' + !notLoggedIn)
if (notLoggedIn) { await handOffTaskSpace(task.id) }

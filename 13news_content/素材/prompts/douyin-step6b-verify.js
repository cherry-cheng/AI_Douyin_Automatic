const task = await useOrCreateTaskSpace('douyin publish')
// 草稿验证：8/21 经验——manage 页没有「草稿」tab，用 upload 页「继续编辑」提示法验证
const snap = await snapshotText()
const compact = snap.replace(/\s+/g,' ')
cliLog('URL_CONFIRM: ' + compact.slice(0, 400))
// 检查是否有「你还有上次未发布的图文，是否继续编辑」提示（= 草稿已存）
cliLog('DRAFT_HINT=' + /继续编辑/.test(compact))

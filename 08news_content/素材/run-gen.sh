#!/bin/bash
# 单张视觉笔记生成 runner：$1=prompt.md路径 $2=输出png绝对路径
# 读 gen-visual-note.js 模板，注入 PROMPT/OUT_PATH，管道喂给 ego-browser nodejs
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
node -e '
const fs = require("fs");
const { spawnSync } = require("child_process");
const tpl = fs.readFileSync(process.argv[1] + "/gen-visual-note.js", "utf8");
const prompt = fs.readFileSync(process.argv[2], "utf8").replace(/^#.*\n/, "").trim();
const script = tpl
  .replace("\"__PROMPT__\"", JSON.stringify(prompt))
  .replace("\"__OUT_PATH__\"", JSON.stringify(process.argv[3]));
const r = spawnSync("ego-browser", ["nodejs"], { input: script, stdio: ["pipe", "inherit", "inherit"] });
process.exit(r.status || 0);
' "$DIR" "$1" "$2"

#!/usr/bin/env node

/**
 * 今日头条热榜获取工具
 * 抓取 https://www.toutiao.com/hot-event/hot-board/ 返回的热点榜单数据
 */

const https = require('https');
const zlib = require('zlib');

// 抓正文使用移动端 UA + 移动端 Referer，匹配 m.toutiao.com/info 接口预期
const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1';

const USER_AGENTS = [
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/123.0.0.0 Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
];

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

const DEFAULT_HEADERS = {
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
  'Referer': 'https://www.toutiao.com/',
  'Origin': 'https://www.toutiao.com',
};

function decompressBody(buffer, contentEncoding) {
  if (!contentEncoding) return buffer;
  const encoding = String(contentEncoding).toLowerCase();
  if (encoding.includes('gzip')) return zlib.gunzipSync(buffer);
  if (encoding.includes('deflate')) return zlib.inflateSync(buffer);
  if (encoding.includes('br')) return zlib.brotliDecompressSync(buffer);
  return buffer;
}

/**
 * 发起 HTTP GET 请求并解析 JSON
 * @param {string} url
 * @param {object} headers
 */
function httpGetJson(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      method: 'GET',
      headers: {
        ...DEFAULT_HEADERS,
        'User-Agent': getRandomUserAgent(),
        ...headers,
      },
    };

    const req = https.request(options, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        try {
          const buffer = Buffer.concat(chunks);
          const decompressed = decompressBody(buffer, res.headers['content-encoding']);
          const text = decompressed.toString('utf-8');
          const data = JSON.parse(text);
          resolve(data);
        } catch (e) {
          const status = res.statusCode || 0;
          reject(new Error(`Failed to parse JSON (status=${status}): ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    req.end();
  });
}

async function getHotBoard(limit = 50) {
  const safeLimit = Number.isFinite(limit) ? Math.max(1, Math.min(200, Math.floor(limit))) : 50;
  const url = 'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc';
  const resp = await httpGetJson(url);

  if (!resp || !Array.isArray(resp.data)) {
    throw new Error('获取今日头条热榜失败：返回结构不符合预期');
  }

  const items = resp.data.map((item, index) => {
    let cleanedLink = '';
    try {
      const u = new URL(item.Url);
      u.search = '';
      u.hash = '';
      cleanedLink = u.toString();
    } catch {
      cleanedLink = typeof item.Url === 'string' ? item.Url : '';
    }

    const popularity = Number.parseInt(item.HotValue, 10);

    return {
      rank: index + 1,
      title: item.Title || '',
      popularity: Number.isFinite(popularity) ? popularity : 0,
      link: cleanedLink,
      cover: item.Image && item.Image.url ? item.Image.url : null,
      label: item.LabelDesc || item.Label || null,
      clusterId: String(item.ClusterIdStr || item.ClusterId || ''),
      categories: Array.isArray(item.InterestCategory) ? item.InterestCategory : [],
    };
  });

  return items.slice(0, safeLimit);
}

/**
 * 睡眠，用于批量抓正文时降低请求频率、规避风控
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 解码常见 HTML 实体
 */
function decodeEntities(str) {
  return String(str)
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&amp;/g, '&'); // 放最后，避免二次解码
}

/**
 * 把今日头条 content 字段里的 HTML 清洗成纯文本。
 * 去掉 <img> 等标签，将 <p>/<br> 转为换行，逐段 trim 后保留非空段落。
 */
function htmlToText(html) {
  if (!html) return '';
  return decodeEntities(
    String(html)
      .replace(/<img[^>]*>/gi, '')
      .replace(/<\/(p|div|h[1-6]|li|tr)>/gi, '\n')
      .replace(/<br\s*\/?>(?=\s|$)/gi, '\n')
      .replace(/<[^>]+>/g, '')
  )
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n');
}

/**
 * 把秒/毫秒级时间戳格式化为可读字符串（失败返回 null）
 */
function formatTimestamp(ts) {
  const raw = String(ts || '').trim();
  if (!/^\d+$/.test(raw)) return null;
  const num = Number(raw);
  const ms = raw.length >= 13 ? num : num * 1000;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return null;
  // YYYY-MM-DD HH:mm:ss (UTC) —— 去掉毫秒与 T 分隔，便于阅读
  return d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z');
}

/**
 * 抓取单篇文章/热点正文。
 *
 * 数据来源：移动端 info 接口 https://m.toutiao.com/i{id}/info/
 * 该接口免签名、免 cookie，对两种 ID 均生效：
 *   - 普通文章：从热榜 item.Url 的 /article/{id} 提取的文章 ID
 *   - 热点聚合：直接使用 ClusterIdStr（话题聚合页的 ID）
 *
 * @param {string|number} id  文章 ID 或聚合 ID
 * @returns {Promise<object>}  规整后的正文数据
 */
async function getDetail(id) {
  if (!id) throw new Error('getDetail 需要传入 id');
  const safeId = String(id).replace(/[^0-9]/g, '');
  if (!safeId) throw new Error('id 必须为数字');

  const url = `https://m.toutiao.com/i${safeId}/info/`;
  const resp = await httpGetJson(url, {
    'User-Agent': MOBILE_USER_AGENT,
    'Referer': 'https://m.toutiao.com/',
    'Origin': 'https://m.toutiao.com',
  });

  const data = resp && resp.data;
  if (!data) {
    throw new Error('获取正文失败：info 接口未返回 data 字段');
  }

  const html = data.content || '';
  return {
    id: safeId,
    title: data.title || '',
    source: data.source || data.media_user || null,
    publishTime: formatTimestamp(data.publish_time),
    url: data.url || null,
    isHot: !!data.is_toutiao_hot,
    contentText: htmlToText(html),
    contentHtml: html,
    diggCount: Number(data.digg_count) || 0,
    commentCount: Number(data.comment_count) || 0,
    repostCount: Number(data.repost_count) || 0,
  };
}

/**
 * 从热榜 item.Url 中提取文章 ID（/article/{id} 形式）；提取不到返回 null。
 * 用于区分普通文章（有 articleId）与热点聚合（仅 clusterIdStr）。
 */
function extractArticleId(rawUrl) {
  if (!rawUrl) return null;
  const m = String(rawUrl).match(/\/article\/(\d+)/);
  return m ? m[1] : null;
}

/**
 * 抓取热榜并为每条补充正文。
 *
 * @param {number} limit  热榜条数（默认 10，避免一次抓取过多正文触发风控）
 * @param {object} [opts]
 * @param {number} [opts.delay=250]  每条正文请求之间的间隔（毫秒）
 */
async function getHotBoardWithContent(limit = 10, opts = {}) {
  const safeLimit = Number.isFinite(limit) ? Math.max(1, Math.min(50, Math.floor(limit))) : 10;
  const delay = Number.isFinite(opts.delay) ? Math.max(0, opts.delay) : 250;

  const items = await getHotBoard(safeLimit);
  const results = [];

  for (const item of items) {
    // 普通文章优先用文章 ID（/article/{id} 仍在清洗后的 link 路径里），
    // 热点聚合 link 形如 /trending/{id}，提取不到则 fallback 到 clusterIdStr
    const detailId = extractArticleId(item.link) || item.clusterId;
    const entry = { ...item, detail: null, detailError: null };
    try {
      entry.detail = await getDetail(detailId);
    } catch (e) {
      entry.detailError = e.message;
    }
    results.push(entry);
    if (delay > 0) await sleep(delay);
  }

  return results;
}

function printHelp() {
  console.log(`
今日头条热榜工具

用法:
  node scripts/toutiao.js <command> [args]

命令:
  hot, list [limit]      获取热榜（默认 50 条）
  detail <id>            按 ID 获取单篇正文（文章 ID 或热点聚合 ID 均可）
  content [limit]        获取热榜并抓取每条正文（默认 10 条）

示例:
  # 获取热榜（默认50条）
  node scripts/toutiao.js hot

  # 获取热榜前10条
  node scripts/toutiao.js hot 10

  # 获取某篇/某热点正文（id 来自热榜）
  node scripts/toutiao.js detail 7666646939391639615

  # 获取热榜前 5 条 + 正文
  node scripts/toutiao.js content 5
`);
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  try {
    switch (command) {
      case 'hot':
      case 'list':
      case '--hot':
      case '-h': {
        const limitArg = args[1];
        const limit = limitArg ? Number.parseInt(limitArg, 10) : 50;
        const data = await getHotBoard(limit);
        console.log(JSON.stringify(data, null, 2));
        break;
      }
      case 'detail':
      case '--detail': {
        const id = args[1];
        if (!id) {
          console.error('用法: node scripts/toutiao.js detail <id>');
          process.exit(1);
        }
        const data = await getDetail(id);
        console.log(JSON.stringify(data, null, 2));
        break;
      }
      case 'content':
      case '--content': {
        const limitArg = args[1];
        const limit = limitArg ? Number.parseInt(limitArg, 10) : 10;
        const data = await getHotBoardWithContent(limit);
        console.log(JSON.stringify(data, null, 2));
        break;
      }
      case 'help':
      case '--help':
      case '-?':
      default:
        printHelp();
        process.exit(0);
    }
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

module.exports = {
  getHotBoard,
  getDetail,
  getHotBoardWithContent,
  htmlToText,
  formatTimestamp,
};

if (require.main === module) {
  main();
}

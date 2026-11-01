import storage from "@system.storage"

const INDEX_KEY = "local_ans_index"
const LEGACY_KEY = "local_answers"
const ITEM_PREFIX = "ans_item_"
const DEFAULT_HOST = "http://192.168.10.10:25566"

const AST_TAGS = {
  t: 1, txt: 1, r: 1, f: 1, sq: 1, sup_g: 1, sub_g: 1, sup: 1, sub: 1,
  vec: 1, chem_seq: 1, chem_a: 1, m: 1, paragraph: 1, h1: 1, h2: 1, h3: 1, c: 1
}

function unwrapStorage(data) {
  if (data === undefined || data === null) return ""
  if (typeof data === "string") return data
  if (typeof data === "object") {
    if (typeof data.data === "string") return data.data
    if (data.data === null || data.data === undefined) return ""
    if (typeof data.data === "number" || typeof data.data === "boolean") {
      return String(data.data)
    }
    if (typeof data.data === "object") {
      try {
        return JSON.stringify(data.data)
      } catch (e) {
        return ""
      }
    }
  }
  return String(data)
}

function parseJson(raw, fallback) {
  const fb = fallback === undefined ? null : fallback
  if (raw === undefined || raw === null || raw === "") return fb
  if (typeof raw === "object") return raw
  try {
    const cleaned = String(raw).trim().replace(/^\uFEFF/, "")
    if (!cleaned) return fb
    return JSON.parse(cleaned)
  } catch (e) {
    return fb
  }
}

function storageGet(key, cb) {
  storage.get({
    key: key,
    success: (data) => {
      cb(unwrapStorage(data), null)
    },
    fail: (data, code) => {
      cb("", code || 1)
    }
  })
}

function storageSet(key, value, cb) {
  storage.set({
    key: key,
    value: typeof value === "string" ? value : JSON.stringify(value),
    success: () => {
      if (cb) cb(true, null)
    },
    fail: (data, code) => {
      if (cb) cb(false, code)
    }
  })
}

function storageDelete(key, cb) {
  storage.delete({
    key: key,
    success: () => {
      if (cb) cb(true)
    },
    fail: () => {
      storageSet(key, "", () => {
        if (cb) cb(true)
      })
    }
  })
}

function isAstTag(v) {
  return typeof v === "string" && AST_TAGS[v] === 1
}

function isAstNode(node) {
  return Array.isArray(node) && node.length > 0 && isAstTag(node[0])
}

function rowChildren(node) {
  if (!Array.isArray(node) || node.length < 2) return []
  if (node.length === 2 && Array.isArray(node[1])) {
    if (isAstNode(node[1])) return [node[1]]
    return node[1]
  }
  return node.slice(1)
}

function astText(node) {
  if (node === undefined || node === null) return ""
  if (typeof node === "string" || typeof node === "number") return String(node)
  if (Array.isArray(node)) {
    const tag = node[0]
    if (tag === "t" || tag === "txt") return String(node[1] || "")
    if (tag === "r") return rowChildren(node).map(astText).join("")
    if (tag === "chem_seq") {
      const kids = Array.isArray(node[1]) ? node[1] : node.slice(1)
      return kids.map(astText).join("")
    }
    if (tag === "f") return astText(node[1]) + "/" + astText(node[2])
    if (tag === "sq") return "√" + astText(node[1])
    return node.slice(1).map(astText).join("")
  }
  if (typeof node === "object") {
    if (node.raw) return String(node.raw)
    if (node.value) return String(node.value)
    if (node.ast) return astText(node.ast)
    if (node.content) return astText(node.content)
  }
  return ""
}

function inspectItem(item) {
  const pages = item && item.pages
  const pageCount = Array.isArray(pages) ? pages.length : 0
  let blockCount = 0
  let astChars = 0
  if (Array.isArray(pages)) {
    for (let i = 0; i < pages.length; i++) {
      const page = pages[i]
      const blocks = (page && page.blocks) ? page.blocks : (Array.isArray(page) ? page : [])
      if (Array.isArray(blocks)) {
        blockCount += blocks.length
        for (let j = 0; j < blocks.length; j++) {
          astChars += astText(blocks[j]).length
        }
      }
    }
  }
  const raw = item && item.raw_text ? String(item.raw_text) : ""
  return {
    pageCount: pageCount,
    blockCount: blockCount,
    astChars: astChars,
    pagesEmpty: pageCount === 0,
    blocksEmpty: blockCount === 0,
    rawEmpty: raw.trim() === "",
    astEmpty: astChars === 0
  }
}

function buildSummary(item) {
  if (item && item.summary && String(item.summary).trim()) {
    return String(item.summary).trim()
  }
  if (item && item.raw_text) {
    const t = String(item.raw_text).replace(/\s+/g, " ").trim()
    if (t) return t.substring(0, 18)
  }
  const info = inspectItem(item || {})
  if (info.astChars > 0 && item && item.pages) {
    for (let i = 0; i < item.pages.length; i++) {
      const page = item.pages[i]
      const blocks = (page && page.blocks) ? page.blocks : []
      for (let j = 0; j < blocks.length; j++) {
        const text = astText(blocks[j]).replace(/\s+/g, " ").trim()
        if (text) return text.substring(0, 18)
      }
    }
  }
  return ""
}

function toIndexEntry(item, stored) {
  const id = String((item && (item.id || item.ans_id)) || "")
  const info = inspectItem(item || {})
  const summary = buildSummary(item)
  return {
    id: id,
    ans_id: String((item && (item.ans_id || item.id)) || id),
    title: (item && item.title) || "无标题解析",
    category: (item && item.category) || "数学",
    total_pages: item && item.total_pages ? item.total_pages : info.pageCount || 1,
    summary: summary || ("共 " + (info.pageCount || 1) + " 页"),
    stored: stored !== false,
    pagesEmpty: info.pagesEmpty,
    blocksEmpty: info.blocksEmpty,
    rawEmpty: info.rawEmpty,
    astEmpty: info.astEmpty,
    blockCount: info.blockCount
  }
}

function itemKey(id) {
  return ITEM_PREFIX + String(id)
}

function loadIndex(cb) {
  storageGet(INDEX_KEY, (raw, err) => {
    let list = parseJson(raw, null)
    if (Array.isArray(list) && list.length > 0) {
      cb(list)
      return
    }
    storageGet(LEGACY_KEY, (legacyRaw) => {
      const legacy = parseJson(legacyRaw, [])
      if (!Array.isArray(legacy) || legacy.length === 0) {
        cb([])
        return
      }
      const migrated = []
      let pending = legacy.length
      if (pending === 0) {
        cb([])
        return
      }
      for (let i = 0; i < legacy.length; i++) {
        const item = legacy[i] || {}
        const entry = toIndexEntry(item, true)
        migrated.push(entry)
        storageSet(itemKey(entry.id), item, () => {
          pending -= 1
          if (pending <= 0) {
            storageSet(INDEX_KEY, migrated, () => {
              cb(migrated)
            })
          }
        })
      }
    })
  })
}

function saveIndex(list, cb) {
  storageSet(INDEX_KEY, list || [], cb)
}

function loadItem(id, cb) {
  storageGet(itemKey(id), (raw) => {
    const item = parseJson(raw, null)
    if (item) {
      cb(item)
      return
    }
    storageGet(LEGACY_KEY, (legacyRaw) => {
      const list = parseJson(legacyRaw, [])
      if (!Array.isArray(list)) {
        cb(null)
        return
      }
      let found = null
      for (let i = 0; i < list.length; i++) {
        const it = list[i]
        if (String(it.id) === String(id) || String(it.ans_id) === String(id)) {
          found = it
          break
        }
      }
      cb(found)
    })
  })
}

function upsertAnswer(item, cb) {
  const ready = item || {}
  if (!ready.id && ready.ans_id) ready.id = ready.ans_id
  if (!ready.ans_id && ready.id) ready.ans_id = ready.id
  if (!ready.category) ready.category = "数学"
  if (!ready.summary) ready.summary = buildSummary(ready)
  const info = inspectItem(ready)
  ready.total_pages = ready.total_pages || info.pageCount || 1

  storageSet(itemKey(ready.id), ready, (ok, code) => {
    loadIndex((list) => {
      const next = []
      for (let i = 0; i < list.length; i++) {
        if (String(list[i].id) !== String(ready.id) && String(list[i].ans_id) !== String(ready.id)) {
          next.push(list[i])
        }
      }
      next.unshift(toIndexEntry(ready, ok))
      saveIndex(next, () => {
        if (cb) cb(ok, code, next)
      })
    })
  })
}

function deleteAnswer(id, cb) {
  loadIndex((list) => {
    const next = []
    for (let i = 0; i < list.length; i++) {
      if (String(list[i].id) !== String(id) && String(list[i].ans_id) !== String(id)) {
        next.push(list[i])
      }
    }
    storageDelete(itemKey(id), () => {
      saveIndex(next, () => {
        storageGet(LEGACY_KEY, (legacyRaw) => {
          const legacy = parseJson(legacyRaw, [])
          if (Array.isArray(legacy) && legacy.length) {
            const kept = []
            for (let i = 0; i < legacy.length; i++) {
              const it = legacy[i]
              if (String(it.id) !== String(id) && String(it.ans_id) !== String(id)) {
                kept.push(it)
              }
            }
            storageSet(LEGACY_KEY, kept, () => {
              if (cb) cb(next)
            })
          } else if (cb) {
            cb(next)
          }
        })
      })
    })
  })
}

function clearAnswers(cb) {
  loadIndex((list) => {
    let pending = (list || []).length
    const finish = () => {
      storageSet(INDEX_KEY, "[]", () => {
        storageSet(LEGACY_KEY, "[]", () => {
          storageDelete(INDEX_KEY, () => {
            storageDelete(LEGACY_KEY, () => {
              storageDelete("current_category", () => {
                if (cb) cb(true)
              })
            })
          })
        })
      })
    }
    if (pending === 0) {
      finish()
      return
    }
    for (let i = 0; i < list.length; i++) {
      storageDelete(itemKey(list[i].id), () => {
        pending -= 1
        if (pending <= 0) finish()
      })
    }
  })
}

function describeValue(raw) {
  const empty = raw === undefined || raw === null || String(raw).trim() === ""
  let parsed = null
  let parseOk = false
  if (!empty) {
    parsed = parseJson(raw, null)
    parseOk = parsed !== null
  }
  let preview = empty ? "(空)" : String(raw)
  if (preview.length > 180) preview = preview.substring(0, 180) + "..."
  return {
    empty: empty,
    length: empty ? 0 : String(raw).length,
    parseOk: parseOk,
    isArray: Array.isArray(parsed),
    arrayLen: Array.isArray(parsed) ? parsed.length : 0,
    preview: preview,
    parsed: parsed
  }
}

function dumpStorage(cb) {
  const baseKeys = [
    INDEX_KEY,
    LEGACY_KEY,
    "current_category",
    "debug_mode",
    "reader_font_size",
    "server_host"
  ]
  loadIndex((index) => {
    const keys = baseKeys.slice()
    for (let i = 0; i < index.length; i++) {
      keys.push(itemKey(index[i].id))
    }
    const rows = []
    let pending = keys.length
    const done = () => {
      if (pending > 0) return
      cb({
        indexCount: index.length,
        index: index,
        rows: rows
      })
    }
    if (pending === 0) {
      cb({ indexCount: 0, index: [], rows: [] })
      return
    }
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i]
      storageGet(key, (raw, err) => {
        const desc = describeValue(raw)
        const row = {
          key: key,
          empty: desc.empty,
          missing: !!err && desc.empty,
          length: desc.length,
          preview: desc.preview,
          note: ""
        }
        if (key === INDEX_KEY) {
          row.note = desc.empty ? "索引为空" : ("题目 " + desc.arrayLen + " 条")
        } else if (key === LEGACY_KEY) {
          row.note = desc.empty ? "旧缓存为空" : ("旧格式 " + desc.arrayLen + " 条")
        } else if (key.indexOf(ITEM_PREFIX) === 0) {
          const item = desc.parsed
          if (!item) {
            row.note = "题目正文为空或无法解析"
          } else {
            const info = inspectItem(item)
            row.note = "页:" + (info.pagesEmpty ? "空" : info.pageCount) +
              " 块:" + (info.blocksEmpty ? "空" : info.blockCount) +
              " 原文:" + (info.rawEmpty ? "空" : "有") +
              " AST:" + (info.astEmpty ? "空" : info.astChars + "字")
          }
        } else {
          row.note = desc.empty ? "空" : "有值"
        }
        rows.push(row)
        pending -= 1
        done()
      })
    }
  })
}

function getServerHost(cb) {
  storageGet("server_host", (raw) => {
    const host = String(raw || "").trim() || DEFAULT_HOST
    cb(host.replace(/\/$/, ""))
  })
}

export default {
  INDEX_KEY: INDEX_KEY,
  LEGACY_KEY: LEGACY_KEY,
  DEFAULT_HOST: DEFAULT_HOST,
  unwrapStorage: unwrapStorage,
  parseJson: parseJson,
  storageGet: storageGet,
  storageSet: storageSet,
  storageDelete: storageDelete,
  rowChildren: rowChildren,
  astText: astText,
  inspectItem: inspectItem,
  buildSummary: buildSummary,
  toIndexEntry: toIndexEntry,
  loadIndex: loadIndex,
  loadItem: loadItem,
  upsertAnswer: upsertAnswer,
  deleteAnswer: deleteAnswer,
  clearAnswers: clearAnswers,
  dumpStorage: dumpStorage,
  getServerHost: getServerHost
}

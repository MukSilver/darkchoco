// 감시 Worker 의 판단만 시험한다. 바깥을 부르지 않는다.  node monitor/test.mjs
import assert from 'node:assert/strict'
import { check, shouldNotify } from './src/index.js'

const res = (body, ok = true) => async () => ({ json: async () => body, ok })

assert.equal(await check('x', res({ ok: true, accepting: true })), 'ok')
assert.equal(await check('x', res({ ok: true, accepting: false, reason: 'budget' })), 'budget')
assert.equal(await check('x', res({ ok: false, accepting: false, reason: 'no_version' })), 'no_version')
assert.equal(await check('x', async () => { throw new Error('연결 끊김') }), 'down')
assert.equal(await check('x', async () => ({ json: async () => { throw new Error('json 아님') } })), 'bad')

// 상태 기억이 있을 때: 바뀔 때만
assert.equal(shouldNotify(null, 'ok', 0, true), false)
assert.equal(shouldNotify(null, 'down', 0, true), true)
assert.equal(shouldNotify('ok', 'down', 7, true), true)
assert.equal(shouldNotify('down', 'down', 30, true), false)
assert.equal(shouldNotify('down', 'ok', 12, true), true)

// 상태 기억이 없을 때: 멈춰 있는 동안 30분마다
assert.equal(shouldNotify(null, 'down', 0, false), true)
assert.equal(shouldNotify(null, 'down', 10, false), false)
assert.equal(shouldNotify(null, 'down', 30, false), true)
assert.equal(shouldNotify(null, 'ok', 0, false), false)

console.log('감시 판단 시험 통과')

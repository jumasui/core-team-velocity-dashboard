const {test} = require('node:test');
const assert = require('node:assert/strict');
const {timeBins, binDurations, relativeCounts} = require('./histogram.js');

test('early time bands end at 1, 2, 4, 8 and 16', () => {
  assert.deepEqual(timeBins([.1, 1, 2, 4, 16]), [0, 1, 2, 4, 8, 16]);
  assert.deepEqual(binDurations([.1, 1, 2, 4, 16]).counts, [1, 1, 1, 1, 1]);
});
test('time bands increase linearly by 16 after the initial bands', () => {
  assert.deepEqual(timeBins([48]), [0,1,2,4,8,16,32,48]);
  assert.deepEqual(binDurations([0,1,2,4,8,16,32,48]).counts, [1,1,1,1,1,1,2]);
});
test('percentages retain the sample denominator', () => {
  assert.deepEqual(relativeCounts([1, 3]), [25, 75]);
  assert.deepEqual(relativeCounts([0, 0]), [null, null]);
  assert.throws(() => relativeCounts([-1, 3]));
});

test('boundary values enter the next bin; the final edge stays included', () => {
  assert.deepEqual(binDurations([0, 1, 2, 3], [0, 1, 2, 3]).counts, [1, 1, 2]);
});
test('missing, negative and non-finite durations are counted as omitted', () => {
  const r = binDurations([null, undefined, NaN, Infinity, -1, 0, 1], [0, 1, 2]);
  assert.equal(r.omitted, 5);
  assert.deepEqual(r.counts, [1, 1]);
});
test('empty samples do not manufacture observations', () => {
  assert.deepEqual(binDurations([]).counts, []);
  assert.deepEqual(timeBins([]), []);
});
test('zero durations remain measurable', () => {
  assert.equal(binDurations([0, 0, 0]).counts.reduce((a, b) => a + b), 3);
});
test('outliers are included without clipping', () => {
  const r = binDurations([0, .001, 1, 9999]);
  assert.equal(r.counts.reduce((a, b) => a + b), 4);
  assert.ok(r.edges.at(-1) >= 9999);
});
test('shared bins preserve separate group sample totals', () => {
  const edges = timeBins([.1, .2, 10, 20]);
  assert.deepEqual(binDurations([.1, .2], edges).edges, binDurations([10, 20], edges).edges);
  assert.equal(binDurations([10, 20], edges).counts.reduce((a, b) => a + b), 2);
});
test('invalid edges and uncovered values are rejected', () => {
  assert.throws(() => binDurations([1], [0, 0]));
  assert.throws(() => binDurations([1], [0, Infinity]));
  assert.throws(() => binDurations([3], [0, 1, 2]));
});

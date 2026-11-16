const {test} = require('node:test');
const assert = require('node:assert/strict');
const {completedIssue, selectPrs, completionCounts} = require('./cohorts.js');
const done = {open:false, completed_in_window:true, history_errors:[], reached_done:true, created_at:'2026-01-01', direct_pr_urls:['direct'], pr_urls:['direct','dependency']};
const options = {port:'all', period:'all', start:Date.parse('2025-11-16'), end:Date.parse('2026-11-16')};
test('only direct PR links to Done Jiras qualify', () => {
  const open = {...done, open:true, direct_pr_urls:['open-ticket']};
  assert.deepEqual(selectPrs([{url:'direct'}, {url:'dependency'}, {url:'open-ticket'}, {url:'unlinked'}], [done,open], options), [{url:'direct'}]);
});
test('Done duplicates remain Done, while missing history is excluded from timing', () => {
  assert.ok(completedIssue({...done, resolution:'Duplicate'}));
  assert.equal(completedIssue({...done, history_errors:['gap']}), false);
});
test('completion denominator includes unfinished and reopened Jiras but excludes older creation dates', () => {
  const result = completionCounts([done, {...done,open:true}, {...done,open:true,reached_done:false}, {...done,created_at:'2024-01-01'}], options.start, options.end);
  assert.deepEqual(result, {total:3,done:1,reopened:1,notDone:1,reached:2});
});
test('no cohort produces no invented completion percentage', () => {
  assert.equal(completionCounts([], options.start, options.end).total, 0);
});

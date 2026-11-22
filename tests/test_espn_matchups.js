/* Offline regression tests for the actual ESPN fantasy matchup scoring schema. */
'use strict';
const assert=require('node:assert/strict');
const matchups=require('../assets/espn-matchups.js');
const check=(name,run)=>{run();console.log('PASS',name)};

check('ESPN scores and projections do not become zero when unavailable',()=>{
  assert.equal(matchups.formatPoints(null),'—');
  assert.equal(matchups.formatPoints(undefined),'—');
  assert.equal(matchups.formatPoints(NaN),'—');
  assert.equal(matchups.formatPoints('129.5'),'—');
  assert.equal(matchups.formatPoints(-3),'—');
  assert.equal(matchups.formatPoints(121.5),'121.50');
  assert.equal(matchups.formatPoints(0),'0.00');
});
check('Upcoming matchup never fabricates a winning team or live score',()=>{
  const game={winner:'UNDECIDED',home:{points:0,projectedPoints:145},
    away:{points:0,projectedPoints:null}};
  assert.equal(matchups.phase(game),'UPCOMING / NOT FINAL');
  assert.equal(matchups.scored(game,'home'),null);
  assert.equal(matchups.scored(game,'away'),null);
  assert.equal(matchups.winnerSide(game),null);
});
check('Partially scored matchup remains NOT FINAL until ESPN confirms',()=>{
  const game={winner:'UNDECIDED',home:{points:93.5,projectedPoints:147},
    away:{points:0,projectedPoints:141}};
  assert.equal(matchups.phase(game),'SCORING REPORTED');
  assert.equal(matchups.scored(game,'home'),93.5);
  assert.equal(matchups.scored(game,'away'),0);
  assert.equal(matchups.winnerSide(game),null);
});
check('Final winners and losers use verified ESPN winner status',()=>{
  const game={winner:'HOME',home:{points:140.2},away:{points:108.7}};
  assert.equal(matchups.phase(game),'FINAL');
  assert.equal(matchups.winnerSide(game),'home');
  assert.equal(matchups.scored(game,'home'),140.2);
  game.winner='AWAY';
  assert.equal(matchups.winnerSide(game),'away');
  game.winner='TIE';
  assert.equal(matchups.phase(game),'FINAL');
  assert.equal(matchups.winnerSide(game),null);
});
check('Completed matchup with a legitimate zero remains zero',()=>{
  const game={winner:'AWAY',home:{points:0},away:{points:89.5}};
  assert.equal(matchups.scored(game,'home'),0);
});
check('Week selector draws only actual verified matchups in chronological order',()=>{
  const data={matchups:[
    {week:12,home:{name:'First'},away:{name:'Second'}},
    {week:10,home:{name:'Third'},away:{name:'Fourth'}},
    {week:12,home:{name:'Fifth'},away:{name:'Sixth'}},
    {week:999,home:{name:'Future'},away:{name:'Other'}},
    {week:11,home:{name:'Incomplete'}}
  ]};
  assert.deepEqual(matchups.availableWeeks(data),[10,12]);
});
check('Fantasy W-L-T records have no invented tied games',()=>{
  assert.equal(matchups.record({wins:6,losses:5,ties:0}),'6-5');
  assert.equal(matchups.record({wins:5,losses:5,ties:1}),'5-5-1');
  assert.equal(matchups.record({wins:null,losses:5}),'Record unavailable');
});
check('Team emblems can fall back to sanitized initials',()=>{
  assert.equal(matchups.initials('Sunday Morning Panic'),'SM');
  assert.equal(matchups.initials('4th'),'4T');
  assert.equal(matchups.initials(''),'??'.slice(0,2).replace('??','?'));
});
console.log('All ESPN fantasy scoreboard tests passed.');

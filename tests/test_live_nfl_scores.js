/* Offline contract tests for ESPN NFL scoreboard parsing and refresh logic. */
'use strict';
const assert=require('node:assert/strict');
const scores=require('../assets/live-nfl-scores.js');

function event(id,state,away,home,period,clock,details){
  return {
    id:String(id),
    competitions:[{competitors:[
      {homeAway:'away',team:{abbreviation:'SEA'},score:away},
      {homeAway:'home',team:{abbreviation:'LAR'},score:home},
    ]}],
    status:{period:period||0,displayClock:clock||'',
      type:{state,completed:state==='post',shortDetail:details||''}},
  };
}
function test(name,fn){try{fn();console.log('PASS',name)}catch(e){console.error('FAIL',name);throw e}}
test('pregame score 0 is NOT shown as live',()=>{
  const game=scores.parseGame(event(1,'pre','0','0',0,'','Sun, 1 PM'));
  assert.equal(game.state,'pre');assert.equal(game.away.score,null);
  assert.equal(game.home.score,null);assert.equal(scores.gameStatus(game),'SCHEDULED');
});
test('live game includes actual away and home scores, quarter and clock',()=>{
  const game=scores.parseGame(event(2,'in','17','24',3,'09:11','3rd & 10'));
  assert.equal(game.away.score,17);assert.equal(game.home.score,24);
  assert.equal(scores.gameStatus(game),'Q3 · 09:11');
  assert.equal(game.completed,false);
});
test('halftime, OT and FINAL handling',()=>{
  assert.equal(scores.gameStatus(scores.parseGame(event(3,'in','14','14',2,'0:00','Halftime'))),'HALFTIME');
  assert.equal(scores.gameStatus(scores.parseGame(event(3,'in','21','21',5,'7:02','OT'))),'OT · 7:02');
  const final=scores.parseGame(event(3,'post','27','24',4,'0:00','Final'));
  assert.equal(final.completed,true);assert.equal(scores.gameStatus(final),'FINAL');
  assert.equal(final.away.score,27);
});
test('game IDs must match and no scores are invented from missing fields',()=>{
  const d=scores.parseScoreboard({events:[event(1,'in','7','3',1,'12:10',''),event(2,'pre','','',0,'','')]},2026,12);
  assert.equal(d.size,2);assert.equal(d.get('1').away.score,7);
  assert.equal(d.has('9999'),false);
  assert.equal(scores.numericScore(''),null);
  assert.equal(scores.numericScore('NaN'),null);
  assert.equal(scores.numericScore(-20),null);
  assert.throws(()=>scores.parseScoreboard({events:[]}),/No NFL games/);
});
test('published snapshot fallback preserves verified final results',()=>{
  const final=scores.scheduleFallback({id:'401',completed:true,status:'Final',period:4,
    home:{score:'26'},away:{score:'20'}});
  assert.equal(final.state,'post');assert.equal(final.home.score,26);
  assert.equal(scores.gameStatus(final),'FINAL');
  const pending=scores.scheduleFallback({id:'402',completed:false,status:'Scheduled',
    away:{score:'0'},home:{score:'0'}});
  assert.equal(pending.state,'pre');assert.equal(pending.away.score,null);
});
test('refresh interval adapts to kickoff and live play',()=>{
  const now=new Date('2026-11-22T18:00:00Z');
  assert.equal(scores.scheduleInterval([{state:'in',date:now.toISOString()}],now),45000);
  assert.equal(scores.scheduleInterval([{state:'pre',date:'2026-11-22T19:00:00Z'}],now),60000);
  assert.equal(scores.scheduleInterval([{state:'post',date:'2026-11-22T17:00:00Z'}],now),180000);
  assert.equal(scores.scheduleInterval([{state:'pre',date:'2026-11-28T18:00:00Z'}],now),600000);
});
test('only validated ESPN NFL week/season can be requested',()=>{
  assert.equal(scores.endpoint(2026,12),
    'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=12&limit=100');
  assert.throws(()=>scores.endpoint(0,12));assert.throws(()=>scores.endpoint(2026,0));
});
test('live NFL updates require the same ESPN game and both opponent teams',()=>{
  const published={id:'401',completed:false,home:{abbr:'NYG'},away:{abbr:'PHI'}};
  const latest={id:'401',state:'in',period:2,completed:false,home:{abbr:'NYG',score:17},away:{abbr:'PHI',score:10}};
  assert.equal(scores.verifiedGameUpdate(published,latest),true);
  assert.equal(scores.verifiedGameUpdate(published,{...latest,id:'402'}),false);
  assert.equal(scores.verifiedGameUpdate(published,{...latest,home:{abbr:'PHI',score:17}}),false);
  assert.equal(scores.verifiedGameUpdate(published,{...latest,away:{abbr:'PHI',score:null}}),false);
  assert.equal(scores.numericScore([]),null);
  assert.equal(scores.numericScore({}),null);
});
test('a completed game never reverts to live or pregame',()=>{
  const published={id:'401',completed:true,home:{abbr:'NYG'},away:{abbr:'PHI'}};
  const final={id:'401',state:'post',completed:true,home:{abbr:'NYG',score:24},away:{abbr:'PHI',score:23}};
  const old={id:'401',state:'in',completed:false,home:{abbr:'NYG',score:17},away:{abbr:'PHI',score:10}};
  assert.equal(scores.verifiedGameUpdate(published,final),true);
  assert.equal(scores.verifiedGameUpdate(published,old,final),false);
  assert.equal(scores.verifiedGameUpdate({...published,completed:false},{...old,period:1},
    {...old,period:3}),false);
});
test('ESPN post state without completed confirmation is not labeled FINAL',()=>{
  const feed=event(88,'post','17','24',4,'0:00','Game over');
  feed.status.type.completed=false;
  const result=scores.parseGame(feed);
  assert.equal(result.completed,false);
  assert.match(scores.gameStatus(result),/confirmation pending/);
});

console.log('All ESPN live-score tests passed.');

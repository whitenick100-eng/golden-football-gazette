'use strict';
/* Prevent accidental mislabeling of ESPN season totals as live game stats. */
const assert=require('node:assert/strict');
const t=require('../assets/nfl-player-ticker.js');
const test=(name,fn)=>{fn();console.log('PASS',name)};
const athlete=(id,name,stats)=>({athlete:{id:String(id),displayName:name},stats});
const box={
 boxscore:{players:[
  {team:{abbreviation:'CIN'},statistics:[
   {name:'passing',labels:['C/ATT','YDS','AVG','TD','INT','SACKS','RTG'],
    athletes:[athlete(1,'Test Quarterback',['22/31','286','9.2','3','1','1-5','115.2'])]},
   {name:'rushing',labels:['CAR','YDS','AVG','TD','LONG'],
    athletes:[athlete(2,'Test Running Back',['19','127','6.7','1','29'])]},
   {name:'receiving',labels:['REC','YDS','AVG','TD','LONG','TGTS'],
    athletes:[athlete(3,'Test Wide Receiver',['7','103','14.7','2','36','10'])]},
   {name:'defensive',labels:['TOT'],athletes:[athlete(5,'Unrelated Defender',['7'])]}
  ]},
  {team:{abbreviation:'WAS'},statistics:[
   {name:'passing',labels:['C/ATT','YDS','AVG','TD','INT','SACKS','RTG'],
    athletes:[athlete(4,'Test Opposing QB',['16/25','173','6.9','0','0','0','99'])]}
  ]}
 ]}};
const event={id:'401873011',state:'in'};
test('game summary includes only true game yards and TDs, never season totals',()=>{
 const stats=t.gameBoxStats(box,event);
 assert.equal(stats.length,4);
 const qb=stats.find(x=>x.name==='Test Quarterback');
 assert.equal(qb.amount,286);assert.equal(qb.touchdowns,3);
 assert.equal(qb.text,'286 PASS YDS · 3 TD');assert.equal(qb.phase,'LIVE');
 const rb=stats.find(x=>x.kind==='rushing');
 assert.equal(rb.text,'127 RUSH YDS · 1 TD');
 const wr=stats.find(x=>x.kind==='receiving');
 assert.equal(wr.text,'103 REC YDS · 2 TD');
 assert.equal(stats.some(x=>x.name==='Unrelated Defender'),false);
});
test('pregame game box is not labeled live',()=>{
 assert.deepEqual(t.gameBoxStats(box,{...event,state:'pre'}),[]);
});
test('completed game box is labeled final',()=>{
 const p=t.gameBoxStats(box,{...event,state:'post'})[0];
 assert.equal(p.phase,'FINAL');
});
test('season scoreboard leaders must remain separate from game boxes',()=>{
 const scoreboard={events:[{id:'401873078',status:{type:{state:'in'}},
   competitions:[{competitors:[{team:{id:'1',abbreviation:'CIN'}}],
      leaders:[{name:'passingYards',leaders:[{
        athlete:{id:'1',displayName:'Test Quarterback',team:{id:'1'}},
        value:2600,displayValue:'2600 YDS, 20 TD'
      }]}]
   }]}]};
 const values=t.seasonLeaders(scoreboard);
 assert.equal(values[0].amount,2600);
 assert.equal(values[0].phase,'SEASON');
 assert.equal(values[0].text,'2600 YDS, 20 TD');
 assert.equal(values[0].team,'CIN');
 // A live game state never changes the season metric's source label.
 assert.notEqual(values[0].phase,'LIVE');
});
test('ticker covers live and completed games from the same NFL week',()=>{
 const events=[{id:'1',state:'pre',date:'2026-11-22T18:00:00Z'},
 {id:'2',state:'in',date:'2026-11-22T18:00:00Z'},
 {id:'3',state:'post',date:'2026-11-19T20:00:00Z'}];
 const active=t.selectGames(events);
 assert.deepEqual(active.games.map(x=>x.id),['2','3']);
 assert.equal(active.active,1);
 assert.equal(active.partial,false);
 const final=t.selectGames(events.filter(x=>x.state!=='in'));
 assert.deepEqual(final.games.map(x=>x.id),['3']);
 assert.equal(final.active,0);
});
test('full 16-game NFL week is covered instead of truncating after eight games',()=>{
 const events=Array.from({length:16},(_,i)=>({
   id:String(i+1),state:'post',date:'2026-11-22T20:00:00Z'
 }));
 const result=t.selectGames(events);
 assert.equal(result.games.length,16);
 assert.equal(result.partial,false);
 assert.equal(result.active,0);
});
test('direct ESPN scoreboard automatically detects next regular-season week',()=>{
 const first={season:{year:2026,type:2},week:{number:11}};
 const next={season:{year:2026,type:2},week:{number:12}};
 assert.deepEqual(t.currentWeek(first),{season:2026,week:11});
 assert.deepEqual(t.currentWeek(next),{season:2026,week:12});
 assert.equal(t.boardURL(...Object.values(t.currentWeek(next))),
   'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=12&limit=100');
 assert.throws(()=>t.currentWeek({season:{year:2026,type:3},week:{number:1}}));
 assert.throws(()=>t.currentWeek({season:{year:2026,type:2},week:{number:null}}));
});
test('numbers reject missing/invalid stats instead of inventing points',()=>{
 for(const value of ['',undefined,null,'NaN',{},[]]){
   assert.equal(t.numeric(value),null);
 }
 assert.equal(t.numeric('0'),0);
 const bad={name:'passing',labels:['YDS','TD']};
 assert.equal(t.statEntry(bad,athlete(2,'Example',['','']), 'CIN', event),null);
});
test('week/game identifiers cannot insert URLs or arbitrary network destinations',()=>{
 assert.throws(()=>t.summaryURL('123&redirect=https://evil.test'));
 assert.throws(()=>t.boardURL(2026,0));
 assert.equal(t.summaryURL('401873011'),
 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401873011');
});
test('top player leaders use actual yard values and limit per category',()=>{
 const rows=t.gameBoxStats(box,event);
 const best=t.topByKind(rows,1);
 assert.equal(best.length,3);
 assert.deepEqual(best.map(p=>p.kind),['passing','rushing','receiving']);
});
console.log('All NFL player-stat ticker tests passed.');

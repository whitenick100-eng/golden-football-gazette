/* Offline regression tests: NFL-exclusive live mode and seven-sport fallback. */
'use strict';
const assert=require('node:assert/strict');
const multi=require('../assets/multisport-ticker.js');
const nfl=require('../assets/nfl-player-ticker.js');
const sport=id=>multi.SPORTS.find(s=>s.id===id);
const now=Date.parse('2026-11-23T19:00:00Z');
const teams=(state='post',date='2026-11-22T23:00:00Z')=>({
 events:[{id:'401000000',date,status:{type:{state}},name:'Test match',
   competitions:[{competitors:[
     {homeAway:'away',score:'109',team:{abbreviation:'AWY'}},
     {homeAway:'home',score:'102',team:{abbreviation:'HME'}}
   ]}],links:[{href:'https://www.espn.com/nba/game/_/gameId/401000000'}]}]
});
function test(name,run){run();console.log('PASS',name)}
test('all requested sports are included exactly once',()=>{
 assert.deepEqual(multi.SPORTS.map(s=>s.id),[
  'NBA','WNBA','PGA','NCAA MEN','NCAA WOMEN','MLB','NASCAR']);
 assert.equal(new Set(multi.SPORTS.map(s=>s.path)).size,7);
});
test('only a real in-progress NFL game activates NFL-exclusive mode',()=>{
 const status=state=>({events:[{id:'4019901',status:{type:{state}}}]});
 assert.equal(nfl.nflGameInProgress(status('pre')),false);
 assert.equal(nfl.nflGameInProgress(status('post')),false);
 assert.equal(nfl.nflGameInProgress(status('in')),true);
 assert.equal(nfl.nflGameInProgress({events:[
   {id:'1',status:{type:{state:'post'}}},
   {id:'2',status:{type:{state:'in'}}}
 ]}),true);
 assert.equal(nfl.nflGameInProgress({events:[]}),false);
 assert.equal(nfl.nflGameInProgress(null),false);
});
test('NBA/WNBA/NCAA/MLB scores require actual ESPN scores and live/final state',()=>{
 for(const id of ['NBA','WNBA','NCAA MEN','NCAA WOMEN','MLB']){
  const rows=multi.scoreRows(teams(),sport(id),now);
  assert.equal(rows.length,1,id);
  assert.equal(rows[0].name,'AWY 109 — HME 102');
  assert.equal(rows[0].team,'FINAL');
  assert.equal(rows[0].sport,id);
  assert.equal(rows[0].href,'https://www.espn.com/nba/game/_/gameId/401000000');
  assert.equal(multi.scoreRows(teams('pre'),sport(id),now).length,0);
  assert.equal(multi.scoreRows(teams('post','2026-11-10T20:00:00Z'),sport(id),now).length,0);
  const missing=teams();delete missing.events[0].competitions[0].competitors[0].score;
  assert.equal(multi.scoreRows(missing,sport(id),now).length,0);
 }
 const live=multi.scoreRows(teams('in'),sport('NBA'),now);
 assert.equal(live[0].team,'LIVE');
});
test('PGA leaderboard uses explicit athlete order and published score',()=>{
 const doc={events:[{date:'2026-11-22T19:00:00Z',
  status:{type:{state:'post'}},name:'Test Tour Event',
  competitions:[{competitors:[
   {order:2,athlete:{displayName:'Second Golfer'},score:'-13'},
   {order:1,athlete:{displayName:'First Golfer'},score:'-15'}
  ]}]}]};
 const result=multi.scoreRows(doc,sport('PGA'),now);
 assert.equal(result.length,1);
 assert.equal(result[0].text,'First Golfer -15');
 assert.equal(result[0].team,'RESULT');
 doc.events[0].competitions[0].competitors[1].order=undefined;
 assert.equal(multi.scoreRows(doc,sport('PGA'),now).length,0);
});
test('NASCAR race leader requires ESPN position 1, not a guessed winner',()=>{
 const doc={events:[{date:'2026-11-22T19:00:00Z',
  status:{type:{state:'in'}},name:'Test NASCAR Race',
  competitions:[{competitors:[{order:1,athlete:{displayName:'Race Leader'}}]}]}]};
 assert.equal(multi.scoreRows(doc,sport('NASCAR'),now)[0].text,'Race Leader · P1');
 assert.equal(multi.scoreRows(doc,sport('NASCAR'),now)[0].team,'LIVE LEADER');
 doc.events[0].competitions[0].competitors[0].order=7;
 assert.equal(multi.scoreRows(doc,sport('NASCAR'),now).length,0);
});
test('news is dated, article-linked and never automatically miscalled breaking',()=>{
 const doc={articles:[{
  headline:'Star player moves to new team',type:'HeadlineNews',
  published:'2026-11-23T15:00:00Z',
  links:{web:{href:'https://www.espn.com/nba/story/_/id/123/star-player'}}
 },{
  headline:'Old off-season article',published:'2025-11-23T15:00:00Z',
  links:{web:{href:'https://www.espn.com/nba/story/_/id/456/old'}}
 },{
  headline:'Breaking: confirmed trade',type:'BreakingNews',published:'2026-11-23T14:00:00Z',
  links:{web:{href:'https://www.espn.com/nba/story/_/id/789/trade'}}
 }]};
 const rows=multi.newsRows(doc,sport('NBA'),now);
 assert.equal(rows.length,2);
 assert.equal(rows[0].team,'LATEST NEWS');
 assert.equal(rows[1].team,'BREAKING');
 assert.ok(rows[0].text.includes('Nov 23'));
});
test('hostile article and game URLs are rejected',()=>{
 for(const bad of ['javascript:alert(1)','https://www.espn.com.evil.test/x',
                   'http://www.espn.com/x','https://evil.test/x']){
  assert.equal(multi.espnLink(bad),null);
 }
 const bad={articles:[{headline:'False story',
  published:'2026-11-23T12:00:00Z',
  links:{web:{href:'javascript:alert(1)'}}}]};
 assert.equal(multi.newsRows(bad,sport('NBA'),now).length,0);
});
test('mixed ticker gives each sport fair placement instead of NBA-only coverage',()=>{
 const feeds=Object.fromEntries(multi.SPORTS.map(s=>[
   s.id,{scores:[{sport:s.id,kind:'score',name:'Score'}],
         news:[{sport:s.id,kind:'news',name:'Headline'}]}]));
 const mixed=multi.mixRows(feeds);
 assert.equal(mixed.length,14);
 assert.deepEqual(mixed.slice(0,4).map(r=>r.sport),['NBA','NBA','WNBA','WNBA']);
 assert.deepEqual(new Set(mixed.map(r=>r.sport)).size,7);
});
async function offlineIntegration(){
 const fake={
  fetch:async url=>{
    if(url.includes('/basketball/nba/scoreboard'))return {ok:true,json:async()=>teams()};
    if(url.includes('/basketball/nba/news'))return {ok:true,json:async()=>({
      articles:[{headline:'Verified NBA headline',
      published:new Date(Date.now()-60*60*1000).toISOString(),
      links:{web:{href:'https://www.espn.com/nba/story/_/id/12345/verified'}}}]
    })};
    throw Error('Simulated ESPN feed outage');
  },
  setTimeout,clearTimeout
 };
 const result=await multi.load(fake,true);
 assert.equal(result.sourcesAvailable,2);
 assert.equal(result.partial,true);
 assert.equal(result.rows.some(r=>r.sport==='NBA'&&r.kind==='news'),true);
 assert.equal(result.rows.every(r=>r.href.startsWith('https://www.espn.com/')),true);
 console.log('PASS partial outages keep verified items, without fabricated fillers');
}
offlineIntegration().catch(err=>{console.error(err);process.exitCode=1});

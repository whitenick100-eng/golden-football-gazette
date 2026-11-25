/* Offline regression tests: NFL-exclusive live mode and nine-league selectable scores/news. */
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
  'NFL','NBA','WNBA','PGA','NCAA FB','NCAA MEN','NCAA WOMEN','MLB','NASCAR']);
 assert.equal(new Set(multi.SPORTS.map(s=>s.path)).size,9);
 assert.deepEqual(multi.SPORT_IDS,['ALL',...multi.SPORTS.map(s=>s.id)]);
 assert.equal(multi.validSportSelection('NFL'),true);
 assert.equal(multi.validSportSelection('ALL'),true);
 assert.equal(multi.validSportSelection('NBA; DROP TABLE'),false);
 assert.equal(sport('NFL').path,'football/nfl');
 assert.equal(sport('NCAA FB').kind,'team');
 assert.equal(sport('NCAA FB').path,'football/college-football');
 assert.equal(sport('NCAA FB').scoreboardQuery,'scoreboard?groups=80&limit=100');
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
 for(const id of ['NFL','NBA','WNBA','NCAA FB','NCAA MEN','NCAA WOMEN','MLB']){
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
test('NASCAR rejects ESPN race scores; official NASCAR.com headlines only',()=>{
 const doc={events:[{date:'2026-11-22T19:00:00Z',
  status:{type:{state:'in'}},name:'ESPN race',
  competitions:[{competitors:[{order:1,athlete:{displayName:'Race Leader'}}]}]}]};
 assert.equal(multi.scoreRows(doc,sport('NASCAR')).length,0);
 assert.equal(sport('NASCAR').page,'https://www.nascar.com/');
 assert.notEqual(sport('NASCAR').path,'racing/nascar-premier');
});
test('NASCAR.com news accepts only exact official dated news permalinks',()=>{
 const fresh=new Date(Date.now()-24*60*60*1000);
 const day=fresh.toISOString().slice(0,10);
 const parts=day.split('-');
 const url='https://www.nascar.com/news-media/'+parts.join('/')+'/official-cup-series-story/';
 const feed={schema:1,source:'NASCAR.com',status:'available',
   fetchedAt:new Date().toISOString(),articles:[
    {title:'NASCAR confirms an official Cup Series story',url,
     date:day,dateBasis:'official NASCAR.com dated article permalink',type:'news'},
    {title:'ESPN NASCAR news should be blocked',url:'https://www.espn.com/racing/nascar/story/123',
     date:day,dateBasis:'official NASCAR.com dated article permalink',type:'news'},
    {title:'Spoofed NASCAR.com hostname is rejected',
     url:'https://www.nascar.com.evil.test/news-media/'+parts.join('/')+'/official-story/',
     date:day,dateBasis:'official NASCAR.com dated article permalink',type:'news'}
   ],results:[]};
 const rows=multi.nascarRows(feed);
 assert.equal(rows.scores.length,0);
 assert.equal(rows.news.length,1);
 assert.equal(rows.news[0].sport,'NASCAR');
 assert.equal(rows.news[0].href,url);
 assert.ok(rows.news[0].text.startsWith('NASCAR.com · '));
 assert.equal(multi.nascarLink('https://www.espn.com/racing/nascar/'),null);
 assert.equal(multi.nascarLink('javascript:alert(1)'),null);
 assert.throws(()=>multi.nascarRows({...feed,source:'ESPN'}));
 assert.throws(()=>multi.nascarRows({...feed,status:'unavailable'}));
});
test('ESPN cross-listed racing stories never appear as NASCAR ticker news',()=>{
 const row=multi.newsRows({articles:[{
  headline:'NASCAR Cup Series championship article',
  published:new Date().toISOString(),
  links:{web:{href:'https://www.espn.com/racing/nascar/story/_/id/12345'}}
 }]},sport('NBA'));
 assert.equal(row.length,0);
});

test('news is dated, article-linked and never automatically miscalled breaking',()=>{
 const doc={articles:[{
  headline:'Star player traded to a new team',type:'HeadlineNews',
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
 assert.equal(rows[0].team,'BREAKING');
 assert.equal(rows[1].team,'MAJOR NEWS');
 assert.ok(rows[0].text.includes('Nov 23'));
});
test('news keeps its sport badge but corrects cross-listed ESPN article topics',()=>{
 const article=(href,extra={})=>({
  headline:'A confirmed major trade',
  published:'2026-11-23T17:00:00Z',
  links:{web:{href}},...extra
 });
 const nba=sport('NBA');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/nba/story/_/id/1'),nba),'NBA');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/college-football/story/_/id/2'),nba),'NCAA FB');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/wnba/story/_/id/3'),nba),'WNBA');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/espn/story/_/id/4',{
  categories:[{type:'league',description:'NASCAR'}]
 }),nba),'NASCAR');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/espn/story/_/id/5',{
  categories:[{type:'team',description:'NASCAR'}]
 }),nba),'NBA');
 assert.equal(multi.classifyNewsSport(article('https://www.espn.com/mlb/story/_/id/6',{
  categories:[{type:'league',description:'NBA'}]
 }),nba),'MLB'); // Canonical article route has priority over mismatched metadata.
 const crossListed=multi.newsRows({articles:[article(
  'https://www.espn.com/college-football/story/_/id/2'
 )]},nba,now);
 assert.equal(crossListed.length,1);
 assert.equal(crossListed[0].sport,'NCAA FB');
 assert.equal(crossListed[0].kind,'news');
 assert.equal(crossListed[0].name,'A confirmed major trade');
});
test('cross-posted NFL news gets its own accurate NFL badge, never a false NBA badge',()=>{
 const rows=multi.newsRows({articles:[
  {headline:'Breaking: NFL quarterback traded',type:'BreakingNews',published:'2026-11-23T18:00:00Z',
   links:{web:{href:'https://www.espn.com/nfl/story/_/id/7'}}},
  {headline:'NBA star injured ahead of playoffs',published:'2026-11-23T17:00:00Z',
   links:{web:{href:'https://www.espn.com/nba/story/_/id/8'}}}
 ]},sport('NBA'),now);
 assert.equal(rows.length,2);
 assert.equal(rows.find(x=>x.sport==='NFL').team,'BREAKING');
 assert.equal(rows.find(x=>x.sport==='NBA').name,'NBA star injured ahead of playoffs');
});
test('cross-listed identical articles appear only once in mixed sport rotation',()=>{
 const href='https://www.espn.com/wnba/story/_/id/12345';
 const story={sport:'WNBA',kind:'news',href,name:'Verified WNBA news'};
 const feeds={
  NBA:{scores:[],news:[story]},
  WNBA:{scores:[],news:[{...story}]}
 };
 const result=multi.mixRows(feeds);
 assert.equal(result.filter(r=>r.href===href).length,1);
});
test('breaking stories stay prominent while ordinary recent news also appears',()=>{
 const mk=(headline,ageHours,type='HeadlineNews')=>({
  headline,type,
  published:new Date(now-ageHours*60*60*1000).toISOString(),
  links:{web:{href:'https://www.espn.com/nba/story/_/id/'+
    (headline.length*13+Math.round(ageHours*10))+'/'+encodeURIComponent(headline)}}
 });
 const rows=multi.newsRows({articles:[
   mk('Weekend podcast: predictions and odds',1),
   mk('NBA superstar signs record contract',9),
   mk('All-time player traded in blockbuster deal',3),
   mk('Breaking: playoff contender fires head coach',2,'BreakingNews'),
   mk('Rookie injured ahead of championship final',55),
   mk('Power rankings and preview',1)
 ]},sport('NBA'),now);
 assert.equal(rows.length,4);
 assert.equal(rows[0].team,'BREAKING');
 assert.equal(rows[0].name,'Breaking: playoff contender fires head coach');
 assert.equal(rows[1].name,'All-time player traded in blockbuster deal');
 assert.equal(rows[2].name,'Rookie injured ahead of championship final');
 assert.equal(rows[2].team,'LATEST NEWS'); // >48h: notable but no longer fresh breaking.
 assert.equal(rows[3].name,'NBA superstar signs record contract');
 assert.ok(rows.every(row=>row.sport==='NBA'&&row.date>=now-30*24*60*60*1000));
 assert.equal(multi.newsImportance(mk('Random podcast recap',1),now),null);
 assert.equal(multi.newsImportance(mk('Player signs new deal',55),now).label,'LATEST NEWS');
 assert.equal(multi.newsImportance(mk('One ordinary game was played',2),now).label,'LATEST NEWS');
 const yesterday=multi.newsImportance(mk('Breaking: player signs record contract',22,'BreakingNews'),now);
 assert.ok(yesterday);
 assert.equal(yesterday.breaking,false,'Old alerts must not stay labeled breaking');
 const fresh=multi.newsImportance(mk('Breaking: star traded',2,'BreakingNews'),now);
 assert.equal(fresh.breaking,true);
});
test('ordinary sport reporting displays even when no major news is available',()=>{
 const article=(headline,days,id)=>({
   headline,published:new Date(now-days*24*60*60*1000).toISOString(),
   links:{web:{href:'https://www.espn.com/wnba/story/_/id/'+id+'/verified'}}});
 const onlyRegular={articles:[
  article('Roster outlook before next season',2,1),
  article('Team announces new home schedule',8,2),
  article('Community programs growing through basketball',12,3),
  article('WNBA player interview following training',31,4)
 ]};
 const rows=multi.newsRows(onlyRegular,sport('WNBA'),now);
 assert.equal(rows.length,3);
 assert.deepEqual(rows.map(x=>x.team),['LATEST NEWS','RECENT NEWS','RECENT NEWS']);
 assert.ok(rows.every(x=>x.sport==='WNBA'));
 assert.ok(rows.every(x=>x.href.startsWith('https://www.espn.com/wnba/')));
});
test('offseason older news remains labeled and sourced instead of fabricated',()=>{
 const article=(headline,days,id)=>({
  headline,published:new Date(now-days*24*60*60*1000).toISOString(),
  links:{web:{href:'https://www.espn.com/wnba/story/_/id/'+id+'/story'}}});
 const feed={articles:[
  article('League announces updated season plans',21,1),
  article('Team reflects on season achievements',26,2),
  article('Retired player looks back on career',45,3)
 ]};
 const rows=multi.newsRows(feed,sport('WNBA'),now);
 assert.equal(rows.length,2);
 assert.ok(rows.every(x=>x.team==='OLDER NEWS'));
 assert.ok(rows.every(x=>x.text.includes('ESPN ·')));
});
test('weekly sports still show actual final scores with event date',()=>{
 const weekly=multi.scoreRows(teams('post','2026-11-17T23:00:00Z'),sport('NCAA FB'),now);
 assert.equal(weekly.length,1);
 assert.equal(weekly[0].team,'FINAL');
 assert.ok(weekly[0].text.includes('Nov 17'));
 const tooOld=multi.scoreRows(teams('post','2026-11-14T23:00:00Z'),sport('NCAA FB'),now);
 assert.equal(tooOld.length,0);
});
test('selected tabs show up to 3 scores plus 4 news, All Sports has a shorter mix',()=>{
 const news=Array.from({length:4},(_,i)=>({
  sport:'NBA',kind:'news',name:'ESPN verified story '+i,
  href:'https://www.espn.com/nba/story/_/id/'+(9000+i)
 }));
 const scores=Array.from({length:3},(_,i)=>({
  sport:'NBA',kind:'score',name:'Verified NBA score '+i,
  date:now-i*1000,href:'https://www.espn.com/nba/game/_/gameId/'+(8000+i)
 }));
 const feed={NBA:{news,scores}};
 const selected=multi.mixRows(feed,'NBA');
 assert.equal(selected.length,7);
 assert.equal(selected.filter(row=>row.kind==='score').length,3);
 assert.equal(selected.filter(row=>row.kind==='news').length,4);
 assert.deepEqual([...new Set(selected.map(r=>r.sport))],['NBA']);
 const all=multi.mixRows(feed);
 assert.equal(all.length,5);
 assert.equal(all.filter(row=>row.kind==='news').length,2);
});
test('verified game scores are prioritized ahead of major news per sport',()=>{
 const feeds={
  NBA:{
   scores:[{sport:'NBA',kind:'score',name:'LAL 111 — BOS 110'},
           {sport:'NBA',kind:'score',name:'NYK 99 — MIA 98'},
           {sport:'NBA',kind:'score',name:'ORL 102 — CHI 100'}],
   news:[{sport:'NBA',kind:'news',href:'https://www.espn.com/nba/story/_/id/5',
    name:'Breaking: major roster trade'}]
  }
 };
 const rows=multi.mixRows(feeds);
 assert.deepEqual(rows.slice(0,4).map(x=>x.kind),
  ['score','score','news','score']);
 assert.equal(rows[0].sport,'NBA');
 assert.equal(rows[2].sport,'NBA');
});
test('all nine leagues fit in the complete score/news rotation',()=>{
 const rows=multi.mixRows(Object.fromEntries(multi.SPORTS.map(s=>[
   s.id,{
     scores:Array.from({length:3},(_,i)=>({
       sport:s.id,kind:'score',name:s.id+' verified score '+i,
       date:now-i*1000,href:s.page
     })),
     news:[{sport:s.id,kind:'news',name:'Significant '+s.id+' headline',href:s.page+'/story/123'}]
   }
 ])));
 assert.equal(rows.length,36);
 assert.equal(rows.some(r=>r.sport==='NASCAR'&&r.kind==='news'),true);
 assert.equal(rows.some(r=>r.sport==='NFL'&&r.kind==='score'),true);
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
         news:[{sport:s.id,kind:'news',name:'Headline',href:s.page}]}]));
 const mixed=multi.mixRows(feeds);
 assert.equal(mixed.length,18);
 assert.deepEqual(mixed.slice(0,4).map(r=>r.sport),['NFL','NFL','NBA','NBA']);
 assert.deepEqual(new Set(mixed.map(r=>r.sport)).size,9);
});
async function nascarSourceIsolation(){
 const urls=[];
 const day=new Date(Date.now()-24*60*60*1000).toISOString().slice(0,10);
 const link='https://www.nascar.com/news-media/'+day.replace(/-/g,'/')+'/verified-cup-series-story/';
 const mock={fetch:async url=>{
   urls.push(url);
   if(url.startsWith('data/nascar-ticker.json?ts='))return {ok:true,json:async()=>({
     schema:1,source:'NASCAR.com',status:'available',fetchedAt:new Date().toISOString(),
     articles:[{title:'NASCAR announces verified Cup Series developments',url:link,date:day,
       dateBasis:'official NASCAR.com dated article permalink',type:'news'}],
     results:[]})};
   throw Error('NASCAR-only selection fetched another sport: '+url);
 },setTimeout,clearTimeout};
 const data=await multi.load(mock,true,'NASCAR');
 assert.equal(urls.length,1,'NASCAR must fetch only the locally published official NASCAR.com snapshot');
 assert.equal(data.sourcesAvailable,1);
 assert.equal(data.selectedSport,'NASCAR');
 assert.equal(data.rows.length,1);
 assert.ok(data.rows.every(r=>r.sport==='NASCAR'&&r.href.startsWith('https://www.nascar.com/')));
 assert.ok(!urls.some(url=>url.includes('site.api.espn.com')||url.includes('racing/nascar')));
 console.log('PASS NASCAR-only official source is isolated from all ESPN sports');
}

async function selectedSportIntegration(){
 const calls=[];
 const recent=new Date(Date.now()-60*60*1000).toISOString();
 const mock={
  fetch:async url=>{
   calls.push(url);
   if(url.includes('/football/nfl/scoreboard'))return {ok:true,json:async()=>teams('post',recent)};
   if(url.includes('/football/nfl/news'))return {ok:true,json:async()=>({
     articles:[{headline:'Breaking: NFL team fires coach',type:'BreakingNews',published:recent,
       links:{web:{href:'https://www.espn.com/nfl/story/_/id/541/coach'}}}]
   })};
   if(url.includes('/basketball/nba/scoreboard'))return {ok:true,json:async()=>teams('post',recent)};
   if(url.includes('/basketball/nba/news'))return {ok:true,json:async()=>({
     articles:[{headline:'NBA star traded in major deal',published:recent,
       links:{web:{href:'https://www.espn.com/nba/story/_/id/542/trade'}}}]
   })};
   throw Error('unexpected sport requested: '+url);
  },setTimeout,clearTimeout
 };
 const nflOnly=await multi.load(mock,true,'NFL');
 assert.equal(nflOnly.selectedSport,'NFL');
 assert.equal(nflOnly.partial,false);
 assert.equal(nflOnly.sourcesAvailable,2);
 assert.equal(calls.length,2,'Selecting NFL should fetch NFL only, not all nine leagues');
 assert.ok(calls.every(x=>x.includes('/football/nfl/')));
 assert.equal(nflOnly.rows.length,2);
 assert.ok(nflOnly.rows.some(x=>x.kind==='score'&&x.sport==='NFL'&&x.team==='FINAL'));
 assert.ok(nflOnly.rows.some(x=>x.kind==='news'&&x.sport==='NFL'&&x.team==='BREAKING'));
 const count=calls.length;
 const cached=await multi.load(mock,false,'NFL');
 assert.equal(calls.length,count,'Selecting an unchanged league must reuse its fresh ESPN cache');
 assert.equal(cached.rows.length,2);
 const nbaOnly=await multi.load(mock,true,'NBA');
 assert.equal(calls.length,4,'Selecting NBA must fetch only its own two ESPN feeds');
 assert.ok(nbaOnly.rows.length>0&&nbaOnly.rows.every(x=>x.sport==='NBA'));
 await assert.rejects(multi.load(mock,true,'NFL<script>'),/Unknown sports ticker filter/);
 console.log('PASS sport buttons select and cache only requested ESPN league feeds');
}
async function offlineIntegration(){
 const fake={
  fetch:async url=>{
    if(url.includes('/basketball/nba/scoreboard'))return {ok:true,json:async()=>teams('post',new Date(Date.now()-12*60*60*1000).toISOString())};
    if(url.includes('/football/college-football/scoreboard')){
      assert.ok(url.includes('groups=80'),'Fetch FBS scoreboard for NCAA football');
      return {ok:true,json:async()=>teams('post',new Date(Date.now()-8*60*60*1000).toISOString())};
    }
    if(url.includes('/basketball/nba/news'))return {ok:true,json:async()=>({
      articles:[{headline:'NBA superstar signs record contract',
      published:new Date(Date.now()-60*60*1000).toISOString(),
      links:{web:{href:'https://www.espn.com/nba/story/_/id/12345/verified'}}}]
    })};
    throw Error('Simulated ESPN feed outage');
  },
  setTimeout,clearTimeout
 };
 const result=await multi.load(fake,true);
 assert.equal(result.sourcesAvailable,3);
 assert.equal(result.rows.some(r=>r.sport==='NCAA FB'&&r.kind==='score'),true);
 assert.equal(result.partial,true);
 assert.equal(result.rows.some(r=>r.sport==='NBA'&&r.kind==='news'),true);
 assert.equal(result.rows.every(r=>r.href.startsWith('https://www.espn.com/')),true);
 console.log('PASS partial outages keep verified items, without fabricated fillers');
}
nascarSourceIsolation().then(selectedSportIntegration).then(offlineIntegration).catch(err=>{console.error(err);process.exitCode=1});

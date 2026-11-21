/* Golden Football Gazette NFL scoreboard — browser-side live scores.
 * Official source: ESPN public NFL scoreboard. No GitHub deploy is needed
 * between plays. Source data remains authoritative; no estimated scores.
 */
(function(root){
'use strict';
const BASE='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard';
const PRE='pre', LIVE='in', POST='post';

function numericScore(value){
  if(value===null||value===undefined||value==='')return null;
  const n=Number(value);
  return Number.isFinite(n)&&n>=0&&n<300?n:null;
}

function parseGame(event){
  if(!event || event.id===undefined)return null;
  const competition=(event.competitions||[])[0];
  if(!competition || !Array.isArray(competition.competitors))return null;
  const st=event.status||{};
  const type=st.type||{};
  const state=['pre','in','post'].includes(type.state)?type.state:
    (type.completed?POST: st.period>0?LIVE:PRE);
  const sides={};
  for(const c of competition.competitors){
    if(c.homeAway==='home'||c.homeAway==='away'){
      sides[c.homeAway]={score:state===PRE?null:numericScore(c.score)};
    }
  }
  if(!sides.home||!sides.away)return null;
  let detail=typeof type.shortDetail==='string'?type.shortDetail.trim():
    typeof type.detail==='string'?type.detail.trim():'';
  detail=detail.slice(0,70);
  const clock=typeof st.displayClock==='string'?st.displayClock.slice(0,14):'';
  const period=Number.isInteger(st.period)&&st.period>=0&&st.period<=9?st.period:0;
  return {id:String(event.id),state,completed:state===POST && !!(type.completed||type.state===POST),
    period,clock,detail,home:sides.home,away:sides.away};
}

function parseScoreboard(payload,year,week){
  if(!payload||!Array.isArray(payload.events))throw Error('Invalid ESPN NFL scoreboard response');
  // ESPN sometimes returns a generic week; game ID matching prevents cross-week substitution.
  const games=new Map();
  for(const event of payload.events){
    const game=parseGame(event);
    if(game)games.set(game.id,game);
  }
  if(!games.size)throw Error('No NFL games found in scoreboard feed');
  return games;
}

function gameStatus(game){
  if(game.state===POST)return game.completed?'FINAL':'Game ended · confirmation pending';
  if(game.state===LIVE){
    const value=game.detail.toLowerCase();
    if(value.includes('half'))return 'HALFTIME';
    if(value.includes('delay')||value.includes('suspend'))return 'DELAYED';
    if(value.includes('end of'))return game.detail;
    if(game.period>4)return 'OT'+(game.clock?' · '+game.clock:'');
    if(game.period>=1)return 'Q'+game.period+(game.clock?' · '+game.clock:'');
    return game.detail||'LIVE';
  }
  const detail=game.detail.toLowerCase();
  if(detail.includes('postpon')||detail.includes('cancel'))return game.detail.toUpperCase();
  return 'SCHEDULED';
}

function scheduleFallback(item){
  const status=(item.status||'').toLowerCase();
  const completed=!!item.completed;
  const clock=typeof item.displayClock==='string'?item.displayClock:'';
  const period=Number.isInteger(item.period)?item.period:0;
  const live=(!completed && (item.state==='in'||item.statusType==='in'||status.includes('progress')));
  return {id:String(item.id),state:completed?POST:live?LIVE:PRE,completed,period,clock,
    detail:String(item.status||'').slice(0,70),
    away:{score:completed||live?numericScore(item.away?.score):null},
    home:{score:completed||live?numericScore(item.home?.score):null}};
}
function scheduleInterval(games,now){
  const n=now.getTime();
  if(games.some(g=>g.state===LIVE))return 45000;
  const close=games.some(g=>{
    if(g.state===POST)return false;
    const ms=Date.parse(g.date);
    return Number.isFinite(ms)&&ms-n<3*3600000&&ms-n>-(6*3600000);
  });
  if(close)return 60000;
  const recentlyEnded=games.some(g=>{
    const ms=Date.parse(g.date);
    return g.state===POST&&Number.isFinite(ms)&&n-ms>=0&&n-ms<6*3600000;
  });
  return recentlyEnded?180000:600000;
}
function endpoint(year,week){
  if(!Number.isInteger(year)||year<2020||year>2100||
      !Number.isInteger(week)||week<1||week>22)throw Error('Unverified NFL season/week');
  return BASE+'?dates='+year+'&seasontype=2&week='+week+'&limit=100';
}

const api={parseGame,parseScoreboard,gameStatus,scheduleFallback,scheduleInterval,endpoint,numericScore};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root||!root.document||!root.fetch)return;
root.GazetteNFL=api;

let schedule=null,feed=new Map(),working=false,timer=null,lastSuccess=null;
let inFlight=false;
const doc=root.document;
const $=id=>doc.getElementById(id);
function label(message){
 const el=$('live-score-status');if(el)el.textContent=message;
}
function formatTime(date){
 return date.toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
}
function updateOne(card,item,verified){
 if(!card)return;
 const home=card.querySelector('[data-score-side="home"]');
 const away=card.querySelector('[data-score-side="away"]');
 const status=card.querySelector('[data-nfl-phase]');
 const link=card.querySelector('[data-gamecast-link]');
 if(home)home.textContent=item.home.score===null?'—':String(item.home.score);
 if(away)away.textContent=item.away.score===null?'—':String(item.away.score);
 if(status){
   status.className='score-phase score-phase-'+item.state;
   status.textContent=gameStatus(item);
   if(item.state===LIVE&&verified)status.classList.add('is-live');
 }
 const stamp=card.querySelector('[data-score-verification]');
 if(stamp)stamp.textContent=verified?'ESPN live scoreboard · last successful update':'Last published ESPN snapshot';
 if(link&&/^[0-9]+$/.test(item.id))link.href='https://www.espn.com/nfl/game/_/gameId/'+item.id;
}
function paint(verified){
 if(!schedule)return;
 for(const original of schedule.games||[]){
   const id=String(original.id);
   const item=feed.get(id)||scheduleFallback(original);
   // Team scores are never crossed between games; both cards share the same event ID.
   for(const card of doc.querySelectorAll('.game-card[data-nfl-game-id="'+id+'"]')){
     updateOne(card,item,verified&&feed.has(id));
   }
 }
}
function next(){
 if(timer)root.clearTimeout(timer);
 if(!working)return;
 const games=(schedule.games||[]).map(g=>Object.assign({},g,{state:(feed.get(String(g.id))||scheduleFallback(g)).state}));
 timer=root.setTimeout(refresh,scheduleInterval(games,new Date()));
}
async function refresh(){
 if(!working||!schedule||inFlight)return;
 if(doc.hidden){next();return;}
 inFlight=true;
 label('Checking ESPN live NFL scoreboard…');
 try{
   const controller=new AbortController();
   const timeout=root.setTimeout(()=>controller.abort(),15000);
   let response;
   try{
     response=await root.fetch(endpoint(Number(schedule.season),Number(schedule.week)),{
       mode:'cors',cache:'no-store',credentials:'omit',signal:controller.signal
     });
   }finally{
     root.clearTimeout(timeout);
   }
   if(!response.ok)throw Error('ESPN scoreboard HTTP '+response.status);
   const current=parseScoreboard(await response.json());
   const ids=new Set((schedule.games||[]).map(g=>String(g.id)));
   // Reject a cross-week API response: never mislabel scores for another week.
   const matches=[...current.keys()].filter(id=>ids.has(id));
   if(matches.length===0)throw Error('No verified ESPN event IDs match this NFL week');
   feed=current;
   lastSuccess=new Date();
   paint(true);
   const active=matches.filter(id=>current.get(id).state===LIVE).length;
   label((active?'● '+active+' NFL game'+(active===1?'':'s')+' live':'Scores checked')+
     ' · ESPN refreshed '+formatTime(lastSuccess)+
     ' · Automatic refresh when page is open');
 }catch(err){
   paint(!!lastSuccess);
   const message=lastSuccess
       ?'Live scoreboard temporarily unreachable · Last successful ESPN check '+formatTime(lastSuccess)
       :'Live scoreboard unavailable · Showing the last published ESPN snapshot';
   label(message+' · Use ESPN Gamecast for latest');
   console.warn('Gazette NFL live-score update:',err.message);
 }finally{
   inFlight=false;
   next();
 }
}

api.start=function(data){
 if(!data||!Array.isArray(data.games)||!data.games.length)return;
 schedule=data;feed=new Map();working=true;lastSuccess=null;
 paint(false);refresh();
 if(!api.eventsRegistered){
   api.eventsRegistered=true;
   doc.addEventListener('visibilitychange',()=>{if(!doc.hidden&&working)refresh()});
   root.addEventListener('online',()=>{if(working)refresh()});
   const btn=$('refresh-nfl-scores');
   if(btn)btn.addEventListener('click',()=>refresh());
 }
};
api.stop=function(){working=false;if(timer)root.clearTimeout(timer)};
})(typeof window!=='undefined'?window:null);

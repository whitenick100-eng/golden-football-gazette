/* The Golden Football Gazette — verified NFL player-stat ticker.
 * ESPN game summary boxscore = GAME statistics. ESPN scoreboard leaders =
 * SEASON totals, never live game stats. All values keep explicit mode labels.
 */
(function(root){
'use strict';
const BASE='https://site.api.espn.com/apis/site/v2/sports/football/nfl/';
const CATEGORIES={passing:{short:'PASS',stat:'PASS YDS'},
                  rushing:{short:'RUSH',stat:'RUSH YDS'},
                  receiving:{short:'REC',stat:'REC YDS'},
                  fantasy:{short:'FANTASY',stat:'FANTASY PTS'}};
const MAX_GAMES=18;
const MAX_PARALLEL_BOX_SCORES=4;
const CURRENT_BOARD_URL=BASE+'scoreboard?limit=100';
const REFRESH_GAME_MS=90000,REFRESH_OTHER_MS=600000;
const FINAL_BOX_RECHECK_MS=15*60*1000; // Post-game stat corrections can arrive after FINAL.

function numeric(v){
 if(typeof v!=='number'&&typeof v!=='string')return null;
 if(String(v).trim()==='')return null;
 const n=Number(v);
 return Number.isFinite(n)&&n>=-100&&n<10000?n:null;
}
function statEntry(section,person,team,game){
 if(!CATEGORIES[section?.name]||!person||!Array.isArray(person.stats))return null;
 const labels=section.labels||[];
 const y=labels.indexOf('YDS'),td=labels.indexOf('TD');
 if(y<0||td<0||y>=person.stats.length||td>=person.stats.length)return null;
 const yards=numeric(person.stats[y]),touchdowns=numeric(person.stats[td]);
 const name=person.athlete?.displayName||person.athlete?.fullName;
 const playerId=person.athlete?.id;
 if(typeof name!=='string'||!name.trim()||yards===null||touchdowns===null||
    yards< -100||yards>1000||!Number.isInteger(touchdowns)||touchdowns<0||touchdowns>15)return null;
 // Exclude non-participating, zero-activity placeholder rows.
 if(yards===0&&touchdowns===0)return null;
 return {
   name:name.trim().slice(0,90),playerId:String(playerId||''),
   team:typeof team==='string'?team.slice(0,8):'',
   kind:section.name,amount:yards,touchdowns,
   gameId:String(game?.id||''),phase:game?.state==='in'?'LIVE':'FINAL',
   text:yards+' '+CATEGORIES[section.name].stat+' · '+touchdowns+' TD'
 };
}
function gameBoxStats(doc,event){
 const groups=doc?.boxscore?.players;
 if(!Array.isArray(groups)||!event||!['in','post'].includes(event.state))return [];
 // A summary response for a different matchup must never be shown as this game.
 const reportedId=doc?.header?.id;
 if(reportedId!==undefined&&reportedId!==null&&String(reportedId)!==String(event.id))return [];
 const players=[];
 for(const team of groups){
   const abbr=team?.team?.abbreviation||'';
   for(const section of team?.statistics||[]){
     if(!CATEGORIES[section?.name])continue;
     for(const athlete of section.athletes||[]){
       const p=statEntry(section,athlete,abbr,event);
       if(p)players.push(p);
     }
   }
 }
 return players;
}
function scoreboardLeaders(board){
 const found=new Map();
 for(const ev of board?.events||[]){
   const comp=ev?.competitions?.[0];
   for(const section of comp?.leaders||[]){
     const kind=section.name==='passingYards'?'passing':
       section.name==='rushingYards'?'rushing':
       section.name==='receivingYards'?'receiving':null;
     if(!kind)continue;
     for(const entry of section.leaders||[]){
       const id=String(entry?.athlete?.id||'');
       const name=entry?.athlete?.displayName||entry?.athlete?.fullName;
       const yards=numeric(entry?.value);
       const text=entry?.displayValue;
       if(!id||!name||yards===null)continue;
       const teamId=String(entry?.team?.id||entry?.athlete?.team?.id||'');
       let abbr='';
       for(const side of comp?.competitors||[]){
         if(String(side?.team?.id||'')===teamId)abbr=side.team.abbreviation||'';
       }
       const key=kind+'-'+id;
       const item={name,playerId:id,team:abbr,kind,amount:yards,
         touchdowns:null,phase:'SCOREBOARD',
         text:typeof text==='string'&&text.trim()?text.slice(0,95):yards+' '+CATEGORIES[kind].stat};
       if(!found.has(key)||item.amount>found.get(key).amount)found.set(key,item);
     }
   }
 }
 return topByKind([...found.values()],4);
}
function topByKind(input,limit=4){
 const rows=[];const seen=new Set();
 for(const kind of ['passing','rushing','receiving']){
   const sorted=input.filter(p=>p.kind===kind).sort((a,b)=>b.amount-a.amount);
   let n=0;
   for(const p of sorted){
     const key=kind+':'+p.playerId+':'+p.name;
     if(seen.has(key))continue;
     seen.add(key);rows.push(p);n++;
     if(n>=limit)break;
   }
 }
 return rows;
}
function boardEvents(board){
 return (board?.events||[]).map(e=>({
   id:String(e.id||''),
   state:e.status?.type?.state,
   date:e.date
 })).filter(e=>/^\d+$/.test(e.id));
}
function selectGames(events){
 // Keep all games already underway or finished from the *same NFL week*.
 // Never mix these per-game box scores with scoreboard season-leader totals.
 const played=events.filter(e=>e.state==='in'||e.state==='post')
   .sort((a,b)=>(b.state==='in')-(a.state==='in') ||
      ((Date.parse(b.date)||0)-(Date.parse(a.date)||0)));
 return {games:played.slice(0,MAX_GAMES),
   active:played.filter(g=>g.state==='in').length,
   partial:played.length>MAX_GAMES};
}
function currentWeek(board){
 const season=Number(board?.season?.year);
 const week=Number(board?.week?.number);
 const seasonType=Number(board?.season?.type ?? 2);
 if(!Number.isInteger(season)||season<2024||season>2100||
    !Number.isInteger(week)||week<1||week>22||seasonType!==2){
   throw Error('ESPN current NFL regular-season week not verified');
 }
 return {season,week};
}
function boardURL(year,week){
 if(!Number.isInteger(year)||year<2024||year>2100||!Number.isInteger(week)||week<1||week>22){
   throw Error('NFL season/week not verified');
 }
 return BASE+'scoreboard?dates='+year+'&seasontype=2&week='+week+'&limit=100';
}
function summaryURL(id){
 if(!/^\d+$/.test(String(id)))throw Error('Unexpected ESPN game ID');
 return BASE+'summary?event='+id;
}
const api={numeric,statEntry,gameBoxStats,scoreboardLeaders,topByKind,boardEvents,
           selectGames,currentWeek,boardURL,summaryURL};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root||!root.document||!root.fetch)return;
root.GazetteStatTicker=api;
const doc=root.document,bar=doc.getElementById('nfl-stat-track'),
  status=doc.getElementById('nfl-stat-ticker-status'),
  mode=doc.getElementById('nfl-stat-ticker-mode'),
  btn=doc.getElementById('nfl-stat-ticker-refresh');
if(!bar||!status||!mode||!btn)return;
let inFlight=false,timer=null,last=null,stop=false,season=null,week=null;
// Rotate in newly recorded player performances before recycling old leaders.
const previouslySeen=new Map();
let previouslyFeatured=new Set();
let previouslyShown=[];
const playerKey=p=>[p.gameId,p.kind,p.playerId||p.name].join(':');
function newlyRecorded(players){
 const changed=[];
 const fresh=new Map();
 for(const p of players){
   const key=[p.gameId,p.kind,p.playerId||p.name].join(':');
   const stat=[p.amount,p.touchdowns].join(':');
   if(previouslySeen.get(key)!==stat)changed.push(p);
   fresh.set(key,stat);
 }
 previouslySeen.clear();for(const [key,value] of fresh)previouslySeen.set(key,value);
 if(!changed.length&&previouslyShown.length){
   const latest=new Map(players.map(p=>[playerKey(p),p]));
   const same=previouslyShown.map(p=>latest.get(playerKey(p))).filter(Boolean);
   if(same.length)return {rows:same,changed:0};
 }
 const chosen=[];
 for(const kind of ['passing','rushing','receiving']){
   const eligible=players.filter(p=>p.kind===kind);
   const changes=changed.filter(p=>p.kind===kind);
   const sorter=(a,b)=>Number(b.phase==='LIVE')-Number(a.phase==='LIVE')||b.amount-a.amount;
   const ordered=[...changes.filter(p=>!previouslyFeatured.has(p.playerId)).sort(sorter),
     ...changes.filter(p=>previouslyFeatured.has(p.playerId)).sort(sorter),
     ...eligible.filter(p=>!previouslyFeatured.has(p.playerId)).sort(sorter),
     ...eligible.sort(sorter)];
   const used=new Set();let total=0;
   for(const p of ordered){const key=p.playerId||p.name;if(used.has(key))continue;
     chosen.push(p);used.add(key);if(++total===4)break;}
 }
 previouslyFeatured=new Set(chosen.map(p=>p.playerId||p.name));
 previouslyShown=chosen;
 return {rows:chosen,changed:changed.length};
}

const finalBoxCache=new Map();
const tag=(name,value,cls)=>{const element=doc.createElement(name);
  if(value!==undefined)element.textContent=String(value);
  if(cls)element.className=cls;return element};
function dateLabel(date){
 return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',
   month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(date);
}
function makeCard(player,duplicate){
 const link=tag('a',undefined,'nfl-player-ticker-item');
 if(/^\d+$/.test(player.playerId||'')){
   link.href='https://www.espn.com/nfl/player/_/id/'+player.playerId;
   link.target='_blank';link.rel='noopener noreferrer';
 }else{
   link.removeAttribute('href');link.classList.add('not-linked');
 }
 if(duplicate)link.tabIndex=-1;
 const kind=tag('span',CATEGORIES[player.kind]?.short||'NFL','ticker-stat-kind');
 link.append(kind,tag('strong',player.name,'ticker-player-name'),
  tag('span',player.team,'ticker-player-team'),
  tag('span',player.text,'ticker-player-stat'));
 return link;
}
function paint(data){
 last=data;
 bar.replaceChildren();
 if(!data.rows.length){
   bar.append(tag('span','Verified player statistics are not available yet.','ticker-empty'));
   bar.classList.remove('ticker-animate');return;
 }
 const first=tag('div',undefined,'nfl-stat-group');
 for(const p of data.rows)first.append(makeCard(p,false));
 bar.append(first);
 if(data.rows.length>1){
   const clone=tag('div',undefined,'nfl-stat-group');
   clone.setAttribute('aria-hidden','true');
   for(const p of data.rows)clone.append(makeCard(p,true));
   bar.append(clone);bar.classList.add('ticker-animate');
 }else bar.classList.remove('ticker-animate');
 mode.textContent=data.mode;
 status.textContent=(data.stale?'Last verified':'ESPN checked')+' '+dateLabel(data.checked)+
  (data.partial?' · Partial game coverage':'')+
  ' · '+(data.notes||'');
}
async function loadJSON(url,timeout=16000){
 const controller=new AbortController();
 const limit=root.setTimeout(()=>controller.abort(),timeout);
 try{
   const r=await root.fetch(url,{mode:'cors',cache:'no-store',credentials:'omit',signal:controller.signal});
   if(!r.ok)throw Error('ESPN returned HTTP '+r.status);
   return await r.json();
 }finally{root.clearTimeout(limit)}
}
function next(ms){
 if(timer)root.clearTimeout(timer);
 if(!stop)timer=root.setTimeout(refresh,ms);
}
async function fallbackFantasy(){
 const r=await root.fetch('data/top-performers.json?ts='+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error('No published fantasy leaderboard');
 const data=await r.json();
 if(data.leagueId!==1413446022||data.season!==season||!Array.isArray(data.players))throw Error('No verified fantasy leaderboard');
 const rows=data.players.filter(p=>typeof p.name==='string'&&numeric(p.points)!==null)
   .map(p=>({name:p.name,playerId:String(p.playerId||''),
     team:p.position||'NFL',kind:'fantasy',amount:p.points,
     text:Number(p.points).toFixed(2)+' FANTASY PTS'})).slice(0,5);
 if(!rows.length)throw Error('No fantasy player totals');
 return {rows,mode:'LAST COMPLETED FANTASY WEEK '+data.week,
         checked:new Date(data.fetchedAt),notes:'ESPN fantasy points · not live NFL stats',partial:false};
}
// Resolve the week from ESPN at runtime: the ticker can roll into the next
// week's games even before the daily GitHub Pages data publication completes.
async function latestWeek(){
 try{
   return {...currentWeek(await loadJSON(CURRENT_BOARD_URL,12000)),
     source:'ESPN current week'};
 }catch(_){
   // The scheduled daily publication is an explicit, verified fallback.
   const snap=await loadJSON('data/nfl-week.json?ts='+Date.now());
   if(!Number.isInteger(snap.season)||snap.season<2024||snap.season>2100||
      !Number.isInteger(snap.week)||snap.week<1||snap.week>22){
     throw Error('No verified NFL week');
   }
   return {season:snap.season,week:snap.week,source:'Published ESPN schedule'};
 }
}
async function boxForGame(game){
 const cached=finalBoxCache.get(game.id);
 // Completed boxes are immutable; fetch them once per visit. Live boxes
 // are always checked again so the scroll updates during games.
 if(game.state==='post'&&cached?.state==='post'&&
    Date.now()-cached.checkedAt<FINAL_BOX_RECHECK_MS)return {rows:cached.rows,stale:false};
 try{
   const stats=gameBoxStats(await loadJSON(summaryURL(game.id),15000),game);
   if(stats.length)finalBoxCache.set(game.id,{state:game.state,rows:stats,checkedAt:Date.now()});
   return {rows:stats,stale:false};
 }catch(error){
   if(cached?.state===game.state)return {rows:cached.rows,stale:true};
   throw error;
 }
}
async function fetchWeeklyBoxes(games){
 const result=new Array(games.length);
 let index=0;
 async function worker(){
   while(index<games.length){
     const i=index++;
     try{result[i]=await boxForGame(games[i]);}
     catch(_){result[i]={rows:[],failed:true};}
   }
 }
 await Promise.all(Array.from({length:Math.min(MAX_PARALLEL_BOX_SCORES,games.length)},()=>worker()));
 return result;
}
async function refresh(){
 if(inFlight||stop)return;
 if(doc.hidden){next(REFRESH_OTHER_MS);return}
 inFlight=true;btn.disabled=true;
 try{
   const current=await latestWeek();
   if(current.season!==season||current.week!==week){
     // No last-week players should silently carry over to a new game week.
     finalBoxCache.clear();previouslySeen.clear();previouslyFeatured.clear();previouslyShown=[];
   }
   season=current.season;week=current.week;
   const board=await loadJSON(boardURL(season,week));
   if(!Array.isArray(board.events)||!board.events.length)throw Error('ESPN NFL scoreboard has no events');
   const selected=selectGames(boardEvents(board));
   const results=await fetchWeeklyBoxes(selected.games);
   let rows=[],partial=selected.partial;
   for(const item of results){
     rows.push(...item.rows);
     if(item.failed||item.stale||!item.rows.length)partial=true;
   }
   if(rows.length){
     const hasFinal=selected.games.some(g=>g.state==='post');
     const heading=selected.active?
       'NFL WEEK '+week+' · LIVE'+(hasFinal?' + FINAL':'')+' GAME STATS':
       'NFL WEEK '+week+' GAME STATS';
     const chosen=newlyRecorded(rows);
     paint({rows:chosen.rows,mode:heading+(chosen.changed?' · NEW STATS':''),
       checked:new Date(),notes:'Passing · rushing · receiving · ESPN game box scores · '+current.source,
       partial,stale:results.some(x=>x.stale)});
   }else{
     const leaders=scoreboardLeaders(board);
     if(!leaders.length)throw Error('ESPN player stats unavailable');
     paint({rows:leaders,mode:'ESPN NFL SCOREBOARD LEADERS',
       checked:new Date(),notes:selected.active?
          'Game box scores pending · ESPN scoreboard figures; not verified season totals · '+current.source:
          'ESPN scoreboard figures · not independently verified season totals · '+current.source,
       partial:!!selected.games.length});
   }
   next(selected.active?REFRESH_GAME_MS:REFRESH_OTHER_MS);
 }catch(e){
   if(last){
     paint({...last,stale:true,notes:'Source temporarily unavailable · '+(last.notes||'')});
   }else{
     try{paint(await fallbackFantasy())}
     catch(_){status.textContent='ESPN stat feed temporarily unavailable';mode.textContent='NFL PLAYER STATS'}
   }
   next(REFRESH_OTHER_MS);
   console.warn('Gazette NFL stat ticker:',e.message);
 }finally{inFlight=false;btn.disabled=false}
}
btn.addEventListener('click',refresh);
doc.addEventListener('visibilitychange',()=>{if(!doc.hidden)refresh()});
root.addEventListener('online',refresh);
refresh();
})(typeof window!=='undefined'?window:null);

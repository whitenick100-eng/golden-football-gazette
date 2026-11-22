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
const MAX_GAMES=8;
const REFRESH_GAME_MS=90000,REFRESH_OTHER_MS=600000;

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
 if(typeof name!=='string'||!name.trim()||yards===null||touchdowns===null)return null;
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
function seasonLeaders(board){
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
         touchdowns:null,phase:'SEASON',
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
 const active=events.filter(e=>e.state==='in');
 const complete=events.filter(e=>e.state==='post')
   .sort((a,b)=>Date.parse(b.date)-Date.parse(a.date));
 // Never mix FINAL game totals into a ticker marked LIVE.
 const candidates=active.length?active:complete;
 return {games:candidates.slice(0,MAX_GAMES),active:active.length,
   partial:candidates.length>MAX_GAMES};
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
const api={numeric,statEntry,gameBoxStats,seasonLeaders,topByKind,boardEvents,
           selectGames,boardURL,summaryURL};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root||!root.document||!root.fetch)return;
root.GazetteStatTicker=api;
const doc=root.document,bar=doc.getElementById('nfl-stat-track'),
  status=doc.getElementById('nfl-stat-ticker-status'),
  mode=doc.getElementById('nfl-stat-ticker-mode'),
  btn=doc.getElementById('nfl-stat-ticker-refresh');
if(!bar||!status||!mode||!btn)return;
let inFlight=false,timer=null,last=null,stop=false,season=2026,week=null;
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
 if(data.leagueId!==1413446022||data.season!==2026||!Array.isArray(data.players))throw Error('No verified fantasy leaderboard');
 const rows=data.players.filter(p=>typeof p.name==='string'&&numeric(p.points)!==null)
   .map(p=>({name:p.name,playerId:String(p.playerId||''),
     team:p.position||'NFL',kind:'fantasy',amount:p.points,
     text:Number(p.points).toFixed(2)+' FANTASY PTS'})).slice(0,5);
 if(!rows.length)throw Error('No fantasy player totals');
 return {rows,mode:'LAST COMPLETED FANTASY WEEK '+data.week,
         checked:new Date(data.fetchedAt),notes:'ESPN fantasy points · not live NFL stats',partial:false};
}
async function refresh(){
 if(inFlight||stop)return;
 if(doc.hidden){next(REFRESH_OTHER_MS);return}
 inFlight=true;btn.disabled=true;
 try{
   const snap=await loadJSON('data/nfl-week.json?ts='+Date.now());
   if(!Number.isInteger(snap.season)||!Number.isInteger(snap.week))throw Error('No verified NFL week');
   season=snap.season;week=snap.week;
   const board=await loadJSON(boardURL(season,week));
   if(!Array.isArray(board.events)||!board.events.length)throw Error('ESPN NFL scoreboard has no events');
   const selected=selectGames(boardEvents(board));
   let rows=[],errors=0,partial=selected.partial;
   if(selected.games.length){
     const result=await Promise.allSettled(selected.games.map(async g=>{
       const summary=await loadJSON(summaryURL(g.id),15000);
       return gameBoxStats(summary,g);
     }));
     for(const item of result){
       if(item.status==='fulfilled')rows.push(...item.value);
       else errors++;
     }
     partial=partial||errors>0;
   }
   if(rows.length){
     paint({rows:topByKind(rows,4),mode:selected.active?'LIVE NFL GAME STATS':'NFL WEEK '+week+' GAME STATS',
       checked:new Date(),notes:'Passing · rushing · receiving · ESPN box scores',partial});
   }else{
     const leaders=seasonLeaders(board);
     if(!leaders.length)throw Error('ESPN player stats unavailable');
     paint({rows:leaders,mode:'2026 NFL SEASON LEADERS',
       checked:new Date(),notes:selected.active?'Live game box scores pending; season totals shown':'Season totals · not live game stats',
       partial:false});
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

/* Golden Football Gazette — ESPN-style fantasy league matchup scoreboard.
 * This displays only scores and projections found in the published, validated
 * ESPN league snapshot. It never invents winners, scores, live odds or logos.
 */
(function(root){
'use strict';
const LEAGUE_URL='https://fantasy.espn.com/football/league?leagueId=1413446022';
const FINAL=new Set(['HOME','AWAY','TIE']);
const LIVE_BASE='https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/1413446022';
const POLL_MS=30000; // Best-effort checks; ESPN may throttle or prohibit browser CORS.
const PUBLISHED_SNAPSHOT_TTL_MS=5*60*1000; // Revalidate static fallback at most once per five minutes.

function shouldRefreshPublishedSnapshot(lastChecked,now,force=false){
  return force||!Number.isFinite(lastChecked)||lastChecked<=0||
    now<lastChecked||now-lastChecked>=PUBLISHED_SNAPSHOT_TTL_MS;
}
function validPoints(value) {
  return typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<1000 ? value : null;
}
function formatPoints(value) {
  const n=validPoints(value);
  return n===null?'—':n.toFixed(2);
}
function phase(game) {
  if(FINAL.has(game?.winner))return 'FINAL';
  if(validPoints(game?.home?.points)>0||validPoints(game?.away?.points)>0)return 'SCORING REPORTED';
  return 'UPCOMING / NOT FINAL';
}
function scored(game,side) {
  const n=validPoints(game?.[side]?.points);
  if(n===null)return null;
  // An ESPN 0.00 placeholder before kickoff is not a recorded result.
  return phase(game)==='FINAL'||n>0||validPoints(game?.[side==='home'?'away':'home']?.points)>0?n:null;
}
function winnerSide(game) {
  if(game?.winner==='HOME')return 'home';
  if(game?.winner==='AWAY')return 'away';
  return null;
}
function availableWeeks(data) {
  return [...new Set((data?.matchups||[])
    .filter(g=>g&&g.home?.name&&g.away?.name&&Number.isInteger(g.week)&&g.week>=1&&g.week<=22)
    .map(g=>g.week))].sort((a,b)=>a-b);
}
function record(team) {
  if(!team)return 'Record unavailable';
  const wins=team.wins,losses=team.losses,ties=team.ties;
  if(!Number.isInteger(wins)||!Number.isInteger(losses))return 'Record unavailable';
  return wins+'-'+losses+(Number.isInteger(ties)&&ties>0?'-'+ties:'');
}
function initials(name) {
  const words=String(name||'').trim().split(/\s+/).filter(Boolean);
  return (words.length>1?words.slice(0,2).map(s=>s[0]).join(''):String(words[0]||'?').slice(0,2)).toUpperCase();
}


const ESPN_LEAGUE='1413446022';
const ESPN_SEASON=2026;
function liveMatchupMerge(existing,fresh,week) {
  // All corrections come from ESPN's requested fantasy week. Never merge an
  // arbitrary team ID or an unfinished response with another matchup.
  if(String(existing?.leagueId)!==ESPN_LEAGUE||Number(existing?.season)!==ESPN_SEASON||
     String(fresh?.id)!==ESPN_LEAGUE||
     (fresh?.seasonId!==undefined&&fresh?.seasonId!==null&&Number(fresh.seasonId)!==ESPN_SEASON)||
     !Number.isInteger(week)||week<1||week>22||
     !Array.isArray(existing.matchups)||!Array.isArray(existing.standings)||
     !Array.isArray(fresh.schedule))throw Error('Unverified ESPN league/season/week payload');

  const matchups=existing.matchups.map(game=>({...game,
    home:{...(game.home||{})},away:{...(game.away||{})}}));
  const byId=new Map(matchups.filter(g=>Number(g.week)===week&&g.id!==null&&g.id!==undefined)
    .map(g=>[String(g.id),g]));
  const seen=new Set();
  let matched=0,scoredGames=0,verifiedSides=0;
  for(const current of fresh.schedule){
    if(!current||Number(current.matchupPeriodId)!==week)continue;
    const id=String(current.id??'');
    const target=byId.get(id);
    if(!target||seen.has(id))continue;
    const validSides=['home','away'].every(side=>{
      const updated=current[side],saved=target[side];
      return updated&&saved&&saved.teamId!==null&&saved.teamId!==undefined&&
        String(updated.teamId)===String(saved.teamId);
    });
    // ESPN may send future playoff placeholders and partially hydrated events.
    if(!validSides)continue;
    const incomingScores=['home','away'].map(side=>{
      const item=current[side];
      return validPoints(item.totalPointsLive??item.totalPoints);
    });
    const winner=['HOME','AWAY','TIE','UNDECIDED'].includes(current.winner)?
      current.winner:null;
    // Zero is a valid FINAL score but null is NOT a zero. Never turn an
    // incomplete payload into an apparent score or a new final.
    const hasScores=incomingScores.some(v=>v!==null);
    if(!hasScores&&!FINAL.has(winner))continue;
    if(FINAL.has(winner)&&incomingScores.some(v=>v===null))continue;
    seen.add(id);matched++;
    if(hasScores)scoredGames++;
    for(let i=0;i<2;i++){
      const side=['home','away'][i],value=incomingScores[i];
      if(value!==null){target[side].points=value;verifiedSides++;}
      const projection=validPoints(current[side].totalProjectedPointsLive);
      if(projection!==null&&projection>0)target[side].projectedPoints=projection;
    }
    if(winner&&(FINAL.has(winner)||!FINAL.has(target.winner)))target.winner=winner;
  }
  if(!matched)throw Error('ESPN live response has no verified matching matchups');

  const standings=existing.standings.map(t=>({...t}));
  if(Array.isArray(fresh.teams)){
    const teams=new Map(fresh.teams.filter(t=>t&&t.id!==null&&t.id!==undefined)
      .map(t=>[String(t.id),t]));
    for(const team of standings){
      const official=teams.get(String(team.teamId))?.record?.overall;
      if(!official)continue;
      for(const field of ['wins','losses','ties']){
        if(Number.isInteger(official[field])&&official[field]>=0&&official[field]<=22)
          team[field]=official[field];
      }
    }
  }
  const expected=byId.size;
  const incomingWeek=Number(fresh.status?.currentMatchupPeriod);
  return {snapshot:{...existing,matchups,standings,
      currentMatchupPeriod:Number.isInteger(incomingWeek)&&
        incomingWeek>=week&&incomingWeek<=22?incomingWeek:existing.currentMatchupPeriod},
    matched,expected,scoredGames,verifiedSides};
}

const api={validPoints,formatPoints,phase,scored,winnerSide,availableWeeks,record,initials,liveMatchupMerge,shouldRefreshPublishedSnapshot};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root||!root.document||!root.fetch)return;

const doc=root.document;
const $=id=>doc.getElementById(id);
const cards=$('espn-games'),weekSelect=$('espn-week-select'),previous=$('espn-week-prev'),
  next=$('espn-week-next'),status=$('espn-status'),summary=$('espn-week-summary'),refresh=$('espn-week-refresh');
if(!cards||!weekSelect||!previous||!next||!status||!summary||!refresh)return;

let snapshot=null,selectedWeek=null,loading=false,liveCheckedAt=null,lastLiveAt=null,liveError='',liveCoverage='';
let lastPublishedSnapshotCheck=0;
const emblemSources=new Map();
let emblemsLoading=null;
const trustedESPNLogo=url=>typeof url==='string'&&/^https:\/\/(?:mystique-api\.fantasy\.espn\.com|g\.espncdn\.com|a\.espncdn\.com)\//.test(url);
const trustedCachedLogo=(url,id)=>typeof url==='string'&&
  /^assets\/fantasy-logos\/team-\d+\.(?:png|jpg|jpeg|webp|gif|svg)$/.test(url)&&
  url.split('/').pop().startsWith('team-'+String(id)+'.');
async function loadEmblems(){
 if(emblemsLoading)return emblemsLoading;
 emblemsLoading=(async()=>{
  const sources=await Promise.allSettled([
   root.fetch('assets/espn-team-logos.json',{cache:'force-cache'}).then(r=>{if(!r.ok)throw Error('Logo catalog unavailable');return r.json()}),
   root.fetch('assets/fantasy-logos/manifest.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Cached logo manifest unavailable');return r.json()})
  ]);
  const catalog=sources[0].status==='fulfilled'?sources[0].value:null;
  const manifest=sources[1].status==='fulfilled'?sources[1].value:null;
  if(String(catalog?.leagueId)==='1413446022'&&Array.isArray(catalog.teams)){
   for(const team of catalog.teams){
    if(!Number.isInteger(team.id))continue;
    emblemSources.set(String(team.id),{remote:trustedESPNLogo(team.logo)?team.logo:null,local:null});
   }
  }
  if(String(manifest?.leagueId)==='1413446022'&&manifest.teams&&typeof manifest.teams==='object'){
   for(const [id,item] of Object.entries(manifest.teams)){
    if(!/^\d+$/.test(id)||!item||typeof item!=='object')continue;
    const existing=emblemSources.get(id)||{remote:null,local:null};
    existing.remote=trustedESPNLogo(item.sourceUrl)?item.sourceUrl:existing.remote;
    existing.local=trustedCachedLogo(item.localUrl,id)?item.localUrl:null;
    emblemSources.set(id,existing);
   }
  }
 })();
 return emblemsLoading;
}
function teamEmblem(teamId,name,snapshotLogo){
 const id=String(teamId??'');
 const saved=emblemSources.get(id)||{};
 const remote=trustedESPNLogo(snapshotLogo)?snapshotLogo:saved.remote;
 const local=saved.local;
 const holder=tag('span',undefined,'gazette-logo-holder');
 holder.setAttribute('aria-label',name+' team emblem');
 const fallback=()=>{holder.replaceChildren(tag('span',initials(name),'gazette-logo-initials'));};
 if(!local&&!remote){fallback();return holder;}
 const image=tag('img',undefined,'gazette-team-logo');
 image.alt=name+' ESPN fantasy emblem';image.loading='lazy';image.decoding='async';
 image.onerror=()=>{
  if(local&&remote&&image.getAttribute('src')===local){image.src=remote;return;}
  fallback();
 };
 holder.append(image);
 image.src=local||remote;
 return holder;
}

const tag=(name,value,cls)=>{
  const e=doc.createElement(name);
  if(value!==undefined)e.textContent=String(value);
  if(cls)e.className=cls;
  return e;
};
const lastChecked=value=>{
  const d=new Date(value);
  if(Number.isNaN(d.getTime()))return 'verification time unavailable';
  return new Intl.DateTimeFormat('en-US',{
    timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric',
    hour:'numeric',minute:'2-digit',hour12:true,timeZoneName:'short'
  }).format(d);
};
function createTeam(game,side,details,win){
  const team=game[side]||{};
  const club=(snapshot.standings||[]).find(t=>String(t.teamId)===String(team.teamId));
  const section=tag('div',undefined,'espn-matchup-team'+(win===side?' espn-matchup-winner':''));
  const identity=tag('div',undefined,'espn-team-identity');
  const names=tag('div',undefined,'espn-matchup-identity-text');
  names.append(tag('strong',team.name||'Team unavailable','espn-matchup-name'),
               tag('span',record(club),'espn-matchup-record'));
  identity.append(teamEmblem(team.teamId,team.name||'Fantasy team',club?.logo),names);
  section.append(identity);
  const points=tag('div',undefined,'espn-matchup-points');
  const actual=scored(game,side);
  const actualValue=tag('strong',formatPoints(actual),'espn-points-total');
  actualValue.setAttribute('aria-label',(team.name||side)+' actual fantasy points: '+(actual===null?'not yet reported':formatPoints(actual)));
  points.append(actualValue,tag('span',actual===null?'No recorded points yet':'ESPN actual points','espn-points-type'));
  section.append(points);
  const projection=validPoints(team.projectedPoints);
  const projectionRow=tag('div',undefined,'espn-projection-row');
  projectionRow.append(tag('span','Projected final'),tag('strong',formatPoints(projection)));
  section.append(projectionRow);
  if(win===side)section.append(tag('div','WINNER','espn-matchup-winner-label'));
  return section;
}
function createCard(game,index){
  const win=winnerSide(game);
  const state=phase(game);
  const card=tag('article',undefined,'espn-matchup-card');
  card.setAttribute('aria-label','Matchup '+(index+1)+': '+game.away.name+' versus '+game.home.name);
  if(state==='FINAL')card.classList.add('espn-matchup-final');
  const header=tag('div',undefined,'espn-card-heading');
  header.append(tag('span','MATCHUP '+String(index+1).padStart(2,'0'),'espn-matchup-index'));
  const chip=tag('span',state,'espn-matchup-state');
  chip.dataset.state=state==='FINAL'?'final':state==='SCORING REPORTED'?'reported':'upcoming';
  header.append(chip);
  card.append(header);
  const battle=tag('div',undefined,'espn-team-battle');
  battle.append(createTeam(game,'away',null,win),
                tag('span','VS','espn-versus'),
                createTeam(game,'home',null,win));
  card.append(battle);
  const footer=tag('div',undefined,'espn-matchup-footer');
  if(state==='FINAL'&&game.winner==='TIE')footer.textContent='ESPN result: Tie';
  else if(state==='FINAL'&&win)footer.textContent='Final · '+game[win].name+' wins';
  else if(state==='SCORING REPORTED')footer.textContent='Scores as of the last ESPN data refresh · Not final';
  else footer.textContent='Awaiting ESPN scoring · Projections shown when available';
  card.append(footer);
  return card;
}
function render(){
  if(!snapshot)return;
  const weeks=availableWeeks(snapshot);
  if(!weeks.length){
    cards.replaceChildren(tag('p','No verified matchups are available from ESPN.','espn-no-matchups'));
    summary.textContent='No matchups available';return;
  }
  if(!weeks.includes(selectedWeek)){
    const fromEspn=Number(snapshot.currentMatchupPeriod);
    selectedWeek=weeks.includes(fromEspn)?fromEspn:weeks[weeks.length-1];
  }
  weekSelect.value=String(selectedWeek);
  const index=weeks.indexOf(selectedWeek);
  previous.disabled=index<=0;next.disabled=index===weeks.length-1;
  const games=snapshot.matchups.filter(g=>Number(g.week)===selectedWeek&&g.home?.name&&g.away?.name);
  games.sort((a,b)=>{
    const x=Number(a.id),y=Number(b.id);
    return Number.isFinite(x)&&Number.isFinite(y)?x-y:
      String(a.away.name).localeCompare(String(b.away.name));
  });
  cards.replaceChildren();
  for(const [i,game] of games.entries())cards.append(createCard(game,i));
  if(!games.length)cards.append(tag('p','ESPN has not published matchups for this week.','espn-no-matchups'));
  const finals=games.filter(g=>phase(g)==='FINAL').length;
  summary.textContent='Week '+selectedWeek+' · '+games.length+' matchup'+(games.length===1?'':'s')+
    ' · '+finals+' final'+(finals===1?'':'s')+
    (games.length!==Math.floor((snapshot.standings||[]).length/2)?' · ESPN schedule may be incomplete':'');
  status.textContent=liveCheckedAt?
    'ESPN public API checked '+lastChecked(liveCheckedAt)+(liveCoverage?' · '+liveCoverage:'')+
    ' · Best effort, not guaranteed real time · Scores and projections are distinct':
    (lastLiveAt?'Last successful direct ESPN scores '+lastChecked(lastLiveAt):
      'Last published ESPN snapshot '+lastChecked(snapshot.fetchedAt))+
    ' · Live API unavailable'+(liveError?' ('+liveError+')':'')+
    ' · Open ESPN for authoritative live scores';
  const leagueCards=$('gazette-team-records');
  if(leagueCards){
    leagueCards.replaceChildren();
    for(const t of snapshot.standings||[]){
      const card=tag('div',undefined,'gazette-record-card');
      const clubIdentity=tag('div',undefined,'gazette-record-identity');
      clubIdentity.append(teamEmblem(t.teamId,t.name,t.logo),tag('strong',t.name,'gazette-record-name'));
      card.append(clubIdentity,tag('span',record(t),'gazette-record-value'));
      leagueCards.append(card);
    }
  }
}
function populateWeeks(){
  weekSelect.replaceChildren();
  for(const week of availableWeeks(snapshot)){
    const opt=tag('option','Week '+week);opt.value=String(week);
    weekSelect.append(opt);
  }
}

async function checkLive(){
 const week=Number(snapshot?.currentMatchupPeriod)||selectedWeek;
 if(!Number.isInteger(week)||week<1||week>22)throw Error('Cannot determine current ESPN scoring week');
 const url=LIVE_BASE+'?view=mTeam&view=mMatchupScore&view=mScoreboard&view=mLiveScoring'+
   '&matchupPeriodId='+week+'&scoringPeriodId='+week+'&ts='+Date.now();
 const controller=new AbortController();
 const timer=root.setTimeout(()=>controller.abort(),12000);
 let fresh;
 try{
  const response=await root.fetch(url,{mode:'cors',credentials:'omit',cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('HTTP '+response.status);
  fresh=await response.json();
 }finally{root.clearTimeout(timer)}
 const merged=liveMatchupMerge(snapshot,fresh,week);
 snapshot=merged.snapshot;
 liveCoverage=merged.matched+' / '+merged.expected+' week '+week+' matchups verified'+
  (merged.matched<merged.expected?' (partial response)':'');
 liveCheckedAt=new Date();lastLiveAt=liveCheckedAt;liveError='';
}
async function load(forcePublishedSnapshot=false){
 if(loading)return;
 loading=true;refresh.disabled=true;
 status.textContent='Checking the latest published ESPN scores and attempting a direct ESPN refresh…';
 // ESPN live scoring is checked every poll, but the published fallback changes
 // only on Pages deployment. Revalidate it every five minutes or on manual refresh.
 if(!snapshot||shouldRefreshPublishedSnapshot(lastPublishedSnapshotCheck,Date.now(),forcePublishedSnapshot)){
  try{
   const response=await root.fetch('data/league.json',{cache:'no-cache'});
   if(!response.ok)throw Error('No ESPN snapshot published');
   const data=await response.json();
   if(String(data.leagueId)!=='1413446022'||data.season!==2026||
      data.status==='unavailable'||!data.fetchedAt||
      !Array.isArray(data.matchups)||!Array.isArray(data.standings)){
     throw Error('Current verified ESPN league snapshot unavailable');
   }
   lastPublishedSnapshotCheck=Date.now();
   // Never regress a more recent successful live score to a delayed daily snapshot.
   if(!lastLiveAt||!snapshot||new Date(data.fetchedAt)>lastLiveAt)snapshot=data;
   populateWeeks();
  }catch(error){
   if(!snapshot){
    cards.replaceChildren(tag('p','ESPN matchup scores could not be verified. Try again or open the ESPN league.','espn-no-matchups'));
    summary.textContent='Scoreboard unavailable';
    status.textContent='No verified ESPN scoreboard snapshot available.';
    loading=false;refresh.disabled=false;return;
   }
  }
 }
 try{await checkLive()}
 catch(error){
  liveError=error.name==='AbortError'?'timeout / ESPN browser access':String(error.message||'unavailable').slice(0,80);
  if(liveCheckedAt){
   // Failed subsequent poll: last direct check is not a current guarantee.
   liveCheckedAt=null;
  }
 }
 render();
 loading=false;refresh.disabled=false;
}
weekSelect.addEventListener('change',()=>{selectedWeek=Number(weekSelect.value);render()});
previous.addEventListener('click',()=>{
  const w=availableWeeks(snapshot),i=w.indexOf(selectedWeek);
  if(i>0){selectedWeek=w[i-1];render()}
});
next.addEventListener('click',()=>{
  const w=availableWeeks(snapshot),i=w.indexOf(selectedWeek);
  if(i>=0&&i<w.length-1){selectedWeek=w[i+1];render()}
});
refresh.addEventListener('click',()=>load(true));
// Browser checks ESPN directly when CORS permits, and always keeps the
// published, timestamped GitHub Pages snapshot as the honest fallback.
const gamesActive=()=>snapshot?.matchups?.some(g=>
  Number(g.week)===Number(snapshot.currentMatchupPeriod)&&phase(g)==='SCORING REPORTED');
root.setInterval(()=>{if(!doc.hidden&&gamesActive())load()},POLL_MS);
root.setInterval(()=>{if(!doc.hidden&&!gamesActive())load()},3*60*1000);
doc.addEventListener('visibilitychange',()=>{if(!doc.hidden)load()});
loadEmblems().finally(()=>{if(snapshot)render()});
load();
})(typeof window!=='undefined'?window:null);

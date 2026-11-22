/* Golden Football Gazette — ESPN-style fantasy league matchup scoreboard.
 * This displays only scores and projections found in the published, validated
 * ESPN league snapshot. It never invents winners, scores, live odds or logos.
 */
(function(root){
'use strict';
const LEAGUE_URL='https://fantasy.espn.com/football/league?leagueId=1413446022';
const FINAL=new Set(['HOME','AWAY','TIE']);

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

const api={validPoints,formatPoints,phase,scored,winnerSide,availableWeeks,record,initials};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root||!root.document||!root.fetch)return;

const doc=root.document;
const $=id=>doc.getElementById(id);
const cards=$('espn-games'),weekSelect=$('espn-week-select'),previous=$('espn-week-prev'),
  next=$('espn-week-next'),status=$('espn-status'),summary=$('espn-week-summary'),refresh=$('espn-week-refresh');
if(!cards||!weekSelect||!previous||!next||!status||!summary||!refresh)return;

let snapshot=null,selectedWeek=null,loading=false;
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
  const emblem=tag('span',initials(team.name),'espn-matchup-emblem');
  if(team.teamId!==undefined&&team.teamId!==null)emblem.dataset.espnTeamId=String(team.teamId);
  const names=tag('div',undefined,'espn-matchup-identity-text');
  names.append(tag('strong',team.name||'Team unavailable','espn-matchup-name'),
               tag('span',record(club),'espn-matchup-record'));
  identity.append(emblem,names);
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
  status.textContent='ESPN league snapshot checked '+lastChecked(snapshot.fetchedAt)+
    ' · Scores and projections are distinct · Not a live ESPN connection';
}
function populateWeeks(){
  weekSelect.replaceChildren();
  for(const week of availableWeeks(snapshot)){
    const opt=tag('option','Week '+week);opt.value=String(week);
    weekSelect.append(opt);
  }
}
async function load(){
  if(loading)return;
  loading=true;refresh.disabled=true;
  try{
    const response=await root.fetch('data/league.json?ts='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('No ESPN snapshot published');
    const data=await response.json();
    if(String(data.leagueId)!=='1413446022'||data.season!==2026||
       data.status==='unavailable'||!data.fetchedAt||
       !Array.isArray(data.matchups)||!Array.isArray(data.standings)){
      throw Error('Current verified ESPN league snapshot unavailable');
    }
    snapshot=data;populateWeeks();render();
  }catch(error){
    if(!snapshot){
      cards.replaceChildren(tag('p','ESPN matchup scores could not be verified. Try again or open the ESPN league.','espn-no-matchups'));
      summary.textContent='Scoreboard unavailable';
      status.textContent='No verified ESPN scoreboard snapshot available.';
    }else status.textContent='ESPN update failed · Last successful data: '+lastChecked(snapshot.fetchedAt);
    console.warn('ESPN Gazette matchup scoreboard:',error.message);
  }finally{loading=false;refresh.disabled=false}
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
refresh.addEventListener('click',load);
// The website is static and this rechecks the newest published data rather than
// querying ESPN directly. The GitHub workflow updates the public snapshot daily.
root.setInterval(()=>{if(!doc.hidden)load()},15*60*1000);
doc.addEventListener('visibilitychange',()=>{if(!doc.hidden)load()});
load();
})(typeof window!=='undefined'?window:null);

/* Golden Football Gazette — source-verified off-live-NFL scores and news.
 * Loaded only when the official NFL scoreboard confirms no games in progress.
 * Every sport uses an ESPN scoreboard and news feed; no estimates or fabricated
 * headlines, winners, scores, or racing/golf positions are allowed.
 */
(function(root){
'use strict';
const BASE='https://site.api.espn.com/apis/site/v2/sports/';
const SPORTS=Object.freeze([
  {id:'NFL',path:'football/nfl',kind:'team',page:'https://www.espn.com/nfl/'},
  {id:'NBA',path:'basketball/nba',kind:'team',page:'https://www.espn.com/nba/'},
  {id:'WNBA',path:'basketball/wnba',kind:'team',page:'https://www.espn.com/wnba/'},
  {id:'PGA',path:'golf/pga',kind:'golf',page:'https://www.espn.com/golf/'},
  {id:'NCAA FB',path:'football/college-football',kind:'team',page:'https://www.espn.com/college-football/',scoreboardQuery:'scoreboard?groups=80&limit=100'},
  {id:'NCAA MEN',path:'basketball/mens-college-basketball',kind:'team',page:'https://www.espn.com/mens-college-basketball/'},
  {id:'NCAA WOMEN',path:'basketball/womens-college-basketball',kind:'team',page:'https://www.espn.com/womens-college-basketball/'},
  {id:'MLB',path:'baseball/mlb',kind:'team',page:'https://www.espn.com/mlb/'},
  {id:'NASCAR',path:'racing/nascar-premier',kind:'racing',page:'https://www.espn.com/racing/nascar/'}
]);
const MAX_SCORE_AGE_MS=72*60*60*1000;
const MAX_NEWS_AGE_MS=48*60*60*1000; // Late-breaking stories only: no week-old filler.
const FETCH_TIMEOUT_MS=9000;
const MAX_PARALLEL=4;
const CACHE_MS=5*60*1000;
// Cache each league independently so selecting one sport does not refetch all.
const leagueCache=new Map();
const SPORT_IDS=Object.freeze(['ALL',...SPORTS.map(s=>s.id)]);
function validSportSelection(id){return SPORT_IDS.includes(id)}

function espnLink(raw){
 if(typeof raw!=='string')return null;
 try{
   const u=new URL(raw);
   if(u.protocol!=='https:'||u.hostname!=='www.espn.com')return null;
   return u.href;
 }catch(_){return null}
}
// News feeds can cross-list stories from other leagues. Match the sport to
// the story itself before rendering the badge; never label an NFL/NHL article
// as NBA simply because it appeared in the NBA feed.
const ARTICLE_PATH_SPORTS=[
  [/^\/nba(?:\/|$)/,'NBA'],
  [/^\/wnba(?:\/|$)/,'WNBA'],
  [/^\/golf(?:\/|$)/,'PGA'],
  [/^\/college-football(?:\/|$)/,'NCAA FB'],
  [/^\/mens-college-basketball(?:\/|$)/,'NCAA MEN'],
  [/^\/womens-college-basketball(?:\/|$)/,'NCAA WOMEN'],
  [/^\/mlb(?:\/|$)/,'MLB'],
  [/^\/(?:racing\/nascar|nascar)(?:\/|$)/,'NASCAR'],
  [/^\/nfl(?:\/|$)/,'NFL'],
  [/^\/nhl(?:\/|$)/,'NHL'],
  [/^\/soccer(?:\/|$)/,'SOCCER']
];
const ARTICLE_SPORT_ALIASES=Object.freeze({
  nba:'NBA',wnba:'WNBA',pga:'PGA',golf:'PGA',
  collegefootball:'NCAA FB',ncaaf:'NCAA FB',cfb:'NCAA FB',
  menscollegebasketball:'NCAA MEN',ncaam:'NCAA MEN',
  womenscollegebasketball:'NCAA WOMEN',ncaaw:'NCAA WOMEN',
  mlb:'MLB',majorleaguebaseball:'MLB',nascar:'NASCAR',
  nfl:'NFL',nhl:'NHL',soccer:'SOCCER'
});
function classifyNewsSport(article,sport){
 const href=espnLink(article?.links?.web?.href);
 if(href){
   const pathname=new URL(href).pathname.toLowerCase();
   for(const [pattern,id] of ARTICLE_PATH_SPORTS){
     if(pattern.test(pathname))return id;
   }
 }
 // Use explicit league/sport metadata only. Team names or generic 'sports'
 // tags are not a reliable substitute for the article's actual category.
 const matches=new Set();
 for(const category of Array.isArray(article?.categories)?article.categories:[]){
   if(!['league','sport'].includes(String(category?.type||'').toLowerCase()))continue;
   for(const field of ['leagueId','league','description','name','slug','sport']){
     const value=category?.[field];
     if(typeof value!=='string')continue;
     const key=value.toLowerCase().replace(/[^a-z0-9]/g,'');
     if(ARTICLE_SPORT_ALIASES[key])matches.add(ARTICLE_SPORT_ALIASES[key]);
   }
 }
 if(matches.size===1)return [...matches][0];
 // When the article supplies no specific category, retain the known
 // league-specific ESPN news feed as the last-resort attribution.
 return sport.id;
}
function eventLink(event,sport){
 for(const link of event?.links||[]){
   const url=espnLink(link?.href);
   if(url)return url;
 }
 return sport.page;
}
function asScore(value){
 if(value===undefined||value===null||value==='')return null;
 if(typeof value!=='number'&&typeof value!=='string')return null;
 const v=Number(value);
 return Number.isFinite(v)&&v>=0&&v<=500?String(value):null;
}
function activeOrFinal(event,now){
 const state=event?.status?.type?.state;
 if(!['in','post'].includes(state))return null;
 const d=Date.parse(event?.date||'');
 if(!Number.isFinite(d)||d>now+30*60*1000||now-d>MAX_SCORE_AGE_MS)return null;
 return state;
}
function teamScore(event,sport,state,now){
 const c=event?.competitions?.[0];
 if(!Array.isArray(c?.competitors))return null;
 const home=c.competitors.find(t=>t.homeAway==='home');
 const away=c.competitors.find(t=>t.homeAway==='away');
 const h=asScore(home?.score),a=asScore(away?.score);
 const hname=home?.team?.abbreviation||home?.team?.shortDisplayName;
 const aname=away?.team?.abbreviation||away?.team?.shortDisplayName;
 if(h===null||a===null||!hname||!aname)return null;
 return {sport:sport.id,kind:'score',name:String(aname).slice(0,20)+' '+a+
   ' — '+String(hname).slice(0,20)+' '+h,
   team:state==='in'?'LIVE':'FINAL',text:'ESPN verified '+(state==='in'?'live score':'final score'),
   href:eventLink(event,sport),date:Date.parse(event.date),checked:now};
}
function individualResult(event,sport,state,now){
 const c=event?.competitions?.[0];
 if(!Array.isArray(c?.competitors)||!c.competitors.length)return null;
 // ESPN publishes competitive rank as order; never infer a rank from list order.
 const leaders=c.competitors.filter(p=>Number.isInteger(p?.order)&&p.order>=1)
   .sort((a,b)=>a.order-b.order);
 const leader=leaders[0];
 if(!leader||leader.order!==1||!leader.athlete?.displayName)return null;
 const name=String(leader.athlete.displayName).slice(0,65);
 const tournament=String(event?.shortName||event?.name||sport.id).slice(0,65);
 let result;
 if(sport.kind==='golf'){
   const score=typeof leader.score==='string'||typeof leader.score==='number'?
     String(leader.score):'';
   if(!score.trim())return null; // No posted round/tournament score.
   result=name+' '+score;
 }else{
   result=name+' · P1';
 }
 return {sport:sport.id,kind:'score',name:tournament,
   team:state==='in'?'LIVE LEADER':'RESULT',
   text:result,href:eventLink(event,sport),date:Date.parse(event.date),checked:now};
}
function scoreRows(data,sport,now=Date.now()){
 if(!data||!Array.isArray(data.events))return [];
 const rows=[];
 for(const event of data.events.slice(0,65)){
   const state=activeOrFinal(event,now);
   if(!state)continue;
   const row=sport.kind==='team'?teamScore(event,sport,state,now):
     individualResult(event,sport,state,now);
   if(row)rows.push(row);
 }
 return rows.sort((a,b)=>Number(b.team.startsWith('LIVE'))-
   Number(a.team.startsWith('LIVE'))||b.date-a.date).slice(0,3);
}
// ESPN does not expose a trustworthy, cross-sport popularity ranking in these
// public feeds. Editorial prominence, publication time and verifiable major
// news events are proxies. Never claim a story has measured high readership.
const MAJOR_NEWS=/\b(?:trades?|traded|deal|acquires?|acquired|signs?|signed|signing|contract|extension|injur(?:y|ies|ed)|ruled out|out for|season[- ]ending|fired|firing|dismissed|suspend(?:ed|sion|s)|arrested|upset|champion(?:ship|s)?|title|finals|playoffs?|postseason|record[- ]breaking|historic|milestone|retires?|retirement|draft|mvp|major award|clinches?|advances?|qualifies?|crash|pole position|tournament winner)\b/i;
const EXTRA_MAJOR=/\b(?:blockbuster|shocking|breaking|huge|historic|title|championship|national title|record[- ]breaking|first[- ]ever|sweeps?|no\.\s*1)\b/i;
const LOW_VALUE_NEWS=/\b(?:podcast|how to watch|streaming guide|betting|best bets?|prop bets?|odds|preview|predictions?|power rankings|fantasy advice|mailbag|opinion|mock draft|what to watch|watch live|daily picks?)\b/i;
function newsImportance(article,now=Date.now(),sourceIndex=0){
 const headline=String(article?.headline||'').trim();
 const published=Date.parse(article?.published||article?.lastModified||'');
 if(!headline||!Number.isFinite(published)||published>now+60*60*1000||
   now-published>MAX_NEWS_AGE_MS)return null;
 const age=now-published;
 const breaking=(/breaking/i.test(String(article?.type||''))||
   /^breaking(?:[:\s-]|$)/i.test(headline))&&age<=12*60*60*1000;
 // ESPN article position is a modest editorial signal, but not proof of views.
 const major=MAJOR_NEWS.test(headline),extra=EXTRA_MAJOR.test(headline);
 if((LOW_VALUE_NEWS.test(headline)&&!breaking)||(!major&&!extra&&!breaking))return null;
 const priority=(breaking?16:0)+(major?5:0)+(extra?4:0)+
   (age<=6*60*60*1000?6:age<=18*60*60*1000?4:age<=30*60*60*1000?2:0)+
   Math.max(0,3-Math.max(0,sourceIndex));
 return {priority,breaking,published};
}
function newsRows(data,sport,now=Date.now()){
 if(!Array.isArray(data?.articles))return [];
 const rows=[],used=new Set();
 for(const [index,article] of data.articles.entries()){
   const signal=newsImportance(article,now,index);
   const link=espnLink(article?.links?.web?.href);
   if(!signal||!link||used.has(link))continue;
   const storySport=classifyNewsSport(article,sport);
   // NFL news is allowed here only when NFL games are idle; other unknown
   // sports cannot be cross-listed as supported news.
   if(!SPORTS.some(available=>available.id===storySport))continue;
   used.add(link);
   rows.push({sport:storySport,kind:'news',name:article.headline.trim().slice(0,110),
     team:signal.breaking?'BREAKING':'MAJOR NEWS',
     text:'ESPN · '+new Date(signal.published).toLocaleDateString('en-US',{month:'short',day:'numeric'}),
     href:link,date:signal.published,priority:signal.priority,checked:now});
 }
 return rows.sort((a,b)=>b.priority-a.priority||b.date-a.date).slice(0,2);
}
function mixRows(perSport){
 const rows=[],seenNews=new Set(),seenScores=new Set();
 function append(row){
   if(!row)return;
   if(row.kind==='news'){
     if(!row.href||seenNews.has(row.href))return;
     seenNews.add(row.href);
   }else if(row.kind==='score'){
     const key=[row.sport,row.href,row.name,row.date].join(':');
     if(seenScores.has(key))return;
     seenScores.add(key);
   }
   rows.push(row);
 }
 // Lead with verified scores for *each* sport, then one ranked major news
 // headline. This prevents weak stories from crowding out current results.
 for(const sport of SPORTS){
   const feed=perSport[sport.id]||{scores:[],news:[]};
   append(feed.scores[0]);
   append(feed.scores[1]);
   append(feed.news[0]);
   append(feed.scores[2]);
 }
 return rows.slice(0,32);
}
async function fetchJSON(root,url){
 const controller=new AbortController();
 const timeout=root.setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);
 try{
   const response=await root.fetch(url,{mode:'cors',credentials:'omit',
     cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error('ESPN response HTTP '+response.status);
   return await response.json();
 }finally{root.clearTimeout(timeout)}
}
async function load(rootWindow=root,force=false,selected='ALL'){
 const now=Date.now();
 if(!validSportSelection(selected))throw Error('Unknown sports ticker filter');
 if(!rootWindow?.fetch)throw Error('Browser fetch unavailable');
 const requested=selected==='ALL'?SPORTS:SPORTS.filter(s=>s.id===selected);
 const perSport={};
 const tasks=[];
 const checks={};
 let failures=0,successes=0;
 for(const sport of requested){
   const fromCache=leagueCache.get(sport.id);
   if(!force&&fromCache&&now-fromCache.at<CACHE_MS&&now>=fromCache.at){
     perSport[sport.id]=fromCache.feed;
     failures+=fromCache.failures;
     successes+=fromCache.successes;
   }else{
     perSport[sport.id]={scores:[],news:[]};
     checks[sport.id]={failures:0,successes:0};
     tasks.push({sport,kind:'score'},{sport,kind:'news'});
   }
 }
 let cursor=0;
 async function worker(){
   while(cursor<tasks.length){
     const task=tasks[cursor++];
     const endpoint=task.kind==='score'?
       (task.sport.scoreboardQuery||'scoreboard?limit=35'):'news?limit=20';
     const url=BASE+task.sport.path+'/'+endpoint;
     try{
       const data=await fetchJSON(rootWindow,url);
       if(task.kind==='score')perSport[task.sport.id].scores=scoreRows(data,task.sport,now);
       else perSport[task.sport.id].news=newsRows(data,task.sport,now);
       checks[task.sport.id].successes++;successes++;
     }catch(_){
       checks[task.sport.id].failures++;failures++;
     }
   }
 }
 await Promise.all(Array.from({length:Math.min(MAX_PARALLEL,tasks.length)},()=>worker()));
 for(const sport of requested){
   const check=checks[sport.id];
   // An outage cannot become a trusted, empty news/score cache entry.
   if(check?.successes)leagueCache.set(sport.id,{
     feed:perSport[sport.id],at:Date.now(),
     failures:check.failures,successes:check.successes
   });
 }
 // Selected league gets only its own verified scores and article topics.
 const rows=mixRows(perSport).filter(row=>selected==='ALL'||row.sport===selected);
 return {rows,checked:new Date(),partial:failures>0,sourcesAvailable:successes,
   selectedSport:selected,
   mode:selected==='ALL'?'NFL · NBA · WNBA · PGA · NCAA FB + BASKETBALL · MLB · NASCAR SCORES + NEWS':
     selected+' · VERIFIED SCORES + MAJOR NEWS',
   notes:failures?'Some ESPN feeds unavailable · Verified scores and major news only':
     'Live and final scores · significant ESPN headlines from the last 48h'};
}
const api={SPORTS,SPORT_IDS,validSportSelection,asScore,espnLink,activeOrFinal,scoreRows,newsRows,mixRows,classifyNewsSport,newsImportance,load};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(root&&root.document)root.GazetteMultiSport=api;
})(typeof window!=='undefined'?window:null);

/* Keep the existing Gazette lead-story styling. Replace only archival
 * Week 11 text when a RECENT, SOURCE-VERIFIED ESPN fantasy league lead exists.
 * Never turn fictional banter or unapproved editorial into factual headlines.
 */
(function(root){
 'use strict';
 const DOC=root?.document;
 if(!DOC)return;
 const section=DOC.getElementById('headlines');
 if(!section)return;
 const kicker=section.querySelector('.kicker');
 const headline=section.querySelector('h2');
 const body=section.querySelector('p');
 if(!kicker||!headline||!body)return;
 kicker.textContent='The lead story · Historical Week 11 archive';
 const hour=60*60*1000;
 async function run(){
  try{
   const response=await root.fetch('data/weekly-features.json?ts='+Date.now(),{cache:'no-store'});
   if(!response.ok)throw Error('Verified daily brief unavailable');
   const data=await response.json();
   if(data?.status!=='available'||!Array.isArray(data.coverage))
     throw Error('Verified daily desk unavailable');
   const published=new Date(data.generatedAt);
   const leagueSource=new Date(data.sources?.espnLeague);
   const age=Date.now()-leagueSource.getTime();
   if(!Number.isFinite(age)||age< -10*60*1000||age>48*hour ||
      !Number.isFinite(published.getTime())||published.getTime()<leagueSource.getTime())
      throw Error('ESPN league story has no recent verified source');
   const lead=data.coverage.find(s=>s?.tag==='Fantasy League'&&
     typeof s.headline==='string'&&s.headline.trim()&&
     typeof s.body==='string'&&s.body.trim()&&s.source==='ESPN fantasy league standings');
   if(!lead)throw Error('No verified ESPN Fantasy League lead');
   // textContent, not innerHTML: fetched content cannot inject HTML or scripts.
   headline.textContent=lead.headline;
   body.textContent=lead.body+' · ESPN verified '+leagueSource.toLocaleString('en-US',{
      timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',
      minute:'2-digit',timeZoneName:'short'})+'.';
   kicker.textContent='The lead story · Verified ESPN fantasy league';
  }catch(error){
   root.console?.info?.('Gazette lead story retaining clearly labeled archive:',error.message);
  }
 }
 run();
})(typeof window!=='undefined'?window:null);

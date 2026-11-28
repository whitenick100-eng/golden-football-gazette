/* Isolated mobile navigation behavior tests; no network or DOM packages. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync(require('node:path').join(__dirname,'../assets/mobile-gazette.js'),'utf8');

function boot(initialHash='',mobile=true){
 const docHandlers={},rootHandlers={};
 let rivalryActive=false;
 const featureTitle={textContent:''},featureDesc={textContent:''},featureStatus={textContent:''};
 const featureCard={
   attributes:{},classList:{toggle(name,active){this[name]=active}},
   setAttribute(name,value){this.attributes[name]=value},
   querySelector(selector){return selector==='.gazette-mobile-feature-title'?featureTitle:
     selector==='.gazette-mobile-feature-desc'?featureDesc:null;}
 };
 const navButtons=['home','scores','league','gazette','more'].map(view=>({
   dataset:{mobileNav:view},
   attributes:{},
   setAttribute(key,value){this.attributes[key]=value},
   removeAttribute(key){delete this.attributes[key]}
 }));
 const forward={dataset:{},textContent:''};
 let scrollDelta=0,scrolledTo=null;
 const holder={
   clientWidth:360,
   firstElementChild:{getBoundingClientRect:()=>({width:340})},
   scrollBy({left}){scrollDelta+=left}
 };
 const doc={
   body:{dataset:{}},
   readyState:'complete',
   addEventListener(name,fn){docHandlers[name]=fn},
   querySelector(selector){
     if(selector==='.gazette-mobile-feature[data-mobile-target="article-one"]')return featureCard;
     if(selector==='article.governors-cup-active #governors-cup-special:not([hidden])')return rivalryActive?{}:null;
     return null;
   },
   querySelectorAll(selector){return selector==='[data-mobile-nav]'?navButtons:[]},
   getElementById(id){return id==='gazette-mobile-next-article'?forward:
     id==='espn-games'?holder:id==='gazette-mobile-feature-one-status'?featureStatus:null}
 };
 const screen={
   matches:mobile,
   addEventListener(event,fn){this.change=fn}
 };
 const location={pathname:'/golden-football-gazette/',search:'',hash:initialHash};
 const root={
   document:doc,location,
   history:{pushState(_state,_title,href){location.hash=href.slice(href.indexOf('#'))}},
   matchMedia(query){assert.equal(query,'(max-width: 700px)');return screen},
   addEventListener(name,fn){rootHandlers[name]=fn},
   scrollTo(...args){scrolledTo=args},
   requestAnimationFrame(fn){fn()}
 };
 const sandbox={window:root,module:{exports:{}},console};
 vm.runInNewContext(src,sandbox,{filename:'mobile-gazette.js'});
 function buttonClick(target,extra={}){
   const button={
     dataset:{mobileTarget:target,...extra},
     hasAttribute(key){return key==='data-mobile-carousel'&&this.dataset.mobileCarousel!==undefined},
     closest(selector){return selector==='.gazette-mobile-only'?{}:null}
   };
   docHandlers.click({target:{closest(){return button}}});
 }
 return {doc,root,screen,forward,holder,navButtons,buttonClick,rootHandlers,featureTitle,featureDesc,featureStatus,featureCard,
   setRivalry(active){rivalryActive=active;docHandlers['gazette:editionchange']();},
   getDelta(){return scrollDelta},getScroll(){return scrolledTo}};
}
function test(name,fn){fn();console.log('PASS',name);}
test('mobile homepage loads with all five buttons and active state',()=>{
 const x=boot();
 assert.equal(x.doc.body.dataset.gazetteMobileView,'home');
 assert.equal(x.navButtons[0].attributes['aria-current'],'page');
 assert.equal(x.navButtons[1].attributes['aria-current'],undefined);
});
test('deep links open dedicated Page One and Page Two from any phone',()=>{
 const x=boot('#page-one');
 assert.equal(x.doc.body.dataset.gazetteMobileView,'article-one');
 assert.equal(x.forward.dataset.mobileTarget,'article-two');
 assert.equal(x.forward.textContent,'Read Page Two →');
 x.buttonClick('article-two');
 assert.equal(x.doc.body.dataset.gazetteMobileView,'article-two');
 assert.equal(x.root.location.hash,'#page-two');
 assert.equal(x.forward.dataset.mobileTarget,'article-one');
 assert.equal(x.forward.textContent,'← Read Page One');
 x.buttonClick('gazette');
 assert.equal(x.doc.body.dataset.gazetteMobileView,'gazette');
 assert.equal(x.root.location.hash,'#gazette');
});
test('navigation switches among scores, league and more without new page downloads',()=>{
 const x=boot();
 for(const section of ['scores','league','more','home']){
   x.buttonClick(section);
   assert.equal(x.doc.body.dataset.gazetteMobileView,section);
   assert.equal(x.root.location.hash,'#'+section);
 }
 x.root.location.hash='#league';
 x.rootHandlers.popstate();
 assert.equal(x.doc.body.dataset.gazetteMobileView,'league');
});
test('real matchup carousel scrolls one full card and supports reverse',()=>{
 const x=boot();
 x.buttonClick(undefined,{mobileCarousel:'next'});
 assert.equal(x.getDelta(),350);
 x.buttonClick(undefined,{mobileCarousel:'previous'});
 assert.equal(x.getDelta(),0);
});
test('desktop viewport leaves the existing site entirely unmodified',()=>{
 const x=boot('#page-two',false);
 assert.equal(x.doc.body.dataset.gazetteMobileView,undefined);
 x.buttonClick('gazette');
 assert.equal(x.doc.body.dataset.gazetteMobileView,undefined);
 assert.equal(x.root.location.hash,'#page-two');
 x.screen.matches=true;
 x.screen.change();
 assert.equal(x.doc.body.dataset.gazetteMobileView,'article-two');
 x.screen.matches=false;
 x.screen.change();
 assert.equal(x.doc.body.dataset.gazetteMobileView,undefined);
});

test('Page One featured card follows the special edition and restores the fantasy preview',()=>{
 const x=boot();
 assert.equal(x.featureTitle.textContent,'The League Report');
 x.setRivalry(true);
 assert.equal(x.featureTitle.textContent,'Kentucky Tradition, The Governors Cup');
 assert.match(x.featureDesc.textContent,/Louisville Cardinals and Kentucky Wildcats/);
 assert.equal(x.featureCard.classList['governors-cup-feature'],true);
 assert.match(x.featureStatus.textContent,/One-time special edition/);
 x.setRivalry(false);
 assert.equal(x.featureTitle.textContent,'The League Report');
 assert.match(x.featureDesc.textContent,/Verified Gridiron Giggles/);
 assert.equal(x.featureCard.classList['governors-cup-feature'],false);
 assert.match(x.featureStatus.textContent,/ESPN-verified/);
});

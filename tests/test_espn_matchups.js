/* Offline regression tests for the actual ESPN fantasy matchup scoring schema. */
'use strict';
const assert=require('node:assert/strict');
const matchups=require('../assets/espn-matchups.js');
const check=(name,run)=>{run();console.log('PASS',name)};

check('ESPN scores and projections do not become zero when unavailable',()=>{
  assert.equal(matchups.formatPoints(null),'—');
  assert.equal(matchups.formatPoints(undefined),'—');
  assert.equal(matchups.formatPoints(NaN),'—');
  assert.equal(matchups.formatPoints('129.5'),'—');
  assert.equal(matchups.formatPoints(-3),'—');
  assert.equal(matchups.formatPoints(121.5),'121.50');
  assert.equal(matchups.formatPoints(0),'0.00');
});
check('Upcoming matchup never fabricates a winning team or live score',()=>{
  const game={winner:'UNDECIDED',home:{points:0,projectedPoints:145},
    away:{points:0,projectedPoints:null}};
  assert.equal(matchups.phase(game),'UPCOMING / NOT FINAL');
  assert.equal(matchups.scored(game,'home'),null);
  assert.equal(matchups.scored(game,'away'),null);
  assert.equal(matchups.winnerSide(game),null);
});
check('Partially scored matchup remains NOT FINAL until ESPN confirms',()=>{
  const game={winner:'UNDECIDED',home:{points:93.5,projectedPoints:147},
    away:{points:0,projectedPoints:141}};
  assert.equal(matchups.phase(game),'SCORING REPORTED');
  assert.equal(matchups.scored(game,'home'),93.5);
  assert.equal(matchups.scored(game,'away'),0);
  assert.equal(matchups.winnerSide(game),null);
});
check('Final winners and losers use verified ESPN winner status',()=>{
  const game={winner:'HOME',home:{points:140.2},away:{points:108.7}};
  assert.equal(matchups.phase(game),'FINAL');
  assert.equal(matchups.winnerSide(game),'home');
  assert.equal(matchups.scored(game,'home'),140.2);
  game.winner='AWAY';
  assert.equal(matchups.winnerSide(game),'away');
  game.winner='TIE';
  assert.equal(matchups.phase(game),'FINAL');
  assert.equal(matchups.winnerSide(game),null);
});
check('Completed matchup with a legitimate zero remains zero',()=>{
  const game={winner:'AWAY',home:{points:0},away:{points:89.5}};
  assert.equal(matchups.scored(game,'home'),0);
});
check('Week selector draws only actual verified matchups in chronological order',()=>{
  const data={matchups:[
    {week:12,home:{name:'First'},away:{name:'Second'}},
    {week:10,home:{name:'Third'},away:{name:'Fourth'}},
    {week:12,home:{name:'Fifth'},away:{name:'Sixth'}},
    {week:999,home:{name:'Future'},away:{name:'Other'}},
    {week:11,home:{name:'Incomplete'}}
  ]};
  assert.deepEqual(matchups.availableWeeks(data),[10,12]);
});
check('Fantasy W-L-T records have no invented tied games',()=>{
  assert.equal(matchups.record({wins:6,losses:5,ties:0}),'6-5');
  assert.equal(matchups.record({wins:5,losses:5,ties:1}),'5-5-1');
  assert.equal(matchups.record({wins:null,losses:5}),'Record unavailable');
});
check('Team emblems can fall back to sanitized initials',()=>{
  assert.equal(matchups.initials('Sunday Morning Panic'),'SM');
  assert.equal(matchups.initials('4th'),'4T');
  assert.equal(matchups.initials(''),'??'.slice(0,2).replace('??','?'));
});
check('Both league records and matchups reuse authentic ESPN fantasy emblem URLs',()=>{
  const fs=require('node:fs');
  const source=fs.readFileSync(require.resolve('../assets/espn-matchups.js'),'utf8');
  const catalog=JSON.parse(fs.readFileSync(require.resolve('../assets/espn-team-logos.json'),'utf8'));
  assert.equal(catalog.leagueId,1413446022);
  assert.equal(catalog.teams.length,10);
  assert.equal(new Set(catalog.teams.map(t=>t.id)).size,10);
  assert.ok(source.includes('assets/fantasy-logos/manifest.json'));
  assert.ok(source.includes('teamEmblem(team.teamId'));
  assert.ok(source.includes('teamEmblem(t.teamId'));
  assert.ok(source.includes('image.onerror'));
});

check('Direct ESPN merge validates league identity and exact scoring period',()=>{
  const base={leagueId:'1413446022',season:2026,currentMatchupPeriod:11,
    standings:[{teamId:1,name:'A',wins:5,losses:5,ties:0},{teamId:2,name:'B',wins:4,losses:6,ties:0}],
    matchups:[{id:72,week:11,winner:'UNDECIDED',
      home:{teamId:1,points:13,projectedPoints:125},
      away:{teamId:2,points:10,projectedPoints:110}}]};
  const fresh={id:1413446022,seasonId:2026,
    schedule:[{id:72,matchupPeriodId:11,winner:'UNDECIDED',
      home:{teamId:1,totalPointsLive:37.25,totalProjectedPointsLive:145},
      away:{teamId:2,totalPointsLive:21.55,totalProjectedPointsLive:132}}]};
  const update=matchups.liveMatchupMerge(base,fresh,11);
  const optionalSeason={...fresh};delete optionalSeason.seasonId;
  assert.equal(matchups.liveMatchupMerge(base,optionalSeason,11).matched,1);
  assert.equal(update.matched,1);
  assert.equal(update.snapshot.matchups[0].home.points,37.25);
  assert.equal(update.snapshot.matchups[0].away.points,21.55);
  assert.equal(base.matchups[0].home.points,13,'snapshot must not mutate before verification');
  assert.throws(()=>matchups.liveMatchupMerge(base,{...fresh,id:999999},11),/Unverified/);
  assert.throws(()=>matchups.liveMatchupMerge(base,{...fresh,seasonId:2025},11),/Unverified/);
  assert.throws(()=>matchups.liveMatchupMerge(base,fresh,12),/no verified/i);
});
check('ESPN rejects swapped teams, nonnumeric scores and unknown matchups',()=>{
  const base={leagueId:1413446022,season:2026,currentMatchupPeriod:11,
    standings:[],matchups:[{id:10,week:11,winner:'UNDECIDED',
      home:{teamId:1,points:11},away:{teamId:2,points:10}}]};
  const bad={id:1413446022,seasonId:2026,schedule:[
    {id:10,matchupPeriodId:11,home:{teamId:2,totalPointsLive:95},away:{teamId:1,totalPointsLive:85}},
    {id:99,matchupPeriodId:11,home:{teamId:1,totalPointsLive:80},away:{teamId:2,totalPointsLive:40}}
  ]};
  assert.throws(()=>matchups.liveMatchupMerge(base,bad,11),/no verified/i);
  const malformed={...bad,schedule:[{id:10,matchupPeriodId:11,winner:'HOME',
    home:{teamId:1,totalPointsLive:'105'},away:{teamId:2,totalPointsLive:null}}]};
  assert.throws(()=>matchups.liveMatchupMerge(base,malformed,11),/no verified/i);
});
check('Partial ESPN response preserves other matchups and confirmed final winners',()=>{
  const base={leagueId:1413446022,season:2026,currentMatchupPeriod:11,
    standings:[{teamId:1,wins:7,losses:3,ties:0}],matchups:[
      {id:12,week:11,winner:'HOME',home:{teamId:1,points:120},away:{teamId:2,points:100}},
      {id:13,week:11,winner:'UNDECIDED',home:{teamId:3,points:13},away:{teamId:4,points:9}}
    ]};
  const fresh={id:1413446022,seasonId:2026,
    schedule:[{id:12,matchupPeriodId:11,winner:'UNDECIDED',
      home:{teamId:1,totalPointsLive:121},away:{teamId:2,totalPointsLive:99}}],
    teams:[{id:1,record:{overall:{wins:8,losses:3,ties:0}}}]};
  const result=matchups.liveMatchupMerge(base,fresh,11);
  assert.equal(result.matched,1);
  assert.equal(result.expected,2);
  assert.equal(result.snapshot.matchups[0].winner,'HOME','final may not silently revert');
  assert.equal(result.snapshot.matchups[1].home.points,13,'missing game retains prior verified score');
  assert.equal(result.snapshot.standings[0].wins,8);
  assert.equal(base.standings[0].wins,7);
});

console.log('All ESPN fantasy scoreboard tests passed.');

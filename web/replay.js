(function(root){
 'use strict';
 class ReplayClock{
  constructor(events,origin){this.events=events;this.origin=Date.parse(origin);this.duration=Math.max(0,...events.map(e=>(Date.parse(e.ts)-this.origin)/1000));this.elapsed=0;this.speed=1;this.playing=false;this.last=null}
  play(now){this.playing=true;this.last=now}
  pause(){this.playing=false;this.last=null}
  restart(){this.pause();this.elapsed=0}
  setSpeed(value){if(![1,2,4].includes(value))throw Error('Unsupported speed');this.speed=value}
  tick(now){if(this.playing){this.elapsed=Math.min(this.duration,this.elapsed+Math.max(0,now-this.last)/1000*this.speed);this.last=now;if(this.elapsed>=this.duration)this.pause()}return this.visible()}
  visible(){return this.events.filter(e=>(Date.parse(e.ts)-this.origin)/1000<=this.elapsed)}
  root(){const e=this.events.find(e=>e.stage==='ROOT CAUSE');if(e){this.elapsed=Math.max(0,(Date.parse(e.ts)-this.origin)/1000);this.pause()}return e}
 }
 if(typeof module!=='undefined')module.exports={ReplayClock};else root.ReplayClock=ReplayClock;
})(typeof window==='undefined'?globalThis:window);

// Fault injection is confined to this test launcher, never the shipped worker.
const threads=require('node:worker_threads'),Original=threads.Worker;
let first=true;
threads.Worker=class extends Original{
 constructor(...args){super(...args);this.crashOnce=first;first=false;}
 postMessage(...args){super.postMessage(...args);if(this.crashOnce){this.crashOnce=false;setTimeout(()=>this.terminate(),5);}}
};
require('../overlay-solver.cjs');

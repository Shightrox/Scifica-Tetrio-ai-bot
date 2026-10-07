importScripts('engine.js');
onmessage=e=>{const t=performance.now();try{postMessage({id:e.data.id,...Tetris.analyze(e.data.state),ms:performance.now()-t});}catch(error){postMessage({id:e.data.id,error:String(error)});}};

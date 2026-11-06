/* One unity-gain Web Audio route per player; only the active visible canvas animates. */
(()=>{
    const entries=new WeakMap();
    const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)');
    let context=null,mode=localStorage.getItem('music-spectrum-mode')||'digital';
    if(!['digital','analog','off'].includes(mode))mode='digital';
    const clock=value=>{const seconds=Number.isFinite(value)?Math.max(0,Math.floor(value)):0;return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');};
    function markup(url){return `<div class="audio-player"><canvas class="audio-spectrum" aria-hidden="true"></canvas><div class="player-surface"><div class="spectrum-toolbar"><span>오디오 스펙트럼</span><select class="spectrum-mode" aria-label="스펙트럼 표시 방식"><option value="digital">디지털</option><option value="analog">아날로그</option><option value="off">끄기</option></select></div><audio preload="none" src="${url}" aria-label="생성한 음악"></audio><div class="player-controls"><button type="button" class="player-toggle" data-play="true" aria-label="재생" aria-pressed="false"><span aria-hidden="true">${window.StudioIcons('play')}</span></button><input class="player-seek" type="range" min="0" max="1000" step="1" value="0" aria-label="재생 위치" disabled><button type="button" class="player-mute" aria-label="음소거" aria-pressed="false"><span aria-hidden="true">${window.StudioIcons('volume')}</span></button></div><div class="player-meta"><span class="player-time">00:00 / 00:00</span><label class="player-volume-label">음량<input class="player-volume" type="range" min="0" max="1" step="0.05" value="1" aria-label="재생 음량"></label></div><p class="spectrum-note" role="status" hidden></p></div></div>`;}
    function attach(root){
        for(const audio of root.querySelectorAll('.audio-player audio')){
            if(entries.has(audio))continue;
            const player=audio.closest('.audio-player');
            const entry={audio,player,canvas:player.querySelector('canvas'),analyser:null,source:null,frame:0,last:0,disposed:false};
            entry.context=entry.canvas.getContext('2d');
            entry.frequency=new Uint8Array(512);entry.wave=new Uint8Array(1024);
            entries.set(audio,entry);player.querySelector('.spectrum-mode').value=mode;
            player.dataset.spectrumMode=mode;
            player.querySelector('.player-seek').oninput=event=>{
                if(Number.isFinite(audio.duration)&&audio.duration>0)audio.currentTime=Number(event.target.value)*audio.duration/1000;
            };
            player.querySelector('.player-mute').onclick=()=>{audio.muted=!audio.muted;};
            player.querySelector('.player-volume').oninput=event=>{audio.volume=Number(event.target.value);if(audio.volume>0)audio.muted=false;};
            player.querySelector('.spectrum-mode').onchange=event=>{
                mode=event.target.value;localStorage.setItem('music-spectrum-mode',mode);
                document.querySelectorAll('.audio-player audio').forEach(media=>{
                    const other=entries.get(media);if(!other)return;
                    other.player.querySelector('.spectrum-mode').value=mode;other.player.dataset.spectrumMode=mode;
                    cancelAnimationFrame(other.frame);other.frame=0;draw(other);
                    if(!media.paused){prepare(media);start(other);}
                });
            };
            for(const type of ['loadedmetadata','durationchange','timeupdate','volumechange','seeked','emptied'])audio.addEventListener(type,()=>update(entry));
            audio.addEventListener('play',()=>{prepare(audio);start(entry);});
            for(const type of ['pause','ended','error'])audio.addEventListener(type,()=>{cancelAnimationFrame(entry.frame);entry.frame=0;update(entry);});
            entry.resize=new ResizeObserver(()=>draw(entry));entry.resize.observe(player);
            update(entry);draw(entry);
        }
    }
    function update(entry){
        if(entry.disposed)return;
        const {audio,player}=entry,seek=player.querySelector('.player-seek');
        const duration=Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:0;
        seek.disabled=!duration;
        seek.value=duration?Math.round(audio.currentTime/duration*1000):0;
        seek.setAttribute('aria-valuetext',clock(audio.currentTime)+' / '+clock(duration));
        player.querySelector('.player-time').textContent=clock(audio.currentTime)+' / '+clock(duration);
        player.querySelector('.player-volume').value=audio.volume;
        const mute=player.querySelector('.player-mute');mute.setAttribute('aria-pressed',String(audio.muted));
        mute.setAttribute('aria-label',audio.muted?'음소거 해제':'음소거');mute.querySelector('span').innerHTML=window.StudioIcons(audio.muted?'muted':'volume');
    }
    function connect(entry){
        if(entry.disposed||entry.source)return;
        entry.analyser=context.createAnalyser();entry.analyser.fftSize=1024;entry.analyser.smoothingTimeConstant=.82;
        entry.source=context.createMediaElementSource(entry.audio);
        // Exactly one audible path: no parallel connection that would increase gain.
        entry.source.connect(entry.analyser);entry.analyser.connect(context.destination);
        entry.player.dataset.spectrumReady='true';
    }
    function prepare(audio){
        const entry=entries.get(audio);if(!entry||entry.disposed||mode==='off')return;
        try{
            const Constructor=window.AudioContext||window.webkitAudioContext;
            if(!Constructor)throw Error('Web Audio unavailable');
            context??=new Constructor();
            const resumed=context.state==='running'?Promise.resolve():context.resume();
            return resumed.then(()=>{
                if(entry.disposed||context.state!=='running')return;
                connect(entry);if(!audio.paused)start(entry);
            }).catch(()=>fallback(entry));
        }catch{fallback(entry);}
    }
    function fallback(entry){
        // If graph creation failed midway, retain an audible single route.
        if(entry.source){try{entry.source.disconnect();entry.analyser?.disconnect();entry.source.connect(context.destination);entry.analyser=null;}catch{}}
        const note=entry.player.querySelector('.spectrum-note');
        note.hidden=false;note.textContent='스펙트럼을 사용할 수 없어 기본 오디오로 재생합니다.';
    }
    function draw(entry){
        if(entry.disposed||!entry.context)return;
        const {canvas,player}=entry,box=player.getBoundingClientRect();
        if(box.width<1||box.height<1)return;
        const ratio=Math.min(devicePixelRatio||1,2),width=Math.round(box.width),height=Math.round(box.height);
        if(canvas.width!==Math.round(width*ratio)||canvas.height!==Math.round(height*ratio)){canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);}
        const ctx=entry.context;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);
        if(mode==='off')return;
        ctx.lineWidth=2;ctx.strokeStyle='rgba(67,116,102,.38)';
        const gradient=ctx.createLinearGradient(0,height,0,0);gradient.addColorStop(0,'#8eae72');gradient.addColorStop(.6,'#4daaa2');gradient.addColorStop(1,'#8795d5');
        ctx.fillStyle=gradient;
        if(mode==='analog'){
            if(entry.analyser)entry.analyser.getByteTimeDomainData(entry.wave);else entry.wave.fill(128);
            ctx.beginPath();
            for(let i=0;i<entry.wave.length;i++){
                const x=i*width/(entry.wave.length-1),y=height*.55+(entry.wave[i]-128)/128*height*.42;
                if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
            }
            ctx.strokeStyle='#4c9c94';ctx.lineWidth=2.5;ctx.stroke();
        }else{
            if(entry.analyser)entry.analyser.getByteFrequencyData(entry.frequency);else entry.frequency.fill(0);
            const count=Math.min(56,Math.max(20,Math.floor(width/10))),step=width/count;
            for(let i=0;i<count;i++){
                const bin=Math.min(511,Math.round(Math.pow(i/(count-1),1.8)*511));
                const level=Math.max(2,entry.frequency[bin]/255*height*.83);
                for(let y=0;y<level;y+=8)ctx.fillRect(i*step+2,height-8-y,Math.max(2,step-4),5);
            }
        }
        player.dataset.spectrumDrawn=mode;
    }
    function start(entry){
        if(entry.disposed||entry.audio.paused||mode==='off'||!entry.audio.closest('details')?.open)return;
        if(entry.frame)return;
        const tick=now=>{
            entry.frame=0;
            if(entry.disposed||entry.audio.paused||entry.audio.ended||mode==='off'||document.hidden||!entry.audio.closest('details')?.open)return;
            if(now-entry.last>33){draw(entry);entry.last=now;}
            if(!reduceMotion.matches)entry.frame=requestAnimationFrame(tick);
        };
        entry.frame=requestAnimationFrame(tick);
    }
    function release(root){
        for(const audio of root.querySelectorAll('.audio-player audio')){
            const entry=entries.get(audio);if(!entry)continue;
            audio.pause();entry.disposed=true;cancelAnimationFrame(entry.frame);entry.resize.disconnect();
            entry.source?.disconnect();entry.analyser?.disconnect();entries.delete(audio);
        }
    }
    document.getElementById('jobs').addEventListener('toggle',event=>{
        if(event.target.matches('.result-disclosure')&&event.target.open){const entry=entries.get(event.target.querySelector('audio'));if(entry){draw(entry);start(entry);}}
    },true);
    document.addEventListener('visibilitychange',()=>{
        for(const audio of document.querySelectorAll('.audio-player audio')){
            const entry=entries.get(audio);if(!entry)continue;
            cancelAnimationFrame(entry.frame);entry.frame=0;if(!document.hidden)start(entry);
        }
    });
    reduceMotion.addEventListener('change',()=>{
        document.querySelectorAll('.audio-player audio').forEach(audio=>{
            const entry=entries.get(audio);if(!entry)return;cancelAnimationFrame(entry.frame);entry.frame=0;draw(entry);start(entry);
        });
    });
    window.AudioSpectrum={markup,attach,prepare,release};
})();

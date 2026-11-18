/* Song Workshop view: Repaint (section fix & ending extend), Cover/Arrange, and Retake. */
(()=>{
    const $=id=>document.getElementById(id);
    const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const REPAINT_PRESETS={
        natural:{repaintMode:'conservative',repaintStrength:0.25},
        balanced:{repaintMode:'balanced',repaintStrength:0.50},
        fresh:{repaintMode:'aggressive',repaintStrength:0.90}
    };

    let isOpen=false;
    let sourceJob=null;
    let allJobs=[];
    let activeTab='repaint';
    let lyricsTab='orig';
    let repaintSubMode='section';
    let repaintPreset='balanced';
    let startSec=0;
    let endSec=15;
    let extendSec=20;
    let coverStrength=0.85;
    let retakeVariance=0.30;
    let titleTouched=false;
    let submitting=false;
    let cancelling=false;
    let pendingEditId=null;
    let comparedJob=null;
    let previewEndTime=null;
    let runStartedAt=0;
    let clockTimer=null;
    let dragState=null;
    let suppressNextBarClick=false;

    function formatClock(sec){
        const total=Math.max(0,Math.floor(Number(sec)||0));
        return String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0');
    }

    function jobDisplayTitle(job){
        if(!job)return '제목 없는 노래';
        const raw=(job.title||'').trim()||(job.title===undefined?(job.prompt||''):'');
        return raw.trim()||(job.settings?.instrumental?'연주곡':'노래');
    }

    function baseSongTitle(job){
        return jobDisplayTitle(job).replace(/\s*\((?:구간 수정|편곡 변경|다른 테이크|\+\d+초 연장)\)\s*$/,'').trim()||jobDisplayTitle(job);
    }

    function suggestedTitle(){
        const base=baseSongTitle(sourceJob);
        if(activeTab==='repaint'){
            return repaintSubMode==='extend'?`${base} (+${Math.round(extendSec)}초 연장)`:`${base} (구간 수정)`;
        }
        if(activeTab==='cover')return `${base} (편곡 변경)`;
        return `${base} (다른 테이크)`;
    }

    function sourceDuration(){
        if(!sourceJob)return 30;
        if(Number.isFinite(sourceJob.durationSeconds)&&sourceJob.durationSeconds>0)return sourceJob.durationSeconds;
        if(Number.isFinite(sourceJob.settings?.seconds)&&sourceJob.settings.seconds>0)return sourceJob.settings.seconds;
        return 30;
    }

    function getSourceAudio(){
        return $('workshop-source-player')?.querySelector('audio')||null;
    }

    function pauseAllWorkshopAudio(except=null){
        for(const audio of $('song-workshop')?.querySelectorAll('audio')||[]){
            if(audio!==except&&!audio.paused)audio.pause();
        }
    }

    function releasePlayerContainer(containerId){
        const el=$(containerId);
        if(!el)return;
        window.AudioSpectrum?.release(el);
        el.innerHTML='';
    }

    function syncWorkshopPlayButton(container,playing){
        const btn=container?.querySelector('.player-toggle');
        if(!btn)return;
        btn.classList.toggle('is-playing',playing);
        btn.setAttribute('aria-pressed',String(playing));
        btn.setAttribute('aria-label',playing?'일시정지':'재생');
        const span=btn.querySelector('span');
        if(span&&window.StudioIcons)span.innerHTML=window.StudioIcons(playing?'pause':'play');
    }

    function attachWorkshopPlayerControls(container){
        const audio=container?.querySelector('audio');
        const btn=container?.querySelector('.player-toggle');
        if(!audio||!btn)return;
        syncWorkshopPlayButton(container,!audio.paused&&!audio.ended);
        btn.addEventListener('click',async()=>{
            if(audio.paused||audio.ended){
                pauseAllWorkshopAudio(audio);
                window.AudioSpectrum?.prepare(audio);
                try{await audio.play();}catch(e){}
            }else{
                audio.pause();
            }
        });
        audio.addEventListener('play',()=>{
            pauseAllWorkshopAudio(audio);
            syncWorkshopPlayButton(container,true);
        });
        for(const evt of ['pause','ended','error']){
            audio.addEventListener(evt,()=>syncWorkshopPlayButton(container,false));
        }
    }

    function rulerStepsForDuration(totalSeconds){
        if(totalSeconds<=30)return {majorStep:5,midStep:5,minorStep:1};
        if(totalSeconds<=60)return {majorStep:10,midStep:5,minorStep:1};
        if(totalSeconds<=120)return {majorStep:15,midStep:5,minorStep:5};
        if(totalSeconds<=240)return {majorStep:30,midStep:15,minorStep:5};
        if(totalSeconds<=420)return {majorStep:60,midStep:30,minorStep:10};
        return {majorStep:60,midStep:30,minorStep:15};
    }

    function buildTimeRulerHTML(totalSeconds,includeRangeOverlay=false){
        const total=Math.max(2,Number(totalSeconds)||30);
        const {majorStep,midStep,minorStep}=rulerStepsForDuration(total);
        const ticks=[];
        let hasEndTick=false;
        for(let t=0;t<=total+0.001;t+=minorStep){
            const sec=Math.round(t);
            const pct=Math.min(100,Math.max(0,(sec/total)*100));
            const isFirst=sec===0;
            const isExactEnd=Math.abs(total-sec)<0.05;
            const isMajor=isFirst||isExactEnd||(sec%majorStep===0);
            const isMid=!isMajor&&(sec%midStep===0);
            if(isExactEnd)hasEndTick=true;
            if(!isFirst&&!isExactEnd&&(total-sec)<minorStep*0.45)continue;
            const nearEnd=!isFirst&&!isExactEnd&&(total-sec)<majorStep*0.42;
            const showLabel=isMajor&&!nearEnd;
            const cls=['workshop-ruler-tick',isMajor?'is-major':(isMid?'is-mid':'is-minor')];
            if(isFirst)cls.push('is-first');
            if(isExactEnd)cls.push('is-last');
            const label=showLabel?`<span class="workshop-ruler-label">${formatClock(sec)}</span>`:'';
            ticks.push(`<span class="${cls.join(' ')}" style="left:${pct.toFixed(3)}%">${label}</span>`);
        }
        if(!hasEndTick){
            ticks.push(`<span class="workshop-ruler-tick is-major is-last" style="left:100%"><span class="workshop-ruler-label">${formatClock(total)}</span></span>`);
        }
        const overlay=includeRangeOverlay
            ?'<div class="workshop-ruler-range" hidden></div><div class="workshop-ruler-playhead"></div>'
            :'';
        return `${overlay}<div class="workshop-ruler-ticks">${ticks.join('')}</div>`;
    }

    function renderTimeRulers(){
        const total=totalSongSeconds();
        const timelineRuler=$('workshop-timeline-ruler');
        if(timelineRuler)timelineRuler.innerHTML=buildTimeRulerHTML(total,true);
    }

    function seekSourceAudioByRatio(ratio){
        const audio=getSourceAudio();
        if(!audio)return;
        const clamped=Math.min(1,Math.max(0,ratio));
        const applySeek=()=>{
            const dur=Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:totalSongSeconds();
            audio.currentTime=clamped*dur;
            syncTimeline();
        };
        if(audio.readyState>=1||Number.isFinite(audio.duration)){
            applySeek();
        }else{
            audio.addEventListener('loadedmetadata',applySeek,{once:true});
            audio.load();
        }
    }

    function renderSourcePlayer(){
        const wrap=$('workshop-source-player');
        if(!wrap||!sourceJob?.audioUrl)return;
        releasePlayerContainer('workshop-source-player');
        wrap.innerHTML=window.AudioSpectrum.markup(escapeHTML(sourceJob.audioUrl));
        const toggleBtn=wrap.querySelector('.player-toggle');
        if(toggleBtn){
            const restartBtn=document.createElement('button');
            restartBtn.type='button';
            restartBtn.id='workshop-restart-btn';
            restartBtn.className='player-restart';
            restartBtn.setAttribute('aria-label','처음 위치로 이동');
            restartBtn.title='처음 위치(00:00)로 이동';
            restartBtn.innerHTML=`<span aria-hidden="true">${window.StudioIcons('skipStart')}</span>`;
            restartBtn.addEventListener('click',()=>seekSourceAudioByRatio(0));
            toggleBtn.after(restartBtn);
        }
        const audio=getSourceAudio();
        if(audio)audio.preload='metadata';
        window.AudioSpectrum.attach(wrap);
        attachWorkshopPlayerControls(wrap);
        renderTimeRulers();
        if(!audio)return;
        audio.addEventListener('loadedmetadata',()=>{
            if(Number.isFinite(audio.duration)&&audio.duration>1){
                sourceJob._measuredDuration=audio.duration;
                renderTimeRulers();
                clampRange();
                syncTimeline();
            }
        });
        audio.addEventListener('timeupdate',()=>{
            if(previewEndTime!==null&&audio.currentTime>=previewEndTime){
                audio.pause();
                previewEndTime=null;
                syncPreviewButton();
            }
            syncTimeline();
        });
        audio.addEventListener('pause',()=>{
            if(previewEndTime!==null){
                previewEndTime=null;
                syncPreviewButton();
            }
        });
        audio.addEventListener('ended',()=>{
            previewEndTime=null;
            syncPreviewButton();
            syncTimeline();
        });
    }

    function totalSongSeconds(){
        if(sourceJob?._measuredDuration&&Number.isFinite(sourceJob._measuredDuration))return sourceJob._measuredDuration;
        return sourceDuration();
    }

    function clampRange(){
        const total=Math.max(2,totalSongSeconds());
        startSec=Math.max(0,Math.min(startSec,Math.max(0,total-2)));
        endSec=Math.max(startSec+2,Math.min(endSec,total));
        startSec=Math.round(startSec);
        endSec=Math.round(endSec);
        if(endSec-startSec<2){
            if(startSec>=2)startSec=endSec-2;
            else endSec=Math.min(total,startSec+2);
        }
        const startInput=$('workshop-start-sec'),endInput=$('workshop-end-sec');
        if(startInput){startInput.max=String(Math.max(0,Math.floor(total-2)));startInput.value=String(startSec);}
        if(endInput){endInput.max=String(Math.ceil(total));endInput.value=String(endSec);}
        const startClock=$('workshop-start-clock'),endClock=$('workshop-end-clock');
        if(startClock)startClock.textContent=formatClock(startSec);
        if(endClock)endClock.textContent=formatClock(endSec);
        const span=Math.max(0,Math.round(endSec-startSec));
        const summary=$('workshop-range-summary');
        if(summary){
            summary.textContent=`선택 구간: ${formatClock(startSec)} ~ ${formatClock(endSec)} (총 ${span}초 수정 · 앞뒤 원곡은 그대로 유지)`;
        }
        syncTimeline();
    }

    function syncTimeline(){
        const total=Math.max(1,totalSongSeconds());
        const audio=getSourceAudio();
        const current=audio&&Number.isFinite(audio.currentTime)?audio.currentTime:0;
        const pct=Math.min(100,Math.max(0,(current/total)*100));
        const playhead=$('workshop-timeline-playhead');
        if(playhead)playhead.style.left=pct.toFixed(2)+'%';
        const cursor=$('workshop-timeline-cursor');
        if(cursor)cursor.textContent=`재생 위치 ${formatClock(current)}`;
        const totalEl=$('workshop-timeline-total');
        if(totalEl)totalEl.textContent=formatClock(total);
        const bar=$('workshop-timeline-bar');
        if(bar)bar.setAttribute('aria-valuenow',String(Math.round(pct)));
        const rangeEl=$('workshop-timeline-range');
        const rangeLabel=$('workshop-timeline-range-label');
        const startTag=$('workshop-range-start-tag');
        const endTag=$('workshop-range-end-tag');
        const showRange=activeTab==='repaint'&&repaintSubMode==='section';
        if(rangeLabel){
            rangeLabel.hidden=!showRange;
            if(showRange){
                const span=Math.max(0,Math.round(endSec-startSec));
                rangeLabel.textContent=`구간: ${formatClock(startSec)} ~ ${formatClock(endSec)} (${span}초)`;
            }
        }
        const timelineRuler=$('workshop-timeline-ruler');
        const rulerPlayhead=timelineRuler?.querySelector('.workshop-ruler-playhead');
        if(rulerPlayhead)rulerPlayhead.style.left=pct.toFixed(2)+'%';
        const rulerRange=timelineRuler?.querySelector('.workshop-ruler-range');
        if(rangeEl||rulerRange){
            const leftPct=Math.min(100,Math.max(0,(startSec/total)*100));
            const widthPct=Math.min(100-leftPct,Math.max(1.5,((endSec-startSec)/total)*100));
            if(rangeEl){
                rangeEl.hidden=!showRange;
                if(showRange){
                    rangeEl.style.left=leftPct.toFixed(2)+'%';
                    rangeEl.style.width=widthPct.toFixed(2)+'%';
                    rangeEl.classList.toggle('is-narrow',widthPct<16);
                    if(startTag)startTag.textContent=formatClock(startSec);
                    if(endTag)endTag.textContent=formatClock(endSec);
                }
            }
            if(rulerRange){
                rulerRange.hidden=!showRange;
                if(showRange){
                    rulerRange.style.left=leftPct.toFixed(2)+'%';
                    rulerRange.style.width=widthPct.toFixed(2)+'%';
                }
            }
        }
    }

    function syncPreviewButton(){
        const btn=$('workshop-preview-range');
        if(!btn)return;
        const active=previewEndTime!==null;
        btn.classList.toggle('is-playing',active);
        btn.innerHTML=window.StudioIcons(active?'stop':'play')+' <span>'+(active?'구간 듣기 멈추기':'선택한 구간만 들어보기')+'</span>';
    }

    function syncExtendSummary(){
        const total=Math.round(totalSongSeconds());
        const maxExtend=Math.max(5,Math.min(120,600-total));
        extendSec=Math.max(5,Math.min(maxExtend,Math.round(Number(extendSec)||20)));
        const input=$('workshop-extend-custom');
        if(input){
            input.max=String(maxExtend);
            input.value=String(extendSec);
        }
        for(const btn of document.querySelectorAll('#workshop-extend-presets [data-extend-sec]')){
            const val=Number(btn.dataset.extendSec);
            btn.disabled=val>maxExtend;
            const active=val===extendSec;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }
        const summary=$('workshop-extend-summary');
        if(summary){
            summary.textContent=`원곡 ${formatClock(total)} + 연장 ${extendSec}초 → 예상 완성 길이 ${formatClock(total+extendSec)}`;
        }
    }

    function syncPromptCount(){
        const promptEl=$('workshop-prompt'),countEl=$('workshop-prompt-count');
        if(!promptEl||!countEl)return;
        const count=Array.from(promptEl.value).length;
        countEl.textContent=`${count.toLocaleString('ko-KR')} / 2,000자`;
        countEl.classList.toggle('over-limit',count>2000);
    }

    function syncModeUI(){
        for(const tab of document.querySelectorAll('.workshop-mode-tab')){
            const active=tab.dataset.workshopMode===activeTab;
            tab.classList.toggle('is-active',active);
            tab.setAttribute('aria-selected',String(active));
        }
        $('workshop-panel-repaint').hidden=activeTab!=='repaint';
        $('workshop-panel-cover').hidden=activeTab!=='cover';
        $('workshop-panel-retake').hidden=activeTab!=='retake';

        const isSection=activeTab==='repaint'&&repaintSubMode==='section';
        $('workshop-capture-row').hidden=!isSection;
        $('workshop-section-controls').hidden=repaintSubMode!=='section';
        $('workshop-extend-controls').hidden=repaintSubMode!=='extend';
        $('workshop-repaint-sub-section').classList.toggle('is-active',repaintSubMode==='section');
        $('workshop-repaint-sub-section').setAttribute('aria-pressed',String(repaintSubMode==='section'));
        $('workshop-repaint-sub-extend').classList.toggle('is-active',repaintSubMode==='extend');
        $('workshop-repaint-sub-extend').setAttribute('aria-pressed',String(repaintSubMode==='extend'));

        for(const btn of document.querySelectorAll('#workshop-repaint-mode-group [data-repaint-preset]')){
            const active=btn.dataset.repaintPreset===repaintPreset;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }
        for(const btn of document.querySelectorAll('#workshop-cover-strength-group [data-cover-strength]')){
            const active=Math.abs(Number(btn.dataset.coverStrength)-coverStrength)<0.01;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }
        for(const btn of document.querySelectorAll('#workshop-retake-variance-group [data-retake-variance]')){
            const active=Math.abs(Number(btn.dataset.retakeVariance)-retakeVariance)<0.01;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }

        const step3Title=$('workshop-step3-title'),step3Desc=$('workshop-step3-desc');
        if(activeTab==='repaint'){
            if(repaintSubMode==='extend'){
                step3Title.textContent='연장할 길이 및 이어 부를 가사 설정';
                step3Desc.textContent='노래가 끊긴 뒷부분을 얼마나 더 늘릴지 고르고, 이어 부를 가사가 빠지지 않았는지 확인하세요.';
            }else{
                step3Title.textContent='고칠 구간 및 가사·발음 수정';
                step3Desc.textContent='고치고 싶은 시작~끝 시간과 수정 강도를 고른 뒤, 문제가 된 구간의 가사를 다듬어 주세요.';
            }
        }else if(activeTab==='cover'){
            step3Title.textContent='편곡 방향 및 새로운 스타일 입력';
            step3Desc.textContent='원곡 멜로디 유지 강도와 바꾸고 싶은 반주 스타일·악기 구성을 입력해 주세요.';
        }else{
            step3Title.textContent='테이크 변주 폭 및 세부 확인';
            step3Desc.textContent='원곡과 얼마나 다르게 다시 부를지 선택하고, 필요하면 가사와 스타일을 미세 조정하세요.';
        }

        const isInstrumental=Boolean(sourceJob?.settings?.instrumental);
        $('workshop-lyrics-wrap').hidden=isInstrumental;
        $('workshop-body-grid')?.classList.toggle('is-instrumental',isInstrumental);

        const submitBtn=$('workshop-submit-btn');
        if(submitBtn){
            const iconName=activeTab==='repaint'?'scissors':(activeTab==='cover'?'layers':'repeat');
            let label='노래 다듬기 시작';
            if(submitting||pendingEditId)label='노래를 다듬고 있습니다…';
            else if(activeTab==='repaint')label=repaintSubMode==='extend'?'뒷부분 이어 붙이기 시작':'선택 구간 다시 부르기 시작';
            else if(activeTab==='cover')label='새로운 편곡으로 다시 만들기';
            else label='다른 느낌으로 다시 부르기';
            submitBtn.innerHTML=window.StudioIcons(iconName)+' <span>'+label+'</span>';
        }

        if(!titleTouched&&$('workshop-title')){
            $('workshop-title').value=suggestedTitle();
        }
        syncExtendSummary();
        syncTimeline();
        syncRunState();
    }

    function syncCoverVoices(){
        const sel=$('workshop-cover-voice');
        if(!sel)return;
        const ctx=window.StudioAppContext?.getContext();
        const items=Array.isArray(ctx?.referenceAudios)?ctx.referenceAudios:[];
        const prev=sel.value;
        sel.innerHTML='<option value="">원래 노래 스타일 유지 (음색 변경 안 함)</option>'+items.map(item=>`<option value="${escapeHTML(item.id)}">${escapeHTML(item.name)}</option>`).join('');
        if(items.some(i=>i.id===prev))sel.value=prev;
    }

    function syncVersionSwitcher(){
        const wrap=$('workshop-version-wrap'),sel=$('workshop-version-select');
        if(!wrap||!sel||!sourceJob)return;
        const rootId=sourceJob.rootJobId||sourceJob.id;
        const family=allJobs
            .filter(j=>j.status==='completed'&&j.settings?.mode==='song'&&(j.id===rootId||j.rootJobId===rootId))
            .slice()
            .sort((a,b)=>(Number(a.createdAt)||0)-(Number(b.createdAt)||0));
        if(family.length<=1){
            wrap.hidden=true;
            sel.replaceChildren();
            return;
        }
        wrap.hidden=false;
        sel.replaceChildren();
        let editSeq=0;
        for(const item of family){
            const opt=document.createElement('option');
            opt.value=item.id;
            const dur=Number.isFinite(item.durationSeconds)?item.durationSeconds:item.settings?.seconds;
            if(item.id===rootId){
                opt.textContent=Number.isFinite(dur)?`원본 노래 (${formatClock(dur)})`:'원본 노래';
            }else{
                editSeq+=1;
                const summary=item.editSpec?.summaryLabel||'수정본';
                opt.textContent=`${editSeq}차 · ${summary}`;
            }
            sel.append(opt);
        }
        sel.value=sourceJob.id;
    }

    function syncDeviceNote(){
        const note=$('workshop-device-note');
        const ctx=window.StudioAppContext?.getContext();
        if(!note||!ctx)return;
        const backend=ctx.backend||sourceJob?.settings?.backend||'cpu';
        const label=backend==='apple'?'Apple Silicon (MPS) 가속':(backend==='cuda'?'NVIDIA GPU (CUDA) 가속':'CPU 호환 모드');
        note.textContent=`저사양 최적화 적용: 곡 구성 플래너를 건너뛰고 ${label}로 선택한 다듬기 작업만 바로 실행합니다.`;
    }

    function syncRunState(){
        const ctx=window.StudioAppContext?.getContext();
        const anyRunning=allJobs.some(j=>['queued','running'].includes(j.status));
        const runningJob=allJobs.find(j=>j.id===pendingEditId&&['queued','running'].includes(j.status))||(anyRunning?allJobs.find(j=>['queued','running'].includes(j.status)):null);
        const submitBtn=$('workshop-submit-btn');
        if(submitBtn)submitBtn.disabled=submitting||anyRunning||!sourceJob;

        const progWrap=$('workshop-run-progress'),progStatus=$('workshop-progress-status'),progSub=$('workshop-progress-sub'),cancelBtn=$('workshop-cancel-btn');
        if(runningJob){
            progWrap.hidden=false;
            runStartedAt=runningJob.createdAt||Date.now()/1000;
            const elapsed=formatClock(Date.now()/1000-runStartedAt);
            const title=runningJob.id===pendingEditId?'노래 다듬기 진행 중':'현재 다른 음악 작업 진행 중';
            if(!progStatus.querySelector('.dot-matrix-scanner')){
                progStatus.innerHTML=`<div class="dot-matrix-main"><span class="dot-matrix-label">${escapeHTML(title)}</span><span class="dot-matrix-clock">${elapsed}</span></div><div class="dot-matrix-scanner" aria-hidden="true"><span></span></div>`;
            }else{
                progStatus.querySelector('.dot-matrix-label').textContent=title;
                progStatus.querySelector('.dot-matrix-clock').textContent=elapsed;
            }
            if(progSub){
                progSub.textContent=runningJob.phase||'오디오를 다듬고 있습니다…';
                progSub.hidden=false;
            }
            if(cancelBtn){
                cancelBtn.disabled=cancelling;
                cancelBtn.textContent=cancelling?'중단 요청 중…':'작업 중단';
            }
        }else{
            progWrap.hidden=true;
            runStartedAt=0;
            if(progStatus)progStatus.innerHTML='';
            if(progSub)progSub.hidden=true;
        }
        syncDeviceNote();
    }

    function originalLyricsForJob(job){
        if(!job)return '';
        if(job.editSpec?.originalLyrics)return job.editSpec.originalLyrics;
        const rootId=job.rootJobId||job.id;
        if(rootId&&rootId!==job.id){
            const root=allJobs.find(item=>item.id===rootId);
            if(root?.lyrics)return root.editSpec?.originalLyrics||root.lyrics;
        }
        return job.lyrics||'';
    }

    function editRecordsForJob(job){
        if(!job)return [];
        if(Array.isArray(job.editHistory)&&job.editHistory.length){
            return job.editHistory.filter(item=>item&&typeof item==='object');
        }
        if(job.editSpec?.mode){
            const spec=job.editSpec;
            const start=Number.isFinite(Number(spec.repaintStart))?Number(spec.repaintStart):0;
            const end=Number.isFinite(Number(spec.repaintEnd))?Number(spec.repaintEnd):(Number.isFinite(Number(spec.targetDuration))?Number(spec.targetDuration):(Number(spec.sourceDuration)||0));
            return [{
                jobId:job.id,
                mode:spec.mode,
                subMode:spec.subMode,
                summaryLabel:spec.summaryLabel||'',
                repaintStart:start,
                repaintEnd:end,
                startClock:spec.startClock||formatClock(start),
                endClock:spec.endClock||formatClock(end),
                editedLyrics:(spec.editedLyrics??job.lyrics??'').trim(),
                editedPrompt:(job.prompt||'').trim()
            }];
        }
        return [];
    }

    function autoResizeLyricsTextarea(){
        const el=$('workshop-lyrics');
        if(!el)return;
        const lines=String(el.value||'').split('\n').length;
        el.rows=Math.max(12,lines+1);
        el.style.height='auto';
        if(el.scrollHeight>0){
            el.style.height=`${Math.max(320,el.scrollHeight+6)}px`;
        }
    }

    function setLyricsTab(tabName){
        lyricsTab=tabName==='history'?'history':'orig';
        const isOrig=lyricsTab==='orig';
        const origTab=$('workshop-lyrics-tab-orig'),histTab=$('workshop-lyrics-tab-history');
        const origPanel=$('workshop-lyrics-panel-orig'),histPanel=$('workshop-lyrics-panel-history');
        if(origTab){
            origTab.classList.toggle('is-active',isOrig);
            origTab.setAttribute('aria-selected',String(isOrig));
        }
        if(histTab){
            histTab.classList.toggle('is-active',!isOrig);
            histTab.setAttribute('aria-selected',String(!isOrig));
        }
        if(origPanel)origPanel.hidden=!isOrig;
        if(histPanel)histPanel.hidden=isOrig;
        if(isOrig)autoResizeLyricsTextarea();
    }

    function renderEditRecordHTML(rec,index,totalCount,origLyrics,withLoadBtn=false){
        const startClock=rec.startClock||formatClock(rec.repaintStart||0);
        const endClock=rec.endClock||formatClock(rec.repaintEnd||0);
        const rangeText=`시작 ${startClock} ~ 끝 ${endClock}`;
        const badge=rec.summaryLabel||'다듬기 수정';
        const rawLyrics=String(rec.editedLyrics||'').trim();
        const sameAsOriginal=Boolean(rawLyrics&&origLyrics&&rawLyrics===origLyrics.trim());
        const body=rawLyrics?(sameAsOriginal?'원본 가사와 동일 (가사 변경 없음)'+(rec.editedPrompt?`\n스타일: ${rec.editedPrompt}`:''):rawLyrics):(rec.editedPrompt?`스타일 변경: ${rec.editedPrompt}`:'가사 변경 없음');
        const stepLabel=totalCount>1?`${index+1}차 수정`:'수정 내역';
        const loadBtnHTML=withLoadBtn&&rawLyrics?`<button type="button" class="workshop-history-load-btn" data-load-edit-index="${index}">가사창에 불러오기</button>`:'';
        return `<article class="workshop-edit-history-item"><div class="edit-record-head"><span class="edit-record-step">${escapeHTML(stepLabel)}</span><span class="edit-record-range">${escapeHTML(rangeText)}</span><span class="edit-record-badge">${escapeHTML(badge)}</span></div><pre class="edit-record-lyrics">${escapeHTML(body)}</pre>${loadBtnHTML?`<div class="edit-record-actions">${loadBtnHTML}</div>`:''}</article>`;
    }

    function renderEditHistory(){
        const wrap=$('workshop-edit-history-wrap'),list=$('workshop-edit-history-list'),emptyEl=$('workshop-edit-history-empty'),countEl=$('workshop-edit-history-count');
        if(!wrap||!list)return;
        const targetJob=comparedJob||sourceJob;
        const records=editRecordsForJob(targetJob);
        if(countEl)countEl.textContent=String(records.length);
        if(!records.length){
            if(emptyEl)emptyEl.hidden=false;
            list.hidden=true;
            list.innerHTML='';
            return;
        }
        const orig=originalLyricsForJob(targetJob);
        if(emptyEl)emptyEl.hidden=true;
        list.hidden=false;
        list.innerHTML=records.map((rec,idx)=>renderEditRecordHTML(rec,idx,records.length,orig,true)).join('');
    }

    function renderComparison(){
        const card=$('workshop-comparison-card');
        if(!card)return;
        const detailEl=$('workshop-compare-edit-detail');
        if(!comparedJob||!comparedJob.audioUrl||!sourceJob?.audioUrl){
            card.hidden=true;
            if(detailEl){detailEl.hidden=true;detailEl.innerHTML='';}
            releasePlayerContainer('workshop-compare-orig-player');
            releasePlayerContainer('workshop-compare-new-player');
            return;
        }
        card.hidden=false;
        $('workshop-compare-orig-title').textContent=jobDisplayTitle(sourceJob);
        $('workshop-compare-new-title').textContent=jobDisplayTitle(comparedJob);
        $('workshop-compare-new-tag').textContent=comparedJob.editSpec?.summaryLabel||'방금 다듬은 노래';

        releasePlayerContainer('workshop-compare-orig-player');
        releasePlayerContainer('workshop-compare-new-player');
        const origWrap=$('workshop-compare-orig-player'),newWrap=$('workshop-compare-new-player');
        origWrap.innerHTML=window.AudioSpectrum.markup(escapeHTML(sourceJob.audioUrl));
        newWrap.innerHTML=window.AudioSpectrum.markup(escapeHTML(comparedJob.audioUrl));
        window.AudioSpectrum.attach(origWrap);
        window.AudioSpectrum.attach(newWrap);
        attachWorkshopPlayerControls(origWrap);
        attachWorkshopPlayerControls(newWrap);

        if(detailEl){
            const records=editRecordsForJob(comparedJob);
            if(records.length){
                const latest=records[records.length-1];
                detailEl.hidden=false;
                detailEl.innerHTML=`<div class="workshop-compare-detail-title">이번 수정 기록</div>${renderEditRecordHTML(latest,records.length-1,1,originalLyricsForJob(comparedJob))}`;
            }else{
                detailEl.hidden=true;
                detailEl.innerHTML='';
            }
        }

        const baseName=(comparedJob.title?.trim()||('music-'+comparedJob.id)).replace(/[\\/:*?"<>|\x00-\x1f]/g,'-').replace(/[. ]+$/,'').slice(0,80)||('music-'+comparedJob.id);
        const filename=baseName.startsWith('SoriSoop_')?baseName:('SoriSoop_'+baseName);
        const wavLink=$('workshop-compare-wav'),mp3Link=$('workshop-compare-mp3');
        wavLink.href=comparedJob.audioUrl;
        wavLink.download=`${filename}.wav`;
        mp3Link.href=`/audio/${comparedJob.id}.mp3`;
        mp3Link.download=`${filename}.mp3`;
        $('workshop-compare-download-msg').textContent='';
    }

    function loadJobIntoWorkshop(job,options={}){
        sourceJob=job;
        sourceJob._measuredDuration=null;
        if(!options.keepComparison){
            comparedJob=null;
            pendingEditId=null;
        }
        titleTouched=false;
        const total=Math.round(totalSongSeconds());
        startSec=Math.max(0,Math.round(total*0.25));
        endSec=Math.min(total,Math.max(startSec+5,Math.round(total*0.5)));
        extendSec=Math.min(20,Math.max(5,600-total));

        $('workshop-heading').textContent=jobDisplayTitle(job);
        const badge=$('workshop-source-badge');
        if(job.editSpec?.summaryLabel){
            badge.textContent=job.editSpec.summaryLabel;
            badge.hidden=false;
        }else{
            badge.textContent='원본 노래';
            badge.hidden=false;
        }
        const bpmText=job.composition?.metadata?.bpm?` · ${job.composition.metadata.bpm} BPM`:'';
        const typeText=job.settings?.instrumental?'연주곡':'보컬 노래';
        $('workshop-source-subtitle').textContent=`${typeText} · 길이 ${formatClock(total)}${bpmText}`;

        $('workshop-prompt').value=job.prompt||'';
        syncPromptCount();
        const origLyrics=originalLyricsForJob(job);
        $('workshop-lyrics').value=origLyrics;
        $('workshop-run-error').hidden=true;
        $('workshop-run-error').textContent='';

        syncCoverVoices();
        syncVersionSwitcher();
        renderSourcePlayer();
        clampRange();
        syncModeUI();
        renderComparison();
        renderEditHistory();
        setLyricsTab('orig');
        autoResizeLyricsTextarea();
        window.requestAnimationFrame?.(autoResizeLyricsTextarea);
    }

    function open(jobId){
        const ctx=window.StudioAppContext?.getContext();
        allJobs=ctx?.jobs||[];
        const job=allJobs.find(j=>j.id===jobId);
        if(!job||job.status!=='completed'||job.settings?.mode!=='song')return;

        for(const audio of document.querySelectorAll('#jobs audio'))audio.pause();
        const layout=document.querySelector('main > .layout');
        if(layout)layout.hidden=true;
        $('song-workshop').hidden=false;
        const uiModeSwitch=$('ui-mode-switch');
        if(uiModeSwitch)uiModeSwitch.hidden=true;
        isOpen=true;
        activeTab='repaint';
        repaintSubMode='section';
        repaintPreset='balanced';
        loadJobIntoWorkshop(job);
        window.scrollTo({top:0,behavior:'instant'});
        $('workshop-back-btn')?.focus();
    }

    function close(){
        if(!isOpen)return;
        pauseAllWorkshopAudio();
        releasePlayerContainer('workshop-source-player');
        releasePlayerContainer('workshop-compare-orig-player');
        releasePlayerContainer('workshop-compare-new-player');
        $('song-workshop').hidden=true;
        const uiModeSwitch=$('ui-mode-switch');
        if(uiModeSwitch)uiModeSwitch.hidden=false;
        const layout=document.querySelector('main > .layout');
        if(layout)layout.hidden=false;
        isOpen=false;
        sourceJob=null;
        comparedJob=null;
        pendingEditId=null;
    }

    function onJobsUpdated(jobs){
        allJobs=Array.isArray(jobs)?jobs:[];
        if(!isOpen)return;
        if(pendingEditId){
            const tracked=allJobs.find(j=>j.id===pendingEditId);
            if(tracked){
                if(tracked.status==='completed'){
                    pendingEditId=null;
                    comparedJob=tracked;
                    syncVersionSwitcher();
                    renderComparison();
                    renderEditHistory();
                    syncRunState();
                    $('workshop-comparison-card')?.scrollIntoView({behavior:'smooth',block:'start'});
                    return;
                }
                if(['failed','cancelled','interrupted'].includes(tracked.status)){
                    pendingEditId=null;
                    const errEl=$('workshop-run-error');
                    errEl.textContent=tracked.error||(tracked.status==='cancelled'?'노래 다듬기 작업이 중단되었습니다.':'노래 다듬기에 실패했습니다.');
                    errEl.hidden=false;
                }
            }
        }
        syncVersionSwitcher();
        syncRunState();
    }

    function buildEditSpec(){
        if(activeTab==='repaint'){
            const preset=REPAINT_PRESETS[repaintPreset]||REPAINT_PRESETS.balanced;
            if(repaintSubMode==='extend'){
                return {
                    mode:'repaint',
                    subMode:'extend',
                    extendSeconds:extendSec,
                    repaintMode:preset.repaintMode,
                    repaintStrength:preset.repaintStrength
                };
            }
            return {
                mode:'repaint',
                subMode:'section',
                repaintStart:startSec,
                repaintEnd:endSec,
                repaintMode:preset.repaintMode,
                repaintStrength:preset.repaintStrength
            };
        }
        if(activeTab==='cover'){
            return {
                mode:'cover',
                coverStrength,
                coverNoiseStrength:0.0
            };
        }
        return {
            mode:'retake',
            retakeVariance
        };
    }

    async function submitWorkshopEdit(){
        if(!sourceJob||submitting)return;
        const errEl=$('workshop-run-error');
        errEl.hidden=true;
        errEl.textContent='';

        const prompt=$('workshop-prompt').value.trim();
        const title=$('workshop-title').value.trim();
        const isInstrumental=Boolean(sourceJob.settings?.instrumental);
        const lyrics=isInstrumental?'':$('workshop-lyrics').value;
        const language=isInstrumental?'unknown':(sourceJob.language||sourceJob.composition?.metadata?.language||'ko');
        if(!prompt){
            errEl.textContent='음악 스타일 설명을 입력해 주세요.';
            errEl.hidden=false;
            $('workshop-prompt').focus();
            return;
        }
        if(!isInstrumental&&!lyrics.trim()){
            errEl.textContent='노래 가사를 입력해 주세요.';
            errEl.hidden=false;
            $('workshop-lyrics').focus();
            return;
        }

        const total=totalSongSeconds();
        const targetDuration=activeTab==='repaint'&&repaintSubMode==='extend'?total+extendSec:total;
        const ctx=window.StudioAppContext?.getContext()||{};
        const backend=ctx.backend||sourceJob.settings?.backend||'cpu';
        const settings={
            policy:'manual',
            mode:'song',
            model:'ace-step',
            backend,
            peakDb:ctx.peakDb??sourceJob.settings?.peakDb??-8,
            instrumental:isInstrumental,
            durationMode:'manual',
            seconds:Math.max(10,Math.min(600,Math.round(targetDuration))),
            songQuality:'light',
            songExpert:ctx.songExpert||sourceJob.settings?.songExpert
        };

        let refIds=[];
        if(activeTab==='cover'){
            const picked=$('workshop-cover-voice')?.value;
            if(picked)refIds=[picked];
        }else if(Array.isArray(sourceJob.referenceAudioIds)&&sourceJob.referenceAudioIds.length){
            refIds=sourceJob.referenceAudioIds;
        }else if(sourceJob.referenceAudioId){
            refIds=[sourceJob.referenceAudioId];
        }

        const editSpec={sourceJobId:sourceJob.id,...buildEditSpec()};

        submitting=true;
        syncModeUI();
        try{
            const res=await fetch('/api/generate',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    settings,
                    title,
                    prompt,
                    negativePrompt:sourceJob.negativePrompt||'',
                    lyrics,
                    language,
                    referenceAudioIds:refIds,
                    editSpec
                })
            });
            const data=await res.json();
            if(!res.ok)throw new Error(data.error||'노래 다듬기 요청에 실패했습니다.');
            pendingEditId=data.id;
            comparedJob=null;
            renderComparison();
            await ctx.refreshJobs?.();
        }catch(error){
            errEl.textContent=error.message;
            errEl.hidden=false;
        }finally{
            submitting=false;
            syncModeUI();
        }
    }

    function bindEvents(){
        $('workshop-back-btn')?.addEventListener('click',close);

        $('workshop-version-select')?.addEventListener('change',e=>{
            const next=allJobs.find(j=>j.id===e.target.value);
            if(next&&next.id!==sourceJob?.id){
                loadJobIntoWorkshop(next);
            }
        });

        for(const tab of document.querySelectorAll('.workshop-mode-tab')){
            tab.addEventListener('click',()=>{
                activeTab=tab.dataset.workshopMode;
                syncModeUI();
            });
        }

        $('workshop-repaint-sub-section')?.addEventListener('click',()=>{
            repaintSubMode='section';
            syncModeUI();
        });
        $('workshop-repaint-sub-extend')?.addEventListener('click',()=>{
            repaintSubMode='extend';
            syncModeUI();
        });

        for(const btn of document.querySelectorAll('#workshop-repaint-mode-group [data-repaint-preset]')){
            btn.addEventListener('click',()=>{
                repaintPreset=btn.dataset.repaintPreset;
                syncModeUI();
            });
        }
        for(const btn of document.querySelectorAll('#workshop-cover-strength-group [data-cover-strength]')){
            btn.addEventListener('click',()=>{
                coverStrength=Number(btn.dataset.coverStrength);
                syncModeUI();
            });
        }
        for(const btn of document.querySelectorAll('#workshop-retake-variance-group [data-retake-variance]')){
            btn.addEventListener('click',()=>{
                retakeVariance=Number(btn.dataset.retakeVariance);
                syncModeUI();
            });
        }

        for(const btn of document.querySelectorAll('#workshop-extend-presets [data-extend-sec]')){
            btn.addEventListener('click',()=>{
                extendSec=Number(btn.dataset.extendSec);
                syncModeUI();
            });
        }
        $('workshop-extend-custom')?.addEventListener('input',e=>{
            const v=Number(e.target.value);
            if(Number.isFinite(v)&&v>=5){
                extendSec=v;
                syncExtendSummary();
                if(!titleTouched&&$('workshop-title'))$('workshop-title').value=suggestedTitle();
            }
        });

        for(const btn of document.querySelectorAll('[data-zone]')){
            btn.addEventListener('click',()=>{
                const total=Math.max(2,Math.round(totalSongSeconds()));
                const z=btn.dataset.zone;
                if(z==='intro'){startSec=0;endSec=Math.min(total,Math.max(10,Math.round(total*0.3)));}
                else if(z==='middle'){startSec=Math.round(total*0.3);endSec=Math.max(startSec+4,Math.round(total*0.7));}
                else if(z==='ending'){endSec=total;startSec=Math.max(0,Math.min(total-4,Math.round(total*0.65)));}
                else{startSec=0;endSec=total;}
                clampRange();
            });
        }

        for(const btn of document.querySelectorAll('[data-adjust-target]')){
            btn.addEventListener('click',()=>{
                const delta=Number(btn.dataset.adjust);
                if(btn.dataset.adjustTarget==='start'){
                    startSec+=delta;
                    if(endSec-startSec<2)endSec=Math.min(totalSongSeconds(),startSec+2);
                }else{
                    endSec+=delta;
                    if(endSec-startSec<2)startSec=Math.max(0,endSec-2);
                }
                clampRange();
            });
        }

        $('workshop-start-sec')?.addEventListener('change',e=>{
            const v=Number(e.target.value);
            if(Number.isFinite(v)){startSec=v;clampRange();}
        });
        $('workshop-end-sec')?.addEventListener('change',e=>{
            const v=Number(e.target.value);
            if(Number.isFinite(v)){endSec=v;clampRange();}
        });

        $('workshop-mark-start')?.addEventListener('click',()=>{
            const audio=getSourceAudio();
            const cur=audio&&Number.isFinite(audio.currentTime)?Math.floor(audio.currentTime):0;
            startSec=cur;
            if(endSec<startSec+2)endSec=Math.min(totalSongSeconds(),startSec+10);
            clampRange();
        });
        $('workshop-mark-end')?.addEventListener('click',()=>{
            const audio=getSourceAudio();
            const cur=audio&&Number.isFinite(audio.currentTime)?Math.ceil(audio.currentTime):15;
            endSec=Math.max(2,cur);
            if(endSec-startSec<2)startSec=Math.max(0,endSec-10);
            clampRange();
        });
        $('workshop-preview-range')?.addEventListener('click',async()=>{
            const audio=getSourceAudio();
            if(!audio)return;
            if(previewEndTime!==null){
                audio.pause();
                previewEndTime=null;
                syncPreviewButton();
                return;
            }
            pauseAllWorkshopAudio(audio);
            window.AudioSpectrum?.prepare(audio);
            audio.currentTime=Math.max(0,startSec);
            previewEndTime=endSec;
            syncPreviewButton();
            try{await audio.play();}
            catch(e){previewEndTime=null;syncPreviewButton();}
        });

        const timelineBar=$('workshop-timeline-bar');
        if(timelineBar){
            timelineBar.addEventListener('pointerdown',e=>{
                if(e.button!==0)return;
                const dragTarget=e.target.closest('[data-drag-mode]');
                if(!dragTarget||activeTab!=='repaint'||repaintSubMode!=='section')return;
                const rect=timelineBar.getBoundingClientRect();
                if(rect.width<=0)return;
                e.preventDefault();
                e.stopPropagation();
                dragState={
                    mode:dragTarget.dataset.dragMode,
                    pointerId:e.pointerId,
                    anchorX:e.clientX,
                    origStart:startSec,
                    origEnd:endSec,
                    barWidth:rect.width,
                    moved:false
                };
                timelineBar.classList.add('is-dragging');
                try{timelineBar.setPointerCapture(e.pointerId);}catch(err){}
            });

            timelineBar.addEventListener('pointermove',e=>{
                if(!dragState||e.pointerId!==dragState.pointerId)return;
                const deltaPx=e.clientX-dragState.anchorX;
                if(Math.abs(deltaPx)>2)dragState.moved=true;
                const total=Math.max(2,totalSongSeconds());
                const deltaSec=(deltaPx/dragState.barWidth)*total;
                if(dragState.mode==='move'){
                    const span=dragState.origEnd-dragState.origStart;
                    const nextStart=Math.max(0,Math.min(total-span,dragState.origStart+deltaSec));
                    startSec=Math.round(nextStart);
                    endSec=Math.round(nextStart+span);
                }else if(dragState.mode==='start'){
                    const nextStart=Math.max(0,Math.min(dragState.origEnd-2,dragState.origStart+deltaSec));
                    startSec=Math.round(nextStart);
                }else if(dragState.mode==='end'){
                    const nextEnd=Math.min(total,Math.max(dragState.origStart+2,dragState.origEnd+deltaSec));
                    endSec=Math.round(nextEnd);
                }
                clampRange();
            });

            const finishDrag=e=>{
                if(!dragState||e.pointerId!==dragState.pointerId)return;
                if(dragState.moved||dragState.mode!=='move')suppressNextBarClick=true;
                timelineBar.classList.remove('is-dragging');
                try{timelineBar.releasePointerCapture(e.pointerId);}catch(err){}
                dragState=null;
            };
            timelineBar.addEventListener('pointerup',finishDrag);
            timelineBar.addEventListener('pointercancel',finishDrag);

            timelineBar.addEventListener('click',e=>{
                if(suppressNextBarClick){suppressNextBarClick=false;return;}
                if(e.target.closest('.workshop-range-handle'))return;
                const rect=timelineBar.getBoundingClientRect();
                if(rect.width<=0)return;
                seekSourceAudioByRatio((e.clientX-rect.left)/rect.width);
            });

            timelineBar.addEventListener('keydown',e=>{
                if(!['ArrowLeft','ArrowRight'].includes(e.key))return;
                const handle=e.target.closest('[data-drag-mode]');
                const step=e.shiftKey?5:1;
                const delta=e.key==='ArrowRight'?step:-step;
                if(handle&&handle.dataset.dragMode==='start'){
                    e.preventDefault();
                    startSec=Math.max(0,Math.min(endSec-2,startSec+delta));
                    clampRange();
                    return;
                }
                if(handle&&handle.dataset.dragMode==='end'){
                    e.preventDefault();
                    endSec=Math.min(totalSongSeconds(),Math.max(startSec+2,endSec+delta));
                    clampRange();
                    return;
                }
                const audio=getSourceAudio();
                if(!audio)return;
                e.preventDefault();
                audio.currentTime=Math.min(totalSongSeconds(),Math.max(0,(audio.currentTime||0)+(e.key==='ArrowRight'?5:-5)));
                syncTimeline();
            });
        }

        $('workshop-timeline-ruler')?.addEventListener('click',e=>{
            const rect=e.currentTarget.getBoundingClientRect();
            if(rect.width>0)seekSourceAudioByRatio((e.clientX-rect.left)/rect.width);
        });

        for(const chip of document.querySelectorAll('#workshop-cover-style-chips [data-style-text]')){
            chip.addEventListener('click',()=>{
                const promptEl=$('workshop-prompt');
                if(!promptEl)return;
                const snippet=chip.dataset.styleText;
                const current=promptEl.value.trim();
                promptEl.value=current?`${snippet}, ${current}`:snippet;
                syncPromptCount();
                promptEl.focus();
            });
        }

        $('workshop-title')?.addEventListener('input',()=>{titleTouched=true;});
        $('workshop-prompt')?.addEventListener('input',syncPromptCount);
        $('workshop-lyrics')?.addEventListener('input',autoResizeLyricsTextarea);
        window.addEventListener('resize',()=>{if(isOpen&&lyricsTab==='orig')autoResizeLyricsTextarea();});
        for(const tabBtn of document.querySelectorAll('[data-lyrics-tab]')){
            tabBtn.addEventListener('click',()=>setLyricsTab(tabBtn.dataset.lyricsTab));
        }
        $('workshop-edit-history-list')?.addEventListener('click',e=>{
            const btn=e.target.closest('[data-load-edit-index]');
            if(!btn)return;
            const idx=Number(btn.dataset.loadEditIndex);
            const targetJob=comparedJob||sourceJob;
            const rec=editRecordsForJob(targetJob)[idx];
            const lyricsText=String(rec?.editedLyrics||'').trim();
            const lyricsEl=$('workshop-lyrics');
            if(lyricsEl&&lyricsText){
                lyricsEl.value=lyricsText;
                setLyricsTab('orig');
                lyricsEl.focus();
            }
        });
        $('workshop-submit-btn')?.addEventListener('click',submitWorkshopEdit);
        $('workshop-cancel-btn')?.addEventListener('click',async()=>{
            if(cancelling)return;
            cancelling=true;
            syncRunState();
            try{
                await fetch('/api/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
                await window.StudioAppContext?.getContext()?.refreshJobs?.();
            }finally{
                cancelling=false;
                syncRunState();
            }
        });

        $('workshop-continue-btn')?.addEventListener('click',()=>{
            if(!comparedJob)return;
            loadJobIntoWorkshop(comparedJob);
            window.scrollTo({top:0,behavior:'smooth'});
        });

        $('workshop-compare-mp3')?.addEventListener('click',async event=>{
            const link=event.currentTarget;
            event.preventDefault();
            if(link.getAttribute('aria-disabled')==='true')return;
            const msg=$('workshop-compare-download-msg');
            link.setAttribute('aria-disabled','true');
            link.textContent='MP3 준비 중…';
            msg.textContent='MP3 파일을 준비하고 있습니다…';
            try{
                const res=await fetch(link.href);
                if(!res.ok){
                    const detail=await res.json().catch(()=>({}));
                    throw new Error(detail.error||'MP3 다운로드에 실패했습니다.');
                }
                if(res.body)await res.body.cancel();
                const a=document.createElement('a');
                a.href=link.href;a.download=link.download;
                document.body.append(a);a.click();a.remove();
                msg.textContent='MP3 다운로드를 시작했습니다.';
            }catch(error){
                msg.textContent=error.message;
            }finally{
                link.removeAttribute('aria-disabled');
                link.textContent='MP3 다운로드';
            }
        });

        clockTimer=setInterval(()=>{
            const clock=$('workshop-progress-status')?.querySelector('.dot-matrix-clock');
            if(clock&&runStartedAt)clock.textContent=formatClock(Date.now()/1000-runStartedAt);
        },1000);
    }

    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindEvents);
    else bindEvents();

    window.SongWorkshop={
        open,
        close,
        onJobsUpdated,
        isOpen:()=>isOpen
    };
})();

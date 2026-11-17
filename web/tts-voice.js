/* Qwen3-TTS built-in speaker voice generator modal for vocal reference audio. */
(()=>{
    const $=id=>document.getElementById(id);
    let pollTimer=null;
    let currentResult=null;
    let busy=false;
    let cachedItems=[];
    let activeSlotIndex=0;
    let voiceMode='custom';
    let lastStatus=null;

    function playDoneChime(){
        try{
            const Ctx=window.AudioContext||window.webkitAudioContext;
            if(!Ctx)return;
            const ctx=new Ctx();
            const now=ctx.currentTime;
            // Gentle 3-note ascending chime (C5 -> E5 -> G5)
            const notes=[523.25,659.25,783.99];
            notes.forEach((freq,idx)=>{
                const osc=ctx.createOscillator();
                const gain=ctx.createGain();
                const start=now+idx*0.09;
                osc.type='sine';
                osc.frequency.setValueAtTime(freq,start);
                gain.gain.setValueAtTime(0.0001,start);
                gain.gain.exponentialRampToValueAtTime(0.14,start+0.02);
                gain.gain.exponentialRampToValueAtTime(0.0001,start+0.42);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(start);
                osc.stop(start+0.45);
            });
            setTimeout(()=>{ctx.close().catch(()=>{});},1200);
        }catch(e){}
    }

    async function api(url,body){
        const res=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
        const data=await res.json();
        if(!res.ok)throw Error(data.error||'요청에 실패했습니다.');
        return data;
    }

    function fillOptions(selectEl,items,defaultId){
        if(!selectEl||!Array.isArray(items)||!items.length)return;
        const prev=selectEl.value||defaultId;
        selectEl.replaceChildren();
        for(const item of items){
            const opt=document.createElement('option');
            opt.value=item.id;
            opt.textContent=item.label;
            selectEl.append(opt);
        }
        if(items.some(i=>i.id===prev))selectEl.value=prev;
    }

    function syncVoiceModeUi(){
        const isDesign=voiceMode==='design';
        $('tts-mode-custom')?.classList.toggle('selected',!isDesign);
        $('tts-mode-custom')?.setAttribute('aria-selected',String(!isDesign));
        $('tts-mode-design')?.classList.toggle('selected',isDesign);
        $('tts-mode-design')?.setAttribute('aria-selected',String(isDesign));
        const spWrap=$('tts-speaker-wrap');
        if(spWrap)spWrap.hidden=isDesign;
        const instLabel=$('tts-instruct-label');
        if(instLabel)instLabel.innerHTML=isDesign
            ?'목소리 스타일 설명 <span class="field-optional">(필수)</span>'
            :'어조 · 감정 지시 <span class="field-optional">(선택)</span>';
        const instInput=$('tts-instruct');
        if(instInput)instInput.placeholder=isDesign
            ?'예: 따뜻하고 맑은 20대 한국어 여성 목소리, 차분하고 부드러운 어조'
            :'예: 따뜻하고 부드러운 음색으로 차분하게 말해줘';
    }

    function renderStatus(data){
        lastStatus=data;
        syncVoiceModeUi();
        fillOptions($('tts-speaker'),data.speakers,'Sohee');
        fillOptions($('tts-language'),data.languages,'Korean');

        const notice=$('tts-setup-notice');
        const setupTitle=$('tts-setup-title');
        const installBtn=$('tts-install-btn');
        const setupStatus=$('tts-setup-status');
        const setupElapsed=$('tts-setup-elapsed');
        const setupMotion=$('tts-setup-motion');
        const setupLog=$('tts-setup-log');
        const formEl=$('tts-form');
        const genBtn=$('tts-generate-btn');
        const resetBtn=$('tts-reset-btn');

        const isDesign=voiceMode==='design';
        const modeReady=isDesign?Boolean(data.designReady):Boolean(data.ready);
        const installingThis=Boolean(data.installing)&&(!data.installingMode||data.installingMode===voiceMode);
        const isReady=modeReady&&!installingThis;

        if(notice)notice.hidden=isReady;
        if(formEl)formEl.hidden=!isReady;
        if(genBtn)genBtn.hidden=!isReady;
        if(resetBtn)resetBtn.hidden=!isReady;
        notice?.classList.toggle('is-installing',Boolean(data.installing));
        notice?.classList.toggle('is-error',Boolean(data.error));

        if(setupTitle){
            setupTitle.textContent=isDesign
                ?'Qwen3-TTS 1.7B 음색 디자인 모델 준비가 필요합니다'
                :'Qwen3-TTS 0.6B 기본 성우 모델 준비가 필요합니다';
        }
        if(setupElapsed){
            const sec=Number(data.elapsedSeconds||0);
            if(data.installing&&sec>0){
                const m=Math.floor(sec/60),s=sec%60;
                setupElapsed.textContent=m>0?`${m}분 ${s}초 경과`:`${s}초 경과`;
            }else setupElapsed.textContent='';
        }
        if(setupMotion)setupMotion.hidden=!data.installing;
        if(setupLog){
            const lines=Array.isArray(data.logs)?data.logs:[];
            const showLog=Boolean((data.installing||data.error)&&lines.length);
            setupLog.hidden=!showLog;
            if(showLog){
                setupLog.textContent=lines.join('\n');
                setupLog.scrollTop=setupLog.scrollHeight;
            }
        }

        if(installBtn){
            installBtn.hidden=isReady;
            installBtn.disabled=Boolean(data.installing);
            installBtn.textContent=data.installing
                ?'모델 설치 진행 중…'
                :(isDesign?'Qwen3-TTS 1.7B 음색 디자인 설치 · 약 3.5GB':'Qwen3-TTS 0.6B 모델 설치 · 약 1.5GB');
        }
        if(setupStatus){
            setupStatus.textContent=data.error||data.message||(modeReady?'':(isDesign?'설치 후 텍스트 설명만으로 새로운 목소리를 디자인할 수 있습니다.':'최초 1회 설치 후 오프라인에서도 기본 성우 음성을 생성할 수 있습니다.'));
        }
        if(genBtn){
            genBtn.disabled=busy||!modeReady||Boolean(data.installing);
            if(busy){
                genBtn.innerHTML=(window.StudioIcons?window.StudioIcons('spinner','ui-icon-spin'):'')+' <span>음성을 생성하고 있습니다…</span>';
            }else{
                genBtn.textContent=data.installing?'모델 설치 중…':(!modeReady?'모델 설치 후 사용 가능':'음성 만들기');
            }
        }
    }

    async function refreshStatus(){
        try{
            const data=await api('/api/tts/status');
            renderStatus(data);
            if(data.installing){
                clearTimeout(pollTimer);
                pollTimer=setTimeout(refreshStatus,2000);
            }
        }catch(err){
            if($('tts-setup-status'))$('tts-setup-status').textContent=err.message;
        }
    }

    async function registerPreview(id,name,btnEl){
        const slotSelectIds=['reference-audio-select','reference-audio-select-2'];
        const currentVal=$(slotSelectIds[activeSlotIndex])?.value;
        if(currentVal){
            const ok=confirm(`보컬 음성 ${activeSlotIndex+1}에 이미 음성이 등록되어 있습니다. 새 음성으로 변경하시겠습니까?`);
            if(!ok)return;
        }
        if(btnEl)btnEl.disabled=true;
        try{
            const data=await api('/api/tts/register',{id,name});
            window.dispatchEvent(new CustomEvent('sorisoop:referenceadded',{detail:{item:data.item,slotIndex:activeSlotIndex}}));
            if(btnEl)btnEl.textContent='등록 완료';
            if($('tts-status'))$('tts-status').textContent=`'${data.item.name}'을(를) 보컬 음성 ${activeSlotIndex+1}(으)로 등록했습니다.`;
        }catch(err){
            if(btnEl)btnEl.disabled=false;
            if($('tts-status'))$('tts-status').textContent=err.message;
        }
    }

    function syncTtsPlayButton(card,playing){
        const btn=card?.querySelector('.player-toggle');
        if(!btn)return;
        btn.classList.toggle('is-playing',playing);
        btn.setAttribute('aria-pressed',String(playing));
        btn.setAttribute('aria-label',playing?'일시정지':'재생');
        const span=btn.querySelector('span');
        if(span&&window.StudioIcons)span.innerHTML=window.StudioIcons(playing?'pause':'play');
    }

    function buildVoiceDownloadName(item,ext){
        const raw=(item?.title||'').trim()||(item?.filename||'qwen3_voice.wav').replace(/\.[^.]+$/,'');
        const safe=raw.replace(/[\\/:*?"<>|\r\n]+/g,'_').replace(/^[.\s]+|[.\s]+$/g,'')||'voice';
        const prefixed=safe.startsWith('소리숲성우_')?safe:`소리숲성우_${safe}`;
        return `${prefixed}.${ext}`;
    }

    function syncResultPreviewMeta(item){
        if(!item)return;
        const wavEl=$('tts-save-wav');
        if(wavEl){wavEl.href=item.downloadUrl||(`/tts-audio/${item.id}.wav?download=1`);wavEl.setAttribute('download',buildVoiceDownloadName(item,'wav'));}
        const mp3El=$('tts-save-mp3');
        if(mp3El){mp3El.href=item.mp3Url||(`/tts-audio/${item.id}.mp3?download=1`);mp3El.setAttribute('download',buildVoiceDownloadName(item,'mp3'));}
        const nameInput=$('tts-result-name');
        if(nameInput)nameInput.value=item.title||item.speakerLabel||item.speaker||'';
    }

    async function renameVoiceItem(id,newTitle){
        const clean=(newTitle||'').trim();
        if(!clean)throw new Error('이름을 1~100자로 입력하세요.');
        const data=await api('/api/tts/rename',{id,title:clean});
        const updated=data.item;
        cachedItems=cachedItems.map(entry=>entry.id===id?{...entry,...updated}:entry);
        if(currentResult&&currentResult.id===id){
            currentResult={...currentResult,...updated};
            syncResultPreviewMeta(currentResult);
        }
        renderHistoryList(cachedItems);
        if($('tts-status'))$('tts-status').textContent=`음성 이름을 '${updated.title}'(으)로 변경했습니다.`;
        return updated;
    }

    function renderHistoryList(items){
        const listEl=$('tts-history-list');
        const countEl=$('tts-list-count');
        if(countEl)countEl.textContent=String(items.length);
        if(!listEl)return;
        const openIds=new Set([...listEl.querySelectorAll('details.tts-history-item[open]')].map(el=>el.dataset.id));
        window.AudioSpectrum?.release(listEl);
        listEl.replaceChildren();
        if(!items.length){
            const empty=document.createElement('p');
            empty.className='duration-help';
            empty.textContent='아직 생성된 음성이 없습니다.';
            listEl.append(empty);
            return;
        }
        for(const item of items){
            const card=document.createElement('details');
            card.className='tts-history-item tts-history-disclosure';
            card.dataset.id=item.id;
            if(openIds.has(item.id))card.open=true;

            const summary=document.createElement('summary');
            summary.className='tts-history-summary';

            const displayTitle=item.title||item.speakerLabel||item.speaker;
            const headMain=document.createElement('div');
            headMain.className='tts-history-head';
            const title=document.createElement('strong');
            title.textContent=displayTitle;
            headMain.append(title);

            const renameForm=document.createElement('form');
            renameForm.className='tts-rename-form';
            renameForm.hidden=true;
            const renameInput=document.createElement('input');
            renameInput.type='text';
            renameInput.maxLength=100;
            renameInput.value=displayTitle;
            renameInput.setAttribute('aria-label','음성 이름');
            const renameSave=document.createElement('button');
            renameSave.type='submit';
            renameSave.className='primary-button';
            renameSave.textContent='저장';
            const renameCancel=document.createElement('button');
            renameCancel.type='button';
            renameCancel.className='secondary-button';
            renameCancel.textContent='취소';
            renameCancel.onclick=()=>{renameForm.hidden=true;};
            renameForm.append(renameInput,renameSave,renameCancel);
            renameForm.onsubmit=async e=>{
                e.preventDefault();
                renameSave.disabled=true;
                try{
                    await renameVoiceItem(item.id,renameInput.value);
                }catch(err){
                    renameSave.disabled=false;
                    if($('tts-status'))$('tts-status').textContent=err.message;
                }
            };

            const summaryEditBtn=document.createElement('button');
            summaryEditBtn.type='button';
            summaryEditBtn.className='tts-summary-edit';
            summaryEditBtn.setAttribute('aria-label',`${displayTitle} 이름 변경`);
            summaryEditBtn.title='이름 변경';
            if(window.StudioIcons)summaryEditBtn.innerHTML=window.StudioIcons('edit');
            else summaryEditBtn.textContent='이름 변경';
            summaryEditBtn.onclick=e=>{
                e.preventDefault();
                e.stopPropagation();
                card.open=true;
                renameForm.hidden=!renameForm.hidden;
                if(!renameForm.hidden){
                    renameInput.value=item.title||item.speakerLabel||item.speaker;
                    renameInput.focus();
                    renameInput.select();
                }
            };

            const summaryDelBtn=document.createElement('button');
            summaryDelBtn.type='button';
            summaryDelBtn.className='tts-summary-delete';
            summaryDelBtn.setAttribute('aria-label',`${displayTitle} 음성 삭제`);
            summaryDelBtn.title='삭제';
            if(window.StudioIcons)summaryDelBtn.innerHTML=window.StudioIcons('trash');
            else summaryDelBtn.textContent='삭제';
            summaryDelBtn.onclick=async e=>{
                e.preventDefault();
                e.stopPropagation();
                summaryDelBtn.disabled=true;
                try{
                    await api('/api/tts/delete',{id:item.id});
                    cachedItems=cachedItems.filter(entry=>entry.id!==item.id);
                    await refreshList();
                }catch(err){
                    summaryDelBtn.disabled=false;
                    if($('tts-status'))$('tts-status').textContent=err.message;
                }
            };

            const chev=document.createElement('span');
            chev.className='result-chevron';
            if(window.StudioIcons)chev.innerHTML=window.StudioIcons('chevron');
            summary.append(headMain,summaryEditBtn,summaryDelBtn,chev);

            const body=document.createElement('div');
            body.className='tts-history-body';

            const text=document.createElement('p');
            text.className='tts-history-text';
            text.textContent=item.text||'';

            const playerWrap=document.createElement('div');
            playerWrap.className='tts-history-player';
            if(window.AudioSpectrum){
                playerWrap.innerHTML=window.AudioSpectrum.markup(item.audioUrl);
            }else{
                const audio=document.createElement('audio');
                audio.controls=true;audio.preload='none';audio.src=item.audioUrl;
                playerWrap.append(audio);
            }

            const actions=document.createElement('div');
            actions.className='tts-history-actions';

            const regBtn=document.createElement('button');
            regBtn.type='button';
            regBtn.className='primary-button tts-item-register';
            regBtn.textContent='보컬 등록';
            regBtn.onclick=()=>registerPreview(item.id,item.title||item.filename,regBtn);

            const saveWrap=document.createElement('div');
            saveWrap.className='tts-save-wrap';
            const saveBtn=document.createElement('button');
            saveBtn.type='button';
            saveBtn.className='save tts-item-download';
            saveBtn.textContent='음성파일 저장';
            saveBtn.setAttribute('aria-haspopup','menu');
            saveBtn.setAttribute('aria-expanded','false');

            const saveMenu=document.createElement('div');
            saveMenu.className='tts-save-menu';
            saveMenu.setAttribute('role','menu');
            saveMenu.hidden=true;

            const wavLink=document.createElement('a');
            wavLink.setAttribute('role','menuitem');
            wavLink.href=item.downloadUrl||(`/tts-audio/${item.id}.wav?download=1`);
            wavLink.setAttribute('download',buildVoiceDownloadName(item,'wav'));
            wavLink.textContent='WAV로 저장';
            wavLink.onclick=()=>{saveMenu.hidden=true;saveBtn.setAttribute('aria-expanded','false');};

            const mp3Link=document.createElement('a');
            mp3Link.setAttribute('role','menuitem');
            mp3Link.href=item.mp3Url||(`/tts-audio/${item.id}.mp3?download=1`);
            mp3Link.setAttribute('download',buildVoiceDownloadName(item,'mp3'));
            mp3Link.textContent='MP3로 저장';
            mp3Link.onclick=()=>{saveMenu.hidden=true;saveBtn.setAttribute('aria-expanded','false');};

            saveMenu.append(wavLink,mp3Link);
            saveBtn.onclick=e=>{
                e.stopPropagation();
                const nextHidden=!saveMenu.hidden;
                for(const m of document.querySelectorAll('.tts-save-menu'))m.hidden=true;
                saveMenu.hidden=nextHidden;
                saveBtn.setAttribute('aria-expanded',String(!nextHidden));
            };
            saveWrap.append(saveBtn,saveMenu);

            const delBtn=document.createElement('button');
            delBtn.type='button';
            delBtn.className='delete-result tts-item-delete';
            delBtn.textContent='삭제';
            delBtn.onclick=async()=>{
                delBtn.disabled=true;
                try{
                    await api('/api/tts/delete',{id:item.id});
                    await refreshList();
                }catch(err){
                    delBtn.disabled=false;
                    if($('tts-status'))$('tts-status').textContent=err.message;
                }
            };

            actions.append(regBtn,saveWrap,delBtn);
            body.append(renameForm,text,playerWrap,actions);
            card.append(summary,body);

            const audioEl=card.querySelector('audio');
            const toggleBtn=card.querySelector('.player-toggle');
            if(audioEl&&toggleBtn){
                toggleBtn.onclick=()=>{
                    for(const other of listEl.querySelectorAll('audio')){
                        if(other!==audioEl&&!other.paused)other.pause();
                    }
                    if(audioEl.paused){
                        window.AudioSpectrum?.prepare(audioEl);
                        audioEl.play().catch(()=>{});
                    }else audioEl.pause();
                };
                audioEl.addEventListener('play',()=>syncTtsPlayButton(card,true));
                audioEl.addEventListener('pause',()=>syncTtsPlayButton(card,false));
                audioEl.addEventListener('ended',()=>syncTtsPlayButton(card,false));
            }

            listEl.append(card);
        }
        window.AudioSpectrum?.attach(listEl);
    }

    async function refreshList(){
        try{
            const data=await api('/api/tts/list');
            cachedItems=Array.isArray(data.items)?data.items:[];
            renderHistoryList(cachedItems);
        }catch(err){
            if(cachedItems.length)renderHistoryList(cachedItems);
        }
    }

    function init(){
        const dialog=$('tts-voice-dialog');
        const openBtn=$('reference-audio-tts-btn');
        const openBtn2=$('reference-audio-tts-btn-2');
        if(!dialog||(!openBtn&&!openBtn2))return;

        const openForSlot=slotIdx=>{
            activeSlotIndex=slotIdx;
            dialog.showModal();
            refreshStatus();
            refreshList();
        };
        if(openBtn)openBtn.onclick=()=>openForSlot(0);
        if(openBtn2)openBtn2.onclick=()=>openForSlot(1);

        const close=()=>{
            clearTimeout(pollTimer);
            for(const audio of dialog.querySelectorAll('audio'))audio.pause();
            dialog.close();
        };

        $('close-tts-dialog')?.addEventListener('click',close);
        $('confirm-tts-dialog')?.addEventListener('click',close);
        $('tts-reset-btn')?.addEventListener('click',()=>{
            if($('tts-speaker'))$('tts-speaker').value='Sohee';
            if($('tts-language'))$('tts-language').value='Korean';
            if($('tts-instruct'))$('tts-instruct').value='';
            if($('tts-text'))$('tts-text').value='';
            if($('tts-status'))$('tts-status').textContent='';
            const previewHost=$('tts-preview-player');
            if(previewHost){window.AudioSpectrum?.release(previewHost);previewHost.replaceChildren();}
            if($('tts-result-wrap'))$('tts-result-wrap').hidden=true;
            currentResult=null;
            $('tts-text')?.focus();
        });
        const isOutsideDialog=e=>{
            if(e.target!==dialog||(e.clientX===0&&e.clientY===0))return false;
            const box=dialog.getBoundingClientRect();
            return e.clientX<box.left||e.clientX>box.right||e.clientY<box.top||e.clientY>box.bottom;
        };
        let downOnBackdrop=false;
        dialog.addEventListener('mousedown',e=>{downOnBackdrop=isOutsideDialog(e);});
        dialog.addEventListener('click',e=>{if(downOnBackdrop&&isOutsideDialog(e))close();downOnBackdrop=false;});

        $('tts-mode-custom')?.addEventListener('click',()=>{
            voiceMode='custom';
            if(lastStatus)renderStatus(lastStatus);else syncVoiceModeUi();
        });
        $('tts-mode-design')?.addEventListener('click',()=>{
            voiceMode='design';
            if(lastStatus)renderStatus(lastStatus);else syncVoiceModeUi();
        });

        $('tts-install-btn')?.addEventListener('click',async()=>{
            const btn=$('tts-install-btn');
            if(btn){btn.disabled=true;btn.textContent='설치를 시작하고 있습니다…';}
            if($('tts-setup-status'))$('tts-setup-status').textContent='서버에 설치를 요청하고 있습니다…';
            try{
                const data=await api('/api/tts/setup',{voiceMode});
                if(voiceMode==='design'&&data.designReady===undefined){
                    if($('tts-setup-status'))$('tts-setup-status').textContent='백엔드(app.py)가 이전 버전으로 실행 중입니다. app.py를 재시작한 뒤 다시 시도해 주세요.';
                    if(btn)btn.disabled=false;
                    return;
                }
                renderStatus(data);
                clearTimeout(pollTimer);
                pollTimer=setTimeout(refreshStatus,1500);
            }catch(err){
                if(btn)btn.disabled=false;
                if($('tts-setup-status'))$('tts-setup-status').textContent=err.message;
            }
        });

        $('tts-generate-btn')?.addEventListener('click',async()=>{
            const text=($('tts-text')?.value||'').trim();
            const instruct=($('tts-instruct')?.value||'').trim();
            if(voiceMode==='design'&&!instruct){
                if($('tts-status'))$('tts-status').textContent='새 음색 디자인에는 목소리 스타일 설명을 입력해 주세요.';
                $('tts-instruct')?.focus();
                return;
            }
            if(!text){
                if($('tts-status'))$('tts-status').textContent='생성할 대사나 가사를 입력해 주세요.';
                $('tts-text')?.focus();
                return;
            }
            busy=true;
            const genBtn=$('tts-generate-btn');
            genBtn.disabled=true;
            genBtn.innerHTML=(window.StudioIcons?window.StudioIcons('spinner','ui-icon-spin'):'')+' <span>음성을 생성하고 있습니다…</span>';
            if($('tts-status'))$('tts-status').textContent='';
            try{
                const result=await api('/api/tts/generate',{
                    voiceMode,
                    text,
                    speaker:$('tts-speaker')?.value||'Sohee',
                    language:$('tts-language')?.value||'Korean',
                    instruct,
                });
                currentResult=result;
                const previewHost=$('tts-preview-player');
                if(previewHost){
                    window.AudioSpectrum?.release(previewHost);
                    if(window.AudioSpectrum){
                        previewHost.innerHTML=window.AudioSpectrum.markup(result.audioUrl);
                        window.AudioSpectrum.attach(previewHost);
                        const audioEl=previewHost.querySelector('audio');
                        const toggleBtn=previewHost.querySelector('.player-toggle');
                        if(audioEl&&toggleBtn){
                            toggleBtn.onclick=()=>{
                                for(const other of dialog.querySelectorAll('audio')){
                                    if(other!==audioEl&&!other.paused)other.pause();
                                }
                                if(audioEl.paused){
                                    window.AudioSpectrum?.prepare(audioEl);
                                    audioEl.play().catch(()=>{});
                                }else audioEl.pause();
                            };
                            audioEl.addEventListener('play',()=>syncTtsPlayButton(previewHost,true));
                            audioEl.addEventListener('pause',()=>syncTtsPlayButton(previewHost,false));
                            audioEl.addEventListener('ended',()=>syncTtsPlayButton(previewHost,false));
                        }
                    }else{
                        previewHost.innerHTML=`<audio controls src="${result.audioUrl}"></audio>`;
                    }
                }
                const speakerSel=$('tts-speaker');
                const speakerLabel=voiceMode==='design'
                    ?('음색 디자인 · '+(instruct.length>22?instruct.slice(0,22)+'…':instruct))
                    :(speakerSel?.options?.[speakerSel.selectedIndex]?.textContent||result.speaker);
                currentResult={...result,speakerLabel};
                syncResultPreviewMeta(currentResult);
                const saveMenu=$('tts-save-menu');
                if(saveMenu)saveMenu.hidden=true;
                const wrap=$('tts-result-wrap');
                if(wrap)wrap.hidden=false;
                const regBtn=$('tts-register-btn');
                if(regBtn){regBtn.disabled=false;regBtn.textContent='보컬 음성으로 등록';}
                if($('tts-status'))$('tts-status').textContent='';
                cachedItems=[{...currentResult,text,createdAt:Date.now()/1000},...cachedItems.filter(i=>i.id!==result.id)];
                renderHistoryList(cachedItems);
                playDoneChime();
                await refreshList();
            }catch(err){
                if($('tts-status'))$('tts-status').textContent=err.message;
            }finally{
                busy=false;
                refreshStatus();
            }
        });

        $('tts-save-btn')?.addEventListener('click',e=>{
            e.stopPropagation();
            const menu=$('tts-save-menu');
            const btn=$('tts-save-btn');
            if(!menu)return;
            const open=menu.hidden;
            for(const m of document.querySelectorAll('.tts-save-menu'))m.hidden=true;
            menu.hidden=!open;
            btn?.setAttribute('aria-expanded',String(open));
        });
        for(const id of ['tts-save-wav','tts-save-mp3']){
            $(id)?.addEventListener('click',()=>{
                const menu=$('tts-save-menu');
                if(menu)menu.hidden=true;
                $('tts-save-btn')?.setAttribute('aria-expanded','false');
            });
        }
        document.addEventListener('click',()=>{
            for(const m of document.querySelectorAll('.tts-save-menu'))m.hidden=true;
            $('tts-save-btn')?.setAttribute('aria-expanded','false');
        });
        $('tts-result-rename-btn')?.addEventListener('click',async()=>{
            if(!currentResult)return;
            const btn=$('tts-result-rename-btn');
            if(btn)btn.disabled=true;
            try{
                await renameVoiceItem(currentResult.id,$('tts-result-name')?.value||'');
            }catch(err){
                if($('tts-status'))$('tts-status').textContent=err.message;
            }finally{
                if(btn)btn.disabled=false;
            }
        });
        $('tts-result-name')?.addEventListener('keydown',e=>{
            if(e.key==='Enter'){
                e.preventDefault();
                $('tts-result-rename-btn')?.click();
            }
        });
        $('tts-register-btn')?.addEventListener('click',async()=>{
            if(!currentResult)return;
            const customName=($('tts-result-name')?.value||'').trim()||currentResult.title||currentResult.filename;
            await registerPreview(currentResult.id,customName,$('tts-register-btn'));
        });
    }

    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
    else init();
})();

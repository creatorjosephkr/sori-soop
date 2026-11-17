/* UI mode (beginner / expert) and color theme (white / light-gray / dark-gray) controller. */
(()=>{
    const $=id=>document.getElementById(id);
    const THEME_KEY='sorisoop-theme';
    const MODE_KEY='sorisoop-ui-mode';
    const TIP_KEY='sorisoop-tip-dismissed';
    const THEMES=['white','light-gray','dark-gray'];
    const MODES=['beginner','expert'];

    function currentTheme(){
        const saved=localStorage.getItem(THEME_KEY);
        return THEMES.includes(saved)?saved:'white';
    }
    function currentMode(){
        const saved=localStorage.getItem(MODE_KEY);
        return MODES.includes(saved)?saved:'beginner';
    }

    function applyTheme(theme){
        if(!THEMES.includes(theme))theme='white';
        document.documentElement.dataset.theme=theme;
        try{localStorage.setItem(THEME_KEY,theme);}catch(e){}
        for(const btn of document.querySelectorAll('[data-theme-btn]')){
            const active=btn.dataset.themeBtn===theme;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }
        fetch('/api/window-theme',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme})}).catch(()=>{});
        window.dispatchEvent(new CustomEvent('sorisoop:themechange',{detail:{theme}}));
    }

    function applyUiMode(uiMode){
        if(!MODES.includes(uiMode))uiMode='beginner';
        document.documentElement.dataset.uiMode=uiMode;
        try{localStorage.setItem(MODE_KEY,uiMode);}catch(e){}
        for(const btn of document.querySelectorAll('[data-ui-mode-btn]')){
            const active=btn.dataset.uiModeBtn===uiMode;
            btn.classList.toggle('is-active',active);
            btn.setAttribute('aria-pressed',String(active));
        }
        syncBeginnerView();
        window.dispatchEvent(new CustomEvent('sorisoop:uimodechange',{detail:{uiMode}}));
    }

    function setDurationSeconds(nextSeconds){
        const secSlider=$('seconds');
        const secNum=$('seconds-number');
        const begNum=$('beginner-seconds-number');
        if(!secSlider||!secNum)return;
        const minSec=Number(secSlider.min||1);
        const maxSec=Number(secSlider.max||380);
        const clamped=Math.max(minSec,Math.min(maxSec,Math.round(Number(nextSeconds)||minSec)));
        secSlider.value=String(clamped);
        secNum.value=String(clamped);
        if(begNum)begNum.value=String(clamped);
        secSlider.dispatchEvent(new Event('input',{bubbles:true}));
        syncBeginnerView();
    }

    function stepDuration(delta){
        const secSlider=$('seconds');
        if(!secSlider)return;
        setDurationSeconds(Number(secSlider.value||0)+delta);
    }

    function syncBeginnerView(){
        const wrap=$('beginner-duration-wrap');
        if(!wrap)return;
        const activeTab=document.querySelector('.composer > .tabs button.selected')?.id||document.querySelector('.composer .tabs button.selected')?.id||'bgm';
        const isVocalSong=activeTab==='song'&&$('song-type-vocal')?.getAttribute('aria-pressed')==='true';
        const isSfx=activeTab==='sfx';
        const refCard=$('expert-reference-card');
        if(refCard)refCard.hidden=activeTab!=='song';
        const aceCard=$('expert-acestep-card');
        if(aceCard)aceCard.hidden=activeTab!=='song';
        const buttonsEl=$('beginner-duration-buttons');
        const customRow=$('beginner-duration-custom-row');
        const noteEl=$('beginner-duration-note');
        const hintEl=$('beginner-duration-range-hint');
        const secSlider=$('seconds');
        const begNum=$('beginner-seconds-number');
        const minSec=Number(secSlider?.min||(isSfx?1:10));
        const maxSec=Number(secSlider?.max||(isSfx?60:120));
        const curSec=Number(secSlider?.value||(isSfx?3:30));

        if(isVocalSong){
            wrap.hidden=true;
            if(buttonsEl)buttonsEl.hidden=true;
            if(customRow)customRow.hidden=true;
            if(noteEl)noteEl.hidden=true;
        }else{
            wrap.hidden=false;
            if(noteEl)noteEl.hidden=true;
            if(customRow)customRow.hidden=false;
            if(begNum){
                begNum.min=String(minSec);
                begNum.max=String(maxSec);
                if(document.activeElement!==begNum)begNum.value=String(curSec);
            }
            if(hintEl)hintEl.textContent=`${minSec}~${maxSec}초`;

            const downBtn=$('beginner-sec-down'),upBtn=$('beginner-sec-up');
            if(downBtn)downBtn.disabled=curSec<=minSec;
            if(upBtn)upBtn.disabled=curSec>=maxSec;

            if(buttonsEl){
                if(isSfx){
                    buttonsEl.hidden=true;
                    buttonsEl.replaceChildren();
                }else{
                    buttonsEl.hidden=false;
                    const presets=[{label:'짧게 15초',seconds:15},{label:'보통 30초',seconds:30},{label:'길게 60초',seconds:60}];
                    buttonsEl.replaceChildren();
                    for(const p of presets){
                        if(p.seconds<minSec||p.seconds>maxSec)continue;
                        const btn=document.createElement('button');
                        btn.type='button';
                        btn.className='beginner-duration-btn';
                        btn.setAttribute('aria-pressed',String(curSec===p.seconds));
                        btn.textContent=p.label;
                        btn.onclick=()=>setDurationSeconds(p.seconds);
                        buttonsEl.append(btn);
                    }
                }
            }
        }

        const expDown=$('expert-sec-down'),expUp=$('expert-sec-up');
        if(expDown)expDown.disabled=curSec<=minSec;
        if(expUp)expUp.disabled=curSec>=maxSec;

        const summaryText=$('beginner-summary-text');
        if(summaryText){
            const policy=$('policy')?.value||'auto';
            const quality=$('song-quality')?.value||'light';
            const hasRef=Boolean($('reference-audio-select')?.value||$('reference-audio-select-2')?.value);
            const customBpm=Boolean($('music-bpm')?.value);
            const isCustomized=policy!=='auto'||(activeTab==='song'&&quality==='quality')||hasRef||customBpm;
            summaryText.textContent=isCustomized
                ?'고급 · Advanced 모드에서 설정한 세부 값이 유지되고 있습니다.'
                :'내 컴퓨터 사양에 맞춘 자동 추천 설정이 적용 중입니다.';
        }
    }

    function bindBackdropClose(dialog){
        let downOnBackdrop=false;
        dialog.addEventListener('mousedown',e=>{downOnBackdrop=e.target===dialog;});
        dialog.addEventListener('click',e=>{if(downOnBackdrop&&e.target===dialog)dialog.close();downOnBackdrop=false;});
    }

    function initDialogs(){
        const sysDialog=$('system-dialog');
        const openSys=$('open-system');
        const closeSys=$('close-system');
        const confirmSys=$('confirm-system');
        if(sysDialog&&openSys){
            openSys.onclick=()=>sysDialog.showModal();
            if(closeSys)closeSys.onclick=()=>sysDialog.close();
            if(confirmSys)confirmSys.onclick=()=>sysDialog.close();
            bindBackdropClose(sysDialog);
        }

        const gptDialog=$('chatgpt-lyrics-dialog');
        const openGpt=$('open-chatgpt-lyrics');
        const closeGpt=$('close-chatgpt-lyrics');
        const confirmGpt=$('confirm-chatgpt-lyrics');
        if(gptDialog&&openGpt){
            openGpt.onclick=()=>gptDialog.showModal();
            if(closeGpt)closeGpt.onclick=()=>gptDialog.close();
            if(confirmGpt)confirmGpt.onclick=()=>gptDialog.close();
            bindBackdropClose(gptDialog);
        }

        const tipBanner=$('beginner-tip-banner');
        const dismissTip=$('dismiss-beginner-tip');
        if(tipBanner){
            try{if(localStorage.getItem(TIP_KEY)==='1')tipBanner.hidden=true;}catch(e){}
            if(dismissTip)dismissTip.onclick=()=>{
                tipBanner.hidden=true;
                try{localStorage.setItem(TIP_KEY,'1');}catch(e){}
            };
        }
    }

    function init(){
        applyTheme(currentTheme());
        applyUiMode(currentMode());

        for(const btn of document.querySelectorAll('[data-theme-btn]')){
            btn.onclick=()=>applyTheme(btn.dataset.themeBtn);
        }
        for(const btn of document.querySelectorAll('[data-ui-mode-btn]')){
            btn.onclick=()=>applyUiMode(btn.dataset.uiModeBtn);
        }
        const toExpert=$('beginner-to-expert');
        if(toExpert)toExpert.onclick=()=>applyUiMode('expert');

        const begNum=$('beginner-seconds-number');
        if(begNum){
            begNum.addEventListener('input',()=>{
                if(begNum.value==='')return;
                const val=Number(begNum.value);
                if(!Number.isFinite(val))return;
                const minSec=Number($('seconds')?.min||1);
                const maxSec=Number($('seconds')?.max||380);
                if(val>=minSec&&val<=maxSec)setDurationSeconds(val);
            });
            begNum.addEventListener('blur',()=>{
                const minSec=Number($('seconds')?.min||1);
                const maxSec=Number($('seconds')?.max||380);
                const val=Number(begNum.value);
                if(!Number.isFinite(val)||begNum.value==='')begNum.value=$('seconds')?.value||String(minSec);
                else if(val<minSec||val>maxSec)setDurationSeconds(val);
            });
        }

        $('beginner-sec-down')?.addEventListener('click',()=>stepDuration(-1));
        $('beginner-sec-up')?.addEventListener('click',()=>stepDuration(1));
        $('expert-sec-down')?.addEventListener('click',()=>stepDuration(-1));
        $('expert-sec-up')?.addEventListener('click',()=>stepDuration(1));

        // Keep beginner summary & quick duration in sync whenever underlying controls change.
        const watchIds=['seconds','seconds-number','policy','song-quality','music-bpm','reference-audio-select','reference-audio-select-2'];
        for(const id of watchIds){
            const el=$(id);
            if(el){
                el.addEventListener('input',syncBeginnerView);
                el.addEventListener('change',syncBeginnerView);
            }
        }
        for(const id of ['bgm','song','sfx','song-type-vocal','song-type-instrumental']){
            const el=$(id);
            if(el)el.addEventListener('click',()=>setTimeout(syncBeginnerView,0));
        }

        initDialogs();
        const eb=$('expert-body');
        if(eb){eb.hidden=false;$('expert-toggle')?.setAttribute('aria-expanded','true');}
        syncBeginnerView();
    }

    window.StudioModes={
        applyTheme,
        applyUiMode,
        syncBeginnerView,
        getTheme:currentTheme,
        getMode:currentMode
    };

    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
    else init();
})();

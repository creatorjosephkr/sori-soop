/* Keep first-run preparation in its own dialog; downloads continue when closed. */
(()=>{
    const panel=document.getElementById('model-setup'),message=document.getElementById('setup-status');
    const opener=document.getElementById('open-setup'),labels={bgm:'배경음악',translation:'한국어 번역',song:'노래'};
    let running=false,autoAttempted=false,timer=null,busy=false,pendingOpen=false,previousFocus=null,initial=true;
    function show(){
        if(panel.open)return;
        if(document.querySelector('dialog[open]')){pendingOpen=true;return;}
        pendingOpen=false;previousFocus=document.activeElement;panel.showModal();
    }
    function close(){pendingOpen=false;panel.close();}
    opener.onclick=()=>{show();update();};
    document.getElementById('close-setup').onclick=close;
    document.getElementById('setup-done').onclick=close;
    panel.addEventListener('close',()=>previousFocus?.focus({preventScroll:true}));
    // Escape uses the native dialog close behavior; it does not cancel installation.
    async function update(){
        if(busy)return;
        busy=true;clearTimeout(timer);
        try{
            let status=await api('/api/setup');
            const complete=Object.values(status.ready).every(Boolean);
            if(initial){initial=false;if(!complete&&status.autoSetupEnabled!==false)show();}
            if(pendingOpen)show();
            if(status.autoSetupEnabled!==false&&!complete&&!autoAttempted&&!status.active&&status.state!=='failed'&&!activeJob){
                autoAttempted=true;panel.setAttribute('aria-busy','true');
                message.textContent='첫 실행에 필요한 모델을 자동으로 준비합니다. 인터넷 연결을 유지해 주세요.';
                status=await api('/api/setup',{component:'auto'});
            }
            panel.setAttribute('aria-busy',String(status.active));
            const location=status.storage;
            document.getElementById('setup-storage').textContent=location?`모델·실행 환경 저장 위치: ${location.root}${Number.isFinite(location.freeBytes)?` · 여유 공간 ${(location.freeBytes/1024**3).toFixed(1)}GB`:''}`:'';
            for(const item of panel.querySelectorAll('[data-step]')){
                const kind=item.dataset.step,ready=status.ready[kind],current=status.active&&status.component===kind;
                item.textContent=labels[kind]+(ready?' · 준비 완료':current?' · 준비 중':' · 대기');
                item.classList.toggle('is-current',current);item.classList.toggle('is-ready',ready);
                if(current)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
            }
            for(const button of panel.querySelectorAll('[data-setup]')){
                const kind=button.dataset.setup,ready=status.ready[kind];
                button.disabled=status.active||activeJob||ready;
                button.textContent=labels[kind]+(ready?' 준비 완료':status.state==='failed'?' 다시 준비':' 준비');
            }
            const retry=document.getElementById('setup-retry');
            retry.hidden=status.state!=='failed';retry.disabled=status.active||activeJob;
            message.textContent=status.active?`자동 준비 ${status.step||1}/${status.total||1} · ${labels[status.component]} 실행 환경과 모델을 준비하고 있습니다. 인터넷 속도에 따라 수 분 이상 걸릴 수 있습니다.`:status.error||(complete?'준비를 마쳤습니다. 이제 음악을 만들어 보세요.':'첫 실행 준비를 기다리고 있습니다.');
            opener.textContent=status.active?'실행 준비 중…':complete?'실행 준비 완료':status.state==='failed'?'실행 준비 확인 필요':'실행 준비 상태';
            document.getElementById('setup-done').textContent=complete?'음악 만들기 시작':'닫고 계속 준비';
            if(status.state==='failed')document.getElementById('setup-done').textContent='닫기';
            if(running&&!status.active){await refresh();await jobs();}
            running=status.active;
        }catch(error){message.textContent=error.message;}
        finally{busy=false;timer=setTimeout(update,running||pendingOpen?2000:5000);}
    }
    panel.addEventListener('click',async event=>{
        const button=event.target.closest('[data-setup],#setup-retry');if(!button||button.disabled||busy)return;
        busy=true;autoAttempted=true;
        panel.querySelectorAll('[data-setup],#setup-retry').forEach(item=>item.disabled=true);
        try{await api('/api/setup',{component:button.dataset.setup||'all'});running=true;}
        catch(error){message.textContent=error.message;}
        finally{busy=false;update();}
    });
    setTimeout(update,700);
})();

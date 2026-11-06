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
            const activity=document.getElementById('setup-activity');
            activity.classList.toggle('is-active',status.active);
            document.getElementById('setup-activity-label').textContent=status.active?'파일을 다운로드·설치하고 있습니다':status.state==='failed'?'준비 중 문제가 발생했습니다':complete?'준비 완료':'작업 대기 중';
            const elapsed=Number.isFinite(status.elapsedSeconds)?status.elapsedSeconds:0;
            document.getElementById('setup-elapsed').textContent=status.active?`진행 시간 ${Math.floor(elapsed/60)}분 ${elapsed%60}초`:'';
            const lines=status.log?.lines||[],log=document.getElementById('setup-log');
            const content=lines.length?lines.join('\n'):'준비 작업이 시작되면 여기에 처리 내용이 표시됩니다.';
            // Preserve scroll position when someone is reading earlier entries.
            if(log.textContent!==content){
                const follow=log.scrollHeight-log.scrollTop-log.clientHeight<36;
                log.textContent=content;if(follow)log.scrollTop=log.scrollHeight;
            }
            const quiet=status.quietSeconds||0;
            document.getElementById('setup-log-freshness').textContent=lines.length?(status.active?`· ${quiet<3?'방금 갱신':quiet+'초 전 갱신'}`:'· 마지막 기록'):'';
            document.getElementById('setup-current-file').textContent=status.active&&quiet>=20?'새 로그를 기다리고 있습니다. 큰 파일을 다운로드하거나 압축을 푸는 동안 출력이 잠시 뜸할 수 있습니다.':lines.at(-1)||'현재 처리되는 파일과 설치 내용이 여기에 표시됩니다.';
            const location=status.storage;
            document.getElementById('setup-storage').textContent=location?`모델·실행 환경 저장 위치: ${location.root}${Number.isFinite(location.freeBytes)?` · 여유 공간 ${(location.freeBytes/1024**3).toFixed(1)}GB`:''}`:'';
            for(const item of panel.querySelectorAll('[data-step]')){
                const kind=item.dataset.step,ready=status.ready[kind],current=status.active&&status.component===kind;
                item.textContent=labels[kind]+(ready?' · 준비 완료':current?' · 준비 중':' · 대기');
                item.classList.toggle('is-current',current);item.classList.toggle('is-ready',ready);
                if(current)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
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
        const button=event.target.closest('#setup-retry');if(!button||button.disabled||busy)return;
        busy=true;autoAttempted=true;
        button.disabled=true;
        try{await api('/api/setup',{component:'all'});running=true;}
        catch(error){message.textContent=error.message;}
        finally{busy=false;update();}
    });
    document.getElementById('setup-log-bottom').onclick=()=>{const log=document.getElementById('setup-log');log.scrollTop=log.scrollHeight;};
    setTimeout(update,700);
})();

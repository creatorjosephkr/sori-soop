/* Prepare missing local models automatically, one component at a time. */
(()=>{
    const panel=document.getElementById('model-setup'),message=document.getElementById('setup-status');
    const labels={bgm:'배경음악',translation:'한국어 번역',song:'노래'};
    let running=false,autoAttempted=false,timer=null,busy=false;
    async function update(){
        if(busy)return;
        busy=true;clearTimeout(timer);
        try{
            let status=await api('/api/setup');
            const complete=Object.values(status.ready).every(Boolean);
            panel.hidden=complete&&!status.active;
            if(status.autoSetupEnabled!==false&&!complete&&!autoAttempted&&!status.active&&status.state!=='failed'&&!activeJob){
                autoAttempted=true;panel.hidden=false;panel.open=true;panel.setAttribute('aria-busy','true');
                message.textContent='첫 실행에 필요한 모델을 자동으로 준비합니다. 인터넷 연결을 유지해 주세요.';
                status=await api('/api/setup',{component:'auto'});
            }
            panel.setAttribute('aria-busy',String(status.active));
            for(const button of panel.querySelectorAll('[data-setup]')){
                const kind=button.dataset.setup,ready=status.ready[kind];
                button.disabled=status.active||activeJob||ready;
                button.textContent=labels[kind]+(ready?' 준비 완료':status.state==='failed'?' 다시 준비':' 준비');
            }
            const retry=document.getElementById('setup-retry');
            retry.hidden=status.state!=='failed';retry.disabled=status.active||activeJob;
            message.textContent=status.active?`자동 준비 ${status.step||1}/${status.total||1} · ${labels[status.component]} 실행 환경과 모델을 준비하고 있습니다. 인터넷 속도에 따라 수 분 이상 걸릴 수 있습니다. 앱을 종료하면 준비가 중단됩니다.`:status.error||(complete?'준비를 마쳤습니다. 원하는 기능으로 음악을 만들어 보세요.':'첫 실행 준비를 기다리고 있습니다.');
            if(running&&!status.active){await refresh();await jobs();}
            running=status.active;
        }catch(error){message.textContent=error.message;}
        finally{busy=false;timer=setTimeout(update,running?2000:5000);}
    }
    panel.addEventListener('click',async event=>{
        const button=event.target.closest('[data-setup],#setup-retry');if(!button||button.disabled||busy)return;
        busy=true;autoAttempted=true;
        panel.querySelectorAll('button').forEach(item=>item.disabled=true);
        try{await api('/api/setup',{component:button.dataset.setup||'all'});running=true;}
        catch(error){message.textContent=error.message;}
        finally{busy=false;update();}
    });
    // Show the explanation before beginning any download.
    setTimeout(update,1500);
})();

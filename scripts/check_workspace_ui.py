"""Exercise composer drafts and song result filters against the real local server."""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import webview

def main():
    with tempfile.TemporaryDirectory(prefix='sorisoop-ui-check-') as temp:
        os.environ['LOCAL_MUSIC_DATA']=temp
        os.environ['LOCAL_MUSIC_AUTO_SETUP']='0'
        import app,engine
        for number,(kind,instrumental) in enumerate([('bgm',False),('song',False),('song',True),('sfx',False)],1):
            ident=format(number,'032x')
            engine.save({'id':ident,'title':'Archived '+str(number),'status':'completed','createdAt':1,'settings':{'mode':kind,'instrumental':instrumental}})
            audio=engine.DATA/'audio';audio.mkdir(exist_ok=True)
            (audio/(ident+'.wav')).write_bytes(b'test audio')
            engine.delete_result(ident)
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        window=webview.create_window('Workspace checks',f'http://127.0.0.1:{server.server_port}',hidden=True)
        result={}
        def check():
            try:
                for _ in range(100):
                    if window.evaluate_js("typeof state!=='undefined'&&!!state&&typeof songResultType!=='undefined'"):
                        break
                    time.sleep(.1)
                result['checks']=window.evaluate_js('''(()=>{
                    const assert=(condition,label)=>{if(!condition)throw Error(label);};
                    const $=id=>document.getElementById(id);
                    document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
                    $('bgm').click();$('new-track').click();
                    $('prompt').value='BGM draft';
                    $('preset-genre').value='jazz';$('preset-genre').onchange();
                    const bgm=$('prompt').value;
                    $('song').click();assert($('prompt').value==='','song starts blank');
                    $('prompt').value='Song draft';
                    $('preset-genre').value='rock';$('preset-genre').onchange();
                    const song=$('prompt').value;
                    $('track-title').value='Vocal title';
                    $('song-type-instrumental').click();
                    assert(resultMode==='song'&&songResultType==='instrumental'&&document.getElementById('results-song-instrumental').getAttribute('aria-selected')==='true','instrumental selector opens instrumental list');
                    assert($('track-title').value===''&&$('prompt').value==='','instrumental starts with own title and prompt');
                    $('track-title').value='Instrumental title';$('prompt').value='Instrumental description';
                    $('song-type-vocal').click();
                    assert(resultMode==='song'&&songResultType==='vocal'&&document.getElementById('results-song-vocal').getAttribute('aria-selected')==='true','vocal selector opens vocal list');
                    assert($('track-title').value==='Vocal title'&&$('prompt').value===song,'vocal title and prompt restored');
                    $('song-type-instrumental').click();
                    assert(resultMode==='song'&&songResultType==='instrumental'&&document.getElementById('results-song-instrumental').getAttribute('aria-selected')==='true','instrumental selector opens instrumental list');
                    assert($('track-title').value==='Instrumental title'&&$('prompt').value==='Instrumental description','instrumental title and prompt restored');
                    $('new-track').click();$('song-type-vocal').click();
                    assert($('track-title').value==='Vocal title'&&$('prompt').value===song,'reset keeps other song type draft');

                    $('sfx').click();assert($('prompt').value==='','sfx starts blank');
                    $('prompt').value='SFX draft';
                    $('bgm').click();assert($('prompt').value===bgm&&$('preset-genre').value==='jazz','bgm text and presets restored');
                    $('song').click();assert($('prompt').value===song&&$('preset-genre').value==='rock','song text and presets restored');
                    $('new-track').click();$('bgm').click();assert($('prompt').value===bgm,'reset leaves other draft intact');
                    const fixture=(id,instrumental)=>({id,title:id,prompt:id,status:'completed',createdAt:1,settings:{mode:'song',model:'ace-step',backend:'cpu',seconds:30,...(instrumental===undefined?{}:{instrumental})}});
                    const fixtures=[fixture('legacy'),fixture('vocal',false),...Array.from({length:22},(_,index)=>fixture('instrumental-'+index,true))];
                    jobHistory=fixtures;
                    const originalApi=api;api=async(url,body)=>url==='/api/jobs'?{jobs:fixtures}:originalApi(url,body);
                    $('song').click();
                    assert(!getCurrentPageJobs().some(job=>job.settings.instrumental),'vocal list excludes instrumental');
                    assert(getCurrentPageJobs().length===2,'legacy songs remain vocal');
                    $('results-song-instrumental').click();
                    assert(getCurrentPageJobs().length===20&&getCurrentPageJobs().every(job=>job.settings.instrumental),'instrumental only');
                    renderResultPage(jobHistory.filter(matchesCurrentResults));
                    assert($('jobs').querySelectorAll('.result-disclosure').length===20,'filtered cards rendered');
                    resultPages[resultPageKey()]=2;renderResultPage(jobHistory.filter(matchesCurrentResults));
                    assert(getCurrentPageJobs().length===2,'instrumental second page');
                    $('results-song-vocal').click();assert(getCurrentPageJobs().length===2,'vocal own page');
                    $('results-song-instrumental').click();assert(resultPages[resultPageKey()]===2,'instrumental page retained');
                    jobHistory=fixtures.filter(job=>job.id!=='instrumental-20'&&job.id!=='instrumental-21');
                    renderResultPage(jobHistory.filter(matchesCurrentResults));
                    assert(resultPages[resultPageKey()]===1,'page clamped after deletion');
                    $('sfx').click();assert($('song-result-types').hidden,'song tabs hidden for sfx');
                    assert(!document.body.textContent.includes('(MR)'),'MR labels removed');
                    return 'Composer drafts, presets, result filters and pagination passed';
                })()''')
                window.evaluate_js("""(()=>{
                    window.runningJobCheck='pending';
                    const assert=(condition,label)=>{if(!condition)throw Error(label);};
                    const originalApi=api;
                    let testJobs=[];
                    api=async(url,body)=>url==='/api/jobs'?{jobs:testJobs}:originalApi(url,body);
                    (async()=>{
                        for(const instrumental of [false,true]){
                            for(const status of ['queued','running']){
                                const title=instrumental?'Instrumental in progress':'Vocal in progress';
                                testJobs=[{id:'active-song',title,prompt:'Test',status,createdAt:Date.now()/1000-10,phase:'Test generation phase',settings:{mode:'song',model:'ace-step',backend:'cpu',seconds:30,instrumental}}];
                                selectResultTab('song',instrumental?'instrumental':'vocal');
                                await jobs();
                                assert(document.getElementById('generation-status').classList.contains('is-generating'),'progress animation '+status);
                                assert(document.getElementById('generation-status').textContent.includes(title),'progress title '+status);
                                assert(document.getElementById('generation-status').textContent.includes('Test generation phase'),'progress phase');
                                assert(document.querySelector('#jobs .result-loading'),'loading spinner '+status);
                                assert(document.querySelector('#jobs .result-summary-title').textContent===title,'card title');
                                assert(!document.getElementById('cancel-generation').hidden,'cancel control');
                            }
                        }
                        testJobs=[{...testJobs[0],status:'completed',phase:''}];await jobs();
                        assert(!document.getElementById('generation-status').classList.contains('is-generating'),'progress animation ends');
                        assert(!document.querySelector('#jobs .result-loading'),'spinner ends');
                        const originalConfirm=window.confirm;
                        selectResultTab('bgm');await document.getElementById('open-trash').onclick();
                        assert(document.getElementById('trash-kind').value==='bgm'&&document.querySelectorAll('#trash-items li').length===1,'trash defaults to current list');
                        assert(document.querySelector('#trash-items .trash-item-title').textContent==='Archived 1','archived title rendered');
                        window.confirm=()=>false;await document.getElementById('empty-trash').onclick();
                        assert((await api('/api/trash')).items.length===4,'cancel preserves trash');
                        window.confirm=()=>true;await document.getElementById('empty-trash').onclick();
                        assert((await api('/api/trash')).items.length===3,'empty scoped list only');
                        assert(document.getElementById('empty-trash').disabled,'empty list disables deletion');
                        document.getElementById('trash-kind').value='all';document.getElementById('trash-kind').onchange();
                        assert(document.querySelectorAll('#trash-items li').length===3,'all trash view');
                        await document.getElementById('empty-trash').onclick();
                        assert((await api('/api/trash')).items.length===0,'empty all trash');
                        document.getElementById('close-trash').click();
                        assert(!document.getElementById('trash-dialog').open,'trash dialog closes');
                        window.confirm=originalConfirm;
                        window.runningJobCheck='passed';
                    })().catch(error=>{window.runningJobCheck='error: '+error.message;});
                })()""")
                for _ in range(100):
                    status=window.evaluate_js('window.runningJobCheck')
                    if status!='pending':break
                    time.sleep(.1)
                assert status=='passed',status
                result['runningJobs']='Progress, titles, spinners, trash listing, cancellation and scoped/all emptying passed'
            except Exception as error:
                result['error']=str(error)
            finally:
                window.destroy()
        window.events.loaded+=lambda:threading.Thread(target=check,daemon=True).start()
        try:
            webview.start(storage_path=str(Path(temp)/'webview'))
        finally:
            server.shutdown();server.server_close()
        print(result)
        assert 'error' not in result,result

if __name__=='__main__':main()

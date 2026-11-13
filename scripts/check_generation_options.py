"""Exercise optional prompt controls in the native macOS webview (no models required)."""
from pathlib import Path
import threading, json
import webview
root=Path(__file__).resolve().parent.parent
html='''<details id="negative-options-details"><summary id="negative-summary"></summary><div id="negative-options"></div><input id="negative-custom"></details><section id="tempo-options"><select id="music-bpm"><option value=""></option><option value="120"></option><option value="custom"></option></select><div id="custom-bpm-wrap"><input id="music-bpm-custom" type="number"></div><p id="bpm-preview"></p></section>'''
html+='<script>'+ (root/'web/generation-options.js').read_text()+'</script>'
window=webview.create_window('Options checks',html=html,hidden=True)
result={}
def check():
 try:
  result['checks']=window.evaluate_js('''(()=>{
    const assert=(condition,label)=>{if(!condition)throw Error(label);};
    const api=window.GenerationOptions,$=id=>document.getElementById(id);
    const choose=(value)=>{$('music-bpm').value=value;$('music-bpm').onchange();};
    const rejects=fn=>{try{fn();return false;}catch(e){return true;}};
    api.render('bgm',false);
    assert(!$('negative-options-details').open,'negative details initially collapsed');
    let checks=$('negative-options').querySelectorAll('input');
    assert(checks.length===14&&[...checks].filter(input=>input.checked).length===14,'bgm all defaults selected');
    assert(api.negative().includes('out of tune')&&api.negative().includes('vocals, singing, speech'),'bgm includes all exclusions');
    for(const input of checks){input.checked=false;input.onchange();}
    checks[13].checked=true;checks[13].onchange();
    assert(api.negative()==='vocals, singing, speech','selected exclusion only');
    api.render('song',false);
    assert($('tempo-options').hidden&&[...$('negative-options').querySelectorAll('input')].every(input=>input.checked),'all vocal defaults selected');
    assert($('negative-options').textContent.includes('불분명한 발음')&&!$('negative-options').textContent.includes('보컬·말소리'),'vocal appropriate');
    api.render('song',true);assert($('negative-options').querySelectorAll('input:checked').length===14&&api.negative().includes('vocals, singing, speech'),'song instrumental selects all defaults');if($('negative-custom')){$('negative-custom').value='heavy reverb';$('negative-custom').oninput();assert(api.negative().includes('heavy reverb'),'custom negative included');$('negative-custom').value='';$('negative-custom').oninput();}choose('120');
    assert(api.prompt('Piano')==='Piano\\nTempo: 120 BPM.','preset merged');
    assert(api.prompt('Piano 120 BPM')==='Piano 120 BPM','no duplicate bpm');
    assert(rejects(()=>api.prompt('Piano 80 BPM')),'conflicting bpm');
    choose('custom');$('music-bpm-custom').value='87';$('music-bpm-custom').oninput();
    assert(api.prompt('Piano').includes('87 BPM'),'custom bpm');
    for(const value of ['','29','301','85.5']){$('music-bpm-custom').value=value;$('music-bpm-custom').oninput();assert(rejects(()=>api.prompt('Piano')),'invalid bpm '+value);}
    $('music-bpm-custom').value='87';$('music-bpm-custom').oninput();
    assert(rejects(()=>api.prompt('a'.repeat(2000))),'combined length limit');
    assert(rejects(()=>api.prompt('')),'description required');
    api.render('bgm',false);assert(api.negative()==='vocals, singing, speech'&&$('music-bpm').value==='','mode restoration');
    api.render('sfx',false);assert($('tempo-options').hidden&&$('negative-options').querySelectorAll('input').length===11,'sfx scope');assert(api.negative().includes('music, melody')&&[...$('negative-options').querySelectorAll('input')].every(input=>input.checked),'sfx defaults on');
    api.reset();api.render('bgm',false);assert($('negative-options').querySelectorAll('input:checked').length===14&&$('music-bpm').value==='','reset restores bgm defaults');
    assert(api.negative('song').includes('gibberish')&&api.negative('sfx').includes('music, melody'),'defaults for unvisited types');
    return 'All generation option interaction checks passed';
 })()''')
 except Exception as error:result['error']=str(error)
 finally:window.destroy()
window.events.loaded+=lambda:threading.Thread(target=check,daemon=True).start()
webview.start()
print(json.dumps(result))
assert 'error' not in result

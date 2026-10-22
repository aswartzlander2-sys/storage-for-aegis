"""Audited fixes to the supplied application, applied after gateway integration.
Keep generated cloud-ui.js reproducible; do not edit the raw user reference.
"""
def patch(js):
    def replace(a,b,count=-1):
        nonlocal js
        assert a in js, a[:120]
        js=js.replace(a,b,count)
    replace("localStorage.getItem(RECENT_VIEWS_KEY)","localStorage.getItem(cloudRecentKey())")
    replace("localStorage.setItem(RECENT_VIEWS_KEY,", "localStorage.setItem(cloudRecentKey(),")
    replace("if (!bytes || bytes === 0) return '0 B';", "bytes=Number(bytes); if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';")
    replace('const i = Math.floor(Math.log(bytes) / Math.log(k));', 'const i = Math.max(0,Math.min(sizes.length-1,Math.floor(Math.log(bytes) / Math.log(k))));')
    replace('const free = Math.max(0, STORAGE_QUOTA_BYTES - used);', '''const known = STORAGE_QUOTA_BYTES > 0;
      const denominator = known ? Math.max(STORAGE_QUOTA_BYTES,used,1) : Infinity;
      const free = known ? Math.max(0, STORAGE_QUOTA_BYTES-used) : 0;
      totals={...totals};
      totals.other=(totals.other||0)+Math.max(0,used-Object.values(totals).reduce((a,b)=>a+b,0));''')
    replace('used / STORAGE_QUOTA_BYTES','used / denominator')
    replace('bytes / STORAGE_QUOTA_BYTES','bytes / denominator')
    replace("showTip(rest, 'Available', formatBytes(free), 'Available storage remaining')", "showTip(rest, 'Available', known?formatBytes(free):'Unknown', known?'Available storage remaining':'No capacity has been reported')")
    replace("desc: 'Archives and everything else'", "desc: 'Archives, other files and usage outside this listing'")
    replace('formatBytes(STORAGE_QUOTA_BYTES, 0)', "STORAGE_QUOTA_BYTES>0?formatBytes(STORAGE_QUOTA_BYTES,0):'unknown capacity'")
    replace('const { totals, used } = storageTotals(allBucketItems.length ? allBucketItems : allS3Items);', 'const { totals } = storageTotals(allBucketItems.length ? allBucketItems : allS3Items);\n      const used=cloudUsage();')
    a=js.index('    let bucketStorageBusy = false;');b=js.index('\n    // ---------------------------------------------------------------------',a)
    js=js[:a]+'''    function refreshBucketStorage() {
      allBucketItems=(cloudState?.files||[]).map(f=>({key:f.path,size:f.size,lastModified:''}));
      updateStorageWidget();
    }
''' +js[b:]
    a=js.index('    async function loadDirectory(');b=js.index('    // Parse current items',a)
    js=js[:a]+'''    let directoryGeneration=0;
    async function loadDirectory(retryCount=0) {
      const generation=++directoryGeneration,path=currentPath,epoch=cloudEpoch;
      loadingSpinner.classList.remove('hidden');
      const {data,error}=await s3List(path);
      if(generation!==directoryGeneration||path!==currentPath||epoch!==cloudEpoch)return;
      loadingSpinner.classList.add('hidden');
      if(error){
        if(retryCount<3){setTimeout(()=>{if(generation===directoryGeneration&&path===currentPath&&epoch===cloudEpoch)loadDirectory(retryCount+1)},1200);return}
        allS3Items=[];renderExplorer();showToast('Unable to load storage: '+error.message,'error');return;
      }
      allS3Items=data;renderExplorer();refreshBucketStorage();
    }

''' +js[b:]
    replace("          const { data, error } = await s3List(currentPath);\n          if (error) return;", "          const path=currentPath,source=cloudSelected,epoch=cloudEpoch;\n          const { data, error } = await s3List(path);\n          if (error || path!==currentPath || source!==cloudSelected || epoch!==cloudEpoch) return;")
    # Freeze identity across preview fetches, paint boundaries, audio work and saves.
    replace('      selectedItem = item;\n      if (!drawerOnly)', '      selectedItem = item;\n      const version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>selectedItem===item&&version===cloudPreviewGeneration&&epoch===cloudEpoch;\n      if (!drawerOnly)')
    replace('await openFilePreview(item, true);', 'await openFilePreview(item, true);\n          if(!isCurrent())return;')
    replace('const presignedUrl = await s3PresignUrl(item.key);', 'const presignedUrl = await s3PresignUrl(item.key);\n      if(!isCurrent())return;')
    replace('const textContent = await res.text();', "if(!res.ok)throw Error('File could not be loaded');\n            const textContent = await res.text();\n            if(!isCurrent())return;")
    replace('async function openExpandedPreview() {\n      if (!selectedItem) return;', 'async function openExpandedPreview() {\n      if (!selectedItem) return;\n      const item=selectedItem,version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>selectedItem===item&&version===cloudPreviewGeneration&&epoch===cloudEpoch;')
    replace('expandedExternalLink.href = await s3PresignUrl(selectedItem.key);', 'const fileUrl=await s3PresignUrl(item.key);\n      if(!isCurrent())return;\n      expandedExternalLink.href=fileUrl;')
    replace('await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));', 'await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));\n      if(!isCurrent())return;')
    replace('text = await r.text();', "if(!r.ok)throw Error('File could not be loaded');\n              text = await r.text();\n              if(!isCurrent())return;")
    replace("} catch(e) { text = '// Unable to load file content'; }", "} catch(e) { if(!isCurrent())return; showToast('Unable to load file content','error');expandedPreviewContent.textContent='Unable to load file content. Close this preview and retry.';return; }")
    replace('function closeExpandedPreview() {', 'function closeExpandedPreview() {\n      cloudPreviewGeneration++;')
    replace("btn.disabled = !dirty || (selectedItem", "btn.disabled = btn.dataset.saving==='1' || !dirty || (selectedItem")
    # A successful save must not clear edits typed while that save was in flight.
    a=js.index('    async function saveCodeToS3(');b=js.index('    // =====================================================================',a)
    block=js[a:b].replace('if (!selectedItem) return;', 'if (!selectedItem) return;\n      const item=selectedItem,version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>selectedItem===item&&version===cloudPreviewGeneration&&epoch===cloudEpoch;').replace('selectedItem.name','item.name').replace('selectedItem.key','item.key').replace('if (!btn) return;', "if (!btn||btn.dataset.saving==='1') return;\n      btn.dataset.saving='1';")
    block=block.replace("const { error } = await s3Upload(item.key, file);", "const { error } = await s3Upload(item.key, file);\n        if(!isCurrent())return;\n        const changed=(editor?editor.getValue():box.textContent)!==content;\n        if(!error&&changed){if(editor)editor._baseline=content;btn.dataset.saving='';updateSaveButtonState(btnId,true);btn.innerHTML=originalLabel;showToast('Saved. Your newer edits are still unsaved.');loadDirectory();return;}")
    block=block.replace('      btn.innerHTML = originalLabel;', "      btn.dataset.saving='';\n      btn.innerHTML = originalLabel;")
    js=js[:a]+block+js[b:]
    replace("${ext === 'html' ?", "${['html','htm'].includes(ext) ?")
    replace("if (ext === 'html') {", "if (['html','htm'].includes(ext)) {")
    a=js.index("document.getElementById('expandedInfoBtn').onclick");b=js.index('    expandedCodeModeBtn.onclick',a)
    info=js[a:b].replace('if (!selectedItem) return;', 'if (!selectedItem) return;\n      const item=selectedItem,version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>selectedItem===item&&version===cloudPreviewGeneration&&epoch===cloudEpoch;')
    info=info.replace('await openFilePreview(selectedItem, true);','await openFilePreview(item, true);\n      if(!isCurrent())return;').replace('requestAnimationFrame(() => {','requestAnimationFrame(() => {\n        if(!isCurrent())return;')
    js=js[:a]+info+js[b:]
    a=js.index('async function openFilePreview(');b=js.index('    const aceColorMode',a)
    drawer=js[a:b].replace("box.contentEditable = 'true'", "box.contentEditable = String(cloudCanWrite(item.key))")
    js=js[:a]+drawer+js[b:]
    # The fallback expanded editor obeys the same preview/edit toggle as Ace.
    a=js.index('    function renderExpandedCode(');b=js.index('    function closeExpandedPreview()',a)
    block=js[a:b].replace("box.contentEditable = 'true'", "box.contentEditable = 'false'")
    js=js[:a]+block+js[b:]
    replace("if (!expandedCodeEditor || !cloudCanWrite(selectedItem.key)) return;", "if ((!expandedCodeEditor&&!expandedCodeFallbackBox)||!selectedItem||!cloudCanWrite(selectedItem.key))return;")
    replace('expandedCodeEditor.setReadOnly(!editing);','if(expandedCodeEditor)expandedCodeEditor.setReadOnly(!editing);\n      if(expandedCodeFallbackBox)expandedCodeFallbackBox.contentEditable=String(editing);')
    # Create is not an implicit destructive overwrite of an existing filename.
    replace('await s3Upload(key, file);','await s3Upload(key, file, {createOnly:true});')
    replace('await s3Upload(folderKey, dummyFile);','await s3Upload(folderKey, dummyFile, {createOnly:true});')
    replace('if (!folderName) return;', "if(!folderName||/[\\\\/\\x00-\\x1f]/.test(folderName)||folderName.length>180){showToast('Choose a simple folder name without slashes.','error');return;}")
    # Never silently swallow a folder-list failure before destructive confirmation.
    a=js.index('          try {\n            const { data } = await s3List(it.key);');b=js.index('          paths.push(it.key);',a)
    js=js[:a]+'''          const {data,error}=await s3List(it.key);
          if(error)throw error;
          data.forEach(d=>paths.push(d.key));
''' +js[b:]
    replace('let pendingBulkDeletePaths = null;', 'let pendingBulkDeletePaths = null,pendingDeleteCount=0;')
    replace('pendingBulkDeletePaths = null;\n        deleteModalTitle', "pendingBulkDeletePaths=null;\n        pendingDeleteCount=1;\n        if(item.isFolder){try{pendingBulkDeletePaths=await collectDeletePathsForItems([item])}catch(error){showToast('Unable to list folder: '+error.message,'error');return}}\n        deleteModalTitle",1)
    replace('const paths = await collectDeletePathsForItems([...selectedItems.values()]);', "let paths;try{paths=await collectDeletePathsForItems([...selectedItems.values()])}catch(error){showToast('Unable to list selected folders: '+error.message,'error');return}")
    replace('pendingBulkDeletePaths = paths;', 'pendingBulkDeletePaths = paths;pendingDeleteCount=count;')
    replace('const count = selectedItems.size;\n        const { error }', 'const count = pendingDeleteCount || selectedItems.size;\n        const { error }')
    replace("cancelDeleteBtn.onclick = () => deleteModal.classList.add('hidden');", "cancelDeleteBtn.onclick=()=>{pendingBulkDeletePaths=null;pendingDeleteCount=0;deleteModal.classList.add('hidden')};")
    # Guard late audio/art results. Source URL namespaces also prevent MIDI cache collisions.
    replace('async function setupCustomAudioPlayer(audioUrl, fileName) {', 'async function setupCustomAudioPlayer(audioUrl, fileName) {\n      const version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>version===cloudPreviewGeneration&&epoch===cloudEpoch;')
    replace('const song=midiSongCache.get(midiKey); midiStream=', 'if(!isCurrent())return; const song=midiSongCache.get(midiKey); midiStream=')
    replace('const midiKey=(selectedItem && selectedItem.key) || fileName;', 'const midiKey=audioUrl;')
    replace('      updatePlayPauseState(started);','      if(!isCurrent())return;\n      updatePlayPauseState(started);')
    replace('audioElement.onended = async () => {', 'audioElement.onended = async () => {\n        if(!isCurrent())return;')
    replace('midiStream.offset=nextOffset;', 'if(!isCurrent())return; midiStream.offset=nextOffset;')
    replace('async function loadAudioAlbumArt(audioUrl, audioKey) {', 'async function loadAudioAlbumArt(audioUrl, audioKey) {\n      const version=cloudPreviewGeneration,epoch=cloudEpoch;\n      const isCurrent=()=>version===cloudPreviewGeneration&&epoch===cloudEpoch;')
    replace('const art = extractEmbeddedAlbumArt(buf);','if(!isCurrent())return;\n          const art = extractEmbeddedAlbumArt(buf);')
    replace('if (sib) showAudioAlbumArt(sib);','if (sib&&isCurrent()) showAudioAlbumArt(sib);')
    replace('if (isDrawer && expandedCodeEditor) {','if (isDrawer && expandedCodeEditor && !expandedCodeEditorDirty) {')
    replace('} else if (!isDrawer && codeEditor) {','} else if (!isDrawer && codeEditor && !codeEditorDirty) {')
    replace('(codeEditor && codeEditorDirty) || (expandedCodeEditor && expandedCodeEditorDirty)','codeEditorDirty || expandedCodeEditorDirty')
    replace('if (expandedCodeEditor && expandedCodeEditorDirty) {','if (expandedCodeEditorDirty) {')
    replace('if (codeEditor && codeEditorDirty) {','if (codeEditorDirty) {')
    return js

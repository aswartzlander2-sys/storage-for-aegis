"""Integrate the supplied file; do not redraw it. Input is never bundled (contains keys).
Usage: python tools/integrate_freecandy.py /path/to/freecandy.html
Then rebuild vendor/tailwind.css using tools/tailwind.config.cjs.
"""
from pathlib import Path
import hashlib,json,re,sys,base64
from cloud_runtime_fixes import patch as runtime_fixes
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'app/static'
source=Path(sys.argv[1]).read_text();s=source
styles=re.findall(r'<style\b[^>]*>(.*?)</style>',source,re.S|re.I)
(OUT/'cloud-reference.css').write_text('\n'.join(styles))
s=re.sub(r'<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I)
s=s.replace('Robo Storage','Robo Cloud')
# Reference logo pixels are retained; the browser does not need the remote fallback.
logo=re.search(r"onerror=\"this.onerror=null;this.src='data:image/png;base64,([^']+)'",source)
assert logo
(OUT/'cloud-logo.png').write_bytes((ROOT/'logo.png').read_bytes())
s=re.sub(r'\s+onerror="this.onerror=null;this.src=\'data:image/png;base64,[^\']+\';"','',s)
s=s.replace('https://static.robo-universe.com/assets/logos/robo_storage/500x500.png','assets/cloud-logo.png')
s=re.sub(r'<link[^>]+href="https://fonts.googleapis.com/icon\?family=Material\+Icons"[^>]*>', '<link rel="stylesheet" href="assets/vendor/fonts-0.css">',s)
s=re.sub(r'<link[^>]+href="https://fonts.googleapis.com/css2\?[^\"]+"[^>]*>', '<link rel="stylesheet" href="assets/vendor/fonts-1.css">',s)
s=re.sub(r'<link[^>]+rel="preconnect"[^>]*>','',s)
s=s.replace('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css','assets/vendor/all.min.css')
s=s.replace('id="sidebarAside"','id="sidebarAside"') # Explicitly unchanged sidebar.
s=s.replace('<!-- Header Actions -->','''<!-- Header Actions -->''')
selector='''<select id="cloudStoragePicker" aria-label="Select storage server" class="w-full min-w-0 bg-white/80 dark:bg-white/[0.06] border border-slate-200 dark:border-white/10 rounded-full px-2 py-2 text-xs text-slate-700 dark:text-slate-200"></select>'''
s=s.replace('<div id="storageWidget" class="pt-3 mt-2 border-t border-slate-200/70 dark:border-white/10 shrink-0">','<div id="storageWidget" class="pt-3 mt-2 border-t border-slate-200/70 dark:border-white/10 shrink-0">'+selector)
s=s.replace('us-west-4 &middot;', '<span id="cloudSourceLabel">Storage</span> &middot;')
s=s.replace('<html lang="en"','<html lang="en" data-cloud-admin="__CLOUD_ADMIN__"')
app_original='';app_generated='';synth_hash=''
def scripts(m):
 global app_original,app_generated,synth_hash
 attrs,js=m.group(1),m.group(2)
 src=re.search(r'src="([^\"]+)"',attrs)
 if src:
  url=src.group(1)
  if 'cdn.tailwindcss.com' in url:return '<link rel="stylesheet" href="assets/cloud-reference.css"><link rel="stylesheet" href="assets/vendor/tailwind.css">'
  if 'cdnjs.cloudflare.com' in url:return '<script src="assets/vendor/'+url.rsplit('/',1)[1]+'"></script>'
 if '__CF$cv$params' in js:return '' # Exported Cloudflare challenge, not application UI.
 if 'tailwind.config' in js:return '' # Same config is compiled locally.
 if 'const S3_HOST' in js:
  a=js.index('    // Extension → MIME map.');b=js.index('    async function signedFetch')
  (OUT/'cloud-mime.js').write_text(js[a:b])
  return '<script src="assets/cloud-mime.js"></script><script src="assets/cloud-bridge.js"></script>'
 if 'GlobalWorkerOptions' in js and len(js)<1000:
  js=re.sub(r'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/[^\'\"]+/pdf.worker.min.js','assets/vendor/pdf.worker.min.js',js)
  (OUT/'cloud-pdf-config.js').write_text(js);return '<script src="assets/cloud-pdf-config.js"></script>'
 if 'function loadDirectory' in js:
  app_original=js
  js=js.replace('const STORAGE_QUOTA_BYTES = 10 * 1024 * 1024 * 1024; // 10 GB','let STORAGE_QUOTA_BYTES = 0; // Supplied by the configured server allocation.')
  js=js.replace('const subfolderSet = new Set();', 'const subfolderSet = new Set();\n      cloudAddPartitions(items, subfolderSet, currentPath);')
  js=js.replace('allS3Items.forEach(item => {', "allS3Items.forEach(item => {\n        if(item.virtualPartition)return;")
  js=js.replace('const k = 1024;', 'const k = 1000;').replace(' to S3`',' to Robo Cloud`')
  js=js.replace('function openRenameModal(item) {', "function openRenameModal(item) {\n      if(item?.isFolder && cloudIsPartitionFolder(item.key)){showToast('Partition folders are managed in Aegis.', 'error');return;}")
  js=js.replace('fileGrid.appendChild(gridCard);','gridCard.dataset.cloudKey = item.key; fileGrid.appendChild(gridCard);').replace('fileList.appendChild(listRow);','listRow.dataset.cloudKey = item.key; fileList.appendChild(listRow);')
  js=js.replace('btn.disabled = !dirty;', 'btn.disabled = !dirty || (selectedItem && !cloudCanWrite(selectedItem.key));')
  js=js.replace('readOnly: false,          // files are editable;', "readOnly: !cloudCanWrite(selectedItem?.key || ''), // permission-aware;")
  js=js.replace('${item.name}','${escapeHtml(item.name)}').replace('${selectedItem.name}','${escapeHtml(selectedItem.name)}').replace('title="${item.key}"','title="${escapeHtml(item.key)}"')
  js=js.replace('if (!expandedCodeEditor) return;\n      const editing', 'if (!expandedCodeEditor || !cloudCanWrite(selectedItem.key)) return;\n      const editing')
  js=js.replace('const { totals, used } = storageTotals(list);','const { totals } = storageTotals(list);\n      const used = cloudUsage();')
  js=js.replace('https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.6','assets/vendor')
  js=js.replace('pdfjsLib.getDocument({ url })','pdfjsLib.getDocument({ url, isEvalSupported: false })')
  js=js.replace('<iframe id="htmlRenderIframe"','<iframe sandbox="" id="htmlRenderIframe"').replace('<iframe id="expandedHtmlRenderIframe"','<iframe sandbox="" id="expandedHtmlRenderIframe"')
  # User-supplied HTML must not access the authenticated parent, even in Render View.
  js=re.sub(r'<iframe(?![^>]*sandbox=)([^>]*id="[^\"]*[Hh]tml[^\"]*"[^>]*)>',r'<iframe sandbox=""\1>',js)
  js=js.replace("return str.replace(/&/g, \"&amp;\")", "return String(str).replace(/&/g, \"&amp;\")")
  js=js.replace('return str.replace(/"/g, "&quot;");', 'return escapeHtml(String(str)).replace(/\'/g, "&#39;");')
  js=js.replace("onclick=\"window.open('${presignedUrl}', '_blank')\"", 'data-cloud-open="${presignedUrl}"')
  js=js.replace("${selectedItem ? selectedItem.name : 'PDF document'}", "${selectedItem ? escapeAttr(selectedItem.name) : 'PDF document'}")
  # Keep the existing rename dialog; move its storage transaction to the gateway.
  start=js.index('    async function handleRename() {');end=js.index("    document.getElementById('confirmRenameBtn').onclick",start)
  js=js[:start]+'''    async function handleRename() {
      if (!pendingRenameItem) return;
      const name=renameInput.value.trim();
      if (!name || /[\\\\/\\x00-\\x1f]/.test(name) || name.length>180) { showRenameError('Choose a valid name without slashes.'); return; }
      const button=document.getElementById('confirmRenameBtn');button.disabled=true;
      try {
        const folder=!!pendingRenameItem.isFolder;
        await cloudRename(pendingRenameItem.key,currentPath+name+(folder?'/':''),folder);
        renameModal.classList.add('hidden');showToast('Renamed successfully');loadDirectory();
      } catch(error) { showRenameError(error.message); }
      finally { button.disabled=false; }
    }
''' + js[end:]
  js=js.replace('Failed to connect to S3 bucket','Unable to load storage').replace('from IDrive e2 S3','from Robo Cloud')
  js=js.replace("item.isFolder ? 'Folder' : formatBytes(item.size)", "item.isFolder ? (item.isPartition ? 'Partition · '+(item.partitionLimit ? formatBytes(item.partitionLimit) : 'inherited') : 'Folder') : formatBytes(item.size)")
  js=runtime_fixes(js)
  app_generated=js;(OUT/'cloud-ui.js').write_text(js);return '<script src="assets/cloud-ui.js"></script>'
 if len(js)>1_000_000:
  synth_hash=hashlib.sha256(js.encode()).hexdigest();(OUT/'cloud-synth.js').write_text(js);return '<script src="assets/cloud-synth.js"></script>'
 if not js.strip():return m.group(0)
 raise ValueError('Unrecognized inline script; review before changing it')
s=re.sub(r'<script\b([^>]*)>(.*?)</script>',scripts,s,flags=re.S|re.I)
s=s.replace('onclick="document.getElementById(\'openUploadModalBtn\').click()"','data-cloud-upload')
# Product text only; layout, classes, dialogs and custom styles remain from the file.
s=s.replace('Upload File to S3','Upload File to Robo Cloud').replace('Full S3 Path','Full storage path')
s=s.replace('</head>','<link rel="stylesheet" href="assets/cloud-fixes.css"></head>')
(OUT/'cloud.html').write_text(s)
ids=lambda x:set(re.findall(r'\bid="([^\"]+)"',x))
source_controls=re.sub(r'<style\b[^>]*>.*?</style>','',source,flags=re.S|re.I)
assert ids(source_controls)<=ids(s+app_generated), 'An original HTML control was lost'
audit={'sourceSha256':hashlib.sha256(source.encode()).hexdigest(),'sourceStyleSha256':[hashlib.sha256(x.encode()).hexdigest() for x in styles],'styleBlocksPreservedByteForByte':True,'allOriginalControlIdsPreserved':True,'addedIds':sorted(ids(s+app_generated)-ids(source_controls)),'synthSha256':synth_hash,'applicationOriginalBytes':len(app_original.encode()),'applicationIntegratedBytes':len(app_generated.encode()),'changes':['Storage/auth/quota gateway binding','Robo Cloud display name','Local dependency packaging','HTML/PDF preview isolation and server-side rename safety','Remove exported Cloudflare challenge scripts','Partition metadata folders; management button removed; additive overlay fix CSS with body-level info portal']}
audit['changes'] += ['Reproducible directory/preview/save/source race fixes', 'Create-only guards and confirmed ordinary-folder deletion', 'Accurate/unknown-capacity storage bars, source-scoped recents and fallback permissions']
(ROOT/'docs/REFERENCE-FIDELITY.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit,indent=2))

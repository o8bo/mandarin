"""Mandarin's offline conversion engine. Inputs are never modified or executed."""
from __future__ import annotations
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
from functools import lru_cache
from . import platform_support as platform

IMAGE = {'.png','.jpg','.jpeg','.webp','.tif','.tiff','.bmp','.ico','.gif'}
AUDIO = {'.mp3','.wav','.flac','.ogg','.m4a','.aac','.opus','.aiff','.wma'}
VIDEO = {'.mp4','.mkv','.mov','.webm','.avi','.m4v','.mpeg','.mpg'}
DOC = {'.doc','.docx','.odt','.rtf','.txt'}
SHEET = {'.xls','.xlsx','.ods','.csv','.tsv'}
SLIDE = {'.ppt','.pptx','.odp'}
MAX_ARCHIVE_FILES = 10000
MAX_ARCHIVE_BYTES = 2 * 1024**3

class OperationError(RuntimeError):
    pass

class Cancelled(OperationError):
    pass

def capabilities():
    result = {name: platform.discover_tool(name) for name in platform.TOOLS}
    result.update(pillow=importlib.util.find_spec('PIL') is not None,
                  pypdf=importlib.util.find_spec('pypdf') is not None,
                  archive_max_files=MAX_ARCHIVE_FILES, archive_max_bytes=MAX_ARCHIVE_BYTES)
    return result

def detect(path):
    p=Path(path)
    if p.is_dir(): return 'folder'
    ext=p.suffix.lower()
    if ext in IMAGE:return 'image'
    if ext in AUDIO:return 'audio'
    if ext in VIDEO:return 'video'
    if ext=='.pdf':return 'pdf'
    if ext in {'.srt','.vtt'}:return 'subtitle'
    if ext in DOC:return 'document'
    if ext in SHEET:return 'spreadsheet'
    if ext in SLIDE:return 'presentation'
    if ext in {'.zip','.tar','.gz','.tgz','.bz2','.xz'}:return 'archive'
    return 'unknown'

def param(key,label,typ,default,choices=None):
    d={'key':key,'label':label,'type':typ,'default':default}
    if choices is not None:d['choices']=choices
    return d

@lru_cache(maxsize=8)
def _ffmpeg_encoders(path, modified):
    if not path: return frozenset()
    try:
        result = subprocess.run([path,'-hide_banner','-encoders'],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.WINDOWS else 0)
        return frozenset(re.findall(r'^\s*[VAS][A-Z.]{5}\s+(\S+)', result.stdout.decode('utf-8','replace'), re.M)) if result.returncode == 0 else frozenset()
    except (OSError, subprocess.SubprocessError): return frozenset()

def media_supported(fmt, path):
    if not path: return False
    try: encoders=_ffmpeg_encoders(path,Path(path).stat().st_mtime_ns)
    except OSError:return False
    required={'mp3':{'libmp3lame'},'wav':{'pcm_s16le'},'flac':{'flac'},'ogg':{'libvorbis'},
        'm4a':{'aac'},'opus':{'libopus'},'aiff':{'pcm_s16be'},'mp4':{'libx264','aac'},
        'mov':{'libx264','aac'},'mkv':{'libx264','aac'},'webm':{'libvpx-vp9','libopus'},'gif':{'gif'}}
    return fmt in required and required[fmt] <= encoders

def image_supported(fmt):
    try:
        from PIL import Image
        Image.init()
        return fmt.upper() in Image.SAVE
    except ImportError:return False

def get_operations(paths,mode='convert'):
    cats={detect(p) for p in paths}; c=capabilities(); out=[]
    if not paths:return out
    def add(id,label,detail,params=(),dep=True,reason=''):
        out.append({'id':id,'label':label,'detail':detail,'params':list(params),
                    'available':bool(dep),'reason':reason if not dep else ''})
    if cats=={'image'}:
        if mode=='convert':
            for fmt in ['png','jpeg','webp','tiff','bmp','ico','gif','pdf']:
                if all({'.jpg':'jpeg','.tif':'tiff'}.get(Path(p).suffix.lower(),Path(p).suffix.lower().lstrip('.'))==fmt for p in paths):continue
                add('image:'+fmt,fmt.upper(),'Convert each image; animated inputs use their first frame.',dep=c['pillow'] and image_supported(fmt),reason='Pillow writer for this format is unavailable.')
        else:
            common=[param('quality','Quality (1–100)','int',85)]
            for op,label,params in [('resize','Resize',[param('width','Maximum width','int',1920),param('height','Maximum height','int',1080)]),('rotate','Rotate',[param('degrees','Degrees counterclockwise','int',90)]),('crop','Crop',[param('left','Left','int',0),param('top','Top','int',0),param('width','Width','int',100),param('height','Height','int',100)]),('grayscale','Grayscale',[]),('compress','Compress',common),('strip_metadata','Remove metadata',[])]:
                add('image:'+op,label,'Save a new image beside the original.',params,c['pillow'],'Pillow is not installed.')
    if cats <= {'audio','video'}:
        if mode=='convert':
            formats=['mp3','wav','flac','ogg','m4a','opus','aiff']+(['mp4','webm','mov','mkv','gif'] if 'video' in cats else [])
            for fmt in formats:
                if all(Path(p).suffix.lower()=='.'+fmt for p in paths):continue
                add('media:'+fmt,fmt.upper(),'Encode locally with FFmpeg.',dep=media_supported(fmt,c['ffmpeg']),reason='FFmpeg or a required encoder is unavailable.')
        else:
            add('media:trim','Trim','Times in seconds; audio saves WAV and video saves MP4.',[param('start','Start seconds','float',0),param('duration','Duration seconds','float',10)],media_supported('mp4' if 'video' in cats else 'wav',c['ffmpeg']),'Required FFmpeg encoders are unavailable.')
            if cats=={'audio'}:add('media:normalize','Normalize audio','Loudness normalization; saves a new WAV file.',dep=media_supported('wav',c['ffmpeg']),reason='Required FFmpeg encoders are unavailable.')
            if cats=={'video'}:
                for op,label in [('compress','Compress video'),('remove_audio','Remove audio'),('extract_audio','Extract audio')]:add('media:'+op,label,'Save a new file using FFmpeg.',dep=bool(c['ffmpeg']) if op=='remove_audio' else media_supported('mp3' if op=='extract_audio' else 'mp4',c['ffmpeg']),reason='FFmpeg or a required encoder is unavailable.')
    if cats=={'subtitle'} and mode=='convert':
        for fmt in ['srt','vtt','txt']:add('subtitle:'+fmt,fmt.upper(),'Preserve cue timings; TXT contains cue text only.')
    if mode=='convert' and len(cats)==1 and cats <= {'document','spreadsheet','presentation'}:
        formats={'document':['pdf','docx','odt','txt'],'spreadsheet':['pdf','xlsx','ods','csv','tsv'],'presentation':['pdf','pptx','odp']}[next(iter(cats))]
        for fmt in formats:
            if all(Path(p).suffix.lower()=='.'+fmt for p in paths):continue
            add('document:'+fmt,fmt.upper(),'Convert through an isolated LibreOffice profile.',dep=c['libreoffice'],reason='LibreOffice is not installed.')
    if cats=={'pdf'} and mode=='convert':
        add('pdf:text','TXT — extract text','Extract digital PDF text; OCR is not included.',dep=c['pypdf'] or c['pdftotext'],reason='Install pypdf or Poppler.')
        for fmt in ['png','jpeg']:add('pdf:'+fmt,fmt.upper()+' — one image per page','Rasterize every PDF page at 150 DPI.',dep=c['pdftoppm'],reason='Poppler pdftoppm is not installed.')
    if cats=={'pdf'} and mode=='tools':
        add('pdf:merge','Merge PDFs','Merge selected PDFs in the displayed order.',dep=c['pypdf'] and len(paths)>1,reason='Select at least two PDFs; pypdf is required.')
        add('pdf:split','Split PDF','One output PDF per page.',dep=c['pypdf'],reason='pypdf is not installed.')
        add('pdf:rotate','Rotate PDF','Rotate every page.',[param('degrees','Clockwise degrees','choice','90',['90','180','270'])],c['pypdf'],'pypdf is not installed.')
        add('pdf:text','Extract text','Extract text from digital PDFs; OCR is not included.',dep=c['pypdf'] or c['pdftotext'],reason='Install pypdf or Poppler.')
        add('pdf:images','Extract embedded images','Export embedded images using Poppler.',dep=c['pdfimages'],reason='Poppler pdfimages is not installed.')
    if mode=='tools':
        if cats=={'archive'}:add('archive:extract','Extract archive','Safe ZIP/TAR extraction into a new folder (2 GiB, 10,000 entries maximum).')
        for fmt in ['zip','tar','tar.gz']:add('archive:'+fmt,'Create '+fmt.upper(),'Archive selected files and folders; symbolic links are rejected.')
    return out

def _check(cancelled):
    if cancelled is not None and cancelled.is_set():raise Cancelled('Operation cancelled.')

def _process(args,cancelled=None,env=None):
    try:
        platform.run_process(args, cancelled, env)
    except InterruptedError as error:
        raise Cancelled(str(error)) from error
    except (OSError, RuntimeError) as error:
        raise OperationError(str(error)) from error

def _publish(src,parent,name):
    try:
        return platform.publish_file(src,parent,name)
    except (OSError, RuntimeError, ValueError) as error:
        raise OperationError(str(error)) from error

def _folder_publish(src,parent,name):
    try:
        return platform.publish_directory(src,parent,name)
    except (OSError, RuntimeError, ValueError) as error:
        raise OperationError(str(error)) from error

def _image(path,dest,op,opts):
    from PIL import Image,ImageOps
    with Image.open(path) as original:
        im=ImageOps.exif_transpose(original).copy()
    fmt=op.upper() if op in ['png','jpeg','webp','tiff','bmp','ico','gif','pdf'] else (Image.registered_extensions().get(path.suffix.lower()) or 'PNG')
    if op=='resize':
        size=(int(opts.get('width',1920)),int(opts.get('height',1080)))
        if min(size)<=0:raise OperationError('Image dimensions must be positive.')
        im.thumbnail(size,Image.Resampling.LANCZOS)
    elif op=='rotate':im=im.rotate(float(opts.get('degrees',90)),expand=True)
    elif op=='grayscale':im=ImageOps.grayscale(im)
    elif op=='crop':
        left,top=int(opts.get('left',0)),int(opts.get('top',0));w,h=int(opts.get('width',100)),int(opts.get('height',100))
        if min(left,top)<0 or min(w,h)<=0 or left+w>im.width or top+h>im.height:raise OperationError('Crop rectangle must fit inside the image.')
        im=im.crop((left,top,left+w,top+h))
    if fmt in {'JPEG','PDF','BMP'}:
        if 'A' in im.getbands() or 'transparency' in im.info:
            rgba=im.convert('RGBA');flat=Image.new('RGB',im.size,'white');flat.paste(rgba,mask=rgba.getchannel('A'));im=flat
        else:im=im.convert('RGB')
    quality=int(opts.get('quality',85))
    if not 1<=quality<=100:raise OperationError('Quality must be from 1 to 100.')
    im.info.clear();im.save(dest,format=fmt,quality=quality,optimize=True)

def _subtitle(path,dest,op):
    text=path.read_text(encoding='utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    cues=[]
    timing=re.compile(r'^(\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+(\d{2}:)?\d{2}:\d{2}[.,]\d{3}')
    for block in re.split(r'\n\s*\n',text):
        lines=block.strip().splitlines()
        for i,line in enumerate(lines):
            if timing.match(line):
                t=line.split('-->');a=t[0].strip().replace(',','.');b=t[1].strip().split()[0].replace(',','.')
                if len(a.split(':'))==2:a='00:'+a
                if len(b.split(':'))==2:b='00:'+b
                cues.append((a,b,'\n'.join(lines[i+1:])));break
    if not cues:raise OperationError('No valid SRT/WebVTT cues were found.')
    if op=='txt':result='\n\n'.join(c[2] for c in cues)+'\n'
    else:
        rows=[]
        for i,(a,b,body) in enumerate(cues,1):
            if op=='srt':a=a.replace('.',',');b=b.replace('.',',')
            rows.append((str(i)+'\n' if op=='srt' else '')+a+' --> '+b+'\n'+body)
        result=('WEBVTT\n\n' if op=='vtt' else '')+'\n\n'.join(rows)+'\n'
    dest.write_text(result,encoding='utf-8')

def _safe_member(name,base):
    # Reject Windows paths too, even though extraction runs on Linux.
    if '\\' in name or re.match(r'^[A-Za-z]:',name):raise OperationError('Unsafe archive member path: '+name)
    p=Path(name)
    if p.is_absolute() or '..' in p.parts:raise OperationError('Unsafe archive member path: '+name)
    for component in p.parts:
        try: platform.safe_name(component)
        except ValueError as error: raise OperationError(str(error)) from error
    target=(base/p).resolve()
    if target!=base.resolve() and base.resolve() not in target.parents:raise OperationError('Archive path escapes the destination.')
    return target

def _extract(path,dest,cancelled):
    count=0;size=0;members=[]
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for m in z.infolist():
                count+=1;size+=m.file_size;target=_safe_member(m.filename,dest)
                if stat.S_ISLNK(m.external_attr>>16):raise OperationError('Archive symbolic links are not allowed.')
                if count>MAX_ARCHIVE_FILES or size>MAX_ARCHIVE_BYTES:raise OperationError('Archive exceeds the extraction safety limit.')
                members.append((m,target))
            for m,target in members:
                _check(cancelled)
                if m.is_dir():target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(m) as src, target.open('xb') as out:_bounded_copy(src,out,m.file_size,cancelled)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as tar:
            for m in tar:
                count+=1;size+=m.size;target=_safe_member(m.name,dest)
                if not (m.isfile() or m.isdir()):raise OperationError('Archive links and special files are not allowed.')
                if count>MAX_ARCHIVE_FILES or size>MAX_ARCHIVE_BYTES:raise OperationError('Archive exceeds the extraction safety limit.')
                members.append((m,target))
            for m,target in members:
                _check(cancelled)
                if m.isdir():target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with tar.extractfile(m) as src,target.open('xb') as out:_bounded_copy(src,out,m.size,cancelled)
    else:raise OperationError('Unsupported archive. ZIP and TAR variants are supported.')

def _bounded_copy(src,out,expected,cancelled):
    total=0
    while True:
        _check(cancelled);block=src.read(1024*1024)
        if not block:break
        total+=len(block)
        if total>expected or total>MAX_ARCHIVE_BYTES:raise OperationError('Archive entry exceeded its declared size.')
        out.write(block)

def _archive(paths,dest,fmt,cancelled):
    entries=[];used=set()
    for path in paths:
        name=path.name
        if name in used:raise OperationError('Selected archive inputs have duplicate names.')
        used.add(name)
        candidates=[path]+(list(path.rglob('*')) if path.is_dir() else [])
        for item in candidates:
            _check(cancelled)
            if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()) or not (item.is_file() or item.is_dir()):raise OperationError('Symbolic links and special files cannot be archived.')
            entries.append((item,str(Path(name)/item.relative_to(path)) if item!=path else name))
    if fmt=='zip':
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            for item,name in entries:_check(cancelled);z.write(item,name)
    else:
        with tarfile.open(dest,'w:gz' if fmt=='tar.gz' else 'w') as tar:
            for item,name in entries:_check(cancelled);tar.add(item,arcname=name,recursive=False)


def run_operation(operation_id,paths,options=None,progress=None,cancelled=None):
    opts=options or {};paths=[Path(p).expanduser().absolute() for p in paths]
    if not paths:raise OperationError('Select at least one file.')
    for p in paths:
        if not p.exists():raise OperationError('Input does not exist: '+str(p))
    offered=get_operations(paths,'tools')+get_operations(paths,'convert')
    spec=next((x for x in offered if x['id']==operation_id),None)
    if not spec:raise OperationError('This operation does not support the selected files.')
    if not spec['available']:raise OperationError(spec['reason'])
    group,op=operation_id.split(':',1);outputs=[];warnings=[]
    collective=operation_id in {'pdf:merge','archive:zip','archive:tar','archive:tar.gz'}
    batches=[paths] if collective else [[p] for p in paths]
    try:
        return _run_batches(group,op,batches,opts,outputs,warnings,progress,cancelled)
    except Exception as error:
        error.partial_result={'outputs':list(outputs),'warnings':list(warnings)}
        raise

def _run_batches(group,op,batches,opts,outputs,warnings,progress,cancelled):
    for i,batch in enumerate(batches):
        _check(cancelled);p=batch[0];parent=Path(opts.get('output_dir') or p.parent).expanduser().absolute();parent.mkdir(parents=True,exist_ok=True)
        if group=='archive' and op!='extract':
            for source in batch:
                if source.is_dir() and (parent==source or source in parent.parents):
                    raise OperationError('Choose an output folder outside the folders being archived.')
        if progress:progress(i,len(batches),'Processing '+p.name)
        with tempfile.TemporaryDirectory(prefix='.mandarin-',dir=parent) as scratch:
            work=Path(scratch);produced=[];folder=False
            if group=='image':
                ext=op if op in ['png','jpeg','webp','tiff','bmp','ico','gif','pdf'] else p.suffix.lstrip('.')
                dest=work/(p.stem+'-'+op+'.'+ext);_image(p,dest,op,opts);produced=[dest]
                if p.suffix.lower()=='.gif':warnings.append('Animated image conversion uses the first frame: '+p.name)
            elif group=='subtitle':
                dest=work/(p.stem+'.'+op);_subtitle(p,dest,op);produced=[dest]
            elif group=='media':
                ext=op if op in ['mp3','wav','flac','ogg','m4a','opus','aiff','mp4','webm','mov','mkv','gif'] else ('mp3' if op=='extract_audio' else p.suffix.lstrip('.'))
                if op in {'trim','normalize'}:ext='mp4' if detect(p)=='video' else 'wav'
                if op=='compress':ext='mp4'
                dest=work/(p.stem+'-'+op+'.'+ext);args=[capabilities()['ffmpeg'],'-nostdin','-hide_banner','-loglevel','error','-y','-protocol_whitelist','file,pipe']
                if op=='trim':
                    start=float(opts.get('start',0));duration=float(opts.get('duration',10))
                    if not math.isfinite(start) or not math.isfinite(duration) or start<0 or duration<=0:raise OperationError('Trim times must be finite; duration must be positive.')
                    args+=['-ss',str(start),'-i',p,'-t',str(duration)]
                else:args+=['-i',p]
                args+=['-map_metadata','-1']
                if '.'+ext in AUDIO:args+=['-vn']
                if op=='normalize':args+=['-af','loudnorm=I=-16:TP=-1.5:LRA=11']
                if op=='remove_audio':args+=['-an','-c:v','copy']
                if op!='remove_audio' and (op=='compress' or ext in {'mp4','mov','mkv'}):args+=['-c:v','libx264','-crf','28' if op=='compress' else '23','-preset','medium','-pix_fmt','yuv420p']
                if op!='remove_audio' and ext in {'mp4','mov','mkv'}:args+=['-c:a','aac']
                if ext=='m4a':args+=['-c:a','aac','-b:a','192k']
                if ext=='opus':args+=['-c:a','libopus']
                if ext=='aiff':args+=['-c:a','pcm_s16be']
                if ext=='mp3':args+=['-c:a','libmp3lame','-q:a','2']
                if ext=='webm' and op!='remove_audio':args+=['-c:v','libvpx-vp9','-crf','32','-b:v','0','-c:a','libopus']
                if ext=='gif':args+=['-vf','fps=12,scale=640:-1:flags=lanczos']
                args+=[dest];_process(args,cancelled);produced=[dest]
            elif group=='document':
                profile=work/'profile';profile.mkdir();user=profile/'user';user.mkdir()
                (user/'registrymodifications.xcu').write_text('<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>',encoding='utf-8')
                _process([capabilities()['libreoffice'],'-env:UserInstallation='+profile.as_uri(),'--headless','--nologo','--nodefault','--nofirststartwizard','--convert-to',('csv:Text - txt - csv (StarCalc):9,34,76,1' if op=='tsv' else op),'--outdir',work,p],cancelled,env=dict(os.environ) if platform.WINDOWS else dict(os.environ,GSETTINGS_BACKEND='memory',SAL_USE_VCLPLUGIN='svp',XDG_RUNTIME_DIR=str(work),XDG_CONFIG_HOME=str(profile)))
                if op=='tsv':
                    for source in work.glob('*.csv'):source.rename(source.with_suffix('.tsv'))
                produced=[f for f in work.iterdir() if f.is_file() and f.suffix.lower()=='.'+op]
                if not produced:raise OperationError('LibreOffice did not produce an output; the input or target format may be unsupported.')
            elif group=='pdf':
                if op in {'png','jpeg'}:
                    _process([capabilities()['pdftoppm'],'-'+op,'-r','150',p,work/(p.stem+'-page')],cancelled)
                    produced=sorted(work.glob('*.'+('jpg' if op=='jpeg' else 'png')))
                    if not produced:raise OperationError('PDF rasterizer did not produce any pages.')
                elif op=='images':
                    d=work/'images';d.mkdir();_process([capabilities()['pdfimages'],'-all',p,d/'image'],cancelled)
                    if not list(d.iterdir()):raise OperationError('No embedded images were found in this PDF.')
                    produced=[d];folder=True
                elif op=='text' and not capabilities()['pypdf']:
                    dest=work/(p.stem+'.txt');_process([capabilities()['pdftotext'],p,dest],cancelled);produced=[dest]
                else:
                    from pypdf import PdfReader,PdfWriter
                    if op=='merge':
                        writer=PdfWriter()
                        for source in batch:_check(cancelled);writer.append(str(source))
                        dest=work/'Merged.pdf'
                        with dest.open('wb') as f:writer.write(f)
                        produced=[dest]
                    else:
                        reader=PdfReader(p)
                        if reader.is_encrypted:raise OperationError('Encrypted PDFs must be unlocked before conversion.')
                        if op=='text':
                            dest=work/(p.stem+'.txt');dest.write_text('\n\n'.join(page.extract_text() or '' for page in reader.pages),encoding='utf-8');produced=[dest]
                            warnings.append('Text extraction does not perform OCR: '+p.name)
                        elif op=='rotate':
                            deg=int(opts.get('degrees',90))
                            if deg not in {90,180,270}:raise OperationError('PDF rotation must be 90, 180, or 270 degrees.')
                            writer=PdfWriter()
                            for page in reader.pages:writer.add_page(page.rotate(deg))
                            dest=work/(p.stem+'-rotated.pdf')
                            with dest.open('wb') as f:writer.write(f)
                            produced=[dest]
                        elif op=='split':
                            for n,page in enumerate(reader.pages,1):
                                _check(cancelled);writer=PdfWriter();writer.add_page(page);dest=work/(p.stem+f'-page-{n:03}.pdf')
                                with dest.open('wb') as f:writer.write(f)
                                produced.append(dest)
            elif group=='archive':
                if op=='extract':
                    d=work/'extracted';d.mkdir();_extract(p,d,cancelled);produced=[d];folder=True
                else:
                    dest=work/(p.stem+'-archive.'+op);_archive(batch,dest,op,cancelled);produced=[dest]
            _check(cancelled)
            for dest in produced:
                if folder:outputs.append(_folder_publish(dest,parent,p.stem+'-'+op))
                else:
                    if not dest.exists() or dest.stat().st_size==0:raise OperationError('Converter produced an empty output.')
                    outputs.append(_publish(dest,parent,dest.name))
        if progress:progress(i+1,len(batches),'Completed '+p.name)
    return {'outputs':outputs,'warnings':warnings}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('operation');parser.add_argument('paths',nargs='+');parser.add_argument('--output-dir')
    args=parser.parse_args()
    print(json.dumps(run_operation(args.operation,args.paths,{'output_dir':args.output_dir}),ensure_ascii=False,indent=2))

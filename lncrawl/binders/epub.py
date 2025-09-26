import os
import re
import uuid
import zipfile
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
from xml.dom.minidom import parseString, Document

# Absolute path to the assets directory
ASSETS_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'epub')

class EbookBuilder:
    def __init__(self):
        self.toc = []

    def build(self, title, author, cover_url, chapters, output_path):
        """
        Builds the EPUB file.
        """
        self.novel_title = title
        self.novel_author = author
        self.chapters = chapters
        
        # Create a temporary directory for book assets
        self.temp_dir = os.path.join('temp_epub_build', str(uuid.uuid4()))
        self.oebps_dir = os.path.join(self.temp_dir, 'OEBPS')
        self.text_dir = os.path.join(self.oebps_dir, 'Text')
        self.image_dir = os.path.join(self.oebps_dir, 'Images')
        self.meta_inf_dir = os.path.join(self.temp_dir, 'META-INF')

        os.makedirs(self.text_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.meta_inf_dir, exist_ok=True)

        self._create_mimetype()
        self._create_container_xml()
        self._write_chapters()
        self._write_stylesheet()
        cover_image_path = self._download_cover(cover_url)
        
        self._create_content_opf(cover_image_path)
        self._create_toc_ncx()
        
        # Create the final ZIP file (EPUB)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # Write mimetype file first and uncompressed
            epub_zip.write(os.path.join(self.temp_dir, 'mimetype'), 'mimetype', compress_type=zipfile.ZIP_STORED)
            # Write the rest of the files
            for root, _, files in os.walk(self.temp_dir):
                for file in files:
                    if file == 'mimetype':
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.temp_dir)
                    epub_zip.write(file_path, arcname)

        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_mimetype(self):
        with open(os.path.join(self.temp_dir, 'mimetype'), 'w') as f:
            f.write('application/epub+zip')

    def _create_container_xml(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
        with open(os.path.join(self.meta_inf_dir, 'container.xml'), 'w') as f:
            f.write(content)

    def _write_chapters(self):
        with open(os.path.join(ASSETS_PATH, 'chapter.xhtml'), 'r', encoding='utf-8') as f:
            template = f.read()

        for i, chapter in enumerate(self.chapters):
            filename = f"chapter_{i+1:04d}.xhtml"
            chapter['filename'] = filename
            
            # Simple template replacement
            content = template.replace('{{title}}', chapter.get('title', ''))
            content = content.replace('{{{body}}}', chapter.get('body', ''))

            with open(os.path.join(self.text_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.toc.append({'id': f"chap_{i+1}", 'filename': filename, 'title': chapter.get('title', '')})

    def _write_stylesheet(self):
        import shutil
        shutil.copy(os.path.join(ASSETS_PATH, 'style.css'), self.oebps_dir)

    def _download_cover(self, cover_url):
        if not cover_url:
            return None
        try:
            response = requests.get(cover_url, stream=True, timeout=30)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content))
            
            # Convert to JPG for compatibility
            cover_filename = "cover.jpg"
            save_path = os.path.join(self.image_dir, cover_filename)
            
            if image.mode in ("RGBA", "P"):
                 image = image.convert("RGB")
            
            image.save(save_path, "JPEG")
            return cover_filename
        except Exception as e:
            print(f"Failed to download or process cover image: {e}")
            return None

    def _create_content_opf(self, cover_filename):
        doc = Document()
        package = doc.createElement('package')
        package.setAttribute('xmlns', 'http://www.idpf.org/2007/opf')
        package.setAttribute('unique-identifier', 'bookid')
        package.setAttribute('version', '2.0')
        doc.appendChild(package)

        # METADATA
        metadata = doc.createElement('metadata')
        metadata.setAttribute('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        metadata.setAttribute('xmlns:opf', 'http://www.idpf.org/2007/opf')
        package.appendChild(metadata)
        
        # -- Title, Author, Date, ID
        title_el = doc.createElement('dc:title')
        title_el.appendChild(doc.createTextNode(self.novel_title))
        metadata.appendChild(title_el)
        
        creator_el = doc.createElement('dc:creator')
        creator_el.appendChild(doc.createTextNode(self.novel_author))
        metadata.appendChild(creator_el)

        date_el = doc.createElement('dc:date')
        date_el.appendChild(doc.createTextNode(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')))
        metadata.appendChild(date_el)

        id_el = doc.createElement('dc:identifier')
        id_el.setAttribute('id', 'bookid')
        id_el.appendChild(doc.createTextNode(str(uuid.uuid4())))
        metadata.appendChild(id_el)
        
        # -- Cover
        if cover_filename:
            meta_cover = doc.createElement('meta')
            meta_cover.setAttribute('name', 'cover')
            meta_cover.setAttribute('content', 'cover-image')
            metadata.appendChild(meta_cover)

        # MANIFEST
        manifest = doc.createElement('manifest')
        package.appendChild(manifest)
        
        # -- Manifest items
        self._add_manifest_item(doc, manifest, 'ncx', 'toc.ncx', 'application/x-dtbncx+xml')
        self._add_manifest_item(doc, manifest, 'style', 'style.css', 'text/css')
        if cover_filename:
            self._add_manifest_item(doc, manifest, 'cover-image', f'Images/{cover_filename}', 'image/jpeg')
            self._add_manifest_item(doc, manifest, 'cover-page', 'Text/cover.xhtml', 'application/xhtml+xml')
            with open(os.path.join(ASSETS_PATH, 'cover.xhtml'), 'r') as f:
                cover_xhtml = f.read().replace('{{cover_path}}', f'../Images/{cover_filename}')
            with open(os.path.join(self.text_dir, 'cover.xhtml'), 'w') as f:
                f.write(cover_xhtml)
        
        for chapter_info in self.toc:
            self._add_manifest_item(doc, manifest, chapter_info['id'], f"Text/{chapter_info['filename']}", 'application/xhtml+xml')

        # SPINE
        spine = doc.createElement('spine')
        spine.setAttribute('toc', 'ncx')
        package.appendChild(spine)
        
        if cover_filename:
            self._add_spine_item(doc, spine, 'cover-page')
            
        for chapter_info in self.toc:
            self._add_spine_item(doc, spine, chapter_info['id'])

        # GUIDE
        if cover_filename:
            guide = doc.createElement('guide')
            package.appendChild(guide)
            ref = doc.createElement('reference')
            ref.setAttribute('type', 'cover')
            ref.setAttribute('title', 'Cover')
            ref.setAttribute('href', 'Text/cover.xhtml')
            guide.appendChild(ref)
            
        with open(os.path.join(self.oebps_dir, 'content.opf'), 'w', encoding='utf-8') as f:
            f.write(doc.toprettyxml(indent='  '))

    def _add_manifest_item(self, doc, manifest, item_id, href, media_type):
        item = doc.createElement('item')
        item.setAttribute('id', item_id)
        item.setAttribute('href', href)
        item.setAttribute('media-type', media_type)
        manifest.appendChild(item)

    def _add_spine_item(self, doc, spine, idref):
        item = doc.createElement('itemref')
        item.setAttribute('idref', idref)
        spine.appendChild(item)

    def _create_toc_ncx(self):
        doc = Document()
        ncx = doc.createElement('ncx')
        ncx.setAttribute('xmlns', 'http://www.daisy.org/z3986/2005/ncx/')
        ncx.setAttribute('version', '2005-1')
        doc.appendChild(ncx)

        head = doc.createElement('head')
        ncx.appendChild(head)
        self._add_meta(doc, head, 'dtb:uid', str(uuid.uuid4()))
        self._add_meta(doc, head, 'dtb:depth', '1')

        doc_title = doc.createElement('docTitle')
        title_text = doc.createElement('text')
        title_text.appendChild(doc.createTextNode(self.novel_title))
        doc_title.appendChild(title_text)
        ncx.appendChild(doc_title)
        
        nav_map = doc.createElement('navMap')
        ncx.appendChild(nav_map)
        
        for i, chapter_info in enumerate(self.toc):
            nav_point = doc.createElement('navPoint')
            nav_point.setAttribute('id', f"nav_{i+1}")
            nav_point.setAttribute('playOrder', str(i+1))
            
            nav_label = doc.createElement('navLabel')
            text_node = doc.createElement('text')
            text_node.appendChild(doc.createTextNode(chapter_info['title']))
            nav_label.appendChild(text_node)
            nav_point.appendChild(nav_label)
            
            content = doc.createElement('content')
            content.setAttribute('src', f"Text/{chapter_info['filename']}")
            nav_point.appendChild(content)
            
            nav_map.appendChild(nav_point)

        with open(os.path.join(self.oebps_dir, 'toc.ncx'), 'w', encoding='utf-8') as f:
            f.write(doc.toprettyxml(indent='  '))

    def _add_meta(self, doc, head, name, content):
        meta = doc.createElement('meta')
        meta.setAttribute('name', name)
        meta.setAttribute('content', content)
        head.appendChild(meta)

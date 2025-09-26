import os
import importlib
from urllib.parse import urlparse

# This will hold all the discovered parser classes
# e.g., {'fannovels.com': FanNovelsParser, 'royalroad.com': RoyalRoadParser}
_PARSERS = {}

def load_sources():
    """
    Finds and loads all parser files from the 'sources' directory.
    This should only be run once when the application starts.
    """
    if _PARSERS:
        return # Already loaded

    sources_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sources')
    
    for root, dirs, files in os.walk(sources_dir):
        for file in files:
            if file.endswith('_parser.py'):
                # Construct the module path (e.g., sources.en.f.fannovels_parser)
                relative_path = os.path.relpath(root, sources_dir)
                module_path = 'sources.' + os.path.join(relative_path, file[:-3]).replace(os.sep, '.')
                
                try:
                    module = importlib.import_module(module_path)
                    for attr_name in dir(module):
                        # Find the class that inherits from WebToEpubParser
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and hasattr(attr, 'base_url'):
                            for url in attr.base_url:
                                domain = urlparse(url).netloc.replace('www.', '')
                                _PARSERS[domain] = attr
                                print(f"-> Loaded parser for: {domain}")
                except Exception as e:
                    print(f"Failed to load parser from {module_path}: {e}")

def get_parser_for_url(url):
    """
    Finds the correct parser class for a given URL.
    """
    domain = urlparse(url).netloc.replace('www.', '')
    return _PARSERS.get(domain)

# Automatically load all parsers when this module is imported
load_sources()

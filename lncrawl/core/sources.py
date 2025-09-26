import importlib
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SourceManager:
    """
    Loads and manages all available parser classes from the 'sources' directory.
    """
    def __init__(self):
        self.parsers = {}
        self.load_parsers()

    def load_parsers(self):
        """
        Dynamically imports all parser modules from the `sources` directory.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sources_dir = os.path.join(project_root, 'sources')

        if not os.path.isdir(sources_dir):
            logger.warning(f"Sources directory not found at: {sources_dir}")
            return

        for root, _, files in os.walk(sources_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    module_path = os.path.join(root, file)
                    relative_path = os.path.relpath(module_path, project_root)
                    module_name = relative_path.replace(os.sep, '.')[:-3]
                    
                    try:
                        module = importlib.import_module(module_name)
                        for attr_name in dir(module):
                            if attr_name.endswith('Parser') and attr_name != 'WebToEpubParser':
                                ParserClass = getattr(module, attr_name)
                                if hasattr(ParserClass, 'base_url') and isinstance(ParserClass.base_url, list):
                                    for url in ParserClass.base_url:
                                        hostname = urlparse(url).netloc
                                        self.parsers[hostname] = ParserClass
                                        logger.info(f"-> Loaded parser for: {hostname}")
                    except Exception as e:
                        logger.error(f"Failed to load parser from {module_name}: {e}")

    def get_parser(self, url):
        """
        Returns an instance of the appropriate parser class for a given URL.
        """
        hostname = urlparse(url).netloc
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        elif hostname.startswith('m.'):
            hostname = hostname[2:]

        ParserClass = self.parsers.get(hostname)
        if ParserClass:
            return ParserClass(url)
        return None

_source_manager_instance = None

def get_source_manager():
    """Gets the single instance of the SourceManager."""
    global _source_manager_instance
    if _source_manager_instance is None:
        _source_manager_instance = SourceManager()
    return _source_manager_instance

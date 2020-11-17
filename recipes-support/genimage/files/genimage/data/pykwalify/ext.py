import os.path
import logging
logger = logging.getLogger('appsdk')

def ext_file_exists(value, rule_obj, path):
    if value.startswith("http:") or value.startswith("https:") or value.startswith("ftp:"):
        return True

    if "sub_deploy/deploy" in value:
        return True

    if not os.path.exists(value):
        logger.error("'%s' does not exist", value)
        if "exampleyamls/" in value:
            logger.error("Please run `appsdk exampleyamls' first!!!")
        logger.error("path: %s", path)
        return False

    return True

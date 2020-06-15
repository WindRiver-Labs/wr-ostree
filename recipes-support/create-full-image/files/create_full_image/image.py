
class CreateWicImage(object):
    def __init__(self,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        self.logger = logger
        pass

    def create(self):
        self.logger.info("Create Wic Image")
        pass

class CreateOstreeRepo(object):
    def __init__(self,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        self.logger = logger
        pass

    def create(self):
        self.logger.info("Create Ostree Repo")
        pass

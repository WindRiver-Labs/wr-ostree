

class CreateContainer(object):
    def __init__(self,
                 workdir,
                 machine,
                 target_rootfs,
                 deploydir,
                 logger):

        self.logger = logger
        pass

    def create(self):
        self.logger.info("Create Docker Container")
        pass

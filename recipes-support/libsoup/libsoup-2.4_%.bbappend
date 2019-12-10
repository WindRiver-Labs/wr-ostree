require ${@bb.utils.contains('DISTRO_FEATURES', 'ostree', '${BPN}_ostree.inc', '', d) if bb.utils.contains('WRTEMPLATE', 'feature/ostree', 'true', 'false', d) == 'true' else ''}

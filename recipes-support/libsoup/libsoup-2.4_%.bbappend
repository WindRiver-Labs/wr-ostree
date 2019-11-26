require ${@bb.utils.contains('DISTRO_FEATURES', 'ostree', '${BPN}_ostree.inc', '', d) if bb.utils.contains('BBFILE_COLLECTIONS', 'wrlinux-overc', 'true', 'false', d) == 'false' else ''}

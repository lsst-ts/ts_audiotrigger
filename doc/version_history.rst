v0.3.0 (2025-04-14)
===================

New Features
------------

- Created log config that prints log information. (`DM-49800 <https://rubinobs.atlassian.net//browse/DM-49800>`_)


v0.2.0 (2024-12-17)
===================

New Features
------------

- Split FanControl to provide data to ESS's DataClient and turn fan on/off based on ambient temperature sensor. (`DM-48035 <https://rubinobs.atlassian.net//browse/DM-48035>`_)


Bug Fixes
---------

- Removed dash from noarch argument. (`DM-47355 <https://rubinobs.atlassian.net//browse/DM-47355>`_)
- Changed servers to use 0.0.0.0 instead of localhost. (`DM-48035 <https://rubinobs.atlassian.net//browse/DM-48035>`_)
- Changed USB port to /dev/ttyUSB_lower_right. (`DM-48035 <https://rubinobs.atlassian.net//browse/DM-48035>`_)


v0.1.1 (2024-11-07)
===================

Bug Fixes
---------

- Fixed Jenkinsfile.conda by adding noarch parameter. (`DM-47355 <https://rubinobs.atlassian.net//browse/DM-47355>`_)


Documentation
-------------

- Added towncrier support. (`DM-47355 <https://rubinobs.atlassian.net//browse/DM-47355>`_)
